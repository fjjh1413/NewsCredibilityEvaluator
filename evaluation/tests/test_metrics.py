"""Unit tests for evaluation metrics computation.

These tests operate on **synthetic per-case result dicts** — no real API
calls, no database, no network.  All metric functions must produce correct
results from known inputs.
"""

from __future__ import annotations

import math
import unittest

from evaluation.metrics import (
    ALL_RISK_LEVELS,
    _is_truthy,
    _percentile,
    _safe_float,
    compute_all_metrics,
    compute_classification_metrics,
    compute_evidence_completeness,
    compute_inter_rater_agreement,
    compute_latency_stats,
    compute_retrieval_metrics,
    compute_sample_counts,
    compute_stability_metrics,
    compute_web_trigger_rate,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides) -> dict:
    """Build a minimal valid per-case result dict with sensible defaults."""
    base = {
        "sample_id": "TEST-001",
        "gold_label": "",
        "predicted_label": "",
        "final_score": "",
        "success": True,
        "error_type": "",
        "total_latency_ms": "",
        "parse_latency_ms": "",
        "local_retrieval_latency_ms": "",
        "web_search_latency_ms": "",
        "llm_latency_ms": "",
        "report_latency_ms": "",
        "web_search_allowed": False,
        "web_search_triggered": False,
        "web_trigger_reason": "",
        "local_candidate_count": "",
        "top_similarity": "",
        "retrieved_knowledge_ids": "",
        "relevant_chunk_ids": "",
        "retrieved_chunk_ids": "",
        "evidence_count": 0,
        "valid_evidence_count": 0,
        "citation_fields_complete": False,
        "llm_parse_fallback_used": False,
        "created_at": "",
        "is_demo": False,
        "relevant_knowledge_ids": "",
        "reviewer_1_label": "",
        "reviewer_2_label": "",
        "is_timeout": False,
        "embedding_failed": False,
        "chroma_failed": False,
        "web_search_failed": False,
        "save_failed": False,
        "evidence_has_valid_url": False,
        "has_evidence_insufficient_hint": False,
        "error_message": "",
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════

class SafeFloatTests(unittest.TestCase):
    def test_valid_float(self) -> None:
        self.assertEqual(_safe_float(42.5), 42.5)

    def test_none(self) -> None:
        self.assertIsNone(_safe_float(None))

    def test_invalid_string(self) -> None:
        self.assertIsNone(_safe_float("abc"))

    def test_nan(self) -> None:
        self.assertIsNone(_safe_float(float("nan")))

    def test_inf(self) -> None:
        self.assertIsNone(_safe_float(float("inf")))


class IsTruthyTests(unittest.TestCase):
    def test_true_bool(self) -> None:
        self.assertTrue(_is_truthy(True))

    def test_false_bool(self) -> None:
        self.assertFalse(_is_truthy(False))

    def test_none(self) -> None:
        self.assertFalse(_is_truthy(None))

    def test_string_true(self) -> None:
        self.assertTrue(_is_truthy("true"))
        self.assertTrue(_is_truthy("1"))
        self.assertTrue(_is_truthy("yes"))

    def test_string_false(self) -> None:
        self.assertFalse(_is_truthy("false"))
        self.assertFalse(_is_truthy("0"))
        self.assertFalse(_is_truthy("no"))


# ═══════════════════════════════════════════════════════════════════════════
# percentile
# ═══════════════════════════════════════════════════════════════════════════

class PercentileTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(_percentile([], 50), 0.0)

    def test_single_value(self) -> None:
        self.assertEqual(_percentile([10.0], 50), 10.0)

    def test_p50(self) -> None:
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(_percentile(vals, 50), 3.0)

    def test_p95(self) -> None:
        vals = list(range(1, 101))
        self.assertAlmostEqual(_percentile(vals, 95), 95.05, places=1)

    def test_p0(self) -> None:
        vals = [5.0, 1.0, 3.0]
        self.assertEqual(_percentile(sorted(vals), 0), 1.0)

    def test_p100(self) -> None:
        vals = [5.0, 1.0, 3.0]
        self.assertEqual(_percentile(sorted(vals), 100), 5.0)


# ═══════════════════════════════════════════════════════════════════════════
# sample counts
# ═══════════════════════════════════════════════════════════════════════════

class SampleCountsTests(unittest.TestCase):
    def test_empty(self) -> None:
        result = compute_sample_counts([])
        self.assertEqual(result["total_samples"], 0)
        self.assertEqual(result["valid_samples"], 0)

    def test_demo_excluded(self) -> None:
        results = [
            _make_result(sample_id="DEMO-001", is_demo=True),
            _make_result(sample_id="EVAL-001"),
        ]
        sc = compute_sample_counts(results)
        self.assertEqual(sc["total_samples"], 2)
        self.assertEqual(sc["demo_samples_excluded"], 1)
        self.assertEqual(sc["valid_samples"], 1)

    def test_success_and_failure(self) -> None:
        results = [
            _make_result(sample_id="A", success=True, gold_label="可信新闻"),
            _make_result(sample_id="B", success=False, error_type="timeout"),
            _make_result(sample_id="C", success=True, gold_label="存疑信息"),
        ]
        sc = compute_sample_counts(results)
        self.assertEqual(sc["success_count"], 2)
        self.assertEqual(sc["failure_count"], 1)
        self.assertEqual(sc["gold_label_distribution"], {"可信新闻": 1, "存疑信息": 1})

    def test_predicted_label_distribution(self) -> None:
        results = [
            _make_result(sample_id="A", success=True, predicted_label="可信新闻"),
            _make_result(sample_id="B", success=True, predicted_label="可信新闻"),
            _make_result(sample_id="C", success=True, predicted_label="存疑信息"),
            _make_result(sample_id="D", success=False),  # no predicted label
        ]
        sc = compute_sample_counts(results)
        self.assertEqual(sc["predicted_label_distribution"], {"可信新闻": 2, "存疑信息": 1})


# ═══════════════════════════════════════════════════════════════════════════
# latency
# ═══════════════════════════════════════════════════════════════════════════

class LatencyStatsTests(unittest.TestCase):
    def test_empty(self) -> None:
        lat = compute_latency_stats([])
        for stage in lat:
            self.assertEqual(lat[stage]["count"], 0)

    def test_failed_excluded(self) -> None:
        results = [
            _make_result(sample_id="A", success=False, total_latency_ms=100),
            _make_result(sample_id="B", success=True, total_latency_ms=200),
        ]
        lat = compute_latency_stats(results)
        self.assertEqual(lat["total_latency_ms"]["count"], 1)
        self.assertEqual(lat["total_latency_ms"]["avg"], 200.0)

    def test_stats_values(self) -> None:
        results = [
            _make_result(sample_id="A", success=True, total_latency_ms=100),
            _make_result(sample_id="B", success=True, total_latency_ms=200),
            _make_result(sample_id="C", success=True, total_latency_ms=300),
        ]
        lat = compute_latency_stats(results)
        t = lat["total_latency_ms"]
        self.assertEqual(t["avg"], 200.0)
        self.assertEqual(t["p50"], 200.0)
        self.assertEqual(t["max"], 300.0)

    def test_stage_latencies_may_be_empty(self) -> None:
        """Per-stage latencies are not individually timed; they may be empty."""
        results = [
            _make_result(sample_id="A", success=True, total_latency_ms=500,
                         llm_latency_ms="", parse_latency_ms=""),
        ]
        lat = compute_latency_stats(results)
        self.assertEqual(lat["total_latency_ms"]["count"], 1)
        self.assertEqual(lat["llm_latency_ms"]["count"], 0)  # empty → not counted
        self.assertEqual(lat["parse_latency_ms"]["count"], 0)


# ═══════════════════════════════════════════════════════════════════════════
# web search trigger rate
# ═══════════════════════════════════════════════════════════════════════════

class WebTriggerRateTests(unittest.TestCase):
    def test_no_allowed(self) -> None:
        results = [
            _make_result(sample_id="A", web_search_allowed=False, web_search_triggered=False),
        ]
        ws = compute_web_trigger_rate(results)
        self.assertEqual(ws["web_search_allowed_count"], 0)
        # Denominator is 0 → rate should be 0
        self.assertEqual(ws["web_trigger_rate"], 0.0)

    def test_rate_calculation(self) -> None:
        results = [
            _make_result(sample_id="A", web_search_allowed=True, web_search_triggered=True,
                         web_trigger_reason="top-1 below threshold"),
            _make_result(sample_id="B", web_search_allowed=True, web_search_triggered=False),
            _make_result(sample_id="C", web_search_allowed=True, web_search_triggered=True,
                         web_trigger_reason="top-1 below threshold"),
        ]
        ws = compute_web_trigger_rate(results)
        self.assertEqual(ws["web_search_allowed_count"], 3)
        self.assertEqual(ws["web_search_triggered_count"], 2)
        self.assertAlmostEqual(ws["web_trigger_rate"], 2 / 3, places=4)

    def test_demo_excluded(self) -> None:
        results = [
            _make_result(sample_id="DEMO-001", is_demo=True,
                         web_search_allowed=True, web_search_triggered=True),
            _make_result(sample_id="A", web_search_allowed=True, web_search_triggered=False),
        ]
        ws = compute_web_trigger_rate(results)
        self.assertEqual(ws["web_search_allowed_count"], 1)


# ═══════════════════════════════════════════════════════════════════════════
# retrieval metrics
# ═══════════════════════════════════════════════════════════════════════════

class RetrievalMetricsTests(unittest.TestCase):
    def test_no_annotations(self) -> None:
        results = [_make_result(sample_id="A", success=True)]
        rm = compute_retrieval_metrics(results)
        self.assertEqual(rm["annotated_sample_count"], 0)
        self.assertIn("No samples had relevant_knowledge_ids", rm["note"])

    def test_hit_at_k(self) -> None:
        """Sample has relevant IDs [1,2,3] and retrieved [2,5,1,8]. Top-1 hits, top-3 hits all 3."""
        results = [
            _make_result(
                sample_id="A", success=True,
                relevant_knowledge_ids="1,2,3",
                retrieved_knowledge_ids="2,5,1,8",
            ),
        ]
        rm = compute_retrieval_metrics(results, k_values=[1, 3, 5])
        self.assertEqual(rm["annotated_sample_count"], 1)
        self.assertEqual(rm["hit_at_k"][1], 1.0)   # top-1 = 2 (hit!)
        self.assertEqual(rm["hit_at_k"][3], 1.0)   # top-3 = 2,5,1 (hit!)
        self.assertAlmostEqual(rm["recall_at_k"][1], 1.0 / 3, places=4)  # top-1: {2} ∩ {1,2,3} -> 1/3
        self.assertAlmostEqual(rm["recall_at_k"][3], 2.0 / 3, places=4)  # top-3: {2,5,1} ∩ {1,2,3} = {1,2} -> 2/3

    def test_hit_at_k_miss(self) -> None:
        results = [
            _make_result(
                sample_id="A", success=True,
                relevant_knowledge_ids="10,20",
                retrieved_knowledge_ids="1,2,3,4,5",
            ),
        ]
        rm = compute_retrieval_metrics(results, k_values=[5])
        self.assertEqual(rm["hit_at_k"][5], 0.0)
        self.assertEqual(rm["recall_at_k"][5], 0.0)

    def test_mrr(self) -> None:
        """Relevant: {3}. Retrieved: [1,3,5]. MRR = 1/2 = 0.5"""
        results = [
            _make_result(
                sample_id="A", success=True,
                relevant_knowledge_ids="3",
                retrieved_knowledge_ids="1,3,5",
            ),
        ]
        rm = compute_retrieval_metrics(results)
        self.assertEqual(rm["mrr"], 0.5)

    def test_demo_excluded(self) -> None:
        results = [
            _make_result(sample_id="DEMO-001", is_demo=True, success=True,
                         relevant_knowledge_ids="1", retrieved_knowledge_ids="1"),
        ]
        rm = compute_retrieval_metrics(results)
        self.assertEqual(rm["annotated_sample_count"], 0)

    def test_chunk_level_metrics(self) -> None:
        results = [
            _make_result(
                sample_id="A", success=True,
                relevant_chunk_ids="knowledge:1:chunk:0,knowledge:2:chunk:1",
                retrieved_chunk_ids="knowledge:3:chunk:0,knowledge:2:chunk:1",
            ),
        ]
        rm = compute_retrieval_metrics(results, k_values=[1, 2])
        self.assertEqual(rm["chunk_annotated_sample_count"], 1)
        self.assertEqual(rm["chunk_hit_at_k"][1], 0.0)
        self.assertEqual(rm["chunk_hit_at_k"][2], 1.0)
        self.assertEqual(rm["chunk_recall_at_k"][2], 0.5)
        self.assertEqual(rm["chunk_mrr"], 0.5)

    def test_does_not_mutate_input_rows(self) -> None:
        row = _make_result(
            sample_id="A", success=True,
            relevant_knowledge_ids="1",
            retrieved_knowledge_ids="1",
        )
        compute_retrieval_metrics([row])
        self.assertNotIn("_relevant_ids", row)
        self.assertNotIn("_retrieved_ids", row)


# ═══════════════════════════════════════════════════════════════════════════
# classification metrics
# ═══════════════════════════════════════════════════════════════════════════

class ClassificationMetricsTests(unittest.TestCase):
    def test_no_labeled_samples(self) -> None:
        results = [_make_result(sample_id="A", success=True)]
        cm = compute_classification_metrics(results)
        self.assertEqual(cm["labeled_sample_count"], 0)
        self.assertIsNone(cm["accuracy"])
        self.assertIn("No samples had complete", cm["note"])

    def test_perfect_accuracy(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         gold_label="可信新闻", predicted_label="可信新闻"),
            _make_result(sample_id="B", success=True,
                         gold_label="存疑信息", predicted_label="存疑信息"),
        ]
        cm = compute_classification_metrics(results)
        self.assertEqual(cm["accuracy"], 1.0)
        self.assertEqual(cm["macro_precision"], 1.0)
        self.assertEqual(cm["macro_f1"], 1.0)

    def test_mixed(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         gold_label="可信新闻", predicted_label="可信新闻"),
            _make_result(sample_id="B", success=True,
                         gold_label="可信新闻", predicted_label="存疑信息"),  # FP for 存疑, FN for 可信
            _make_result(sample_id="C", success=True,
                         gold_label="存疑信息", predicted_label="存疑信息"),
        ]
        cm = compute_classification_metrics(results)
        self.assertAlmostEqual(cm["accuracy"], 2 / 3, places=4)
        self.assertLess(cm["macro_f1"], 1.0)

    def test_empty_results(self) -> None:
        cm = compute_classification_metrics([])
        self.assertEqual(cm["labeled_sample_count"], 0)
        self.assertIsNone(cm["accuracy"])

    def test_confusion_matrix_shape(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         gold_label="可信新闻", predicted_label="存疑信息"),
        ]
        cm = compute_classification_metrics(results)
        mat = cm["confusion_matrix"]
        self.assertEqual(len(mat), 4)  # 4 rows (gold labels)
        for row in mat.values():
            self.assertEqual(len(row), 5)  # 4 labels plus explicit abstention

    def test_class_not_in_gold_excluded_from_macro(self) -> None:
        """Classes not present in gold should not contribute to macro averages."""
        results = [
            _make_result(sample_id="A", success=True,
                         gold_label="可信新闻", predicted_label="可信新闻"),
        ]
        cm = compute_classification_metrics(results)
        # Only "可信新闻" is in gold, so macro should be based on 1 class
        self.assertEqual(cm["macro_precision"], 1.0)

    def test_demo_excluded(self) -> None:
        results = [
            _make_result(sample_id="DEMO-001", is_demo=True, success=True,
                         gold_label="可信新闻", predicted_label="可信新闻"),
        ]
        cm = compute_classification_metrics(results)
        self.assertEqual(cm["labeled_sample_count"], 0)


