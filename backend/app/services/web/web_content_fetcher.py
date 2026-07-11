import ipaddress
import json
import logging
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape as html_unescape
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

from app.core.config import get_settings
from app.services.web.page_recognizer import PageRecognition, PageRecognizer
from app.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)

MAX_FETCH_BYTES = 2 * 1024 * 1024  # 2 MB
FETCH_TIMEOUT = 10.0
MAX_REDIRECTS = 3
ALLOWED_SCHEMES = {"http", "https"}
RESERVED_NETWORKS = (
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("224.0.0.0/4"),
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fe80::/10"),
    ipaddress.IPv6Network("fc00::/7"),
)
NOISE_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "noscript", "iframe", "form", "button", "select",
    "input", "textarea", "svg", "img", "video", "audio",
    "canvas", "link", "meta",
}
CONTENT_TAGS = {"article", "main", "section", "div", "p", "pre", "blockquote", "li", "td", "th"}
TITLE_TAGS = {
    "meta[property='og:title']": "content",
    "meta[name='twitter:title']": "content",
    "title": "text",
    "h1": "text",
}
STRUCTURED_TITLE_KEYS = {"headline", "title", "name"}
STRUCTURED_BODY_KEYS = {
    "articlebody",
    "articlecontent",
    "body",
    "content",
    "contentbody",
    "fullcontent",
    "fulltext",
    "text",
}
PUBLISH_META_SOURCE_RANKS = {
    "article:published_time": 550,
    "og:published_time": 540,
    "datepublished": 500,
    "date_published": 490,
    "pubdate": 350,
    "publishdate": 340,
    "publish_date": 330,
    "date": 100,
}
PUBLISH_DATETIME_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?P<year>\d{4})(?:\s*-\s*|\s+)(?P<month>\d{1,2})"
    r"(?:\s*-\s*|\s+)(?P<day>\d{1,2})"
    r"[T\s]+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
    r"(?::(?P<second>\d{1,2}))?"
    r"\s*(?P<timezone>Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)?"
    r"(?!\d)",
    re.IGNORECASE,
)
PUBLISH_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<year>\d{4})(?:\s*-\s*|\s+)(?P<month>\d{1,2})"
    r"(?:\s*-\s*|\s+)(?P<day>\d{1,2})(?!\d)"
)
HTML_ATTRIBUTE_PATTERN = re.compile(
    r"([:\w-]+)\s*=\s*(?:([\"'])(.*?)\2|([^\s>]+))",
    re.DOTALL,
)


@dataclass(frozen=True)
class PublishTimeCandidate:
    value: str
    precision: Literal["date", "datetime"]
    detail_rank: int
    source_rank: int
    document_order: int


@dataclass(frozen=True)
class ExtractedPublishTime:
    value: str
    precision: Literal["date", "datetime"]


class WebContentFetchError(Exception):
    """Raised when page content cannot be fetched safely."""


class SSRFBlockedError(WebContentFetchError):
    """Raised when the target IP is blocked by SSRF guard."""


