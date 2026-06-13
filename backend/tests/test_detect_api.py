import unittest
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1 import detect as detect_api
from app.api.v1.detect import get_db, get_optional_current_user
from app.main import app
from app.schemas.detection import DetectNewsRequest
from app.services.detection_service import detect_news_credibility


VALID_NEWS_CONTENT = "News content with enough detail for validation."


def _db_override():
    return Mock()


def _optional_user_override():
    return SimpleNamespace(id=1, role="user", status="active")


def _clear_detect_rate_limiter() -> None:
    rate_limiter = getattr(detect_api, "detector_rate_limiter", None)
    if rate_limiter is not None:
        rate_limiter.clear()


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
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
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
            mocked_prompt.return_value = "Configured prompt {title} {content} {evidence_list}"

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT),
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
        self.assertEqual(
            mocked_llm.call_args.kwargs["prompt_template"],
            "Configured prompt {title} {content} {evidence_list}",
        )
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
                payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT),
                current_user=None,
            )

        self.assertEqual(result["detection_id"], 124)
        self.assertEqual(result["evidence_score"], 0)
        self.assertIn("证据不足", result["reason"])
        saved_payload = mocked_save.call_args.args[1]
        self.assertIsNone(saved_payload.user_id)
        self.assertEqual(saved_payload.evidence_matches, [])

    def test_detect_news_degrades_and_saves_when_deepseek_fails(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
        ):
            mocked_search.return_value = [_vector_result(1, 0.8)]
            mocked_llm.return_value = {
                "llm_score": 0,
                "risk_level": "存疑信息",
                "reason": "模型调用失败：DeepSeek API Key 未配置",
                "risk_points": ["模型调用失败：DeepSeek API Key 未配置"],
                "keywords": [],
                "suggestion": "配置 API Key。",
                "error": "模型调用失败",
            }
            mocked_rule.return_value = {
                "rule_score": 70,
                "hit_rules": [{"rule_name": "缺少明确来源"}],
            }
            mocked_save.return_value = SimpleNamespace(id=125)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT),
                current_user=None,
            )

            self.assertEqual(result["detection_id"], 125)
            self.assertEqual(result["evidence_score"], 80)
            self.assertEqual(result["llm_score"], 0)
            self.assertEqual(result["rule_score"], 70)
            self.assertEqual(result["final_score"], 76.67)
            self.assertIn("LLM 分析暂不可用，本次结果基于 RAG 和规则评分降级生成", result["reason"])
            self.assertIn("模型调用失败", result["reason"])
            self.assertIn("LLM 分析暂不可用", result["suggestion"])
            self.assertIn("缺少明确来源", result["risk_points"])
            saved_payload = mocked_save.call_args.args[1]
            self.assertEqual(saved_payload.llm_score, 0)
            self.assertEqual(saved_payload.final_score, 76.67)
            self.assertIn("LLM 分析暂不可用", saved_payload.reason)
            self.assertEqual(len(saved_payload.evidence_matches), 1)

    def test_invalid_default_and_fallback_prompt_uses_degraded_detection(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
            patch("app.services.llm_service.get_default_prompt_template") as mocked_fallback,
            patch("app.services.llm_service._load_deepseek_config") as mocked_config,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
        ):
            mocked_search.return_value = []
            mocked_prompt.return_value = "Invalid configured prompt"
            mocked_fallback.return_value = "Invalid fallback prompt"
            mocked_config.return_value = {
                "api_key": "test-key",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "timeout_seconds": 1,
            }
            mocked_rule.return_value = {"rule_score": 90, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=126)

            with self.assertLogs("app.services.llm_service", level="WARNING"):
                result = detect_news_credibility(
                    db=Mock(),
                    payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT),
                    current_user=None,
                )

            self.assertEqual(result["detection_id"], 126)
            self.assertEqual(result["llm_score"], 0)
            self.assertEqual(result["final_score"], 30)
            self.assertIn("LLM 分析暂不可用", result["reason"])
            mocked_save.assert_called_once()


class DetectApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_detect_rate_limiter()
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_optional_current_user] = _optional_user_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_detect_rate_limiter()

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
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "检测完成")
        self.assertEqual(body["data"]["detection_id"], 1)

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_endpoint_returns_degraded_result_when_llm_unavailable(self, mocked_detect) -> None:
        mocked_detect.return_value = {
            "detection_id": 2,
            "final_score": 76.67,
            "evidence_score": 80,
            "llm_score": 0,
            "rule_score": 70,
            "risk_level": "存疑信息",
            "judgement_result": "该新闻存在一定疑点，建议进一步核查",
            "reason": "LLM 分析暂不可用，本次结果基于 RAG 和规则评分降级生成。模型调用失败：DeepSeek API Key 未配置",
            "risk_points": ["模型调用失败：DeepSeek API Key 未配置", "缺少明确来源"],
            "keywords": ["官方通报"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "LLM 分析暂不可用，本次结果基于 RAG 和规则评分降级生成。建议结合权威来源进行人工复核。",
            "agent_steps": [
                "关键词提取完成",
                "知识库证据检索完成",
                "LLM 分析暂不可用，已启用降级检测",
                "风险规则评分完成",
                "检测结果生成完成",
            ],
            "disclaimer": "检测结果仅供参考。",
        }

        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["detection_id"], 2)
        self.assertEqual(body["data"]["llm_score"], 0)
        self.assertIn("LLM 分析暂不可用", body["data"]["reason"])


class DetectRateLimitApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_detect_rate_limiter()
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_optional_current_user] = _optional_user_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_detect_rate_limiter()

    def _valid_request(self) -> dict:
        return {"title": "News title", "content": VALID_NEWS_CONTENT}

    def _success_payload(self) -> dict:
        return {
            "detection_id": 1,
            "final_score": 76,
            "evidence_score": 70,
            "llm_score": 70,
            "rule_score": 80,
            "risk_level": "suspected",
            "judgement_result": "Review recommended.",
            "reason": "Evidence partially supports the claim.",
            "risk_points": ["source needs review"],
            "keywords": ["official notice"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "Keep monitoring authoritative sources.",
            "agent_steps": [],
            "disclaimer": "For reference only.",
        }

    @patch.object(detect_api, "get_settings", create=True)
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_rate_limits_fourth_request_for_same_ip(
        self,
        mocked_detect,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            detect_rate_limit_count=3,
            detect_rate_limit_window_seconds=60,
        )
        mocked_detect.return_value = self._success_payload()

        responses = [
            self.client.post("/api/detect/news", json=self._valid_request())
            for _ in range(4)
        ]

        self.assertEqual([response.status_code for response in responses[:3]], [200, 200, 200])
        self.assertEqual(responses[3].status_code, 429)
        self.assertEqual(responses[3].json()["message"], "检测请求过于频繁，请稍后再试")
        self.assertEqual(mocked_detect.call_count, 3)

    @patch.object(detect_api, "get_settings", create=True)
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_rate_limit_recovers_after_window(
        self,
        mocked_detect,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            detect_rate_limit_count=1,
            detect_rate_limit_window_seconds=1,
        )
        mocked_detect.return_value = self._success_payload()

        first_response = self.client.post("/api/detect/news", json=self._valid_request())
        limited_response = self.client.post("/api/detect/news", json=self._valid_request())
        time.sleep(1.1)
        recovered_response = self.client.post("/api/detect/news", json=self._valid_request())

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(recovered_response.status_code, 200)

    @patch.object(detect_api, "get_settings", create=True)
    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_rate_limit_counts_each_ip_separately(
        self,
        mocked_detect,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            detect_rate_limit_count=1,
            detect_rate_limit_window_seconds=60,
        )
        mocked_detect.return_value = self._success_payload()

        first_ip_response = self.client.post(
            "/api/detect/news",
            json=self._valid_request(),
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        second_ip_response = self.client.post(
            "/api/detect/news",
            json=self._valid_request(),
            headers={"X-Forwarded-For": "203.0.113.11"},
        )
        repeated_first_ip_response = self.client.post(
            "/api/detect/news",
            json=self._valid_request(),
            headers={"X-Forwarded-For": "203.0.113.10"},
        )

        self.assertEqual(first_ip_response.status_code, 200)
        self.assertEqual(second_ip_response.status_code, 200)
        self.assertEqual(repeated_first_ip_response.status_code, 429)


class DetectOptionalAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_detect_rate_limiter()
        app.dependency_overrides[get_db] = _db_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_detect_rate_limiter()

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
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
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
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
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
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
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
            json={"title": "News title", "content": VALID_NEWS_CONTENT},
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, 401)
        mocked_detect.assert_not_called()

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_rejects_short_title(self, mocked_detect) -> None:
        response = self.client.post(
            "/api/detect/news",
            json={"title": "abc", "content": VALID_NEWS_CONTENT},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("新闻标题长度不能少于 4 个字符", response.json()["message"])
        mocked_detect.assert_not_called()

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_detect_news_rejects_short_content(self, mocked_detect) -> None:
        response = self.client.post(
            "/api/detect/news",
            json={"title": "News title", "content": "too short"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("新闻正文长度不能少于 20 个字符", response.json()["message"])
        mocked_detect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