# ═══════════════════════════════════════════════════════════════════════════
# inter-rater agreement
# ═══════════════════════════════════════════════════════════════════════════

class InterRaterAgreementTests(unittest.TestCase):
    def test_no_dual_reviewed(self) -> None:
        results = [_make_result(sample_id="A")]
        ira = compute_inter_rater_agreement(results)
        self.assertEqual(ira["dual_reviewed_count"], 0)
        self.assertIsNone(ira["raw_agreement_rate"])
        self.assertIsNone(ira["cohens_kappa"])

    def test_only_one_reviewer(self) -> None:
        results = [
            _make_result(sample_id="A", reviewer_1_label="可信新闻", reviewer_2_label=""),
        ]
        ira = compute_inter_rater_agreement(results)
        self.assertEqual(ira["dual_reviewed_count"], 0)

    def test_single_sample_no_kappa(self) -> None:
        """Cohen's Kappa requires at least 2 samples."""
        results = [
            _make_result(sample_id="A", reviewer_1_label="可信新闻", reviewer_2_label="可信新闻"),
        ]
        ira = compute_inter_rater_agreement(results)
        self.assertEqual(ira["dual_reviewed_count"], 1)
        self.assertIsNotNone(ira["raw_agreement_rate"])
        self.assertIsNone(ira["cohens_kappa"])
        self.assertIn("Only one dual-reviewed sample", ira.get("note", ""))

    def test_perfect_agreement(self) -> None:
        results = [
            _make_result(sample_id="A", reviewer_1_label="可信新闻", reviewer_2_label="可信新闻"),
            _make_result(sample_id="B", reviewer_1_label="存疑信息", reviewer_2_label="存疑信息"),
            _make_result(sample_id="C", reviewer_1_label="疑似谣言", reviewer_2_label="疑似谣言"),
        ]
        ira = compute_inter_rater_agreement(results)
        self.assertEqual(ira["raw_agreement_rate"], 1.0)
        self.assertAlmostEqual(ira["cohens_kappa"], 1.0)

    def test_partial_agreement(self) -> None:
        results = [
            _make_result(sample_id="A", reviewer_1_label="可信新闻", reviewer_2_label="可信新闻"),
            _make_result(sample_id="B", reviewer_1_label="可信新闻", reviewer_2_label="存疑信息"),
            _make_result(sample_id="C", reviewer_1_label="存疑信息", reviewer_2_label="存疑信息"),
            _make_result(sample_id="D", reviewer_1_label="存疑信息", reviewer_2_label="疑似谣言"),
        ]
        ira = compute_inter_rater_agreement(results)
        self.assertEqual(ira["raw_agreement_rate"], 0.5)
        self.assertLess(ira["cohens_kappa"], 0.5)


