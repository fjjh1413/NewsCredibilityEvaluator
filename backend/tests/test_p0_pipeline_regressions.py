"""Offline integration: real graph/parser/validation/SQLite/report orchestration.

Only retrieval/provider transport are replaced at external seams. Report failure
tests inject the PDF renderer; the abstention scenario uses the real converter.
These fixtures verify behavior, not model accuracy. Set P0_ARTIFACT_DIR to save
the exact request, response, and sanitized prompts for each regression scenario.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.report import Report
from app.models.user import User
from app.schemas.detection import DetectNewsRequest, DetectNewsResult, DetectionDetailOut
from app.schemas.web_search import WebEvidenceItem
from app.services.detection_detail_service import restore_detection_detail_payload
from app.services.detection_service import detect_news_credibility, validate_and_apply_llm_ranking
from app.services.llm_service import DeepSeekServiceError
from app.services.report_service import (
    ReportGenerationError, ReportFileMissingError, generate_detection_report,
    get_report_pdf_for_download,
)


def completion(candidate_ids):
    body = {
        "llm_score": 90, "risk_level": "可信新闻", "reason": "受给定证据支持。",
        "evidence_quality": {"coverage": 90, "consistency": 90, "assessment": "已核对候选。"},
        "evidence_arbitration": {
            "ranked_evidence": [{"candidate_id": cid, "relevance_score": 90,
                "quality_score": 90, "stance": "support", "reason": "覆盖核心主张。"}
                for cid in candidate_ids],
            "rejected_evidence": [],
        },
        "similar_news": [], "risk_points": [], "keywords": ["公告"], "suggestion": "核对原文。",
    }
    return {"choices": [{"message": {"content": json.dumps(body, ensure_ascii=False)}}]}


def local_result(score=0.85, v2=False):
    result = {"metadata": {"knowledge_id": 1, "title": "公开公告",
        "summary": "公告说明测试城市在周一开放图书馆。", "source_name": "公开来源",
        "source_url": "https://example.org/library", "parent_revision": "fixture-revision"},
        "document": "测试城市图书馆在周一开放。", "similarity_score": score,
        "raw_cosine_score": score, "index_version": "v2" if v2 else "v1"}
    if v2:
        result.update(fusion_score=0.99, score_components={"dense_score": score, "final_score": 0.99},
            chunks=[{"chunk_id": "knowledge:1:content:0", "document": "测试城市图书馆在周一开放。",
                     "similarity_score": score, "supporting_spans": [{"text": "图书馆在周一开放", "start": 4, "end": 12}]}],
            supporting_spans=[{"text": "图书馆在周一开放", "start": 4, "end": 12}])
    return result


class P0PipelineRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"REPORT_DIR": self.temp.name,
            "DEEPSEEK_API_KEY": "offline-fixture-only", "BOCHA_API_KEY": "offline-fixture-only",
            "REDIS_ENABLED": "false", "AI_CACHE_ENABLED": "false", "WEB_SEARCH_ENABLED": "true",
            "RAG_SUPPORTING_SPANS_ENABLED": "false", "RAG_CLAIM_AWARE_ENABLED": "false"})
        self.env.start()
        get_settings.cache_clear()
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(id=1, username="p0-user", password_hash="fixture", role="user", status="active")
        self.db.add(self.user)
        self.db.commit()
        self.inputs = DetectNewsRequest(title="城市图书馆开放公告", content="公开公告说明测试城市的图书馆将在周一开放，请核对公告中的时间与地点。", source_name="公开来源")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.env.stop()
        get_settings.cache_clear()
        self.temp.cleanup()

    def run_scenario(self, name, local, responses, web=()):
        with (
            patch("app.services.detection_service.search_similar_knowledge", return_value=local),
            patch("app.services.detection_service.search_evidence", return_value=list(web)),
            patch("app.services.llm_service._post_chat_completion", side_effect=responses) as transport,
            patch("urllib.request.urlopen", side_effect=AssertionError("offline regression attempted network")),
        ):
            result = detect_news_credibility(self.db, self.inputs, self.user)
        # Real Pydantic API serialization must keep the status and evidence metadata.
        api_result = DetectNewsResult.model_validate(result).model_dump(mode="json")
        record = self.db.get(DetectionRecord, result["detection_id"])
        detail = restore_detection_detail_payload(DetectionDetailOut.model_validate(record).model_dump(), record)
        detail = DetectionDetailOut.model_validate(detail).model_dump(mode="json")
        self.assertEqual(api_result["assessment_status"], detail["assessment_status"])
        self.assertEqual(api_result["final_score"], detail["final_score"])
        artifact_dir = os.getenv("P0_ARTIFACT_DIR")
        if artifact_dir:
            target = Path(artifact_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{name}.json").write_text(json.dumps({"kind": "mock-provider integration, not benchmark",
                "request": self.inputs.model_dump(), "response": api_result, "stored_detail": detail,
                "prompts": [c.kwargs["prompt"] for c in transport.call_args_list]}, ensure_ascii=False, indent=2), encoding="utf-8")
        return result, record, transport

    def test_local_hit_completes_and_persists(self):
        result, record, transport = self.run_scenario("local-hit", [local_result()], [completion(["kb:1"])])
        self.assertEqual(result["assessment_status"], "completed")
        self.assertIsNotNone(record.final_score)
        self.assertEqual(len(record.evidence_matches), 1)
        self.assertEqual(transport.call_count, 1)

    def test_v2_web_context_survives_prompt_api_and_database(self):
        web = [WebEvidenceItem(title="网络公告", url="https://example.net/library", summary="图书馆周一开放", site_name="网络来源")]
        result, record, transport = self.run_scenario("v2-web", [local_result(0.2, True)], [completion(["kb:1", "web:1"])], web)
        self.assertTrue(result["web_search_triggered"])
        candidate = next(item for item in result["candidate_evidence_list"] if item["candidate_id"] == "kb:1")
        stored = json.loads(record.analysis_payload)["candidate_evidence_list"]
        self.assertEqual(candidate["raw_cosine_score"], 0.2)
        self.assertEqual(candidate["fusion_score"], 0.99)
        self.assertEqual(candidate["index_version"], "v2")
        self.assertEqual(candidate["parent_revision"], "fixture-revision")
        self.assertTrue(candidate["chunks"])
        self.assertTrue(candidate["supporting_spans"])
        self.assertEqual(next(x for x in stored if x["candidate_id"] == "kb:1"), candidate)
        prompt = transport.call_args.kwargs["prompt"]
        self.assertIn("图书馆在周一开放", prompt)
        for key in ("raw_cosine_score", "fusion_score", "score_components", "similarity_score"):
            self.assertNotIn(f'"{key}"', prompt)

    def test_arbitration_repair_is_bounded_and_can_recover(self):
        result, _, transport = self.run_scenario("arbitration-repaired", [local_result()], [completion(["invented"]), completion(["kb:1"])])
        self.assertEqual(result["assessment_status"], "completed")
        self.assertEqual(result["arbitration_attempts"], 2)
        self.assertEqual(transport.call_count, 2)

    def test_exhausted_arbitration_abstains_even_with_high_model_score(self):
        result, record, transport = self.run_scenario("arbitration-exhausted", [local_result()], [completion(["invented"]), completion(["invented"])])
        self.assertEqual(result["assessment_status"], "degraded")
        self.assertIsNone(record.final_score)
        self.assertEqual(record.risk_level, "无法判断")
        self.assertFalse(record.is_high_risk)
        self.assertEqual(transport.call_count, 2)

    def test_provider_failure_abstains_even_with_high_rule_score(self):
        result, record, _ = self.run_scenario("provider-failure", [local_result()], [DeepSeekServiceError("offline timeout")])
        self.assertEqual(result["assessment_status"], "degraded")
        self.assertGreater(result["rule_score"], 60)
        self.assertIsNone(record.final_score)

    def test_no_evidence_abstains_and_report_has_no_numeric_verdict(self):
        result, record, _ = self.run_scenario("no-evidence", [], [completion([])])
        self.assertEqual(result["assessment_status"], "insufficient_evidence")
        self.assertIsNone(result["final_score"])
        report = generate_detection_report(self.db, record.id, self.user)
        html = (Path(self.temp.name) / report.html_path).read_text(encoding="utf-8")
        self.assertIn('class="score">无法判断</span>', html)
        self.assertNotIn('class="score">无法判断</span> / 100', html)
        pdf = (Path(self.temp.name) / report.pdf_path).read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.save_report_artifact("no-evidence", report, "real PDF converter")
        if os.getenv("P0_ARTIFACT_DIR"):
            (Path(os.environ["P0_ARTIFACT_DIR"]) / "no-evidence.report.pdf").write_bytes(pdf)

    def test_only_neutral_background_cannot_support_a_verdict(self):
        response = completion(["kb:1"])
        body = json.loads(response["choices"][0]["message"]["content"])
        body["evidence_arbitration"]["ranked_evidence"][0]["stance"] = "neutral"
        response["choices"][0]["message"]["content"] = json.dumps(body)
        result, _, _ = self.run_scenario("neutral-only", [local_result()], [response])
        self.assertEqual(result["assessment_status"], "insufficient_evidence")
        self.assertIsNone(result["final_score"])

    def test_invalid_main_score_cannot_be_repaired_by_valid_arbitration(self):
        for invalid in (None, True, "90", float("nan"), float("inf"), -1, 101):
            with self.subTest(score=invalid):
                response = completion(["kb:1"])
                body = json.loads(response["choices"][0]["message"]["content"])
                body["llm_score"] = invalid
                response["choices"][0]["message"]["content"] = json.dumps(body)
                result, _, transport = self.run_scenario("invalid-main-score", [local_result()], [response])
                self.assertEqual(result["assessment_status"], "degraded")
                self.assertEqual(result["arbitration_status"], "invalid_response")
                self.assertIsNone(result["final_score"])
                self.assertEqual(transport.call_count, 1)

    def test_invalid_raw_quality_is_not_silently_accepted_as_zero(self):
        for invalid in (None, True, "90", float("nan"), -1, 101):
            with self.subTest(consistency=invalid):
                response = completion(["kb:1"])
                body = json.loads(response["choices"][0]["message"]["content"])
                body["evidence_quality"]["consistency"] = invalid
                response["choices"][0]["message"]["content"] = json.dumps(body)
                result, _, transport = self.run_scenario("invalid-quality", [local_result()], [response, response])
                self.assertEqual(result["assessment_status"], "degraded")
                self.assertEqual(result["arbitration_status"], "retry_exhausted")
                self.assertEqual(transport.call_count, 2)

    def generate_report(self, record):
        def render(html, path):
            path.write_bytes(b"%PDF-1.4\n offline-renderer fixture")
        with patch("app.services.report_service._convert_html_to_pdf", side_effect=render):
            return generate_detection_report(self.db, record.id, self.user)

    def save_report_artifact(self, name, report, outcome):
        if not os.getenv("P0_ARTIFACT_DIR"):
            return
        target = Path(os.environ["P0_ARTIFACT_DIR"])
        target.mkdir(parents=True, exist_ok=True)
        html = Path(self.temp.name) / report.html_path
        pdf = Path(self.temp.name) / report.pdf_path
        (target / f"{name}.report.json").write_text(json.dumps({
            "outcome": outcome, "report_id": report.id,
            "database_html_path": report.html_path, "database_pdf_path": report.pdf_path,
            "html_exists": html.is_file(), "pdf_exists": pdf.is_file(),
            "rendered_html": html.read_text(encoding="utf-8") if html.is_file() else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_report_regeneration_cleans_old_files_only_after_commit(self):
        _, record, _ = self.run_scenario("report-regeneration", [local_result()], [completion(["kb:1"])])
        first = self.generate_report(record)
        old = (first.html_path, first.pdf_path)
        with patch.dict(os.environ, {"REPORT_GENERATION_CACHE_ENABLED": "false"}):
            get_settings.cache_clear()
            second = self.generate_report(record)
        self.assertNotEqual(second.pdf_path, old[1])
        self.assertTrue((Path(self.temp.name) / second.pdf_path).is_file())
        self.assertTrue(all(not (Path(self.temp.name) / p).exists() for p in old))
        self.save_report_artifact("report-regeneration", second, "committed replacement; old files removed")

    def test_report_does_not_refresh_after_successful_commit(self):
        _, record, _ = self.run_scenario("report-refresh", [local_result()], [completion(["kb:1"])])
        with patch.object(self.db, "refresh", side_effect=RuntimeError("refresh unavailable")) as refresh:
            report = self.generate_report(record)
        refresh.assert_not_called()
        self.assertTrue((Path(self.temp.name) / report.pdf_path).is_file())

    def test_commit_acknowledgement_loss_preserves_referenced_files(self):
        _, record, _ = self.run_scenario("report-commit-ack-loss", [local_result()], [completion(["kb:1"])])
        real_commit = self.db.commit
        def commit_then_fail():
            real_commit()
            raise RuntimeError("commit succeeded; acknowledgement lost")
        with patch.object(self.db, "commit", side_effect=commit_then_fail):
            with self.assertRaises(ReportGenerationError):
                self.generate_report(record)
        self.db.expire_all()
        report = self.db.query(Report).one()
        self.assertTrue((Path(self.temp.name) / report.pdf_path).is_file())
        self.assertTrue((Path(self.temp.name) / report.html_path).is_file())
        self.save_report_artifact("report-commit-ack-loss", report, "commit succeeded then acknowledgement failed; referenced files retained")
        self.assertEqual(self.generate_report(record).id, report.id)

    def test_precommit_failure_cleans_new_files(self):
        _, record, _ = self.run_scenario("report-flush-failure", [local_result()], [completion(["kb:1"])])
        real_flush = self.db.flush
        def fail_report_flush(*args, **kwargs):
            if any(isinstance(item, Report) for item in self.db.new):
                raise RuntimeError("report flush failed")
            return real_flush(*args, **kwargs)
        with patch.object(self.db, "flush", side_effect=fail_report_flush):
            with self.assertRaises(ReportGenerationError):
                self.generate_report(record)
        self.assertFalse(list(Path(self.temp.name).rglob("report_*.pdf")))

    def test_converter_failure_cleans_partial_files(self):
        _, record, _ = self.run_scenario("report-render-failure", [local_result()], [completion(["kb:1"])])
        def failed_render(html, path):
            path.write_bytes(b"partial")
            raise RuntimeError("renderer failed")
        with patch("app.services.report_service._convert_html_to_pdf", side_effect=failed_render):
            with self.assertRaises(ReportGenerationError):
                generate_detection_report(self.db, record.id, self.user)
        self.assertFalse(list(Path(self.temp.name).rglob("report_*.*")))

    def test_old_numeric_report_cannot_be_downloaded_after_abstention(self):
        _, record, _ = self.run_scenario("report-state-change", [local_result()], [completion(["kb:1"])])
        report = self.generate_report(record)
        payload = json.loads(record.analysis_payload)
        payload["assessment_status"] = "degraded"
        record.analysis_payload = json.dumps(payload)
        record.assessment_status = "degraded"
        record.final_score = None
        record.risk_level = "无法判断"
        self.db.commit()
        with self.assertRaises(ReportFileMissingError):
            get_report_pdf_for_download(self.db, report.id, self.user)
        new_report = self.generate_report(record)
        self.assertIn('class="score">无法判断</span>', (Path(self.temp.name) / new_report.html_path).read_text(encoding="utf-8"))

    def test_validator_rejects_invalid_container_and_nonfinite_scores(self):
        candidates = [{"candidate_id": "kb:1"}]
        for raw in (None, [], 1, {"ranked_evidence": 42, "rejected_evidence": []}):
            self.assertTrue(validate_and_apply_llm_ranking(candidates, raw)["errors"])
        raw = json.loads(completion(["kb:1"])["choices"][0]["message"]["content"])["evidence_arbitration"]
        for score in (float("nan"), float("inf"), True):
            value = copy.deepcopy(raw)
            value["ranked_evidence"][0]["quality_score"] = score
            self.assertTrue(validate_and_apply_llm_ranking(candidates, value)["errors"])

    def test_http_response_and_audit_log_do_not_mislabel_abstention(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.v1 import detect as api
        overrides = app.dependency_overrides.copy()
        app.dependency_overrides[api.get_db] = lambda: self.db
        app.dependency_overrides[api.get_optional_current_user] = lambda: self.user
        api.detector_rate_limiter.clear()
        try:
            with (
                patch("app.services.detection_service.search_similar_knowledge", return_value=[]),
                patch("app.services.llm_service._post_chat_completion", return_value=completion([])),
                patch("app.api.v1.detect.record_system_log") as audit,
            ):
                payload = self.inputs.model_dump()
                payload["enable_web_search"] = False
                response = TestClient(app).post("/api/detect/news", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["data"]["assessment_status"], "insufficient_evidence")
            self.assertIsNone(body["data"]["final_score"])
            self.assertIn("无法判断", body["message"])
            self.assertEqual(audit.call_args.kwargs["result_status"], "degraded")
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)
            api.detector_rate_limiter.clear()


if __name__ == "__main__":
    unittest.main()