class RecoverableExtractionError(WebContentFetchError):
    """Raised when extraction failed with a user-actionable recovery path."""

    def __init__(
        self,
        message: str,
        *,
        status: str,
        recovery_action: str,
        login_url: str | None = None,
        page_type: str | None = None,
        confidence: float | None = None,
        signals: list[str] | tuple[str, ...] | None = None,
        recommended_method: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.recovery_action = recovery_action
        self.login_url = login_url
        self.page_type = page_type
        self.confidence = confidence
        self.signals = list(signals or [])
        self.recommended_method = recommended_method


class LoginRequiredError(RecoverableExtractionError):
    """Raised when a page is reachable but hides article content behind login."""

    def __init__(
        self,
        message: str,
        login_url: str | None = None,
        *,
        page_type: str | None = None,
        confidence: float | None = None,
        signals: list[str] | tuple[str, ...] | None = None,
        recommended_method: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status="login_required",
            recovery_action="open_login_then_retry",
            login_url=login_url,
            page_type=page_type,
            confidence=confidence,
            signals=signals,
            recommended_method=recommended_method,
        )


class AntiBotBlockedError(RecoverableExtractionError):
    """Raised when the target page is an anti-bot or access challenge."""

    def __init__(
        self,
        message: str,
        *,
        page_type: str | None = None,
        confidence: float | None = None,
        signals: list[str] | tuple[str, ...] | None = None,
        recommended_method: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status="blocked_by_anti_bot",
            recovery_action="manual_input",
            page_type=page_type,
            confidence=confidence,
            signals=signals,
            recommended_method=recommended_method,
        )


class DynamicRenderRequiredError(RecoverableExtractionError):
    """Raised when article text is only available after browser-side rendering."""

    def __init__(
        self,
        message: str,
        *,
        page_type: str | None = None,
        confidence: float | None = None,
        signals: list[str] | tuple[str, ...] | None = None,
        recommended_method: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status="dynamic_render_required",
            recovery_action="manual_input",
            page_type=page_type,
            confidence=confidence,
            signals=signals,
            recommended_method=recommended_method,
        )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Turn urllib redirects into HTTPError so every hop is validated first."""

    def http_error_302(self, req, fp, code, msg, headers):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _open_without_redirects(request: urllib.request.Request, timeout: float):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    try:
        address_info = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise WebContentFetchError(f"DNS 解析失败：{host}") from exc

    resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for item in address_info:
        address = item[4][0]
        try:
            ip_addr = ipaddress.ip_address(address)
        except ValueError:
            continue
        ip_key = str(ip_addr)
        if ip_key not in seen:
            resolved_ips.append(ip_addr)
            seen.add(ip_key)

    if not resolved_ips:
        raise WebContentFetchError(f"DNS 解析失败：{host}")
    return resolved_ips


def _is_blocked_ip(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip_addr, ipaddress.IPv6Address) and ip_addr.ipv4_mapped:
        ip_addr = ip_addr.ipv4_mapped

    if (
        ip_addr.is_private
        or ip_addr.is_loopback
        or ip_addr.is_link_local
        or ip_addr.is_multicast
        or ip_addr.is_reserved
        or ip_addr.is_unspecified
    ):
        return True

    for network in RESERVED_NETWORKS:
        if ip_addr in network:
            return True
    return False


def _is_private_host(host: str) -> bool:
    """Check whether any resolved address is private, reserved, or non-routable."""
    return any(_is_blocked_ip(ip_addr) for ip_addr in _resolve_host_ips(host))


def _normalise_url(url: str) -> str:
    """Validate scheme and strip fragments."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise WebContentFetchError(f"不支持的协议：{parsed.scheme or '空'}")
    if not parsed.hostname:
        raise WebContentFetchError("URL 缺少有效主机名")
    return parsed._replace(fragment="").geturl()


class WebContentFetcher:
    """SSRF-safe web page content fetcher with HTML cleaning.

    Uses a strict default-deny host check before connecting and after each
    redirect hop.  Extracts human-readable text from HTML using BeautifulSoup
    when available, or falls back to a lightweight regex-based cleaner.
    """

    def __init__(
        self,
        timeout: float | None = None,
        max_bytes: int | None = None,
        allow_private_hosts: bool = False,
    ) -> None:
        settings = get_settings()
        self._timeout = timeout or FETCH_TIMEOUT
        self._max_bytes = max_bytes or MAX_FETCH_BYTES
        self._allow_private = allow_private_hosts
        self._page_recognizer = PageRecognizer()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> str:
        """Fetch *url* and return cleaned text content.

        Returns an empty string when the page cannot be fetched or parsed.
        Callers should handle empty results gracefully.
        """
        try:
            return self._fetch_impl(url)
        except WebContentFetchError as exc:
            logger.warning("Web content fetch failed for %s: %s", url, exc)
            return ""
        except Exception as exc:
            logger.exception("Unexpected error fetching %s", url)
            return ""

    def fetch_article(self, url: str) -> dict[str, Any]:
        """Fetch *url* and return structured article fields.

        Returns title, content, source metadata, normalized ``publish_time``,
        and ``publish_time_precision``. Unlike :meth:`fetch`, this RAISES
        ``WebContentFetchError`` / ``SSRFBlockedError`` on failure because the
        caller asked for this specific URL and must surface the error instead
        of silently degrading to an empty result.
        """
        safe_url = _normalise_url(url)
        hostname = urlparse(safe_url).hostname or ""
        if not self._allow_private and _is_private_host(hostname):
            raise SSRFBlockedError(f"SSRF 阻止：目标地址为私有/保留 IP，URL={safe_url}")

        html_content, final_url = self._http_fetch_with_redirects(safe_url)
        if not html_content:
            raise WebContentFetchError(f"页面内容为空：{safe_url}")

        title, body, extraction_method, warnings = self._extract_article_parts_with_metadata(
            html_content
        )
        content = clean_text(body, max_length=8000)
        recognition = self._page_recognizer.recognize(
            html_content,
            final_url=final_url,
            title=title,
            content=content,
            extraction_method=extraction_method,
        )
        self._raise_for_page_recognition(recognition)

        publish_time = self._extract_publish_time(html_content)
        source_host = urlparse(final_url).hostname or hostname
        return {
            "status": "ok",
            "title": title,
            "content": content,
            "source_name": source_host,
            "source_url": final_url,
            "final_url": final_url,
            "publish_time": publish_time.value if publish_time else None,
            "publish_time_precision": publish_time.precision if publish_time else None,
            "extraction_method": extraction_method,
            "confidence": self._score_extraction_confidence(
                title, content, extraction_method, warnings
            ),
            "warnings": warnings,
            **recognition.to_response_fields(),
        }

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _fetch_impl(self, url: str) -> str:
        safe_url = _normalise_url(url)
        hostname = urlparse(safe_url).hostname or ""

        if not self._allow_private and _is_private_host(hostname):
            raise SSRFBlockedError(f"SSRF 阻止：目标地址为私有/保留 IP，URL={safe_url}")

        html_content, _final_url = self._http_fetch_with_redirects(safe_url)
        if not html_content:
            return ""

        return self._extract_text(html_content)

    def _http_fetch_with_redirects(self, url: str) -> tuple[str, str]:
        """HTTP GET with manual redirect following and per-hop SSRF checks.

        Returns ``(html_content, final_url)`` where ``final_url`` is the URL
        actually served after following redirects.
        """
        current_url = url
        for hop in range(MAX_REDIRECTS + 1):
            hostname = urlparse(current_url).hostname or ""
            if not self._allow_private and _is_private_host(hostname):
                raise SSRFBlockedError(
                    f"SSRF 阻止：redirect {hop} 目标为私有/保留 IP，URL={current_url}"
                )

            request = urllib.request.Request(
                url=current_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; ZhiYunBianZhen/1.0; "
                        "+https://github.com/news-credibility)"
                    ),
                    "Accept": "text/html,application/xhtml+xml,*/*",
                },
                method="GET",
            )

            try:
                with _open_without_redirects(request, timeout=self._timeout) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type and "text/plain" not in content_type:
                        raise WebContentFetchError(
                            f"非文本内容类型：{content_type}"
                        )
                    content = response.read(self._max_bytes)
                    return content.decode("utf-8", errors="replace"), current_url
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    new_url = exc.headers.get("Location") or exc.headers.get("location")
                    if new_url:
                        current_url = urljoin(current_url, new_url)
                        continue
                if exc.code == 401:
                    recognition = self._page_recognizer.recognize_http_error(
                        "",
                        final_url=current_url,
                        status_code=exc.code,
                    )
                    try:
                        self._raise_for_page_recognition(recognition)
                    except RecoverableExtractionError as recoverable:
                        raise recoverable from exc
                if exc.code in (403, 429, 503):
                    challenge_html = self._read_http_error_body(exc)
                    recognition = self._page_recognizer.recognize_http_error(
                        challenge_html,
                        final_url=current_url,
                        status_code=exc.code,
                    )
                    if recognition.status == "blocked_by_anti_bot":
                        try:
                            self._raise_for_page_recognition(recognition)
                        except RecoverableExtractionError as recoverable:
                            raise recoverable from exc
                raise WebContentFetchError(f"HTTP {exc.code} fetching {current_url}") from exc
            except urllib.error.URLError as exc:
                raise WebContentFetchError(f"网络错误 fetching {current_url}: {exc.reason}") from exc
            except (TimeoutError, socket.timeout) as exc:
                raise WebContentFetchError(f"超时 fetching {current_url}") from exc

        raise WebContentFetchError(f"超过最大重定向次数 ({MAX_REDIRECTS})")

    def _read_http_error_body(self, exc: urllib.error.HTTPError) -> str:
        try:
            content = exc.read(self._max_bytes)
        except Exception:
            return ""
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _raise_for_page_recognition(recognition: PageRecognition) -> None:
        common = {
            "page_type": recognition.page_type,
            "confidence": recognition.confidence,
            "signals": recognition.signals,
            "recommended_method": recognition.recommended_method,
        }
        if recognition.status == "login_required":
            raise LoginRequiredError(
                "该链接需要登录后才能读取正文，请登录后重试或改用手动输入",
                login_url=recognition.login_url,
                **common,
            )
        if recognition.status == "blocked_by_anti_bot":
            raise AntiBotBlockedError(
                "该站点启用了访问校验或反爬限制，当前无法自动读取正文，请打开原文复制正文或改用手动输入",
                **common,
            )
        if recognition.status == "dynamic_render_required":
            raise DynamicRenderRequiredError(
                "该新闻页正文由客户端动态生成，当前无法直接读取正文，请打开原文复制正文或改用手动输入",
                **common,
            )

    def _extract_article_parts(self, html: str) -> tuple[str, str]:
        """Extract ``(title, body_text)`` from HTML.

        ``body_text`` is the raw paragraph text joined by blank lines (not yet
        passed through :func:`clean_text`); callers decide whether to clean it.
        Falls back to a regex-based stripper when BeautifulSoup is unavailable.
        """
        title, body, _method, _warnings = self._extract_article_parts_with_metadata(html)
        return title, body

    def _extract_article_parts_with_metadata(
        self, html: str
    ) -> tuple[str, str, str, list[str]]:
        """Extract article fields and explain which extraction path succeeded."""
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            title, body = self._extract_article_parts_regex(html)
            return title, body, "regex", ["beautifulsoup_unavailable"]

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            title, body = self._extract_article_parts_regex(html)
            return title, body, "regex", ["beautifulsoup_parse_failed"]

        # title
        title = ""
        for selector, attr in TITLE_TAGS.items():
            tag = soup.select_one(selector) if "[" in selector else soup.find(selector.split("[", 1)[0])
            if tag:
                if attr == "text":
                    title = tag.get_text(strip=True) if hasattr(tag, "get_text") else ""
                elif attr == "content":
                    title = tag.get("content", "").strip()
                if title:
                    break

        structured_title, structured_body = self._extract_structured_article_fields_from_soup(soup)

        # body
        body_parts: list[str] = []
        article = soup.find("article")
        main = soup.find("main")
        root = article or main or soup.body or soup
        extraction_method = "html"
        warnings: list[str] = []

        if root:
            for tag_name in NOISE_TAGS:
                for node in root.find_all(tag_name):
                    node.decompose()

            paragraphs: list[str] = []
            for p in root.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if text and len(text) > 20:
                    paragraphs.append(text)
            body_parts = paragraphs

        if not title and structured_title:
            title = structured_title

        if not body_parts and structured_body:
            body_parts = [structured_body]
            if structured_title:
                title = structured_title
            extraction_method = "structured_data"
            warnings.append("dom_content_empty")

        if not body_parts:
            body = root.get_text(separator="\n", strip=True) if root else ""
            body_parts = [body] if body else []

        return title.strip(), "\n\n".join(body_parts), extraction_method, warnings

    def _extract_structured_article_fields_from_soup(self, soup: Any) -> tuple[str, str]:
        best_title = ""
        best_body = ""

        for node in soup.find_all("script"):
            raw = node.string or node.get_text(strip=True)
            if not raw:
                continue
            script_type = clean_text(node.get("type", ""), max_length=100).lower()
            node_id = clean_text(node.get("id", ""), max_length=100).lower()
            looks_like_json = raw.lstrip().startswith(("{", "["))
            if (
                script_type not in {"application/ld+json", "application/json"}
                and node_id != "__next_data__"
                and not looks_like_json
            ):
                continue
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, RecursionError, TypeError, ValueError):
                continue
            title, body = self._extract_structured_article_fields(payload)
            if len(body) > len(best_body):
                best_title = title or best_title
                best_body = body

        return best_title, best_body

    def _extract_structured_article_fields(self, value: Any) -> tuple[str, str]:
        best_title = ""
        best_body = ""
        stack: list[tuple[Any, int]] = [(value, 0)]
        visited = 0

        while stack and visited < 512:
            current, depth = stack.pop()
            visited += 1
            if isinstance(current, dict):
                local_title = ""
                local_body = ""
                for raw_key, raw_value in current.items():
                    key = self._normalise_structured_key(raw_key)
                    if isinstance(raw_value, str):
                        text = self._normalise_structured_text(raw_value)
                        if key in STRUCTURED_TITLE_KEYS and 4 <= len(text) <= 255:
                            local_title = local_title or text
                            if not best_title:
                                best_title = text
                        elif key in STRUCTURED_BODY_KEYS and len(text) >= 60:
                            if len(text) > len(local_body):
                                local_body = text
                    if depth < 12 and isinstance(raw_value, (dict, list)):
                        stack.append((raw_value, depth + 1))

                if len(local_body) > len(best_body):
                    best_title = local_title or best_title
                    best_body = local_body

            elif isinstance(current, list) and depth < 12:
                stack.extend((item, depth + 1) for item in current)

        return best_title, best_body

    @staticmethod
    def _normalise_structured_key(value: object) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    @staticmethod
    def _normalise_structured_text(value: str) -> str:
        text = html_unescape(value)
        if "<" in text and ">" in text:
            text = re.sub(
                r"<(?:script|style)[^>]*>.*?</(?:script|style)>",
                " ",
                text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(r"<[^>]+>", " ", text)
        return clean_text(text, max_length=8000)

    @staticmethod
    def _score_extraction_confidence(
        title: str,
        content: str,
        extraction_method: str,
        warnings: list[str],
    ) -> float:
        score = 0.95
        if not title:
            score -= 0.2
        if len(content) < 200:
            score -= 0.35
        elif len(content) < 800:
            score -= 0.1
        if extraction_method == "structured_data":
            score -= 0.08
        if extraction_method == "regex":
            score -= 0.2
        score -= min(len(warnings) * 0.04, 0.2)
        return round(max(0.0, min(1.0, score)), 2)

    def _extract_publish_time(self, html: str) -> ExtractedPublishTime | None:
        """Extract and normalize the most precise credible publication time."""
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            return self._extract_publish_time_regex(html)

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            return self._extract_publish_time_regex(html)

        return self._select_publish_time_candidate(
            self._collect_publish_time_candidates(soup)
        )

    def _collect_publish_time_candidates(self, soup: Any) -> list[PublishTimeCandidate]:
        candidates: list[PublishTimeCandidate] = []
        nodes = list(soup.find_all(True))
        document_order = {id(node): index for index, node in enumerate(nodes)}

        def append_candidate(raw_value: object, source_rank: int, node: Any) -> None:
            normalized = self._normalize_publish_time_candidate(raw_value)
            if normalized is None:
                return
            value, precision, detail_rank = normalized
            candidates.append(
                PublishTimeCandidate(
                    value=value,
                    precision=precision,
                    detail_rank=detail_rank,
                    source_rank=source_rank,
                    document_order=document_order.get(id(node), len(nodes)),
                )
            )

        for node in soup.find_all("meta"):
            keys = {
                clean_text(node.get(attribute, ""), max_length=100).lower()
                for attribute in ("property", "name", "itemprop")
                if node.get(attribute)
            }
            ranks = [
                PUBLISH_META_SOURCE_RANKS[key]
                for key in keys
                if key in PUBLISH_META_SOURCE_RANKS
            ]
            if ranks:
                append_candidate(node.get("content", ""), max(ranks), node)

        for node in soup.find_all("script"):
            script_type = clean_text(node.get("type", ""), max_length=100).lower()
            if script_type != "application/ld+json":
                continue
            raw = node.string or node.get_text(strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, RecursionError, TypeError):
                continue
            for raw_value in self._find_json_ld_publish_times(payload):
                append_candidate(raw_value, 600, node)

        headline_scopes: list[Any] = []
        headline = soup.find("h1")
        if headline is not None:
            ancestor = headline.parent
            for _ in range(4):
                if ancestor is None or getattr(ancestor, "name", None) in {"body", "html"}:
                    break
                text = ancestor.get_text(separator=" ", strip=True)
                headline_text = headline.get_text(separator=" ", strip=True)
                context_text = text.replace(headline_text, "", 1).strip()
                contains_article_body = (
                    getattr(ancestor, "name", None) in {"article", "main"}
                    or ancestor.find(["p", "article", "main"]) is not None
                )
                is_headline_context = not contains_article_body and len(context_text) <= 500
                if is_headline_context:
                    headline_scopes.append(ancestor)
                if context_text and is_headline_context:
                    append_candidate(context_text, 400, ancestor)
                ancestor = ancestor.parent

        for node in soup.find_all("time"):
            itemprop = clean_text(node.get("itemprop", ""), max_length=100).lower()
            if itemprop == "datepublished":
                append_candidate(node.get("datetime", ""), 480, node)
                continue
            inside_semantic_header = any(
                getattr(parent, "name", None) == "header" for parent in node.parents
            )
            inside_headline_scope = any(
                any(parent is scope for parent in node.parents)
                for scope in headline_scopes
            )
            if inside_semantic_header or inside_headline_scope:
                append_candidate(
                    node.get("datetime", ""),
                    450 if inside_semantic_header else 400,
                    node,
                )

        return candidates

    @staticmethod
    def _normalize_publish_time_candidate(
        raw_value: object,
    ) -> tuple[str, Literal["date", "datetime"], int] | None:
        raw = clean_text(str(raw_value), max_length=500) if raw_value is not None else ""
        if not raw:
            return None

        normalized_raw = (
            html_unescape(raw)
            .replace("年", "-")
            .replace("月", "-")
            .replace("日", " ")
            .replace("时", ":")
            .replace("分", ":")
            .replace("秒", "")
            .replace("/", "-")
            .replace(".", "-")
            .replace("：", ":")
        )

        for match in PUBLISH_DATETIME_PATTERN.finditer(normalized_raw):
            parts = {
                name: match.group(name)
                for name in ("year", "month", "day", "hour", "minute", "second")
            }
            second = int(parts["second"]) if parts["second"] is not None else 0
            try:
                value = datetime(
                    int(parts["year"]),
                    int(parts["month"]),
                    int(parts["day"]),
                    int(parts["hour"]),
                    int(parts["minute"]),
                    second,
                )
            except ValueError:
                continue
            rendered = value.strftime("%Y-%m-%dT%H:%M")
            detail_rank = 1
            if parts["second"] is not None:
                rendered += value.strftime(":%S")
                detail_rank = 2
            timezone = match.group("timezone")
            if timezone:
                timezone = timezone.upper()
                if timezone != "Z" and ":" not in timezone:
                    timezone = f"{timezone[:3]}:{timezone[3:]}"
                rendered += timezone
            return rendered, "datetime", detail_rank

        for match in PUBLISH_DATE_PATTERN.finditer(normalized_raw):
            try:
                value = datetime(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            except ValueError:
                continue
            return value.strftime("%Y-%m-%d"), "date", 0

        return None

    @staticmethod
    def _select_publish_time_candidate(
        candidates: list[PublishTimeCandidate],
    ) -> ExtractedPublishTime | None:
        if not candidates:
            return None
        selected = max(
            candidates,
            key=lambda candidate: (
                1 if candidate.precision == "datetime" else 0,
                candidate.source_rank,
                candidate.detail_rank,
                -candidate.document_order,
            ),
        )
        return ExtractedPublishTime(value=selected.value, precision=selected.precision)

    @staticmethod
    def _find_json_ld_publish_times(value: Any) -> list[str]:
        results: list[str] = []
        stack: list[tuple[Any, int]] = [(value, 0)]
        visited = 0
        while stack and visited < 256:
            current, depth = stack.pop()
            visited += 1
            if isinstance(current, dict):
                raw_published = current.get("datePublished")
                if isinstance(raw_published, (str, int, float)):
                    published = clean_text(str(raw_published), max_length=100)
                    if published:
                        results.append(published)
                if depth < 12:
                    stack.extend((child, depth + 1) for child in current.values())
            elif isinstance(current, list) and depth < 12:
                stack.extend((child, depth + 1) for child in current)
        return results

    def _extract_publish_time_regex(self, html: str) -> ExtractedPublishTime | None:
        return self._select_publish_time_candidate(
            self._collect_regex_publish_time_candidates(html)
        )

    def _collect_regex_publish_time_candidates(
        self, html: str
    ) -> list[PublishTimeCandidate]:
        candidates: list[PublishTimeCandidate] = []

        def attributes(tag: str) -> dict[str, str]:
            return {
                match.group(1).lower(): html_unescape(match.group(3) or match.group(4) or "")
                for match in HTML_ATTRIBUTE_PATTERN.finditer(tag)
            }

        def append_candidate(raw_value: object, source_rank: int, order: int) -> None:
            normalized = self._normalize_publish_time_candidate(raw_value)
            if normalized is None:
                return
            value, precision, detail_rank = normalized
            candidates.append(
                PublishTimeCandidate(value, precision, detail_rank, source_rank, order)
            )

        for match in re.finditer(r"<meta\b[^>]*>", html, re.IGNORECASE | re.DOTALL):
            attrs = attributes(match.group(0))
            keys = {
                attrs.get(attribute, "").lower()
                for attribute in ("property", "name", "itemprop")
                if attrs.get(attribute)
            }
            ranks = [
                PUBLISH_META_SOURCE_RANKS[key]
                for key in keys
                if key in PUBLISH_META_SOURCE_RANKS
            ]
            if ranks:
                append_candidate(attrs.get("content", ""), max(ranks), match.start())

        script_pattern = re.compile(
            r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in script_pattern.finditer(html):
            attrs = attributes(match.group("attrs"))
            if attrs.get("type", "").lower() != "application/ld+json":
                continue
            try:
                payload = json.loads(match.group("body"))
            except (json.JSONDecodeError, RecursionError, TypeError):
                continue
            for raw_value in self._find_json_ld_publish_times(payload):
                append_candidate(raw_value, 600, match.start())

        for match in re.finditer(r"<time\b[^>]*>", html, re.IGNORECASE | re.DOTALL):
            attrs = attributes(match.group(0))
            if attrs.get("itemprop", "").lower() == "datepublished":
                append_candidate(attrs.get("datetime", ""), 480, match.start())

        header_pattern = re.compile(
            r"<header\b[^>]*>(?P<body>.*?)</header>",
            re.IGNORECASE | re.DOTALL,
        )
        for header_match in header_pattern.finditer(html):
            for time_match in re.finditer(
                r"<time\b[^>]*>",
                header_match.group("body"),
                re.IGNORECASE | re.DOTALL,
            ):
                attrs = attributes(time_match.group(0))
                append_candidate(
                    attrs.get("datetime", ""),
                    450,
                    header_match.start() + time_match.start(),
                )

        headline = re.search(r"</h1\s*>", html, re.IGNORECASE)
        if headline:
            end = min(len(html), headline.end() + 2000)
            boundary = re.search(
                r"<(?:article|main|section|p)\b",
                html[headline.end():end],
                re.IGNORECASE,
            )
            if boundary:
                end = headline.end() + boundary.start()
            context_html = html[headline.end():end]
            context_text = re.sub(r"<[^>]+>", " ", context_html)
            context_text = clean_text(html_unescape(context_text), max_length=500)
            if context_text:
                append_candidate(context_text, 400, headline.end())

        return candidates

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML using BeautifulSoup if available."""
        title, body = self._extract_article_parts(html)
        result_parts: list[str] = []
        if title:
            result_parts.append(title)
        if body:
            result_parts.append(body)
        return clean_text("\n\n".join(result_parts), max_length=8000) if result_parts else ""

    def _extract_text_regex(self, html: str) -> str:
        """Simple HTML tag stripper used when BeautifulSoup is unavailable."""
        title, body = self._extract_article_parts_regex(html)
        result_parts: list[str] = []
        if title:
            result_parts.append(title)
        if body:
            result_parts.append(body)
        return clean_text("\n\n".join(result_parts), max_length=8000) if result_parts else ""

    def _extract_article_parts_regex(self, html: str) -> tuple[str, str]:
        """Regex fallback for :meth:`_extract_article_parts`.

        Returns ``("", cleaned_text)`` — title is not separated in this
        fallback mode (BeautifulSoup is the supported path; this only runs if
        the optional ``beautifulsoup4`` dependency is missing).
        """
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return "", clean_text(text, max_length=8000)