# ═══════════════════════════════════════════════════════════════════════════
# evidence completeness
# ═══════════════════════════════════════════════════════════════════════════

class EvidenceCompletenessTests(unittest.TestCase):
    def test_no_success(self) -> None:
        results = [_make_result(sample_id="A", success=False)]
        evc = compute_evidence_completeness(results)
        self.assertIn("note", evc)

    def test_with_evidence(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         evidence_count=3, valid_evidence_count=3,
                         citation_fields_complete=True,
                         evidence_has_valid_url=True),
        ]
        evc = compute_evidence_completeness(results)
        self.assertEqual(evc["at_least_one_evidence_rate"], 1.0)
        self.assertEqual(evc["citation_fields_complete_rate"], 1.0)

    def test_conclusion_without_evidence(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         evidence_count=0, predicted_label="存疑信息"),
        ]
        evc = compute_evidence_completeness(results)
        self.assertEqual(evc["conclusion_without_evidence_count"], 1)

    def test_evidence_insufficient_hint(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         evidence_count=0, has_evidence_insufficient_hint=True),
        ]
        evc = compute_evidence_completeness(results)
        self.assertEqual(evc["evidence_insufficient_with_hint_count"], 1)


# ═══════════════════════════════════════════════════════════════════════════
# stability
# ═══════════════════════════════════════════════════════════════════════════

