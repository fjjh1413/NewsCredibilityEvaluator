import unittest
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1 import detect as detect_api
from app.api.v1.detect import get_db, get_optional_current_user
from app.main import app
from app.schemas.detection import DetectNewsRequest
from app.services.detection_service import detect_news_credibility
from app.services.web.web_content_fetcher import (
    AntiBotBlockedError,
    DynamicRenderRequiredError,
    LoginRequiredError,
    SSRFBlockedError,
    WebContentFetchError,
)


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
        "raw_cosine_score": score,
        "index_version": "v1",
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
                "evidence_quality": {
                    "coverage": 80,
                    "consistency": 70,
                    "score": 76.0,
                    "assessment": "证据覆盖较充分。",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [
                        {
                            "candidate_id": "kb:1",
                            "relevance_score": 80,
                            "quality_score": 80,
                            "stance": "support",
                            "claim_ids": ["c1", "c2"],
                            "reason": "直接相关。",
                        },
                        {
                            "candidate_id": "kb:2",
                            "relevance_score": 60,
                            "quality_score": 70,
                            "stance": "neutral",
                            "reason": "提供相关背景。",
                        },
                    ],
                    "rejected_evidence": [],
                },
                "similar_news": [],
                "risk_points": ["来源需要核查"],
                "keywords": ["官方通报"],
                "suggestion": "继续关注权威信息。",
            }
            mocked_rule.return_value = {
                "rule_score": 80,
                "hit_rules": [{"rule_name": "缺少明确来源"}],
            }
            mocked_save.return_value = SimpleNamespace(
                id=123,
                created_at=datetime(2026, 6, 18, 20, 15, 0),
            )
            mocked_prompt.return_value = "Configured prompt {title} {content} {evidence_list}"

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="News title",
                    content=VALID_NEWS_CONTENT,
                    source_name="Example News",
                    source_url="https://example.com/news/1",
                    publish_time="2026-06-18T09:30:00+08:00",
                ),
                current_user=SimpleNamespace(id=7, role="user"),
            )

        self.assertEqual(result["detection_id"], 123)
        self.assertEqual(result["created_at"], datetime(2026, 6, 18, 20, 15, 0))
        self.assertEqual(result["publish_time"], "2026-06-18T09:30:00+08:00")
        self.assertEqual(result["source_url"], "https://example.com/news/1")
        self.assertEqual(result["evidence_score"], 70)
        self.assertEqual(result["llm_score"], 70)
        self.assertEqual(result["rule_score"], 80)
        self.assertEqual(result["final_score"], 73.8)
        self.assertEqual(result["assessment_status"], "completed")
        self.assertEqual(result["arbitration_status"], "ok")
        self.assertEqual(result["quality_status"], "ok")
        self.assertGreater(result["arbitration_quality"]["claim_coverage"], 0)
        self.assertFalse(result["web_search_triggered"])
        # 70 * 0.5 + 76 * 0.3 + 80 * 0.2 = 35 + 22.8 + 16 = 73.8
        self.assertEqual(result["risk_level"], "存疑信息")
        self.assertEqual(result["agent_trace"]["status"], "completed")
        graph_execution = result["agent_trace"]["graph_execution"]
        self.assertEqual(
            graph_execution["graph_name"],
            "evidence-investigation-agent",
        )
        self.assertIn("persist_result", graph_execution["visited_nodes"])
        self.assertNotIn("search_web_evidence", graph_execution["visited_nodes"])
        self.assertEqual(
            result["agent_trace"]["stages"][1]["tool"],
            "chroma_hybrid_search",
        )
        self.assertEqual(len(result["evidence_list"]), 2)
        self.assertEqual(len(result["similar_news"]), 0)
        self.assertEqual(mocked_search.call_args.kwargs["top_k"], 10)
        self.assertEqual(
            mocked_llm.call_args.kwargs["prompt_template"],
            "Configured prompt {title} {content} {evidence_list}",
        )
        saved_payload = mocked_save.call_args.args[1]
        self.assertEqual(saved_payload.user_id, 7)
        self.assertEqual(saved_payload.assessment_status, "completed")
        self.assertEqual(saved_payload.final_score, result["final_score"])
        self.assertEqual(
            saved_payload.analysis_payload["publish_time"],
            "2026-06-18T09:30:00+08:00",
        )
        self.assertEqual(len(saved_payload.evidence_matches), 2)
        self.assertEqual(
            saved_payload.analysis_payload["agent_trace"]["version"],
            "1.0",
        )

    def test_detect_news_continues_when_rag_returns_no_evidence(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = []
            mocked_llm.return_value = {
                "llm_score": 60,
                "risk_level": "存疑信息",
                "reason": "证据较少。",
                "evidence_quality": {
                    "coverage": 50,
                    "consistency": 50,
                    "score": 50.0,
                    "assessment": "证据覆盖不足。",
                },
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
        self.assertEqual(result["assessment_status"], "insufficient_evidence")
        self.assertIsNone(result["final_score"])
        self.assertEqual(result["risk_level"], "无法判断")
        self.assertIn("无法判断", result["reason"])
        self.assertEqual(result["reason"], result["assessment_reason"])
        saved_payload = mocked_save.call_args.args[1]
        self.assertIsNone(saved_payload.user_id)
        self.assertEqual(saved_payload.evidence_matches, [])
        self.assertIsNone(saved_payload.final_score)
        self.assertEqual(saved_payload.assessment_status, "insufficient_evidence")
        self.assertFalse(saved_payload.is_high_risk)

    def test_global_web_search_disabled_skips_bocha(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
            patch("app.services.detection_service.get_settings") as mocked_get_settings,
            patch("app.services.detection_service.should_trigger_web_search") as mocked_should_trigger,
            patch("app.services.detection_service.BochaClient") as mocked_bocha_client,
            patch("app.services.detection_service.search_evidence") as mocked_search_evidence,
        ):
            mocked_get_settings.return_value = SimpleNamespace(
                web_search_enabled=False,
                bocha_api_key="test-key",
                web_search_timeout_seconds=8,
                web_search_count=5,
                web_search_freshness="oneMonth",
            )
            mocked_should_trigger.return_value = True
            mocked_search.return_value = []
            mocked_llm.return_value = {
                "llm_score": 60,
                "risk_level": "存疑信息",
                "reason": "证据较少。",
                "evidence_quality": {
                    "coverage": 50,
                    "consistency": 50,
                    "score": 50.0,
                    "assessment": "证据覆盖不足。",
                },
                "risk_points": [],
                "keywords": [],
                "suggestion": "人工复核。",
            }
            mocked_rule.return_value = {"rule_score": 90, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=125)
            mocked_prompt.return_value = "Configured prompt {title} {content} {evidence_list}"

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT),
                current_user=None,
            )

        self.assertEqual(result["detection_id"], 125)
        self.assertFalse(result["web_search_triggered"])
        mocked_should_trigger.assert_not_called()
        mocked_bocha_client.assert_not_called()
        mocked_search_evidence.assert_not_called()

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
            self.assertEqual(result["evidence_score"], 0)
            self.assertEqual(result["llm_score"], 0)
            self.assertEqual(result["rule_score"], 70)
            self.assertIsNone(result["final_score"])
            self.assertEqual(result["assessment_status"], "degraded")
            self.assertEqual(result["arbitration_status"], "provider_error")
            self.assertEqual(result["risk_level"], "无法判断")
            self.assertIn("无法判断", result["reason"])
            self.assertIn("不要将本次诊断分数作为真假结论", result["suggestion"])
            self.assertIn("缺少明确来源", result["risk_points"])
            saved_payload = mocked_save.call_args.args[1]
            self.assertEqual(saved_payload.llm_score, 0)
            self.assertIsNone(saved_payload.final_score)
            self.assertEqual(saved_payload.assessment_status, "degraded")
            self.assertFalse(saved_payload.is_high_risk)
            self.assertIn("无法判断", saved_payload.reason)
            self.assertEqual(len(saved_payload.evidence_matches), 0)

    def test_invalid_default_and_fallback_prompt_uses_degraded_detection(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
            patch("app.services.llm_service.get_default_prompt_template") as mocked_fallback,
            patch("app.services.llm_service._load_deepseek_config") as mocked_config,
            patch("app.services.llm_service._post_chat_completion") as mocked_transport,
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
                    payload=DetectNewsRequest(title="News title", content=VALID_NEWS_CONTENT,
                                              enable_web_search=False),
                    current_user=None,
                )

            self.assertEqual(result["detection_id"], 126)
            self.assertEqual(result["llm_score"], 0)
            self.assertEqual(result["rule_score"], 90)
            self.assertIsNone(result["final_score"])
            self.assertEqual(result["assessment_status"], "degraded")
            self.assertEqual(result["risk_level"], "无法判断")
            self.assertIn("无法判断", result["reason"])
            mocked_transport.assert_not_called()
            mocked_save.assert_called_once()
            saved_payload = mocked_save.call_args.args[1]
            self.assertIsNone(saved_payload.final_score)
            self.assertEqual(saved_payload.assessment_status, "degraded")
            self.assertFalse(saved_payload.is_high_risk)


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
            "agent_trace": {
                "version": "1.0",
                "agent_name": "evidence-investigation-agent",
                "status": "completed",
                "total_latency_ms": 42.0,
                "stages": [],
            },
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
        self.assertEqual(body["data"]["agent_trace"]["version"], "1.0")

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
    def test_detect_news_rate_limit_ignores_untrusted_forwarded_headers(
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
        spoofed_second_ip_response = self.client.post(
            "/api/detect/news",
            json=self._valid_request(),
            headers={"X-Forwarded-For": "203.0.113.11"},
        )
        repeated_spoofed_first_ip_response = self.client.post(
            "/api/detect/news",
            json=self._valid_request(),
            headers={"X-Forwarded-For": "203.0.113.10"},
        )

        self.assertEqual(first_ip_response.status_code, 200)
        self.assertEqual(spoofed_second_ip_response.status_code, 429)
        self.assertEqual(repeated_spoofed_first_ip_response.status_code, 429)
        self.assertEqual(mocked_detect.call_count, 1)


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


class DetectEvidenceArbitrationTestCase(unittest.TestCase):
    """Regression: LLM arbitration filters irrelevant RAG evidence."""

    def test_llm_receives_complete_ten_item_candidate_pool(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = [
                _vector_result(index, 0.8 - index * 0.01)
                for index in range(1, 11)
            ]
            mocked_llm.return_value = {
                "llm_score": 70,
                "risk_level": "存疑信息",
                "reason": "证据部分支持。",
                "evidence_quality": {
                    "coverage": 70,
                    "consistency": 70,
                    "score": 70,
                    "assessment": "证据部分覆盖。",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [
                        {
                            "candidate_id": "kb:1",
                            "relevance_score": 80,
                            "quality_score": 80,
                            "stance": "support",
                            "reason": "直接相关。",
                        }
                    ],
                    "rejected_evidence": [
                        {
                            "candidate_id": f"kb:{index}",
                            "reason": "不参与本次评分。",
                        }
                        for index in range(2, 11)
                    ],
                },
                "similar_news": [],
                "risk_points": [],
                "keywords": [],
                "suggestion": "继续核查。",
            }
            mocked_rule.return_value = {"rule_score": 80, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=202)

            detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="Ten candidate evidence test",
                    content="This content is long enough to satisfy request validation.",
                ),
                current_user=None,
            )

        self.assertEqual(
            len(mocked_llm.call_args.kwargs["evidence_list"]),
            10,
        )

    def test_no_candidates_has_explicit_no_evidence_quality_state(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge", return_value=[]),
            patch(
                "app.services.detection_service.analyze_news_credibility",
                return_value={
                    "llm_score": 70,
                    "risk_level": "存疑信息",
                    "reason": "没有检索到外部证据。",
                    "risk_points": [],
                    "keywords": [],
                    "suggestion": "继续核查。",
                },
            ),
            patch("app.services.detection_service.analyze_evidence_arbitration") as mocked_arbitration,
            patch(
                "app.services.detection_service.calculate_rule_score",
                return_value={"rule_score": 80, "hit_rules": []},
            ),
            patch(
                "app.services.detection_service.save_detection_record",
                return_value=SimpleNamespace(id=206),
            ),
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="No candidate evidence test",
                    content="This content is long enough to satisfy request validation.",
                ),
                current_user=None,
            )

        self.assertEqual(result["arbitration_status"], "no_evidence")
        self.assertEqual(result["quality_status"], "no_evidence")
        self.assertIsNone(result["evidence_quality"])
        self.assertEqual(result["arbitration_attempts"], 0)
        mocked_arbitration.assert_not_called()

    def test_empty_effective_evidence_abstains_despite_high_diagnostic_scores(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = [_vector_result(1, 0.4)]
            mocked_llm.return_value = {
                "llm_score": 80,
                "risk_level": "可信新闻",
                "reason": "候选证据与新闻无关。",
                "evidence_quality": {
                    "coverage": 0,
                    "consistency": 0,
                    "score": 0,
                    "assessment": "没有有效证据。",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [],
                    "rejected_evidence": [
                        {"candidate_id": "kb:1", "reason": "与核心事实无关。"}
                    ],
                },
                "similar_news": [],
                "risk_points": [],
                "keywords": [],
                "suggestion": "继续核查。",
            }
            mocked_rule.return_value = {"rule_score": 90, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=203)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="No effective evidence test",
                    content="This content is long enough to satisfy request validation.",
                ),
                current_user=None,
            )

        self.assertEqual(result["evidence_list"], [])
        self.assertEqual(result["assessment_status"], "insufficient_evidence")
        self.assertEqual(result["arbitration_status"], "ok")
        self.assertEqual(result["quality_status"], "ok")
        self.assertEqual(result["llm_score"], 80)
        self.assertEqual(result["rule_score"], 90)
        self.assertIsNone(result["final_score"])
        self.assertEqual(result["risk_level"], "无法判断")
        self.assertEqual(len(result["excluded_evidence"]), 1)
        saved_payload = mocked_save.call_args.args[1]
        self.assertIsNone(saved_payload.final_score)
        self.assertEqual(saved_payload.assessment_status, "insufficient_evidence")
        self.assertEqual(saved_payload.evidence_matches, [])
        self.assertFalse(saved_payload.is_high_risk)

    def test_missing_arbitration_retries_and_uses_retry_result(self) -> None:
        missing_arbitration = {
            "llm_score": 40,
            "risk_level": "存疑信息",
            "reason": "首次返回缺少仲裁。",
            "evidence_quality": {
                "coverage": 0,
                "consistency": 0,
                "score": 0,
                "assessment": "首次结果无效。",
            },
            "risk_points": [],
            "keywords": [],
            "suggestion": "重试。",
        }
        valid_retry = {
            "llm_score": 82,
            "risk_level": "可信新闻",
            "reason": "重试后完成仲裁。",
            "evidence_quality": {
                "coverage": 80,
                "consistency": 80,
                "score": 80,
                "assessment": "证据有效。",
            },
            "evidence_arbitration": {
                "ranked_evidence": [
                    {
                        "candidate_id": "kb:1",
                        "relevance_score": 90,
                        "quality_score": 90,
                        "stance": "support",
                        "reason": "直接支持。",
                    }
                ],
                "rejected_evidence": [],
            },
            "similar_news": [
                {
                    "candidate_id": "kb:1",
                    "risk_level": "可信新闻",
                    "relevance_reason": "同一事件。",
                }
            ],
            "risk_points": [],
            "keywords": [],
            "suggestion": "继续关注。",
        }

        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility", return_value=missing_arbitration) as mocked_llm,
            patch("app.services.detection_service.analyze_evidence_arbitration", return_value=valid_retry) as mocked_arbitration,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = [_vector_result(1, 0.8)]
            mocked_rule.return_value = {"rule_score": 80, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=204)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="Arbitration retry test",
                    content="This content is long enough to satisfy request validation.",
                ),
                current_user=None,
            )

        self.assertEqual(mocked_llm.call_count, 1)
        self.assertEqual(mocked_arbitration.call_count, 1)
        self.assertEqual(result["arbitration_status"], "ok")
        self.assertEqual(result["quality_status"], "ok")
        self.assertEqual(result["arbitration_attempts"], 2)
        self.assertEqual(result["llm_score"], 40)
        self.assertEqual(result["reason"], "首次返回缺少仲裁。")
        self.assertEqual(result["evidence_quality"]["score"], 80)
        graph_execution = result["agent_trace"]["graph_execution"]
        self.assertIn(
            "retry_arbitration",
            graph_execution["visited_nodes"],
        )
        retry_transition = next(
            transition
            for transition in graph_execution["transitions"]
            if transition["source"] == "arbitrate_evidence"
        )
        self.assertEqual(retry_transition["route"], "retry")
        self.assertEqual(retry_transition["target"], "retry_arbitration")

    def test_similar_news_uses_llm_risk_judgement(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = [
                _vector_result(1, 0.8),
                _vector_result(2, 0.7),
            ]
            mocked_llm.return_value = {
                "llm_score": 70,
                "risk_level": "存疑信息",
                "reason": "完成分析。",
                "evidence_quality": {
                    "coverage": 70,
                    "consistency": 70,
                    "score": 70,
                    "assessment": "证据有效。",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [
                        {
                            "candidate_id": "kb:1",
                            "relevance_score": 90,
                            "quality_score": 90,
                            "stance": "support",
                            "reason": "直接相关。",
                        },
                        {
                            "candidate_id": "kb:2",
                            "relevance_score": 80,
                            "quality_score": 80,
                            "stance": "neutral",
                            "reason": "相关背景。",
                        },
                    ],
                    "rejected_evidence": [],
                },
                "similar_news": [
                    {
                        "candidate_id": "kb:2",
                        "risk_level": "疑似谣言",
                        "relevance_reason": "同一主题但事实存在差异。",
                    }
                ],
                "risk_points": [],
                "keywords": [],
                "suggestion": "继续核查。",
            }
            mocked_rule.return_value = {"rule_score": 80, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=205)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="Similar news risk test",
                    content="This content is long enough to satisfy request validation.",
                ),
                current_user=None,
            )

        self.assertEqual(len(result["similar_news"]), 1)
        self.assertEqual(result["similar_news"][0]["candidate_id"], "kb:2")
        self.assertEqual(result["similar_news"][0]["risk_level"], "疑似谣言")
        self.assertEqual(
            result["similar_news"][0]["relevance_reason"],
            "同一主题但事实存在差异。",
        )

    def test_llm_excludes_irrelevant_kb_evidence(self) -> None:
        """RAG returns railway notice + debunk page; Web returns earthquake news.

        LLM arbitration should rank web evidence and exclude kb evidence,
        so effective_evidence only has web items and unrelated kb doesn't
        drag down scoring or appear in similar_news.
        """
        from app.schemas.web_search import WebEvidenceItem

        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
            patch("app.services.detection_service.should_trigger_web_search", return_value=True),
            patch("app.services.detection_service.BochaClient") as mocked_bocha,
            patch("app.services.detection_service.search_evidence") as mocked_web_search,
            patch("app.services.detection_service.get_settings") as mocked_get_settings,
        ):
            mocked_get_settings.return_value = SimpleNamespace(
                web_search_enabled=True,
                bocha_api_key="test-key",
                web_search_timeout_seconds=8,
                web_search_count=5,
                web_search_freshness="oneMonth",
            )
            # RAG returns unrelated evidence (railway schedule, debunk page)
            mocked_search.return_value = [
                {
                    "metadata": {
                        "knowledge_id": 5,
                        "title": "中国铁路发布假期增开列车安排",
                        "summary": "铁路部门公开公告的假期列车增开方案。",
                        "category": "society",
                        "truth_label": "credible",
                        "source_name": "铁路部门公开公告",
                        "risk_level": "可信新闻",
                    },
                    "similarity_score": 0.39,
                },
                {
                    "metadata": {
                        "knowledge_id": 34,
                        "title": "网络辟谣专题页",
                        "summary": "近期网络谣言集中辟谣专题。",
                        "category": "society",
                        "truth_label": "credible",
                        "source_name": "中央网信办",
                        "risk_level": "可信新闻",
                    },
                    "similarity_score": 0.35,
                },
            ]
            # Web returns related earthquake news
            mocked_web_search.return_value = [
                WebEvidenceItem(
                    title="青海海西州6.3级地震已致1人遇难8人受伤",
                    summary="据中国地震台网测定...",
                    site_name="腾讯新闻",
                    url="https://news.qq.com/a/20250101/001",
                    date_published="2025-01-01",
                    similarity_score=0.0,
                ),
                WebEvidenceItem(
                    title="青海海西州地震伤者已出院",
                    summary="记者从医院获悉...",
                    site_name="新华网",
                    url="https://xinhuanet.com/2025/01/02/quake",
                    date_published="2025-01-02",
                    similarity_score=0.0,
                ),
            ]

            # LLM returns arbitration: includes web:1 web:2, excludes kb:5, kb:34
            mocked_llm.return_value = {
                "llm_score": 75,
                "risk_level": "可信新闻",
                "reason": "有效证据与新闻核心事实一致。",
                "evidence_quality": {
                    "coverage": 85,
                    "consistency": 80,
                    "score": 83.0,
                    "assessment": "有效证据覆盖核心事实。",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [
                        {
                            "candidate_id": "web:1",
                            "relevance_score": 95,
                            "quality_score": 85,
                            "stance": "support",
                            "reason": "直接描述同一地震事件。",
                        },
                        {
                            "candidate_id": "web:2",
                            "relevance_score": 90,
                            "quality_score": 80,
                            "stance": "support",
                            "reason": "报道伤者出院后续。",
                        },
                    ],
                    "rejected_evidence": [
                        {
                            "candidate_id": "kb:5",
                            "reason": "铁路调度公告，与地震事件无关。",
                        },
                        {
                            "candidate_id": "kb:34",
                            "reason": "辟谣专题页，不能直接支持本新闻。",
                        },
                    ],
                },
                "risk_points": [],
                "keywords": ["青海海西州", "地震"],
                "suggestion": "核对官方通报。",
            }

            mocked_rule.return_value = {"rule_score": 85, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=200)
            mocked_prompt.return_value = "Configured prompt {title} {content} {evidence_list}"

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="青海海西州6.3级地震造成1死8伤 伤者已出院",
                    content="据新华社报道，青海海西州发生6.3级地震，目前已致1人遇难8人受伤，伤者已全部出院。",
                ),
                current_user=SimpleNamespace(id=1, role="user"),
            )

        # No unrelated evidence in evidence_list
        evidence_titles = [e.get("title") for e in result["evidence_list"]]
        self.assertNotIn("中国铁路发布假期增开列车安排", evidence_titles)
        self.assertNotIn("网络辟谣专题页", evidence_titles)

        # Effective evidence should only have earthquake web news
        self.assertEqual(len(result["evidence_list"]), 2)

        # Excluded evidence contains the irrelevant kb items
        excluded_titles = [e.get("title") for e in result.get("excluded_evidence", [])]
        self.assertIn("中国铁路发布假期增开列车安排", excluded_titles)

        # Similar news shouldn't have kb items
        similar_titles = [e["title"] for e in result["similar_news"]]
        self.assertNotIn("中国铁路发布假期增开列车安排", similar_titles)

        # Arbitration status
        self.assertEqual(result.get("arbitration_status"), "ok")
        graph_execution = result["agent_trace"]["graph_execution"]
        self.assertIn(
            "search_web_evidence",
            graph_execution["visited_nodes"],
        )
        web_transition = next(
            transition
            for transition in graph_execution["transitions"]
            if transition["source"] == "route_web_search"
        )
        self.assertEqual(web_transition["route"], "search")
        self.assertEqual(web_transition["target"], "search_web_evidence")

        # Score should be reasonable (not dragged to 0 by kb evidence)
        self.assertGreater(result["final_score"], 50)

        # evidence_matches should save effective evidence
        saved_payload = mocked_save.call_args.args[1]
        saved_titles = [em.title for em in saved_payload.evidence_matches]
        self.assertNotIn("中国铁路发布假期增开列车安排", saved_titles)

    def test_arbitration_unavailable_when_llm_returns_no_arbitration(self) -> None:
        """Unarbitrated candidates must not participate in scoring."""
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch(
                "app.services.detection_service.analyze_evidence_arbitration",
                return_value={
                    "evidence_arbitration": None,
                    "evidence_quality": None,
                    "similar_news": [],
                    "error": "模型返回缺少 evidence_arbitration",
                },
            ),
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.should_trigger_web_search", return_value=False),
        ):
            mocked_search.return_value = [
                {
                    "metadata": {
                        "knowledge_id": 1,
                        "title": "Evidence 1",
                        "summary": "summary",
                        "category": "society",
                        "truth_label": "credible",
                        "source_name": "source",
                        "risk_level": "可信新闻",
                    },
                    "similarity_score": 0.8,
                }
            ]
            mocked_llm.return_value = {
                "llm_score": 60,
                "risk_level": "存疑信息",
                "reason": "test",
                "evidence_quality": {
                    "coverage": 50,
                    "consistency": 50,
                    "score": 50.0,
                    "assessment": "test",
                },
                # No evidence_arbitration key
                "risk_points": [],
                "keywords": [],
                "suggestion": "test",
            }
            mocked_rule.return_value = {"rule_score": 90, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(id=201)

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="Test title",
                    content="Test content with enough length for validation.",
                ),
                current_user=None,
            )

        self.assertEqual(result.get("arbitration_status"), "retry_exhausted")
        self.assertEqual(result.get("quality_status"), "unavailable")
        self.assertEqual(result.get("arbitration_attempts"), 2)
        self.assertIn("evidence_arbitration", result.get("arbitration_error", ""))
        self.assertIsNone(result["evidence_quality"])
        self.assertEqual(len(result["evidence_list"]), 0)
        self.assertEqual(len(result.get("excluded_evidence", [])), 0)
        self.assertEqual(len(result.get("candidate_evidence_list", [])), 1)


class ExtractPreviewApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_detect_rate_limiter()
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_optional_current_user] = _optional_user_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_detect_rate_limiter()

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_extracted_article(self, mocked_fetcher_cls) -> None:
        mocked_fetcher_cls.return_value.fetch_article.return_value = {
            "title": "提取到的标题",
            "content": "提取到的正文内容，足够长度。",
            "source_name": "example.com",
            "source_url": "https://example.com/news/1",
            "publish_time": "2026-06-18T09:30:00+08:00",
            "publish_time_precision": "datetime",
        }

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/news/1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "提取成功")
        self.assertEqual(body["data"]["title"], "提取到的标题")
        self.assertEqual(body["data"]["content"], "提取到的正文内容，足够长度。")
        self.assertEqual(body["data"]["source_name"], "example.com")
        self.assertEqual(body["data"]["source_url"], "https://example.com/news/1")
        self.assertEqual(body["data"]["publish_time"], "2026-06-18T09:30:00+08:00")
        self.assertEqual(body["data"]["publish_time_precision"], "datetime")
        # the URL is passed through to the fetcher
        mocked_fetcher_cls.return_value.fetch_article.assert_called_once_with(
            "https://example.com/news/1"
        )

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_date_precision(self, mocked_fetcher_cls) -> None:
        mocked_fetcher_cls.return_value.fetch_article.return_value = {
            "title": "只有日期的新闻",
            "content": "这是用于验证仅发布日期响应的新闻正文内容。",
            "source_name": "example.com",
            "source_url": "https://example.com/news/date-only",
            "publish_time": "2026-06-19",
            "publish_time_precision": "date",
        }

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/news/date-only"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["publish_time"], "2026-06-19")
        self.assertEqual(response.json()["data"]["publish_time_precision"], "date")

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_null_precision_when_time_missing(
        self, mocked_fetcher_cls
    ) -> None:
        mocked_fetcher_cls.return_value.fetch_article.return_value = {
            "title": "没有发布时间的新闻",
            "content": "这是用于验证发布时间缺失响应的新闻正文内容。",
            "source_name": "example.com",
            "source_url": "https://example.com/news/no-time",
            "publish_time": None,
            "publish_time_precision": None,
        }

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/news/no-time"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["publish_time"])
        self.assertIsNone(response.json()["data"]["publish_time_precision"])

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_422_on_ssrf(self, mocked_fetcher_cls) -> None:
        mocked_fetcher_cls.return_value.fetch_article.side_effect = SSRFBlockedError(
            "SSRF 阻止：目标地址为私有/保留 IP"
        )

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "http://127.0.0.1/admin"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("SSRF", response.json()["message"])

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_422_on_fetch_error(self, mocked_fetcher_cls) -> None:
        mocked_fetcher_cls.return_value.fetch_article.side_effect = WebContentFetchError("超时 fetching")

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/x"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("超时", response.json()["message"])

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_login_required_status(
        self, mocked_fetcher_cls
    ) -> None:
        mocked_fetcher_cls.return_value.fetch_article.side_effect = LoginRequiredError(
            "该链接需要登录后才能读取正文",
            login_url="https://example.com/login",
            page_type="login_wall",
            confidence=0.92,
            signals=("password_form", "login_text_marker"),
            recommended_method="authenticated_retry",
        )

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/member-only"},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["data"]["status"], "login_required")
        self.assertEqual(body["data"]["login_url"], "https://example.com/login")
        self.assertEqual(body["data"]["recovery_action"], "open_login_then_retry")
        self.assertEqual(body["data"]["page_type"], "login_wall")
        self.assertEqual(body["data"]["recognition_confidence"], 0.92)
        self.assertIn("password_form", body["data"]["recognition_signals"])
        self.assertEqual(
            body["data"]["recommended_extraction_method"], "authenticated_retry"
        )

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_dynamic_render_required_status(
        self, mocked_fetcher_cls
    ) -> None:
        mocked_fetcher_cls.return_value.fetch_article.side_effect = DynamicRenderRequiredError(
            "该新闻页正文由客户端动态生成，当前无法直接读取正文",
            page_type="client_rendered_shell",
            confidence=0.84,
            signals=("client_render_marker",),
            recommended_method="browser_render",
        )

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/render-only"},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["data"]["status"], "dynamic_render_required")
        self.assertEqual(body["data"]["recovery_action"], "manual_input")
        self.assertEqual(body["data"]["page_type"], "client_rendered_shell")
        self.assertEqual(body["data"]["recommended_extraction_method"], "browser_render")

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_antibot_status(
        self, mocked_fetcher_cls
    ) -> None:
        mocked_fetcher_cls.return_value.fetch_article.side_effect = AntiBotBlockedError(
            "该站点启用了访问校验或反爬限制",
            page_type="anti_bot_wall",
            confidence=0.9,
            signals=("anti_bot_marker",),
            recommended_method="manual_input",
        )

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/protected"},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["data"]["status"], "blocked_by_anti_bot")
        self.assertEqual(body["data"]["recovery_action"], "manual_input")
        self.assertEqual(body["data"]["page_type"], "anti_bot_wall")
        self.assertIn("anti_bot_marker", body["data"]["recognition_signals"])

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_returns_422_when_title_or_content_empty(
        self, mocked_fetcher_cls
    ) -> None:
        mocked_fetcher_cls.return_value.fetch_article.return_value = {
            "title": "",
            "content": "",
            "source_name": "example.com",
            "source_url": "https://example.com/x",
        }

        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "https://example.com/x"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("未能从该链接提取", response.json()["message"])

    def test_extract_preview_rejects_non_http_url(self) -> None:
        response = self.client.post(
            "/api/detect/extract-preview",
            json={"url": "ftp://example.com/file"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("http://", response.json()["message"])

    @patch("app.api.v1.detect.WebContentFetcher")
    def test_extract_preview_shares_detect_rate_limit(self, mocked_fetcher_cls) -> None:
        with patch.object(detect_api, "get_settings", create=True) as mocked_get_settings:
            mocked_get_settings.return_value = SimpleNamespace(
                detect_rate_limit_count=2,
                detect_rate_limit_window_seconds=60,
                article_fetch_allow_private_hosts=False,
            )
            mocked_fetcher_cls.return_value.fetch_article.return_value = {
                "title": "标题",
                "content": "正文",
                "source_name": "example.com",
                "source_url": "https://example.com/x",
            }

            responses = [
                self.client.post(
                    "/api/detect/extract-preview",
                    json={"url": "https://example.com/x"},
                )
                for _ in range(3)
            ]

        self.assertEqual([r.status_code for r in responses[:2]], [200, 200])
        self.assertEqual(responses[2].status_code, 429)


if __name__ == "__main__":
    unittest.main()
