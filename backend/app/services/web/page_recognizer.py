import re
from dataclasses import dataclass
from html import unescape as html_unescape
from typing import Literal
from urllib.parse import urljoin, urlparse

from app.utils.text_cleaner import clean_text


PageStatus = Literal[
    "ok",
    "login_required",
    "blocked_by_anti_bot",
    "dynamic_render_required",
]
PageType = Literal[
    "static_article",
    "structured_article",
    "client_rendered_shell",
    "login_wall",
    "anti_bot_wall",
    "unknown",
]
RecoveryAction = Literal["none", "open_login_then_retry", "manual_input"]

ALLOWED_LINK_SCHEMES = {"http", "https"}
LOGIN_TEXT_MARKERS = (
    "login required",
    "log in to continue",
    "please log in",
    "please sign in",
    "sign in to continue",
    "登录后",
    "登陆后",
    "请登录",
    "请先登录",
    "需要登录",
    "登录查看",
    "登录后查看",
    "未登录",
    "会员登录",
)
LOGIN_LINK_MARKERS = ("login", "signin", "sign-in", "auth", "登录", "登陆")
ANTIBOT_TEXT_MARKERS = (
    "access denied",
    "checking your browser",
    "cloudflare",
    "complete the security check",
    "enable cookies",
    "human verification",
    "please verify",
    "robot check",
    "too many requests",
    "unusual traffic",
    "verify you are human",
    "人机验证",
    "安全验证",
    "访问被拒绝",
    "访问过于频繁",
    "验证码",
    "请求过于频繁",
)
CLIENT_RENDER_MARKERS = (
    "__next_data__",
    "__nuxt__",
    "__react",
    "__remix",
    "data-reactroot",
    "id=\"app\"",
    "id='app'",
    "id=\"root\"",
    "id='root'",
    "ng-version",
    "enable javascript to run this app",
    "you need to enable javascript",
    "window.__initial_state__",
)


@dataclass(frozen=True)
class PageRecognition:
    status: PageStatus
    page_type: PageType
    recommended_method: str
    confidence: float
    signals: tuple[str, ...]
    recovery_action: RecoveryAction = "none"
    login_url: str | None = None

    def to_response_fields(self) -> dict[str, object]:
        return {
            "page_type": self.page_type,
            "recognition_confidence": self.confidence,
            "recognition_signals": list(self.signals),
            "recommended_extraction_method": self.recommended_method,
        }

    def to_error_data(self) -> dict[str, object]:
        data = {
            "status": self.status,
            "page_type": self.page_type,
            "recovery_action": self.recovery_action,
            "recognition_confidence": self.confidence,
            "recognition_signals": list(self.signals),
            "recommended_extraction_method": self.recommended_method,
        }
        if self.login_url:
            data["login_url"] = self.login_url
        return data