class StabilityMetricsTests(unittest.TestCase):
    def test_all_success(self) -> None:
        results = [
            _make_result(sample_id="A", success=True),
            _make_result(sample_id="B", success=True),
        ]
        stab = compute_stability_metrics(results)
        self.assertEqual(stab["overall_success_rate"], 1.0)

    def test_mixed(self) -> None:
        results = [
            _make_result(sample_id="A", success=True),
            _make_result(sample_id="B", success=False, error_type="timeout"),
            _make_result(sample_id="C", success=False, error_type="timeout"),
        ]
        stab = compute_stability_metrics(results)
        self.assertAlmostEqual(stab["overall_success_rate"], 1 / 3, places=4)
        self.assertEqual(stab["error_type_breakdown"]["timeout"], 2)

    def test_llm_parse_fallback_rate(self) -> None:
        results = [
            _make_result(sample_id="A", success=True, llm_parse_fallback_used=True),
            _make_result(sample_id="B", success=True, llm_parse_fallback_used=False),
        ]
        stab = compute_stability_metrics(results)
        self.assertAlmostEqual(stab["llm_parse_fallback_rate"], 0.5)

    def test_empty(self) -> None:
        stab = compute_stability_metrics([])
        self.assertIn("note", stab)


# ═══════════════════════════════════════════════════════════════════════════
# aggregate
# ═══════════════════════════════════════════════════════════════════════════

