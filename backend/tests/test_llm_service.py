import os
import unittest
from unittest.mock import patch

from app.services.llm_service import (
    analyze_news_credibility,
    build_analysis_prompt,
    get_default_prompt_template,
    parse_analysis_response,
)


class LlmServiceTestCase(unittest.TestCase):
    def test_parse_json_response(self) -> None:
        result = parse_analysis_response(
            """
            {
              "llm_score": 72,
              "risk_level": "存疑信息",
              "reason": "缺少明确来源。",
              "risk_points": ["来源不明确"],
              "keywords": ["网传", "官方回应"],
              "suggestion": "建议核查权威来源。"
            }
            """
        )

        self.assertEqual(result["llm_score"], 72)
        self.assertEqual(result["risk_level"], "存疑信息")
        self.assertEqual(result["risk_points"], ["来源不明确"])
        self.assertEqual(result["keywords"], ["网传", "官方回应"])

    def test_parse_json_code_block_response(self) -> None:
        result = parse_analysis_response(
            """
            模型分析如下：
            ```json
            {
              "llm_score": 88,
              "risk_level": "可信新闻",
              "reason": "与证据一致。",
              "risk_points": [],
              "keywords": "官方通报, 权威媒体",
              "suggestion": "可继续关注后续通报。"
            }
            ```
            """
        )

        self.assertEqual(result["llm_score"], 88)
        self.assertEqual(result["risk_level"], "可信新闻")
        self.assertEqual(result["keywords"], ["官方通报", "权威媒体"])

    def test_fallback_parse_plain_text_response(self) -> None:
        result = parse_analysis_response(
            """
            可信度评分：45
            风险等级：疑似谣言
            判断理由：标题表达夸张，证据不足。
            风险点：来源不明确、缺少权威证据
            关键词：网传、紧急
            建议：等待官方通报。
            """
        )

        self.assertEqual(result["llm_score"], 45)
        self.assertEqual(result["risk_level"], "疑似谣言")
        self.assertIn("标题表达夸张", result["reason"])
        self.assertEqual(result["risk_points"], ["来源不明确", "缺少权威证据"])
        self.assertEqual(result["keywords"], ["网传", "紧急"])

    def test_build_analysis_prompt_includes_inputs(self) -> None:
        prompt = build_analysis_prompt(
            title="Test title",
            content="Test content",
            evidence_list=[{"title": "Evidence"}],
            prompt_template="请分析 {title} {content} {evidence_list}",
        )

        self.assertIn("Test title", prompt)
        self.assertIn("Test content", prompt)
        self.assertIn("Evidence", prompt)
        self.assertIn("llm_score", prompt)

    def test_default_prompt_template_documents_json_contract(self) -> None:
        template = get_default_prompt_template()

        self.assertIn("新闻可信度辅助评估工具", template)
        self.assertIn("不能绝对替代人工事实核查", template)
        self.assertIn("{title}", template)
        self.assertIn("{content}", template)
        self.assertIn("{evidence_list}", template)
        self.assertIn("可信新闻、存疑信息、疑似谣言、高风险谣言", template)
        self.assertIn("不允许输出 Markdown 代码块", template)
        self.assertIn("llm_score", template)
        self.assertIn("risk_level", template)
        self.assertIn("reason", template)
        self.assertIn("risk_points", template)
        self.assertIn("keywords", template)
        self.assertIn("suggestion", template)

    def test_build_analysis_prompt_uses_top_five_evidence(self) -> None:
        prompt = build_analysis_prompt(
            title="Title",
            content="Content",
            evidence_list=[
                {"title": f"Evidence {index}"}
                for index in range(1, 7)
            ],
            prompt_template="证据：{evidence_list}",
        )

        self.assertIn("Evidence 1", prompt)
        self.assertIn("Evidence 5", prompt)
        self.assertNotIn("Evidence 6", prompt)

    def test_analyze_returns_readable_error_without_api_key(self) -> None:
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            result = analyze_news_credibility(
                title="Title",
                content="Content",
                evidence_list=[],
                prompt_template="",
            )

        self.assertEqual(result["llm_score"], 0)
        self.assertEqual(result["risk_level"], "模型调用失败")
        self.assertIn("DEEPSEEK_API_KEY", result["reason"])
        self.assertEqual(result["keywords"], [])


if __name__ == "__main__":
    unittest.main()
