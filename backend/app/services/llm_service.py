import json
import logging
import os
import re
import socket
import urllib.error
import urllib.request
from typing import Any

from app.core.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_TRUSTED,
)
from app.core.config import BASE_DIR
from app.services.prompt_template_validator import (
    NEWS_CREDIBILITY_PROMPT_TYPE,
    PromptTemplateValidationError,
    validate_prompt_template_content,
)
from app.utils.risk_level import get_risk_level_from_score
from app.utils.text_cleaner import clean_text


logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEEPSEEK_API_BASE_ENV = "DEEPSEEK_API_BASE"
DEEPSEEK_MODEL_ENV = "DEEPSEEK_MODEL"
DEEPSEEK_TIMEOUT_ENV = "DEEPSEEK_TIMEOUT_SECONDS"

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_EVIDENCE_LIMIT = 5
LLM_FAILURE_ERROR = "模型调用失败"

DEFAULT_CREDIBILITY_ANALYSIS_PROMPT_TEMPLATE = """
你是“智闻辨真”的新闻可信度辅助评估工具，用于帮助用户初步判断新闻内容的可信度和风险点。
你的结论只作为辅助参考，不能绝对替代人工事实核查、权威媒体报道或官方通报。

请基于以下输入进行分析：

新闻标题：
{title}

新闻正文：
{content}

Top5 检索证据：
{evidence_list}

分析要求：
1. 必须优先依据 Top5 检索证据进行判断，不能脱离证据凭空推断。
2. 如果新闻内容与证据一致，可以给出较高可信度评分。
3. 如果新闻内容与证据冲突、来源不清、表达夸张或缺少权威佐证，需要降低可信度评分。
4. 如果证据不足或证据无法直接支持/反驳新闻，应输出“存疑信息”或“疑似谣言”，不要强行判断真假。
5. 风险等级 risk_level 只能从以下四类中选择一个：可信新闻、存疑信息、疑似谣言、高风险谣言。
6. llm_score 为 0 到 100 的数字，分数越高表示越可信。
7. 必须只输出 JSON 对象，不允许输出 Markdown 代码块，不允许添加解释性前缀或后缀。

JSON 输出格式必须为：
{
  "llm_score": 0,
  "risk_level": "存疑信息",
  "reason": "用一段话说明判断依据，必须引用或概括证据情况。",
  "risk_points": ["风险点1", "风险点2"],
  "keywords": ["关键词1", "关键词2"],
  "suggestion": "给用户的核查或阅读建议。"
}
""".strip()

REQUIRED_RESULT_FIELDS = (
    "llm_score",
    "risk_level",
    "reason",
    "risk_points",
    "keywords",
    "suggestion",
)

RISK_LEVELS = (
    RISK_LEVEL_TRUSTED,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_HIGH,
)


class DeepSeekServiceError(Exception):
    """Raised when the DeepSeek API cannot be called or read safely."""


def analyze_news_credibility(
    title: str,
    content: str,
    evidence_list: list[Any] | None,
    prompt_template: str,
) -> dict[str, Any]:
    """Analyze news credibility with DeepSeek and return a stable dict shape."""

    config = _load_deepseek_config()
    if not config["api_key"]:
        return _build_error_result(
            reason="DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY。",
            risk_point="DeepSeek API Key 未配置",
            suggestion=(
                f"请在后端环境变量或 {BASE_DIR / '.env'} 中配置 "
                "DEEPSEEK_API_KEY 后重试。"
            ),
        )

    try:
        prompt = build_analysis_prompt(
            title=title,
            content=content,
            evidence_list=evidence_list,
            prompt_template=prompt_template,
        )
        response_data = _post_chat_completion(config=config, prompt=prompt)
        assistant_content = _extract_assistant_content(response_data)
        if not assistant_content:
            return _build_error_result(
                reason="DeepSeek API 已返回，但模型内容为空。",
                risk_point="模型返回内容为空",
                suggestion="请稍后重试，或检查模型名称和 Prompt 模板是否可用。",
            )
        return parse_analysis_response(assistant_content)
    except DeepSeekServiceError as exc:
        logger.exception("DeepSeek API call failed")
        return _build_error_result(
            reason=f"DeepSeek API 调用失败：{exc}",
            risk_point="DeepSeek API 调用失败",
            suggestion=(
                "请检查 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、"
                "DEEPSEEK_MODEL 和网络连接后重试。"
            ),
        )