class PageRecognizer:
    """Classify fetched pages before deciding the next extraction strategy."""

    def recognize(
        self,
        html: str,
        *,
        final_url: str,
        title: str,
        content: str,
        extraction_method: str,
    ) -> PageRecognition:
        normalized_title = clean_text(title, max_length=255)
        normalized_content = clean_text(content, max_length=2000)
        visible_text = self._extract_visible_text(html)
        combined_text = clean_text(
            f"{normalized_title}\n{normalized_content}\n{visible_text}",
            max_length=5000,
        ).lower()
        html_lower = html[:200_000].lower()
        signals = self._collect_common_signals(html, html_lower, normalized_content)

        login_signals = self._login_signals(html, combined_text, normalized_title)
        if login_signals and len(normalized_content) < 400:
            return PageRecognition(
                status="login_required",
                page_type="login_wall",
                recommended_method="authenticated_retry",
                confidence=0.92,
                signals=tuple((*signals, *login_signals)),
                recovery_action="open_login_then_retry",
                login_url=self._find_login_url(html, final_url),
            )

        antibot_signals = self._antibot_signals(html, combined_text)
        if antibot_signals and len(clean_text(normalized_content or visible_text, max_length=1200)) < 800:
            return PageRecognition(
                status="blocked_by_anti_bot",
                page_type="anti_bot_wall",
                recommended_method="manual_input",
                confidence=0.9,
                signals=tuple((*signals, *antibot_signals)),
                recovery_action="manual_input",
            )

        if extraction_method == "structured_data" and len(normalized_content) >= 60:
            return PageRecognition(
                status="ok",
                page_type="structured_article",
                recommended_method="structured_data",
                confidence=self._score_article_confidence(
                    normalized_title,
                    normalized_content,
                    base=0.86,
                    signals_count=len(signals),
                ),
                signals=tuple((*signals, "structured_article_data")),
            )

        dynamic_signals = self._client_render_signals(html_lower, normalized_title, normalized_content)
        if dynamic_signals:
            return PageRecognition(
                status="dynamic_render_required",
                page_type="client_rendered_shell",
                recommended_method="browser_render",
                confidence=0.84,
                signals=tuple((*signals, *dynamic_signals)),
                recovery_action="manual_input",
            )

        if len(normalized_content) >= 120:
            article_signals = ["sufficient_readable_text"]
            if "semantic_article_container" in signals or "main_content_container" in signals:
                article_signals.append("reader_like_layout")
            return PageRecognition(
                status="ok",
                page_type="static_article",
                recommended_method=extraction_method or "html",
                confidence=self._score_article_confidence(
                    normalized_title,
                    normalized_content,
                    base=0.88,
                    signals_count=len((*signals, *article_signals)),
                ),
                signals=tuple((*signals, *article_signals)),
            )

        return PageRecognition(
            status="ok",
            page_type="unknown",
            recommended_method=extraction_method or "html",
            confidence=0.35 if not normalized_content else 0.55,
            signals=tuple(signals),
        )

    def recognize_http_error(
        self,
        html: str,
        *,
        final_url: str,
        status_code: int,
    ) -> PageRecognition:
        if status_code == 401:
            return PageRecognition(
                status="login_required",
                page_type="login_wall",
                recommended_method="authenticated_retry",
                confidence=0.88,
                signals=("http_401",),
                recovery_action="open_login_then_retry",
                login_url=final_url,
            )

        if not html and status_code in (403, 429, 503):
            return PageRecognition(
                status="blocked_by_anti_bot",
                page_type="anti_bot_wall",
                recommended_method="manual_input",
                confidence=0.76,
                signals=(f"http_{status_code}",),
                recovery_action="manual_input",
            )

        return self.recognize(
            html,
            final_url=final_url,
            title="",
            content="",
            extraction_method="html",
        )

    def _collect_common_signals(
        self, html: str, html_lower: str, content: str
    ) -> list[str]:
        signals: list[str] = []
        if re.search(r"<article\b", html_lower):
            signals.append("semantic_article_container")
        if re.search(r"<main\b", html_lower):
            signals.append("main_content_container")
        if len(re.findall(r"<p\b", html_lower)) >= 2:
            signals.append("multiple_paragraphs")
        if len(content) >= 120:
            signals.append("readable_text_length")
        if re.search(r"application/ld\+json", html_lower):
            signals.append("json_ld_present")
        if re.search(r"schema\.org/(?:article|newsarticle|blogposting)", html_lower):
            signals.append("schema_article_type")
        return signals

    def _login_signals(
        self, html: str, combined_text: str, title: str
    ) -> tuple[str, ...]:
        signals: list[str] = []
        title_text = clean_text(title, max_length=200).lower()
        if any(marker in combined_text for marker in LOGIN_TEXT_MARKERS):
            signals.append("login_text_marker")
        if any(marker in title_text for marker in LOGIN_TEXT_MARKERS):
            signals.append("login_title_marker")
        if re.search(
            r"<input\b[^>]*type\s*=\s*['\"]?password",
            html,
            re.IGNORECASE,
        ):
            signals.append("password_form")
        return tuple(signals)

    def _antibot_signals(self, html: str, combined_text: str) -> tuple[str, ...]:
        signals: list[str] = []
        if any(marker in combined_text for marker in ANTIBOT_TEXT_MARKERS):
            signals.append("anti_bot_marker")
        if re.search(
            r"<(?:input|div)\b[^>]*(?:captcha|turnstile|hcaptcha|recaptcha)",
            html,
            re.IGNORECASE,
        ):
            signals.append("captcha_widget")
        return tuple(signals)

    @staticmethod
    def _client_render_signals(
        html_lower: str, title: str, content: str
    ) -> tuple[str, ...]:
        if len(clean_text(content, max_length=1200)) >= 120:
            return ()

        signals: list[str] = []
        script_count = len(re.findall(r"<script\b", html_lower))
        has_marker = any(marker in html_lower for marker in CLIENT_RENDER_MARKERS)
        has_app_root = re.search(
            r"<div\b[^>]*id\s*=\s*['\"](?:__next|__nuxt|app|root)['\"]",
            html_lower,
        ) is not None
        has_human_title = len(clean_text(title, max_length=255)) >= 4
        if has_marker and script_count >= 1:
            signals.append("client_render_marker")
        if has_human_title and has_app_root and script_count >= 2:
            signals.append("app_root_with_scripts")
        return tuple(signals)

    @staticmethod
    def _extract_visible_text(html: str) -> str:
        without_scripts = re.sub(
            r"<(?:script|style)[^>]*>.*?</(?:script|style)>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", without_scripts)
        return html_unescape(text)

    def _find_login_url(self, html: str, final_url: str) -> str:
        try:
            from bs4 import BeautifulSoup as bs4_BeautifulSoup
        except ImportError:
            return self._find_login_url_regex(html, final_url)

        try:
            soup = bs4_BeautifulSoup(html, "html.parser")
        except Exception:
            return self._find_login_url_regex(html, final_url)

        for form in soup.find_all("form"):
            has_password = form.find("input", attrs={"type": re.compile("^password$", re.I)})
            action = form.get("action")
            if has_password and action:
                return self._safe_action_url(action, final_url)

        for node in soup.find_all("a"):
            href = node.get("href")
            label = clean_text(node.get_text(" ", strip=True), max_length=100).lower()
            href_lower = clean_text(href, max_length=300).lower() if href else ""
            if href and any(marker in f"{label} {href_lower}" for marker in LOGIN_LINK_MARKERS):
                return self._safe_action_url(href, final_url)

        return final_url

    def _find_login_url_regex(self, html: str, final_url: str) -> str:
        form_match = re.search(
            r"<form\b[^>]*action\s*=\s*(['\"]?)(?P<url>[^'\"\s>]+)\1[^>]*>.*?<input\b[^>]*type\s*=\s*['\"]?password",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if form_match:
            return self._safe_action_url(form_match.group("url"), final_url)

        for match in re.finditer(
            r"<a\b[^>]*href\s*=\s*(['\"]?)(?P<url>[^'\"\s>]+)\1",
            html,
            re.IGNORECASE,
        ):
            candidate = match.group("url")
            if any(marker in candidate.lower() for marker in LOGIN_LINK_MARKERS):
                return self._safe_action_url(candidate, final_url)
        return final_url

    @staticmethod
    def _safe_action_url(value: str, base_url: str) -> str:
        candidate = urljoin(base_url, value.strip())
        parsed = urlparse(candidate)
        if parsed.scheme not in ALLOWED_LINK_SCHEMES or not parsed.hostname:
            return base_url
        return parsed._replace(fragment="").geturl()

    @staticmethod
    def _score_article_confidence(
        title: str,
        content: str,
        *,
        base: float,
        signals_count: int,
    ) -> float:
        score = base
        if not title:
            score -= 0.12
        if len(content) < 200:
            score -= 0.08
        elif len(content) >= 800:
            score += 0.04
        score += min(signals_count * 0.015, 0.08)
        return round(max(0.0, min(0.99, score)), 2)
