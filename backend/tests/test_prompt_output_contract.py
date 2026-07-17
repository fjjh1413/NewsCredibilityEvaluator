import unittest

from app.services.prompt_output_contract import (
    ANALYSIS_CONTRACT_VERSION,
    REQUIRED_RESULT_FIELDS,
    RISK_LEVELS,
    get_contract,
    get_contract_value,
    get_risk_level_default_score,
    render_evidence_arbitration_contract,
    render_output_contract,
)


class PromptOutputContractTests(unittest.TestCase):
    def test_contract_exports_required_versioned_shape(self) -> None:
        contract = get_contract()

        self.assertEqual(contract["version"], ANALYSIS_CONTRACT_VERSION)
        self.assertEqual(tuple(contract["required_fields"]), REQUIRED_RESULT_FIELDS)
        self.assertEqual(
            tuple(item["value"] for item in contract["risk_levels"]),
            RISK_LEVELS,
        )

    def test_rendered_output_contract_contains_all_required_fields(self) -> None:
        contract_text = render_output_contract()

        self.assertIn(f"输出契约版本：{ANALYSIS_CONTRACT_VERSION}", contract_text)
        for field in REQUIRED_RESULT_FIELDS:
            self.assertIn(field, contract_text)
        for risk_level in RISK_LEVELS:
            self.assertIn(risk_level, contract_text)

    def test_rendered_arbitration_contract_uses_same_version(self) -> None:
        contract_text = render_evidence_arbitration_contract()

        self.assertIn(f"输出契约版本：{ANALYSIS_CONTRACT_VERSION}", contract_text)
        self.assertIn("evidence_arbitration", contract_text)
        self.assertIn("evidence_quality", contract_text)
        self.assertIn("similar_news", contract_text)

    def test_contract_value_uses_aliases_and_preserves_zero(self) -> None:
        data = {
            "可信度评分": 0,
            "判断理由": "模型给出的理由",
        }

        self.assertEqual(get_contract_value(data, "llm_score"), 0)
        self.assertEqual(get_contract_value(data, "reason"), "模型给出的理由")

    def test_risk_default_scores_come_from_contract(self) -> None:
        self.assertEqual(get_risk_level_default_score("可信新闻"), 85)
        self.assertEqual(get_risk_level_default_score("存疑信息"), 65)
        self.assertEqual(get_risk_level_default_score("疑似谣言"), 50)
        self.assertEqual(get_risk_level_default_score("高风险谣言"), 25)