class AllMetricsTests(unittest.TestCase):
    def test_empty(self) -> None:
        """All metrics should handle empty result lists gracefully."""
        m = compute_all_metrics([])
        self.assertIn("sample_counts", m)
        self.assertIn("latency", m)
        self.assertIn("web_search", m)
        self.assertIn("retrieval", m)
        self.assertIn("classification", m)
        self.assertIn("inter_rater_agreement", m)
        self.assertIn("evidence_completeness", m)
        self.assertIn("stability", m)

        # All section should have at minimum a note or null values
        for section in m.values():
            self.assertIsInstance(section, dict)

    def test_partial_failures_dont_break_metrics(self) -> None:
        """Even when some samples fail, metrics should compute on the rest."""
        results = [
            _make_result(sample_id="A", success=True, gold_label="可信新闻",
                         predicted_label="可信新闻", total_latency_ms=100),
            _make_result(sample_id="B", success=False, error_type="timeout"),
            _make_result(sample_id="C", success=True, gold_label="可疑信息",  # invalid label
                         predicted_label="存疑信息", total_latency_ms=200),
        ]
        m = compute_all_metrics(results)
        # Sample B excluded from latency, C excluded from classification
        self.assertEqual(m["latency"]["total_latency_ms"]["count"], 2)


# ═══════════════════════════════════════════════════════════════════════════
# specific edge cases
# ═══════════════════════════════════════════════════════════════════════════

