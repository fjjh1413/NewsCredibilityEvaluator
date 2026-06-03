import unittest
from types import SimpleNamespace

from app.services.rule_score_service import calculate_rule_score


class RuleScoreServiceTestCase(unittest.TestCase):
    def test_clean_news_keeps_full_score(self) -> None:
        result = calculate_rule_score(
            title="某地发布防汛工作情况通报",
            content="据当地应急管理部门通报，目前防汛工作有序开展。",
            source_name="当地应急管理部门",
            evidence_list=[
                {
                    "title": "防汛工作情况通报",
                    "truth_label": "可信",
                    "risk_level": "可信新闻",
                    "similarity_score": 0.86,
                }
            ],
        )

        self.assertEqual(result["rule_score"], 100)
        self.assertEqual(result["hit_rules"], [])

    def test_hits_all_core_risk_rules(self) -> None:
        result = calculate_rule_score(
            title="震惊！惊天秘密疯传，所有人必看",
            content="这件事太可怕，百分百是真的，一定要紧急扩散。",
            source_name="网传",
            evidence_list=[
                {
                    "title": "网传消息已被辟谣",
                    "summary": "经核实，该消息为不实信息。",
                    "truth_label": "谣言",
                    "risk_level": "高风险谣言",
                    "similarity_score": 0.91,
                }
            ],
        )

        hit_keys = [rule["rule_key"] for rule in result["hit_rules"]]

        self.assertEqual(result["rule_score"], 10)
        self.assertEqual(
            hit_keys,
            [
                "exaggerated_words",
                "missing_source",
                "emotional_words",
                "absolute_words",
                "evidence_conflict",
            ],
        )

    def test_content_source_hint_avoids_missing_source_rule(self) -> None:
        result = calculate_rule_score(
            title="某地发布道路管制信息",
            content="据公安部门通报，该路段临时管制两小时。",
            source_name=None,
            evidence_list=[],
        )

        hit_keys = [rule["rule_key"] for rule in result["hit_rules"]]

        self.assertNotIn("missing_source", hit_keys)
        self.assertEqual(result["rule_score"], 100)

    def test_low_similarity_negative_evidence_does_not_count_as_conflict(self) -> None:
        result = calculate_rule_score(
            title="普通新闻",
            content="普通正文。",
            source_name="官方通报",
            evidence_list=[
                {
                    "title": "不相关谣言案例",
                    "truth_label": "谣言",
                    "risk_level": "高风险谣言",
                    "similarity_score": 0.31,
                }
            ],
        )

        hit_keys = [rule["rule_key"] for rule in result["hit_rules"]]

        self.assertNotIn("evidence_conflict", hit_keys)
        self.assertEqual(result["rule_score"], 100)

    def test_supports_object_evidence(self) -> None:
        result = calculate_rule_score(
            title="网传某消息",
            content="正文内容。",
            source_name="官方通报",
            evidence_list=[
                SimpleNamespace(
                    title="相似辟谣信息",
                    truth_label="不实",
                    risk_level="疑似谣言",
                    similarity_score=0.8,
                )
            ],
        )

        hit_keys = [rule["rule_key"] for rule in result["hit_rules"]]

        self.assertIn("evidence_conflict", hit_keys)
        self.assertEqual(result["rule_score"], 75)


if __name__ == "__main__":
    unittest.main()
