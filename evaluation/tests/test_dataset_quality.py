from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from evaluation.ai_engineering.metrics import evaluate_cases, validate_prediction_contract
from evaluation.ai_engineering.runner import _csv_row_to_case
from evaluation.dataset_quality import audit_dataset, gold_issues, leakage_findings, verify_manifest
from evaluation.metrics import compute_classification_metrics, compute_inter_rater_agreement, compute_sample_counts
from evaluation.run_evaluation import bind_run_context, parse_args, run_evaluation, run_single_detection
from evaluation.run_title_retrieval_baseline import retrieve

DATASETS = Path(__file__).resolve().parents[1] / "datasets"


class FrozenDataTests(unittest.TestCase):
    def setUp(self):
        with (DATASETS / "news_eval.csv").open(encoding="utf-8", newline="") as file:
            self.rows = list(csv.DictReader(file))

    def test_source_claims_labels_and_annotations_are_unchanged(self):
        source = {str(row["id"]): row for row in (json.loads(line) for line in (DATASETS / "sources/cfever/dev.jsonl").read_text(encoding="utf-8").splitlines())}
        self.assertEqual(len(self.rows), 120)
        for row in self.rows:
            original = source[row["source_record_ids"]]
            self.assertEqual(row["content"], original["claim"])
            self.assertEqual(row["upstream_label"], original["label"])
            self.assertEqual(json.loads(row["upstream_evidence_json"]), original["evidence"])
            self.assertEqual(row["gold_label"], "")
            self.assertEqual(row["reviewer_1_label"], "")

    def test_frozen_manifest_and_no_model_visible_template_leakage(self):
        self.assertEqual(verify_manifest(DATASETS / "frozen_manifest.json")["sample_count"], 120)
        audit = audit_dataset(self.rows)
        self.assertEqual(audit["leakage_count"], 0)
        self.assertFalse(audit["publication_eligible"])

    def test_group_and_evidence_page_splits_are_disjoint(self):
        group_splits = {}
        page_splits = {}
        for row in self.rows:
            group_splits.setdefault(row["topic_id"], set()).add(row["split"])
            for page in json.loads(row["relevant_page_ids"]):
                page_splits.setdefault(page, set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in group_splits.values()))
        self.assertTrue(all(len(splits) == 1 for splits in page_splits.values()))

    def test_legacy_leaky_data_is_quarantined_and_rejected(self):
        with (DATASETS / "quarantine/news_eval_synthetic_leaky.csv").open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 80)
        self.assertEqual(audit_dataset(rows)["leakage_count"], 80)

    def test_gold_gate_exits_before_database_or_provider_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parse_args(["--dataset", str(DATASETS / "news_eval.csv"), "--output-dir", directory])
            self.assertEqual(run_evaluation(args), 2)

    def test_hash_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.csv").write_text("changed")
            (root / "manifest.json").write_text(json.dumps({"files": {"data.csv": "0" * 64}}))
            with self.assertRaises(ValueError):
                verify_manifest(root / "manifest.json")


