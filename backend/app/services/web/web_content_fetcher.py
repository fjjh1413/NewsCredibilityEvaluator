import ipaddress
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

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _fetch_impl(self, url: str) -> str:
        safe_url = _normalise_url(url)
        hostname = urlparse(safe_url).hostname or ""

        if not self._allow_private and _is_private_host(hostname):
            raise SSRFBlockedError(f"SSRF 阻止：目标地址为私有/保留 IP，URL={safe_url}")

        html_content = self._http_fetch_with_redirects(safe_url)
        if not html_content:
            return ""

        return self._extract_text(html_content)

    def _http_fetch_with_redirects(self, url: str) -> str:
        """HTTP GET with manual redirect following and per-hop SSRF checks."""
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
                    return content.decode("utf-8", errors="replace")
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

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML using BeautifulSoup if available."""
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            return self._extract_text_regex(html)

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            return self._extract_text_regex(html)

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

        result_parts: list[str] = []
        if title:
            result_parts.append(title)
        result_parts.extend(body_parts)

        return clean_text("\n\n".join(result_parts), max_length=8000)

    def _extract_text_regex(self, html: str) -> str:
        """Simple HTML tag stripper used when BeautifulSoup is unavailable."""
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return clean_text(text, max_length=8000)