def build_analysis_prompt(
    title: str,
    content: str,
    evidence_list: list[Any] | None,
    prompt_template: str,
) -> str:
    title_text = clean_text(title, max_length=1000)
    content_text = clean_text(content, max_length=12000)
    evidence_json = _dump_json(_limit_evidence_list(evidence_list), indent=2)
    if not title_text or not content_text:
        raise DeepSeekServiceError("新闻标题和正文不能为空，无法构造安全分析Prompt")

    requested_template = clean_text(prompt_template, max_length=None)
    template = _select_safe_prompt_template(requested_template)
    prompt = _render_prompt_template(
        template=template,
        title=title_text,
        content=content_text,
        evidence_json=evidence_json,
    )
    prompt = _ensure_output_contract(prompt)
    prompt = clean_text(prompt, max_length=None)

    if not _rendered_prompt_contains_inputs(
        prompt=prompt,
        title=title_text,
        content=content_text,
        evidence_json=evidence_json,
    ):
        logger.error("Rendered Prompt lost required news inputs; retrying with code fallback")
        fallback = _validated_code_fallback_prompt()
        prompt = _ensure_output_contract(
            _render_prompt_template(
                template=fallback,
                title=title_text,
                content=content_text,
                evidence_json=evidence_json,
            )
        )
        prompt = clean_text(prompt, max_length=None)
        if not _rendered_prompt_contains_inputs(
            prompt=prompt,
            title=title_text,
            content=content_text,
            evidence_json=evidence_json,
        ):
            raise DeepSeekServiceError("安全兜底Prompt渲染失败，已阻止发送无效Prompt")

    return prompt


def get_default_prompt_template() -> str:
    return DEFAULT_CREDIBILITY_ANALYSIS_PROMPT_TEMPLATE


def _select_safe_prompt_template(prompt_template: str) -> str:
    if prompt_template:
        try:
            return validate_prompt_template_content(
                NEWS_CREDIBILITY_PROMPT_TYPE,
                prompt_template,
            )
        except PromptTemplateValidationError as exc:
            logger.warning(
                "Configured news credibility Prompt is invalid; using code fallback: %s",
                exc,
            )
    else:
        logger.warning("No configured prompt template supplied, fallback to built-in prompt.")
    return _validated_code_fallback_prompt()


def _validated_code_fallback_prompt() -> str:
    try:
        return validate_prompt_template_content(
            NEWS_CREDIBILITY_PROMPT_TYPE,
            get_default_prompt_template(),
        )
    except PromptTemplateValidationError as exc:
        logger.exception("Code fallback Prompt failed safety validation")
        raise DeepSeekServiceError("安全兜底Prompt配置无效，已阻止调用DeepSeek") from exc


def _render_prompt_template(
    template: str,
    title: str,
    content: str,
    evidence_json: str,
) -> str:
    return (
        template.replace("{title}", title)
        .replace("{content}", content)
        .replace("{evidence_list}", evidence_json)
        .replace("{evidence_json}", evidence_json)
    )


def _rendered_prompt_contains_inputs(
    prompt: str,
    title: str,
    content: str,
    evidence_json: str,
) -> bool:
    expected_inputs = (
        clean_text(title, max_length=None),
        clean_text(content, max_length=None),
        clean_text(evidence_json, max_length=None),
    )
    return all(value and value in prompt for value in expected_inputs)


def parse_analysis_response(response_text: str) -> dict[str, Any]:
    cleaned_text = clean_text(response_text, max_length=None)
    parsed_json = _parse_json_from_text(cleaned_text)
    if parsed_json is not None:
        return _normalize_result(parsed_json, raw_text=cleaned_text)
    return _fallback_parse_text(cleaned_text)


def _load_deepseek_config() -> dict[str, Any]:
    return {
        "api_key": clean_text(os.getenv(DEEPSEEK_API_KEY_ENV), max_length=None),
        "base_url": clean_text(
            os.getenv(DEEPSEEK_BASE_URL_ENV)
            or os.getenv(DEEPSEEK_API_BASE_ENV)
            or DEFAULT_DEEPSEEK_BASE_URL,
            max_length=None,
        ),
        "model": clean_text(
            os.getenv(DEEPSEEK_MODEL_ENV) or DEFAULT_DEEPSEEK_MODEL,
            max_length=None,
        ),
        "timeout_seconds": _read_timeout_seconds(),
    }


def _read_timeout_seconds() -> float:
    raw_value = os.getenv(DEEPSEEK_TIMEOUT_ENV)
    if not raw_value:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw_value)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return timeout if timeout > 0 else DEFAULT_TIMEOUT_SECONDS


