from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.report import generate_evaluation_report_md


class EvaluationReportTests(unittest.TestCase):
    def test_report_includes_chunk_level_retrieval_metrics(self) -> None:
        metrics = {
            "sample_counts": {},
            "latency": {},
            "web_search": {},
            "retrieval": {
                "annotated_sample_count": 0,
                "chunk_annotated_sample_count": 1,
                "chunk_hit_at_k": {1: 0.0, 2: 1.0},
                "chunk_recall_at_k": {1: 0.0, 2: 0.5},
                "chunk_mrr": 0.5,
            },
            "classification": {},
            "inter_rater_agreement": {},
            "evidence_completeness": {},
            "stability": {},
        }
        output_dir = Path(tempfile.mkdtemp())

        report = generate_evaluation_report_md(output_dir, metrics)

        self.assertIn("Chunk-level Retrieval", report)
        self.assertIn("Chunk Hit@K", report)
        self.assertIn("**Chunk MRR**: 0.5", report)
