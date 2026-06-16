import json
import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings
from app.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)

BOCHA_WEB_SEARCH_URL = "https://api.bochaai.com/v1/web-search"
BOCHA_TIMEOUT_SECONDS = 10.0
BOCHA_MAX_RETRIES = 2
BOCHA_RETRY_BASE_DELAY = 1.0


class BochaServiceError(Exception):
    """Raised when Bocha API operations fail."""


class BochaAuthError(BochaServiceError):
    """HTTP 401/403 — API Key 无效或无权限."""


class BochaRateLimitError(BochaServiceError):
    """HTTP 429 — 超出配额."""


class BochaServerError(BochaServiceError):
    """HTTP 5xx — 服务端故障."""


class BochaTimeoutError(BochaServiceError):
    """请求超时."""


class BochaResponseError(BochaServiceError):
    """响应格式异常."""


def _classify_http_error(status_code: int, message: str) -> BochaServiceError:
    if status_code in (401, 403):
        return BochaAuthError(f"Bocha API Key 无效或无权限 (HTTP {status_code}): {message}")
    if status_code == 429:
        return BochaRateLimitError(f"Bocha API 配额不足 (HTTP 429): {message}")
    if status_code >= 500:
        return BochaServerError(f"Bocha 服务端故障 (HTTP {status_code}): {message}")
    return BochaServiceError(f"Bocha API 请求失败 (HTTP {status_code}): {message}")


def _build_web_search_request(api_key: str, payload: dict[str, Any]) -> urllib.request.Request:
    return urllib.request.Request(
        url=BOCHA_WEB_SEARCH_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )


class BochaClient:
    """Bocha Web Search API HTTP client.

    Encapsulates authentication, retry with exponential backoff, error
    classification, and response parsing so callers only deal with
    ``BochaSearchResponse`` or a ``BochaServiceError``.
    """

    def __init__(self, api_key: str, timeout: float | None = None) -> None:
        if not api_key or not api_key.strip():
            raise BochaAuthError("Bocha API Key 未配置，请设置 BOCHA_API_KEY")
        self._api_key = api_key.strip()
        self._timeout = timeout or BOCHA_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        freshness: str = "noLimit",
        count: int = 10,
        summary: bool = True,
    ) -> dict[str, Any]:
        """Execute a web search against the Bocha API.

        Returns a dict with keys ``webpages`` (list) and ``total_count`` (int).
        """
        cleaned_query = clean_text(query, max_length=500)
        if not cleaned_query:
            raise BochaServiceError("搜索 query 不能为空")

        safe_count = max(1, min(count, 50))
        payload: dict[str, Any] = {
            "query": cleaned_query,
            "freshness": freshness,
            "count": safe_count,
            "summary": summary,
        }

        last_exc: Exception | None = None
        for attempt in range(BOCHA_MAX_RETRIES + 1):
            try:
                return self._execute(payload)
            except BochaAuthError:
                raise  # 认证错误不重试
            except BochaRateLimitError:
                raise  # 配额错误不重试
            except BochaServerError as exc:
                last_exc = exc
                if attempt < BOCHA_MAX_RETRIES:
                    delay = BOCHA_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Bocha server error, retrying in %.1fs (attempt %d/%d)",
                        delay,
                        attempt + 1,
                        BOCHA_MAX_RETRIES,
                    )
                    time.sleep(delay)
            except (BochaTimeoutError, BochaResponseError) as exc:
                last_exc = exc
                if attempt < BOCHA_MAX_RETRIES:
                    delay = BOCHA_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Bocha request failed, retrying in %.1fs (attempt %d/%d)",
                        delay,
                        attempt + 1,
                        BOCHA_MAX_RETRIES,
                    )
                    time.sleep(delay)

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = _build_web_search_request(self._api_key, payload)

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = _read_error_body(exc)
            message = _extract_bocha_error_message(error_body) or clean_text(
                exc.reason, max_length=200
            )
            raise _classify_http_error(exc.code, message) from exc
        except urllib.error.URLError as exc:
            raise BochaServiceError(f"Bocha API 网络连接异常：{exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise BochaTimeoutError("Bocha API 请求超时") from exc
        except Exception as exc:
            raise BochaServiceError(f"Bocha API 调用失败：{type(exc).__name__}: {exc}") from exc

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise BochaResponseError("Bocha API 返回不是有效 JSON") from exc

        return _parse_web_search_response(parsed)


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_bocha_error_message(response_body: str) -> str:
    """Extract a human-readable error message from Bocha error responses."""
    if not response_body:
        return ""
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return clean_text(response_body, max_length=500)

    if isinstance(parsed, dict):
        return clean_text(
            parsed.get("message") or parsed.get("error") or parsed.get("detail") or "",
            max_length=500,
        )
    return clean_text(str(parsed), max_length=500)


def _parse_web_search_response(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize Bocha Web Search response into a stable dict shape.

    The actual Bocha API wraps results in ``data.webPages.value``::

        {
          "code": 200,
          "data": {
            "webPages": {
              "totalEstimatedMatches": 123,
              "value": [{"name": ..., "url": ..., "snippet": ..., "summary": ...}]
            }
          }
        }
    """
    webpages: list[dict[str, Any]] = []
    total_count = 0

    # Bocha wraps results inside data.webPages
    data = parsed.get("data") or parsed
    if isinstance(data, dict):
        web_pages = data.get("webPages") or data
        if isinstance(web_pages, dict):
            raw_webpages = web_pages.get("value") or []
            total_count = web_pages.get("totalEstimatedMatches") or 0
        elif isinstance(web_pages, list):
            raw_webpages = web_pages
            total_count = len(raw_webpages)
        else:
            raw_webpages = []
            total_count = 0
    elif isinstance(data, list):
        raw_webpages = data
        total_count = len(raw_webpages)
    else:
        raw_webpages = []
        total_count = 0

    if isinstance(raw_webpages, list):
        for item in raw_webpages:
            if not isinstance(item, dict):
                continue
            webpages.append(
                {
                    "name": clean_text(item.get("name") or item.get("title"), max_length=255),
                    "url": clean_text(
                        item.get("url") or item.get("displayUrl") or item.get("link"),
                        max_length=500,
                    ),
                    "snippet": clean_text(
                        item.get("snippet") or item.get("description"), max_length=2000
                    ),
                    "summary": clean_text(
                        item.get("summary") or item.get("snippet"), max_length=2000
                    ),
                    "site_name": clean_text(
                        item.get("siteName") or item.get("site_name"), max_length=100
                    ),
                    "site_icon": clean_text(
                        item.get("siteIcon") or item.get("site_icon") or item.get("favicon"),
                        max_length=500,
                    ),
                    "date_published": clean_text(
                        item.get("datePublished")
                        or item.get("date_published")
                        or item.get("date"),
                        max_length=30,
                    ),
                }
            )

    if isinstance(total_count, str):
        try:
            total_count = int(total_count)
        except (ValueError, TypeError):
            total_count = len(webpages)

    return {
        "webpages": webpages,
        "total_count": int(total_count) if isinstance(total_count, (int, float)) else 0,
    }