def _post_chat_completion(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    url = _build_chat_completion_url(config["base_url"])
    payload = {
        "model": config["model"],
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是新闻可信度分析助手。你必须基于用户新闻和检索证据进行分析，"
                    "并只返回符合要求的 JSON。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    request = urllib.request.Request(
        url=url,
        data=_dump_json(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=float(config["timeout_seconds"]),
        ) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        message = _extract_api_error_message(response_body) or clean_text(exc.reason)
        raise DeepSeekServiceError(f"HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise DeepSeekServiceError(f"网络连接异常：{exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise DeepSeekServiceError("请求超时") from exc
    except Exception as exc:
        raise DeepSeekServiceError(f"{type(exc).__name__}: {exc}") from exc

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DeepSeekServiceError("DeepSeek API 返回不是有效 JSON") from exc


def _build_chat_completion_url(base_url: str) -> str:
    normalized = clean_text(base_url, max_length=None).rstrip("/")
    if not normalized:
        normalized = DEFAULT_DEEPSEEK_BASE_URL
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _extract_assistant_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    message = first_choice.get("message") or {}
    if isinstance(message, dict):
        content = message.get("content")
        if content:
            return clean_text(content, max_length=None)

    text = first_choice.get("text")
    return clean_text(text, max_length=None)


def _parse_json_from_text(text: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        picked = _pick_result_dict(parsed)
        if picked is not None:
            return picked
    return None


def _json_candidates(text: str) -> list[str]:
    candidates = [text.strip()]
    candidates.extend(
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    )

    object_text = _extract_first_json_object(text)
    if object_text:
        candidates.append(object_text)

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _pick_result_dict(parsed: Any) -> dict[str, Any] | None:
    if isinstance(parsed, dict):
        if any(field in parsed for field in REQUIRED_RESULT_FIELDS):
            return parsed
        for key in ("data", "result", "analysis"):
            value = parsed.get(key)
            if isinstance(value, dict):
                return value
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    return None


def _normalize_result(data: dict[str, Any], raw_text: str = "") -> dict[str, Any]:
    score = _normalize_score(
        data.get("llm_score")
        or data.get("score")
        or data.get("credibility_score")
        or data.get("可信度评分")
    )
    risk_level = clean_text(
        data.get("risk_level") or data.get("风险等级"),
        max_length=50,
    )
    if not risk_level:
        risk_level = get_risk_level_from_score(score)

    reason = clean_text(
        data.get("reason")
        or data.get("judgement_result")
        or data.get("judgment_result")
        or data.get("判断理由")
        or data.get("reasoning")
        or raw_text
        or "模型未提供判断理由。",
        max_length=2000,
    )

    risk_points = _normalize_string_list(
        data.get("risk_points") or data.get("风险点"),
        fallback=[],
    )
    keywords = _normalize_string_list(
        data.get("keywords") or data.get("关键词"),
        fallback=[],
    )
    suggestion = clean_text(
        data.get("suggestion") or data.get("建议") or "建议结合权威来源进行人工复核。",
        max_length=1000,
    )

    return {
        "llm_score": score,
        "risk_level": risk_level,
        "reason": reason,
        "risk_points": risk_points,
        "keywords": keywords,
        "suggestion": suggestion,
    }


def _fallback_parse_text(text: str) -> dict[str, Any]:
    score = _extract_score(text)
    risk_level = _extract_risk_level(text)
    if score is None and risk_level:
        score = _score_from_risk_level(risk_level)
    if score is None:
        score = 0

    reason = _extract_section(
        text,
        labels=("reason", "判断理由", "理由", "原因"),
    )
    risk_points = _extract_list_section(
        text,
        labels=("risk_points", "风险点", "风险因素"),
    )
    keywords = _extract_list_section(
        text,
        labels=("keywords", "关键词"),
    )
    suggestion = _extract_section(
        text,
        labels=("suggestion", "建议", "核查建议", "辟谣建议"),
    )

    return {
        "llm_score": _normalize_score(score),
        "risk_level": risk_level or get_risk_level_from_score(float(score)),
        "reason": reason
        or f"模型返回非 JSON，已启用兜底解析。原始返回：{clean_text(text, max_length=1200)}",
        "risk_points": risk_points or ["模型未按 JSON 格式返回，已使用文本兜底解析"],
        "keywords": keywords,
        "suggestion": suggestion or "建议结合检索证据和权威来源进行人工复核。",
    }


def _extract_score(text: str) -> float | None:
    patterns = (
        r"(?:llm_score|score|credibility_score)\s*[:：=]\s*(\d+(?:\.\d+)?)",
        r"(?:可信度评分|评分|分数)\s*[:：=]?\s*(\d+(?:\.\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_risk_level(text: str) -> str:
    for risk_level in RISK_LEVELS:
        if risk_level in text:
            return risk_level
    return ""


def _extract_section(text: str, labels: tuple[str, ...]) -> str:
    label_group = "|".join(re.escape(label) for label in labels)
    stop_labels = (
        "llm_score|score|risk_level|reason|risk_points|keywords|suggestion|"
        "评分|风险等级|判断理由|理由|原因|风险点|风险因素|关键词|建议|核查建议|辟谣建议"
    )
    pattern = rf"(?:{label_group})\s*[:：]\s*(.*?)(?=\n\s*(?:{stop_labels})\s*[:：]|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean_text(match.group(1), max_length=1000)


def _extract_list_section(text: str, labels: tuple[str, ...]) -> list[str]:
    section = _extract_section(text, labels=labels)
    if section:
        return _normalize_string_list(section, fallback=[])

    bullet_items = []
    for line in text.splitlines():
        if re.match(r"\s*[-*]\s+", line):
            bullet_items.append(re.sub(r"\s*[-*]\s+", "", line, count=1))
    return _normalize_string_list(bullet_items, fallback=[])


def _normalize_score(value: Any) -> float:
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        score = float(match.group(0)) if match else 0.0
    elif isinstance(value, (int, float)):
        score = float(value)
    else:
        score = 0.0

    score = min(100.0, max(0.0, score))
    return round(score, 2)


def _score_from_risk_level(risk_level: str) -> int:
    mapping = {
        RISK_LEVEL_TRUSTED: 85,
        RISK_LEVEL_SUSPICIOUS: 65,
        RISK_LEVEL_RUMOR: 50,
        RISK_LEVEL_HIGH: 25,
    }
    return mapping.get(risk_level, 0)


def _normalize_string_list(value: Any, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback

    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple):
        raw_items = list(value)
    else:
        raw_items = re.split(r"[,，;；、\n]+", clean_text(value, max_length=None))

    items: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            cleaned = clean_text(_dump_json(item), max_length=500)
        else:
            cleaned = clean_text(item, max_length=500)
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)、])\s*", "", cleaned)
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items or fallback


def _ensure_output_contract(prompt: str) -> str:
    if all(field in prompt for field in REQUIRED_RESULT_FIELDS):
        return prompt

    output_contract = """
输出要求：
1. 必须只输出 JSON 对象，不允许输出 Markdown 代码块，不允许添加解释性前缀或后缀。
2. risk_level 只能从以下四类中选择一个：可信新闻、存疑信息、疑似谣言、高风险谣言。
3. JSON 字段必须包含：llm_score、risk_level、reason、risk_points、keywords、suggestion。
""".strip()
    return f"{prompt}\n\n{output_contract}"


def _limit_evidence_list(evidence_list: list[Any] | None) -> list[Any]:
    if not evidence_list:
        return []
    return list(evidence_list[:DEFAULT_EVIDENCE_LIMIT])


def _build_error_result(
    reason: str,
    risk_point: str,
    suggestion: str,
) -> dict[str, Any]:
    reason_text = clean_text(reason, max_length=2000)
    if LLM_FAILURE_ERROR not in reason_text:
        reason_text = clean_text(f"{LLM_FAILURE_ERROR}：{reason_text}", max_length=2000)

    risk_point_text = clean_text(risk_point, max_length=500)
    if LLM_FAILURE_ERROR not in risk_point_text:
        risk_point_text = clean_text(
            f"{LLM_FAILURE_ERROR}：{risk_point_text}",
            max_length=500,
        )

    return {
        "llm_score": 0,
        "risk_level": RISK_LEVEL_SUSPICIOUS,
        "reason": reason_text,
        "risk_points": [risk_point_text],
        "keywords": [],
        "suggestion": clean_text(suggestion, max_length=1000),
        "error": LLM_FAILURE_ERROR,
    }


def _extract_api_error_message(response_body: str) -> str:
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return clean_text(response_body, max_length=1000)

    error = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(error, dict):
        return clean_text(
            error.get("message") or error.get("code") or _dump_json(error),
            max_length=1000,
        )
    if isinstance(error, str):
        return clean_text(error, max_length=1000)
    return clean_text(_dump_json(parsed), max_length=1000)


def _default_prompt_template() -> str:
    return get_default_prompt_template()


def _dump_json(value: Any, indent: int | None = None) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=indent,
        default=_json_default,
    )


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)
