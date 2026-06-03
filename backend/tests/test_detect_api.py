import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1.detect import get_db, get_optional_current_user
from app.main import app
from app.schemas.detection import DetectNewsRequest
from app.services.detection_service import (
    LLMAnalysisFailedError,
    detect_news_credibility,
)


def _db_override():
    return Mock()


def _optional_user_override():
    return SimpleNamespace(id=1, role="user", status="active")


def _vector_result(knowledge_id: int, score: float) -> dict:
    return {
        "metadata": {
            "knowledge_id": knowledge_id,
            "title": f"Evidence {knowledge_id}",
            "summary": "summary",
            "category": "society",
            "truth_label": "credible",
            "source_name": "official",
            "risk_level": "可信新闻",
            "vector_sync_status": "synced",
        },
        "similarity_score": score,
    }


class DetectServiceTestCase(unittest.TestCase):
    def test_detect_news_computes_scores_and_saves_record(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
        ):
            mocked_search.return_value = [_vector_result(1, 0.8), _vector_result(2, 0.6)]
            mocked_llm.return_value = {
                "llm_score": 70,
                "risk_level": "存疑信息",
                "reason": "证据部分支持。",
                "risk_points": ["来源需要核查"],
                "keywords": ["官方通报"],
                "suggestion": "继续关注权威信息。",
            }
            mocked_rule.return_value = {
                "rule_score": 80,
                "hit_rules": [{"rule_name": "缺少明确来源"}],
            }
            mocked_save.return_value = SimpleNamespace(id=123)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(title="News title", content="News content"),
                current_user=SimpleNamespace(id=7, role="user"),
            )

        self.assertEqual(result["detection_id"], 123)
        self.assertEqual(result["evidence_score"], 70)
        self.assertEqual(result["llm_score"], 70)
        self.assertEqual(result["rule_score"], 80)
        self.assertEqual(result["final_score"], 72)
        self.assertEqual(result["risk_level"], "存疑信息")
        self.assertEqual(len(result["evidence_list"]), 2)
        self.assertEqual(len(result["similar_news"]), 2)
        self.assertEqual(mocked_search.call_args.kwargs["top_k"], 10)
        saved_payload = mocked_save.call_args.args[1]
        self.assertEqual(saved_payload.user_id, 7)
        self.assertEqual(len(saved_payload.evidence_matches), 2)

    def test_detect_news_continues_when_rag_returns_no_evidence(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
        ):
            mocked_search.return_value = []
            mocked_llm.return_value = {
                "llm_score": 60,
                "risk_level": "存疑信息",
                "reason": "证据较少。",
                "risk_points": [],
                "keywords": [],
                "suggestion": "人工复核。",
            }
            mocked_rule.return_value = {"rule_score": 90, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=124)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(title="News title", content="News content"),
                current_user=None,
            )

        self.assertEqual(result["detection_id"], 124)
        self.assertEqual(result["evidence_score"], 0)
        self.assertIn("证据不足", result["reason"])
        saved_payload = mocked_save.call_args.args[1]
        self.assertIsNone(saved_payload.user_id)
        self.assertEqual(saved_payload.evidence_matches, [])

    def test_detect_news_raises_when_deepseek_fails(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
        ):
            mocked_search.return_value = []
            mocked_llm.return_value = {
                "llm_score": 0,
                "risk_level": "模型调用失败",
                "reason": "DeepSeek API Key 未配置",
                "risk_points": ["DeepSeek API Key 未配置"],
                "keywords": [],
                "suggestion": "配置 API Key。",
            }

            with self.assertRaises(LLMAnalysisFailedError):
                detect_news_credibility(
                    db=Mock(),
                    payload=DetectNewsRequest(title="News title", content="News content"),
                    current_user=None,
                )

            mocked_save.assert_not_called()


class DetectApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_optional_current_user] = _optional_user_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_endpoint_returns_success(self, mocked_detect) -> None:
        mocked_detect.return_value = {
            "detection_id": 1,
            "final_score": 76,
            "evidence_score": 70,
            "llm_score": 70,
            "rule_score": 80,
            "risk_level": "存疑信息",
            "judgement_result": "该新闻存在一定疑点，建议进一步核查",
            "reason": "证据部分支持。",
            "risk_points": ["来源需要核查"],
            "keywords": ["官方通报"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "继续关注权威信息。",
            "agent_steps": [
                "关键词提取完成",
                "知识库证据检索完成",
                "大模型可信度分析完成",
                "风险规则评分完成",
                "检测结果生成完成",
            ],
            "disclaimer": "检测结果仅供参考。",
        }

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "检测完成")
        self.assertEqual(body["data"]["detection_id"], 1)

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_endpoint_returns_error_when_llm_fails(self, mocked_detect) -> None:
        mocked_detect.side_effect = LLMAnalysisFailedError("DeepSeek API Key 未配置")

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("DeepSeek 分析失败", response.json()["message"])


class DetectOptionalAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _success_payload(self) -> dict:
        return {
            "detection_id": 1,
            "final_score": 76,
            "evidence_score": 70,
            "llm_score": 70,
            "rule_score": 80,
            "risk_level": "存疑信息",
            "judgement_result": "该新闻存在一定疑点，建议进一步核查",
            "reason": "证据部分支持。",
            "risk_points": ["来源需要核查"],
            "keywords": ["官方通报"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "继续关注权威信息。",
            "agent_steps": [
                "关键词提取完成",
                "知识库证据检索完成",
                "大模型可信度分析完成",
                "风险规则评分完成",
                "检测结果生成完成",
            ],
            "disclaimer": "检测结果仅供参考。",
        }

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_without_token_allows_guest(self, mocked_detect) -> None:
        mocked_detect.return_value = self._success_payload()

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(mocked_detect.call_args.kwargs["current_user"])

    @patch("app.core.deps.decode_token")
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_with_invalid_token_returns_401(
        self,
        mocked_detect,
        mocked_decode,
    ) -> None:
        mocked_decode.side_effect = ValueError("Invalid token")

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
            headers={"Authorization": "Bearer invalid-token"},
        )

        self.assertEqual(response.status_code, 401)
        mocked_detect.assert_not_called()

    @patch("app.core.deps.get_user_by_id")
    @patch("app.core.deps.decode_token")
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_with_valid_token_uses_current_user(
        self,
        mocked_detect,
        mocked_decode,
        mocked_get_user,
    ) -> None:
        mocked_decode.return_value = {"sub": "7"}
        mocked_get_user.return_value = SimpleNamespace(
            id=7,
            username="tester",
            role="user",
            status="active",
        )
        mocked_detect.return_value = self._success_payload()

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_detect.call_args.kwargs["current_user"].id, 7)

    @patch("app.core.deps.get_user_by_id")
    @patch("app.core.deps.decode_token")
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_with_disabled_user_returns_401(
        self,
        mocked_detect,
        mocked_decode,
        mocked_get_user,
    ) -> None:
        mocked_decode.return_value = {"sub": "7"}
        mocked_get_user.return_value = SimpleNamespace(
            id=7,
            username="tester",
            role="user",
            status="disabled",
        )

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "News content"},
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, 401)
        mocked_detect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