class NoFakeAccuracyTests(unittest.TestCase):
    """When gold_label is missing, accuracy must be None, not zero."""

    def test_missing_gold_labels_produce_null_accuracy(self) -> None:
        results = [
            _make_result(sample_id="A", success=True, gold_label="",
                         predicted_label="可信新闻"),
        ]
        cm = compute_classification_metrics(results)
        self.assertIsNone(cm["accuracy"])
        self.assertEqual(cm["labeled_sample_count"], 0)


class NoFakeRecallTests(unittest.TestCase):
    """When relevant_knowledge_ids is missing, recall must not be computed."""

    def test_missing_relevance_annotations_produce_zero_count(self) -> None:
        results = [
            _make_result(sample_id="A", success=True,
                         relevant_knowledge_ids="", retrieved_knowledge_ids="1,2,3"),
        ]
        rm = compute_retrieval_metrics(results)
        self.assertEqual(rm["annotated_sample_count"], 0)


class FailedSamplesNotExcludedTests(unittest.TestCase):
    """Failed samples must be counted, not silently dropped."""

    def test_failure_count_present(self) -> None:
        results = [
            _make_result(sample_id="A", success=True),
            _make_result(sample_id="B", success=False, error_type="timeout"),
            _make_result(sample_id="C", success=False, error_type="detection_service_error"),
        ]
        sc = compute_sample_counts(results)
        self.assertEqual(sc["success_count"], 1)
        self.assertEqual(sc["failure_count"], 2)