class GoldAndStatusTests(unittest.TestCase):
    def test_nonhuman_reviewer_or_same_reviewer_cannot_make_gold(self):
        row = {"gold_label": "可信新闻", "human_review_status": "adjudicated",
               "reviewer_1_id": "A", "reviewer_2_id": "A", "reviewer_1_type": "human",
               "reviewer_2_type": "model", "reviewer_1_label": "可信新闻", "reviewer_2_label": "可信新闻",
               "adjudication_reason": "reason", "source_record_ids": "source-1"}
        self.assertTrue(gold_issues(row))
        row.update(reviewer_2_id="B", reviewer_2_type="human")
        self.assertEqual(gold_issues(row), [])

    def test_labels_only_in_annotation_are_not_input_leakage(self):
        self.assertEqual(leakage_findings({"title": "待核验原文", "content": "一份未经核验的陈述。", "gold_label": "高风险"}), [])

    def test_abstentions_stay_in_accuracy_denominator(self):
        rows = [{"success": True, "gold_eligible": True, "gold_label": "可信新闻", "predicted_label": "可信新闻", "assessment_status": "completed"},
                {"success": True, "gold_eligible": True, "gold_label": "可信新闻", "predicted_label": "无法判断", "assessment_status": "insufficient_evidence"},
                {"success": True, "gold_eligible": True, "gold_label": "可信新闻", "predicted_label": "无法判断", "assessment_status": "degraded"}]
        metrics = compute_classification_metrics(rows)
        self.assertEqual(metrics["accuracy"], 0.3333)
        self.assertEqual(metrics["assessment_coverage"], 0.3333)
        self.assertEqual(metrics["selective_accuracy"], 1.0)
        self.assertEqual(compute_sample_counts(rows)["degraded_count"], 1)

    def test_research_labels_and_synthetic_review_do_not_produce_quality_metrics(self):
        rows = [{"success": True, "gold_eligible": False, "gold_label": "可信新闻", "predicted_label": "可信新闻",
                 "reviewer_1_label": "可信新闻", "reviewer_2_label": "可信新闻", "human_review_status": "pending_independent_review"}]
        self.assertIsNone(compute_classification_metrics(rows)["accuracy"])
        self.assertIsNone(compute_inter_rater_agreement(rows)["cohens_kappa"])

    def test_successful_transport_cannot_synthesize_accepted_or_effective_evidence(self):
        case = _csv_row_to_case({"success": "true", "retrieved_knowledge_ids": "7", "evidence_count": "1", "gold_label": "可信新闻", "gold_eligible": "false"}, 1)
        prediction = case["prediction"]
        self.assertEqual(prediction["arbitration_status"], "unknown")
        self.assertEqual(prediction["quality_status"], "unknown")
        self.assertEqual(prediction["evidence_list"], [])
        self.assertEqual(case["expected"]["risk_level"], "")

    def test_abstention_contract_accepts_null_but_rejects_high_score(self):
        prediction = {"assessment_status": "degraded", "risk_level": "无法判断", "final_score": None,
                      "arbitration_status": "provider_error", "evidence_list": []}
        self.assertEqual(validate_prediction_contract(prediction), [])
        metrics = evaluate_cases([{"prediction": prediction}])["metrics"]
        self.assertEqual(metrics["degraded_rate"], 1.0)
        self.assertEqual(metrics["abstention_rate"], 1.0)
        prediction["final_score"] = 100
        self.assertIn("abstention_contract", validate_prediction_contract(prediction))

    def test_runner_preserves_provider_failure_as_null_score_and_degraded(self):
        detect = Mock(return_value={"risk_level": "无法判断", "final_score": None,
                                    "assessment_status": "degraded", "assessment_reason": "provider unavailable",
                                    "arbitration_status": "provider_error", "quality_status": "failed",
                                    "stage_latency_ms": {"db_save": 4.2}, "evidence_list": []})
        with patch("evaluation.run_evaluation._load_detection_runtime", return_value=(SimpleNamespace, ValueError, LookupError, detect)):
            result = run_single_detection(object(), {"sample_id": "fixture", "title": "测试状态映射", "content": "这段原始主张文本专门检查调用成功但评估降级时的记录语义。"}, False, 0)
        self.assertTrue(result["success"])
        self.assertIsNone(result["final_score"])
        self.assertEqual(result["assessment_status"], "degraded")
        self.assertEqual(result["arbitration_status"], "provider_error")
        self.assertEqual(result["quality_status"], "failed")
        self.assertEqual(result["db_save_latency_ms"], 4.2)
        self.assertEqual(result["report_latency_ms"], "")

    def test_resume_rejects_changed_dataset_and_reused_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bind_run_context(root, {"hash": "one"}, resume=False)
            (root / "_checkpoint.json").write_text('{}')
            bind_run_context(root, {"hash": "one"}, resume=True)
            with self.assertRaises(ValueError):
                bind_run_context(root, {"hash": "two"}, resume=True)
            with self.assertRaises(ValueError):
                bind_run_context(root, {"hash": "one"}, resume=False)

    def test_lexical_baseline_has_deterministic_ties_and_no_gold_input(self):
        corpus = [{"page_id": "台北", "title": "台北"}, {"page_id": "台中", "title": "台中"}]
        self.assertEqual(retrieve("台北市", corpus)[0]["page_id"], "台北")
        self.assertEqual(retrieve("无匹配", corpus), [])
