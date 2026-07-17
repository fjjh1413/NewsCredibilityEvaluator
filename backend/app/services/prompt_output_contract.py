from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "prompt_output_contract.json"
)


class PromptOutputContractError(RuntimeError):
    """Raised when the prompt output contract is missing or malformed."""


def _as_tuple_map(value: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        str(field): tuple(str(alias) for alias in aliases)
        for field, aliases in value.items()
        if isinstance(aliases, list)
    }


def _require_string_list(contract: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = contract.get(key)
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise PromptOutputContractError(f"Invalid prompt output contract field: {key}")
    return tuple(raw)


def _validate_contract(contract: dict[str, Any]) -> None:
    if not isinstance(contract.get("version"), str) or not contract["version"]:
        raise PromptOutputContractError("Prompt output contract version is required")

    _require_string_list(contract, "required_fields")

    aliases = contract.get("field_aliases")
    if not isinstance(aliases, dict):
        raise PromptOutputContractError("Prompt output contract field_aliases is required")

    risk_levels = contract.get("risk_levels")
    if not isinstance(risk_levels, list) or not risk_levels:
        raise PromptOutputContractError("Prompt output contract risk_levels is required")
    for level in risk_levels:
        if not isinstance(level, dict) or not level.get("key") or not level.get("value"):
            raise PromptOutputContractError("Each risk level requires key and value")

    arbitration = contract.get("evidence_arbitration")
    if not isinstance(arbitration, dict):
        raise PromptOutputContractError("Prompt output contract evidence_arbitration is required")
    ranked = arbitration.get("ranked_evidence")
    rejected = arbitration.get("rejected_evidence")
    if not isinstance(ranked, dict) or not isinstance(rejected, dict):
        raise PromptOutputContractError("Arbitration ranked/rejected schemas are required")
    if not ranked.get("required_fields") or not rejected.get("required_fields"):
        raise PromptOutputContractError("Arbitration required fields are required")
    if not arbitration.get("stances"):
        raise PromptOutputContractError("Arbitration stances are required")


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    try:
        with _CONTRACT_PATH.open("r", encoding="utf-8") as file_obj:
            contract = json.load(file_obj)
    except OSError as exc:
        raise PromptOutputContractError("Prompt output contract file is missing") from exc
    except json.JSONDecodeError as exc:
        raise PromptOutputContractError("Prompt output contract file is not valid JSON") from exc

    if not isinstance(contract, dict):
        raise PromptOutputContractError("Prompt output contract must be a JSON object")
    _validate_contract(contract)
    return contract


_CONTRACT = _load_contract()

ANALYSIS_CONTRACT_VERSION = str(_CONTRACT["version"])
REQUIRED_RESULT_FIELDS = tuple(_CONTRACT["required_fields"])
FIELD_ALIASES = _as_tuple_map(_CONTRACT["field_aliases"])
RISK_LEVEL_DETAILS = tuple(copy.deepcopy(_CONTRACT["risk_levels"]))
RISK_LEVELS = tuple(str(item["value"]) for item in RISK_LEVEL_DETAILS)
ARBITRATION_STANCE_VALUES = tuple(
    str(item) for item in _CONTRACT["evidence_arbitration"]["stances"]
)
ARBITRATION_STANCES = frozenset(
    ARBITRATION_STANCE_VALUES
)
ARBITRATION_REQUIRED_KEYS = frozenset(
    str(item)
    for item in _CONTRACT["evidence_arbitration"]["ranked_evidence"]["required_fields"]
)


def get_contract() -> dict[str, Any]:
    """Return a defensive copy of the canonical prompt output contract."""

    return copy.deepcopy(_load_contract())


def get_contract_value(data: dict[str, Any], field: str, default: Any = None) -> Any:
    """Read a field using the contract's known aliases.

    Empty strings and ``None`` are treated as absent. Numeric zero remains a
    valid value, which matters for scores.
    """

    aliases = FIELD_ALIASES.get(field, (field,))
    for alias in aliases:
        if alias not in data:
            continue
        value = data[alias]
        if value is None or value == "":
            continue
        return value
    return default


def get_fallback_value(field: str, default: str = "") -> str:
    fallbacks = _CONTRACT.get("fallbacks", {})
    if not isinstance(fallbacks, dict):
        return default
    return str(fallbacks.get(field) or default)


def get_risk_level_details() -> tuple[dict[str, Any], ...]:
    return tuple(copy.deepcopy(RISK_LEVEL_DETAILS))


def get_risk_level_default_score(risk_level: str) -> int:
    for item in RISK_LEVEL_DETAILS:
        if item.get("value") == risk_level:
            return int(item.get("default_score") or 0)
    return 0


def render_risk_level_phrase() -> str:
    return "、".join(RISK_LEVELS)


def _json_sample() -> str:
    sample = {
        "llm_score": 75,
        "risk_level": "存疑信息",
        "reason": "用一段话说明判断依据，必须引用或概括有效证据情况。",
        "evidence_quality": {
            "coverage": 80,
            "consistency": 70,
            "assessment": "有效证据覆盖较充分，但不同来源之间存在少量差异。",
        },
        "evidence_arbitration": {
            "ranked_evidence": [
                {
                    "candidate_id": "web:2",
                    "relevance_score": 92,
                    "quality_score": 88,
                    "stance": "support",
                    "reason": "该证据直接覆盖当前新闻核心事实。",
                }
            ],
            "rejected_evidence": [
                {
                    "candidate_id": "kb:5",
                    "reason": "该证据描述的是另一个不相关事件。",
                }
            ],
        },
        "similar_news": [
            {
                "candidate_id": "web:2",
                "risk_level": "可信新闻",
                "relevance_reason": "该候选描述同一事件，核心事实与检测新闻一致。",
            }
        ],
        "risk_points": ["风险点1", "风险点2"],
        "keywords": ["关键词1", "关键词2"],
        "suggestion": "给用户的核查或阅读建议。",
    }
    return json.dumps(sample, ensure_ascii=False, indent=2)


def render_output_contract() -> str:
    evidence_quality = _CONTRACT["evidence_quality"]
    arbitration = _CONTRACT["evidence_arbitration"]
    similar_news = _CONTRACT["similar_news"]
    quality_fields = "、".join(evidence_quality["model_required_fields"])
    normalized_quality_fields = "、".join(evidence_quality["normalized_fields"])
    ranked_fields = "、".join(arbitration["ranked_evidence"]["required_fields"])
    rejected_fields = "、".join(arbitration["rejected_evidence"]["required_fields"])
    similar_fields = "、".join(similar_news["required_fields"])
    required_fields = "、".join(REQUIRED_RESULT_FIELDS)
    stances = "、".join(ARBITRATION_STANCE_VALUES)

    return f"""输出契约版本：{ANALYSIS_CONTRACT_VERSION}
输出要求：
1. 必须只输出 JSON 对象，不允许输出 Markdown 代码块，不允许添加解释性前缀或后缀。
2. 顶层 JSON 字段必须包含：{required_fields}。
3. risk_level 只能从以下四类中选择一个：{render_risk_level_phrase()}。
4. evidence_quality 必须是 JSON 对象，模型必须返回 {quality_fields}；后端归一化后固定提供 {normalized_quality_fields}，其中 score 由后端统一计算。
5. evidence_arbitration 必须包含 ranked_evidence 和 rejected_evidence。ranked_evidence 每项必须包含 {ranked_fields}；rejected_evidence 每项必须包含 {rejected_fields}；candidate_id 必须来自输入候选且不得凭空生成。
6. relevance_score 和 quality_score 必须为 0-100 的数字；stance 只能是 {stances}；reason 必须为非空字符串。
7. similar_news 必须是数组，每项包含 {similar_fields}；candidate_id 必须来自 ranked_evidence；没有相似新闻时返回空数组，不得省略字段。
JSON 输出格式必须为：
{_json_sample()}""".strip()


def render_evidence_arbitration_contract() -> str:
    evidence_quality = _CONTRACT["evidence_quality"]
    arbitration = _CONTRACT["evidence_arbitration"]
    similar_news = _CONTRACT["similar_news"]
    quality_fields = "、".join(evidence_quality["model_required_fields"])
    ranked_fields = "、".join(arbitration["ranked_evidence"]["required_fields"])
    rejected_fields = "、".join(arbitration["rejected_evidence"]["required_fields"])
    similar_fields = "、".join(similar_news["required_fields"])
    stances = "、".join(ARBITRATION_STANCE_VALUES)

    return f"""输出契约版本：{ANALYSIS_CONTRACT_VERSION}
必须返回且只返回以下三个顶层字段：
1. evidence_arbitration：包含 ranked_evidence 和 rejected_evidence 两个数组。ranked_evidence 每项必须包含 {ranked_fields}；rejected_evidence 每项必须包含 {rejected_fields}。每个输入 candidate_id 必须且只能出现一次。
2. evidence_quality：包含 {quality_fields}；coverage 和 consistency 必须为 0-100 的数字；assessment 必须是非空字符串；score 由后端统一计算，可省略。
3. similar_news：数组；每项包含 {similar_fields}；candidate_id 必须来自 ranked_evidence；没有则返回空数组。
stance 只能是 {stances}；reason 必须基于证据实际内容。""".strip()
