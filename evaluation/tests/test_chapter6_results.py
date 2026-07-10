from __future__ import annotations

import unittest


class Chapter6ResultTests(unittest.TestCase):
    def test_latency_summary_uses_interpolated_percentiles(self) -> None:
        from evaluation.scripts.chapter6.compile_results import summarize_latencies

        result = summarize_latencies([10.0, 20.0, 30.0, 40.0])

        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["mean_ms"], 25.0)
        self.assertEqual(result["p50_ms"], 25.0)
        self.assertEqual(result["p95_ms"], 38.5)
        self.assertEqual(result["min_ms"], 10.0)
        self.assertEqual(result["max_ms"], 40.0)

    def test_classification_rows_keep_overall_and_per_class_metrics_distinct(self) -> None:
        from evaluation.scripts.chapter6.compile_results import classification_rows

        metrics = {
            "labeled_sample_count": 2,
            "accuracy": 0.5,
            "macro_precision": 0.6,
            "macro_recall": 0.5,
            "macro_f1": 0.55,
            "per_class": {
                "可信新闻": {"precision": 1.0, "recall": 0.5, "f1": 0.67, "tp": 1, "fp": 0, "fn": 1}
            },
        }

        rows = classification_rows(metrics, run_name="original")

        self.assertEqual(rows[0]["scope"], "overall")
        self.assertEqual(rows[0]["accuracy"], 0.5)
        self.assertEqual(rows[1]["scope"], "class")
        self.assertEqual(rows[1]["label"], "可信新闻")
        self.assertEqual(rows[1]["precision"], 1.0)

    def test_stability_summary_uses_only_samples_shared_by_all_runs(self) -> None:
        from evaluation.scripts.chapter6.analyze_stability import summarize_stability

        runs = {
            "original": [
                {"sample_id": "S1", "predicted_label": "可信新闻", "final_score": "80", "total_latency_ms": "100", "retrieved_knowledge_ids": "1,2"},
                {"sample_id": "S2", "predicted_label": "存疑信息", "final_score": "60", "total_latency_ms": "200", "retrieved_knowledge_ids": "3,4"},
                {"sample_id": "ONLY_OLD", "predicted_label": "可信新闻", "final_score": "90", "total_latency_ms": "999", "retrieved_knowledge_ids": "9"},
            ],
            "reproduction": [
                {"sample_id": "S1", "predicted_label": "可信新闻", "final_score": "82", "total_latency_ms": "110", "retrieved_knowledge_ids": "1,2"},
                {"sample_id": "S2", "predicted_label": "疑似谣言", "final_score": "62", "total_latency_ms": "210", "retrieved_knowledge_ids": "3,5"},
            ],
            "third": [
                {"sample_id": "S1", "predicted_label": "可信新闻", "final_score": "84", "total_latency_ms": "120", "retrieved_knowledge_ids": "1,2"},
                {"sample_id": "S2", "predicted_label": "存疑信息", "final_score": "64", "total_latency_ms": "220", "retrieved_knowledge_ids": "3,4"},
            ],
        }

        summary, per_sample = summarize_stability(runs)

        self.assertEqual(summary["repeat_count"], 3)
        self.assertEqual(summary["shared_sample_count"], 2)
        self.assertEqual(summary["prediction_all_same_rate"], 0.5)
        self.assertEqual(summary["latency_avg_ms"], 160.0)
        self.assertEqual(summary["latency_p50_ms"], 160.0)
        self.assertEqual(summary["latency_p95_ms"], 217.5)
        self.assertEqual([row["sample_id"] for row in per_sample], ["S1", "S2"])


if __name__ == "__main__":
    unittest.main()
