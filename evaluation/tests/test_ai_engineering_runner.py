"""Tests for the AI engineering evaluation CLI helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import csv

from evaluation.ai_engineering.runner import (
    load_results_csv_as_cases,
    load_jsonl,
    load_predictions,
    main,
    merge_predictions,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class JsonlLoaderTests(unittest.TestCase):
    def test_load_jsonl_skips_blank_and_comment_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text(
                "\n# comment\n"
                + json.dumps({"case_id": "AI-001", "expected": {}, "prediction": {}})
                + "\n",
                encoding="utf-8",
            )

            rows = load_jsonl(path)

        self.assertEqual(rows, [{"case_id": "AI-001", "expected": {}, "prediction": {}}])

    def test_load_predictions_accepts_jsonl_keyed_by_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.jsonl"
            _write_jsonl(path, [
                {"case_id": "AI-001", "prediction": {"risk_level": "low_risk"}},
            ])

            predictions = load_predictions(path)

        self.assertEqual(predictions, {"AI-001": {"risk_level": "low_risk"}})


class CsvAdapterTests(unittest.TestCase):
    def test_load_results_csv_as_cases_adapts_existing_eval_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "per_case_results.csv"
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "sample_id",
                    "gold_label",
                    "predicted_label",
                    "final_score",
                    "success",
                    "total_latency_ms",
                    "retrieved_knowledge_ids",
                    "retrieved_chunk_ids",
                    "relevant_knowledge_ids",
                    "relevant_chunk_ids",
                    "evidence_count",
                    "error_type",
                    "error_message",
                ])
                writer.writeheader()
                writer.writerow({
                    "sample_id": "NEWS-EVAL-001",
                    "gold_label": "high_risk",
                    "predicted_label": "high_risk",
                    "final_score": "22",
                    "success": "true",
                    "total_latency_ms": "310",
                    "retrieved_knowledge_ids": "kb:official-denial,kb:background",
                    "retrieved_chunk_ids": "",
                    "relevant_knowledge_ids": "kb:official-denial",
                    "relevant_chunk_ids": "",
                    "evidence_count": "1",
                    "error_type": "",
                    "error_message": "",
                })

            cases = load_results_csv_as_cases(path)

        self.assertEqual(cases[0]["case_id"], "NEWS-EVAL-001")
        self.assertEqual(cases[0]["expected"]["risk_level"], "high_risk")
        self.assertEqual(
            cases[0]["prediction"]["candidate_evidence_list"][0]["evidence_id"],
            "kb:official-denial",
        )


class RunnerTests(unittest.TestCase):
    def test_merge_predictions_overrides_embedded_prediction(self) -> None:
        cases = [
            {"case_id": "AI-001", "prediction": {"risk_level": "old"}, "expected": {}},
        ]

        merged = merge_predictions(cases, {"AI-001": {"risk_level": "new"}})

        self.assertEqual(merged[0]["prediction"]["risk_level"], "new")
        self.assertEqual(cases[0]["prediction"]["risk_level"], "old")

    def test_main_writes_summary_and_returns_zero_when_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "cases.jsonl"
            output_path = Path(tmp) / "summary.json"
            _write_jsonl(case_path, [
                {
                    "case_id": "AI-001",
                    "expected": {
                        "risk_level": "high_risk",
                        "score_range": [0, 45],
                        "relevant_evidence_ids": ["kb:official-denial"],
                    },
                    "prediction": {
                        "risk_level": "high_risk",
                        "final_score": 25,
                        "evidence_list": [
                            {"evidence_id": "kb:official-denial", "source": "local"},
                        ],
                        "candidate_evidence_list": [
                            {"evidence_id": "kb:official-denial", "source": "local"},
                        ],
                        "arbitration_status": "accepted",
                        "quality_status": "ok",
                        "stage_latency_ms": {"rag_search": 10, "llm_analysis": 20},
                    },
                }
            ])

            code = main(["--cases", str(case_path), "--output", str(output_path)])

            self.assertEqual(code, 0)
            summary = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["gate"]["passed"])
            self.assertEqual(summary["metrics"]["total_cases"], 1)

    def test_main_accepts_existing_results_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "per_case_results.csv"
            output_path = Path(tmp) / "summary.json"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "sample_id",
                    "gold_label",
                    "predicted_label",
                    "final_score",
                    "success",
                    "total_latency_ms",
                    "retrieved_knowledge_ids",
                    "relevant_knowledge_ids",
                    "evidence_count",
                ])
                writer.writeheader()
                writer.writerow({
                    "sample_id": "NEWS-EVAL-001",
                    "gold_label": "low_risk",
                    "predicted_label": "low_risk",
                    "final_score": "90",
                    "success": "true",
                    "total_latency_ms": "100",
                    "retrieved_knowledge_ids": "kb:official-source",
                    "relevant_knowledge_ids": "kb:official-source",
                    "evidence_count": "1",
                })

            code = main(["--results-csv", str(csv_path), "--output", str(output_path)])

            self.assertEqual(code, 0)
            summary = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["gate"]["passed"])


if __name__ == "__main__":
    unittest.main()
