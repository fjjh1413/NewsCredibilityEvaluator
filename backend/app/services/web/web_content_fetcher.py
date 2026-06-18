import ipaddress
import json
import logging
import re
import socket
import urllib.error
import urllib.request
from html import unescape as html_unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from app.core.config import get_settings
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


class WebContentFetchError(Exception):
    """Raised when page content cannot be fetched safely."""


class SSRFBlockedError(WebContentFetchError):
    """Raised when the target IP is blocked by SSRF guard."""


def _is_private_host(host: str) -> bool:
    """Check whether a hostname resolves to a reserved/private IP address."""
    try:
        ip_addr = ipaddress.ip_address(host)
    except ValueError:
        try:
            ip_addr = ipaddress.ip_address(socket.gethostbyname(host))
        except (OSError, socket.gaierror) as exc:
            raise WebContentFetchError(f"DNS 解析失败：{host}") from exc

    for network in RESERVED_NETWORKS:
        if ip_addr in network:
            return True
    return False


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

    def fetch_article(self, url: str) -> dict[str, str | None]:
        """Fetch *url* and return structured article fields.

        Returns ``{"title", "content", "source_name", "source_url", "publish_time"}``. Unlike
        :meth:`fetch`, this RAISES ``WebContentFetchError`` / ``SSRFBlockedError``
        on failure — the caller asked for this specific URL (e.g. the
        detect-by-link preview endpoint) and must surface the error instead of
        silently degrading to an empty result.
        """
        safe_url = _normalise_url(url)
        hostname = urlparse(safe_url).hostname or ""
        if not self._allow_private and _is_private_host(hostname):
            raise SSRFBlockedError(f"SSRF 阻止：目标地址为私有/保留 IP，URL={safe_url}")

        html_content, final_url = self._http_fetch_with_redirects(safe_url)
        if not html_content:
            raise WebContentFetchError(f"页面内容为空：{safe_url}")

        title, body = self._extract_article_parts(html_content)
        publish_time = self._extract_publish_time(html_content)
        source_host = urlparse(final_url).hostname or hostname
        return {
            "title": title,
            "content": clean_text(body, max_length=8000),
            "source_name": source_host,
            "source_url": final_url,
            "publish_time": publish_time,
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
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
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
                raise WebContentFetchError(f"HTTP {exc.code} fetching {current_url}") from exc
            except urllib.error.URLError as exc:
                raise WebContentFetchError(f"网络错误 fetching {current_url}: {exc.reason}") from exc
            except (TimeoutError, socket.timeout) as exc:
                raise WebContentFetchError(f"超时 fetching {current_url}") from exc

        raise WebContentFetchError(f"超过最大重定向次数 ({MAX_REDIRECTS})")

    def _extract_article_parts(self, html: str) -> tuple[str, str]:
        """Extract ``(title, body_text)`` from HTML.

        ``body_text`` is the raw paragraph text joined by blank lines (not yet
        passed through :func:`clean_text`); callers decide whether to clean it.
        Falls back to a regex-based stripper when BeautifulSoup is unavailable.
        """
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            return self._extract_article_parts_regex(html)

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            return self._extract_article_parts_regex(html)

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

        # body
        body_parts: list[str] = []
        article = soup.find("article")
        main = soup.find("main")
        root = article or main or soup.body or soup

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

        if not body_parts:
            body = root.get_text(separator="\n", strip=True) if root else ""
            body_parts = [body] if body else []

        return title.strip(), "\n\n".join(body_parts)

    def _extract_publish_time(self, html: str) -> str | None:
        """Extract the article publication time from common metadata."""
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            return self._extract_publish_time_regex(html)

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            return self._extract_publish_time_regex(html)

        selectors = (
            ("meta[property='article:published_time']", "content"),
            ("meta[property='og:published_time']", "content"),
            ("meta[name='pubdate']", "content"),
            ("meta[name='publishdate']", "content"),
            ("meta[name='date']", "content"),
            ("meta[itemprop='datePublished']", "content"),
            ("time[datetime]", "datetime"),
        )
        for selector, attribute in selectors:
            node = soup.select_one(selector)
            if node:
                value = clean_text(node.get(attribute, ""), max_length=100)
                if value:
                    return value

        for node in soup.select("script[type='application/ld+json']"):
            raw = node.string or node.get_text(strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, RecursionError, TypeError):
                continue
            value = self._find_json_ld_publish_time(payload)
            if value:
                return value

        return None

    @staticmethod
    def _find_json_ld_publish_time(value: Any) -> str | None:
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
                        return published
                if depth < 12:
                    stack.extend((child, depth + 1) for child in current.values())
            elif isinstance(current, list) and depth < 12:
                stack.extend((child, depth + 1) for child in current)
        return None

    @staticmethod
    def _extract_publish_time_regex(html: str) -> str | None:
        patterns = (
            r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|og:published_time|pubdate|publishdate|date|datePublished)["\'][^>]+content=["\']([^"\']+)',
            r'<time[^>]+datetime=["\']([^"\']+)',
            r'["\']datePublished["\']\s*:\s*["\']([^"\']+)',
        )
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                value = clean_text(html_unescape(match.group(1)), max_length=100)
                if value:
                    return value
        return None

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
