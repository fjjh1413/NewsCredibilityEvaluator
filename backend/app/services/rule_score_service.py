from typing import Any

from app.utils.text_cleaner import clean_text


BASE_RULE_SCORE = 100

EXAGGERATED_WORDS = ("震惊", "疯传", "惊天秘密", "必看", "紧急扩散")
EMOTIONAL_WORDS = (
    "愤怒",
    "恐慌",
    "可怕",
    "吓人",
    "崩溃",
    "心寒",
    "恐怖",
    "惨烈",
    "离谱",
)
ABSOLUTE_WORDS = ("百分百", "100%", "一定", "所有人", "绝对", "必然", "全部")
UNCLEAR_SOURCE_WORDS = (
    "网传",
    "网络来源",
    "朋友圈",
    "微信群",
    "网友爆料",
    "未知来源",
    "不明来源",
    "自媒体",
)
SOURCE_HINT_WORDS = (
    "新华社",
    "人民日报",
    "央视",
    "官方",
    "通报",
    "公告",
    "公安",
    "卫健委",
    "应急管理",
)
NEGATIVE_EVIDENCE_WORDS = (
    "谣言",
    "不实",
    "虚假",
    "假新闻",
    "辟谣",
    "误导",
    "高风险",
    "疑似谣言",
    "不可信",
)

RULE_DEDUCTIONS = {
    "exaggerated_words": 15,
    "missing_source": 20,
    "emotional_words": 15,
    "absolute_words": 15,
    "evidence_conflict": 25,
}


def calculate_rule_score(
    title: str,
    content: str,
    source_name: str | None = None,
    evidence_list: list[Any] | None = None,
) -> dict[str, Any]:
    """Score news risk with simple explainable rules.

    The score starts from 100. Each hit rule deducts a fixed score. A higher
    score means the text looks more credible under these lightweight rules.
    """

    title_text = clean_text(title, max_length=1000)
    content_text = clean_text(content, max_length=12000)
    source_text = clean_text(source_name, max_length=200)
    combined_text = f"{title_text}\n{content_text}"

    hit_rules: list[dict[str, Any]] = []

    exaggerated_hits = _find_terms(combined_text, EXAGGERATED_WORDS)
    if exaggerated_hits:
        hit_rules.append(
            _build_hit_rule(
                rule_key="exaggerated_words",
                rule_name="包含夸张词",
                deduction=RULE_DEDUCTIONS["exaggerated_words"],
                matched_terms=exaggerated_hits,
                description="标题或正文包含容易诱导转发的夸张传播类词语。",
            )
        )

    if _is_missing_clear_source(source_text, combined_text):
        hit_rules.append(
            _build_hit_rule(
                rule_key="missing_source",
                rule_name="缺少明确来源",
                deduction=RULE_DEDUCTIONS["missing_source"],
                matched_terms=[],
                description="未提供明确来源，且正文中没有明显权威来源提示。",
            )
        )

    emotional_hits = _find_terms(combined_text, EMOTIONAL_WORDS)
    if emotional_hits:
        hit_rules.append(
            _build_hit_rule(
                rule_key="emotional_words",
                rule_name="包含强情绪化表达",
                deduction=RULE_DEDUCTIONS["emotional_words"],
                matched_terms=emotional_hits,
                description="标题或正文包含较强情绪化表达，可能影响客观判断。",
            )
        )

    absolute_hits = _find_terms(combined_text, ABSOLUTE_WORDS)
    if absolute_hits:
        hit_rules.append(
            _build_hit_rule(
                rule_key="absolute_words",
                rule_name="包含绝对化表述",
                deduction=RULE_DEDUCTIONS["absolute_words"],
                matched_terms=absolute_hits,
                description="标题或正文包含绝对化表达，可信度需要谨慎评估。",
            )
        )

    conflict_evidence = _find_conflict_evidence(evidence_list or [])
    if conflict_evidence:
        hit_rules.append(
            _build_hit_rule(
                rule_key="evidence_conflict",
                rule_name="与知识库证据存在明显冲突",
                deduction=RULE_DEDUCTIONS["evidence_conflict"],
                matched_terms=conflict_evidence,
                description="Top5 证据中存在高相似且被标记为谣言、不实或高风险的记录。",
            )
        )

    total_deduction = sum(int(rule["deduction"]) for rule in hit_rules)
    rule_score = max(0, min(100, BASE_RULE_SCORE - total_deduction))
    return {
        "rule_score": rule_score,
        "hit_rules": hit_rules,
    }


def _find_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term and term in text]


def _is_missing_clear_source(source_name: str, text: str) -> bool:
    if source_name and not _find_terms(source_name, UNCLEAR_SOURCE_WORDS):
        return False
    return not _find_terms(text, SOURCE_HINT_WORDS)


def _find_conflict_evidence(evidence_list: list[Any]) -> list[str]:
    conflict_items: list[str] = []
    for index, evidence in enumerate(evidence_list[:5], start=1):
        evidence_text = _build_evidence_text(evidence)
        if not _find_terms(evidence_text, NEGATIVE_EVIDENCE_WORDS):
            continue
        if not _is_high_similarity_evidence(evidence):
            continue

        title = clean_text(_get_evidence_value(evidence, "title"), max_length=80)
        conflict_items.append(title or f"evidence_{index}")

    return conflict_items


def _build_evidence_text(evidence: Any) -> str:
    fields = (
        "title",
        "summary",
        "truth_label",
        "risk_level",
        "debunking_explanation",
        "source_name",
    )
    values = [
        clean_text(_get_evidence_value(evidence, field), max_length=1000)
        for field in fields
    ]
    return "\n".join(value for value in values if value)


def _is_high_similarity_evidence(evidence: Any) -> bool:
    score = _get_evidence_value(evidence, "similarity_score")
    if score is None:
        return True
    try:
        return float(score) >= 0.7
    except (TypeError, ValueError):
        return True


def _get_evidence_value(evidence: Any, key: str) -> Any:
    if isinstance(evidence, dict):
        return evidence.get(key)
    return getattr(evidence, key, None)


def _build_hit_rule(
    rule_key: str,
    rule_name: str,
    deduction: int,
    matched_terms: list[str],
    description: str,
) -> dict[str, Any]:
    return {
        "rule_key": rule_key,
        "rule_name": rule_name,
        "deduction": deduction,
        "matched_terms": matched_terms,
        "description": description,
    }
