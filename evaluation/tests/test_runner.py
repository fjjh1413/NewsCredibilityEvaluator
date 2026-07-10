"""Tests for evaluation runner — CSV loading, sanitization, checkpoints."""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the evaluation package is on path
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.run_evaluation import (
    _is_demo,
    _parse_allow_web_search,
    _parse_relevant_knowledge_ids,
    _sanitize_error,
    load_checkpoint,
    load_dataset,
    per_case_file_path,
    PER_CASE_HEADER,
    read_per_case_results,
    save_checkpoint,
    append_per_case_row,
    run_single_detection,
)


# ═══════════════════════════════════════════════════════════════════════════
# sanitization
# ═══════════════════════════════════════════════════════════════════════════

class SanitizeErrorTests(unittest.TestCase):
    def test_sk_key_redacted(self) -> None:
        msg = "Error calling API with key sk-abcdefghijklmnopqrstuvwxyz123456"
        result = _sanitize_error(Exception(msg))
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", result)

    def test_bearer_token_redacted(self) -> None:
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        result = _sanitize_error(Exception(msg))
        self.assertIn("[REDACTED]", result)

    def test_api_key_param_redacted(self) -> None:
        msg = "Failed request with api_key=secretkey1234567890 and other params"
        result = _sanitize_error(Exception(msg))
        self.assertIn("[REDACTED]", result)

    def test_normal_error_not_redacted(self) -> None:
        msg = "Connection timeout after 30 seconds"
        result = _sanitize_error(Exception(msg))
        self.assertEqual(result, msg)

    def test_truncated_long_message(self) -> None:
        msg = "x" * 1000
        result = _sanitize_error(Exception(msg))
        self.assertLessEqual(len(result), 500)


# ═══════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════

class IsDemoTests(unittest.TestCase):
    def test_demo_prefix(self) -> None:
        self.assertTrue(_is_demo("DEMO-001"))
        self.assertTrue(_is_demo("demo-abc"))

    def test_non_demo(self) -> None:
        self.assertFalse(_is_demo("EVAL-001"))
        self.assertFalse(_is_demo(""))


class ParseAllowWebSearchTests(unittest.TestCase):
    def test_global_override(self) -> None:
        self.assertTrue(_parse_allow_web_search({}, True))
        self.assertFalse(_parse_allow_web_search({}, False))

    def test_row_value(self) -> None:
        self.assertTrue(_parse_allow_web_search({"allow_web_search": "true"}, None))
        self.assertFalse(_parse_allow_web_search({"allow_web_search": "false"}, None))
        self.assertTrue(_parse_allow_web_search({"allow_web_search": "1"}, None))
        self.assertTrue(_parse_allow_web_search({"allow_web_search": "yes"}, None))

    def test_default_true(self) -> None:
        self.assertTrue(_parse_allow_web_search({}, None))


class ParseRelevantKnowledgeIdsTests(unittest.TestCase):
    def test_string(self) -> None:
        self.assertEqual(_parse_relevant_knowledge_ids({"relevant_knowledge_ids": "1,2,3"}), "1,2,3")

    def test_list(self) -> None:
        self.assertEqual(
            _parse_relevant_knowledge_ids({"relevant_knowledge_ids": [1, 2, 3]}),
            "1,2,3",
        )

    def test_empty(self) -> None:
        self.assertEqual(_parse_relevant_knowledge_ids({}), "")

    def test_none(self) -> None:
        self.assertEqual(_parse_relevant_knowledge_ids({"relevant_knowledge_ids": None}), "")


# ═══════════════════════════════════════════════════════════════════════════
# CSV loading
# ═══════════════════════════════════════════════════════════════════════════

class LoadDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write_csv(self, name: str, content: str) -> Path:
        path = Path(self.tmpdir) / name
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_basic_csv(self) -> None:
        path = self._write_csv("test.csv", (
            "sample_id,title,content,gold_label\n"
            "EVAL-001,Test Title,Test content with enough length for validation.,可信新闻\n"
        ))
        rows = load_dataset(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sample_id"], "EVAL-001")

    def test_comments_skipped(self) -> None:
        path = self._write_csv("test.csv", (
            "# This is a comment line\n"
            "# Another comment\n"
            "sample_id,title,content,gold_label\n"
            "# inline comment after header\n"
            "EVAL-001,Test Title,Test content with enough length for validation.,可信新闻\n"
        ))
        rows = load_dataset(path)
        self.assertEqual(len(rows), 1)

    def test_duplicate_ids_skipped(self) -> None:
        path = self._write_csv("test.csv", (
            "sample_id,title,content,gold_label\n"
            "EVAL-001,Title A,Test content with enough length for validation.,可信新闻\n"
            "EVAL-001,Title B,Test content with enough length for validation.,存疑信息\n"
        ))
        rows = load_dataset(path)
        self.assertEqual(len(rows), 1)

    def test_empty_id_skipped(self) -> None:
        path = self._write_csv("test.csv", (
            "sample_id,title,content,gold_label\n"
            ",Missing ID,Test content with enough length for validation.,\n"
            "EVAL-001,Title A,Test content with enough length for validation.,可信新闻\n"
        ))
        rows = load_dataset(path)
        self.assertEqual(len(rows), 1)

    def test_jsonl(self) -> None:
        path = Path(self.tmpdir) / "test.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "sample_id": "EVAL-001",
                "title": "Test",
                "content": "Test content with enough length for validation.",
                "gold_label": "可信新闻",
            }) + "\n")
        rows = load_dataset(path)
        self.assertEqual(len(rows), 1)

    def test_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_dataset(Path(self.tmpdir) / "nonexistent.csv")

    def test_unsupported_format(self) -> None:
        path = Path(self.tmpdir) / "test.txt"
        path.touch()
        with self.assertRaises(ValueError):
            load_dataset(path)


# ═══════════════════════════════════════════════════════════════════════════
# checkpoint / resume
# ═══════════════════════════════════════════════════════════════════════════

class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_no_checkpoint(self) -> None:
        completed = load_checkpoint(self.tmpdir)
        self.assertEqual(completed, set())

    def test_save_and_load(self) -> None:
        save_checkpoint(self.tmpdir, {"A", "B", "C"})
        completed = load_checkpoint(self.tmpdir)
        self.assertEqual(completed, {"A", "B", "C"})

    def test_corrupt_checkpoint(self) -> None:
        checkpoint_path = self.tmpdir / "_checkpoint.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text("not valid json")
        completed = load_checkpoint(self.tmpdir)
        self.assertEqual(completed, set())


# ═══════════════════════════════════════════════════════════════════════════
# per-case CSV I/O
# ═══════════════════════════════════════════════════════════════════════════

class PerCaseCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_write_and_read(self) -> None:
        row = {key: "" for key in PER_CASE_HEADER}
        row["sample_id"] = "TEST-001"
        row["success"] = True
        row["gold_label"] = "可信新闻"
        row["predicted_label"] = "可信新闻"
        row["final_score"] = 85.0

        append_per_case_row(self.tmpdir, row)

        results = read_per_case_results(self.tmpdir)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["sample_id"], "TEST-001")
        self.assertEqual(results[0]["gold_label"], "可信新闻")

    def test_append_multiple(self) -> None:
        for i in range(3):
            row = {key: "" for key in PER_CASE_HEADER}
            row["sample_id"] = f"TEST-{i:03d}"
            row["success"] = True
            append_per_case_row(self.tmpdir, row)

        results = read_per_case_results(self.tmpdir)
        self.assertEqual(len(results), 3)

    def test_empty_file(self) -> None:
        results = read_per_case_results(self.tmpdir)
        self.assertEqual(results, [])

    def test_header_fields_match(self) -> None:
        """Ensure PER_CASE_HEADER covers all required output fields."""
        required = [
            "sample_id", "gold_label", "predicted_label", "final_score",
            "success", "error_type", "total_latency_ms",
            "web_search_triggered", "local_candidate_count",
            "top_similarity", "retrieved_knowledge_ids",
            "retrieved_chunk_ids", "retrieval_version", "index_version",
            "candidate_parent_count", "candidate_chunk_count",
            "evidence_count", "valid_evidence_count",
            "citation_fields_complete", "llm_parse_fallback_used",
        ]
        for field in required:
            self.assertIn(field, PER_CASE_HEADER, f"Missing field: {field}")

    def test_read_new_retrieval_counts(self) -> None:
        row = {key: "" for key in PER_CASE_HEADER}
        row["sample_id"] = "TEST-001"
        row["success"] = True
        row["candidate_parent_count"] = 2
        row["candidate_chunk_count"] = 5
        row["retrieved_chunk_ids"] = "knowledge:1:chunk:0,knowledge:2:chunk:1"

        append_per_case_row(self.tmpdir, row)

        results = read_per_case_results(self.tmpdir)
        self.assertEqual(results[0]["candidate_parent_count"], 2)
        self.assertEqual(results[0]["candidate_chunk_count"], 5)
        self.assertEqual(
            results[0]["retrieved_chunk_ids"],
            "knowledge:1:chunk:0,knowledge:2:chunk:1",
        )


class RunSingleDetectionTests(unittest.TestCase):
    @patch("app.services.detection_service.detect_news_credibility")
    def test_records_stage_latency_and_rag_v2_fields(self, mock_detect) -> None:
        mock_detect.return_value = {
            "risk_level": "可信新闻",
            "final_score": 91.5,
            "stage_latency_ms": {
                "extract_keywords": 12.1,
                "rag_search": 23.2,
                "web_search": 34.3,
                "llm_analysis": 45.4,
                "db_save": 5.5,
            },
            "web_search_triggered": False,
            "retrieval_version": "v2",
            "index_version": "v2",
            "candidate_parent_count": 1,
            "candidate_chunk_count": 2,
            "candidate_evidence_list": [
                {
                    "source_type": "knowledge_base",
                    "knowledge_id": 7,
                    "similarity_score": 0.91,
                    "chunks": [
                        {"chunk_id": "knowledge:7:chunk:0"},
                        {"chunk_id": "knowledge:7:chunk:1"},
                    ],
                },
            ],
            "evidence_list": [
                {"title": "Evidence", "summary": "Summary", "source_url": "https://example.com"}
            ],
            "reason": "",
            "analysis_payload": {},
        }
        row = {
            "sample_id": "EVAL-001",
            "title": "测试标题",
            "content": "这是一段足够长的测试内容，用来触发离线评测调用。",
            "gold_label": "可信新闻",
        }

        result = run_single_detection(
            db=object(),
            row=row,
            allow_web_search_global=False,
            retries=0,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["parse_latency_ms"], 12.1)
        self.assertEqual(result["local_retrieval_latency_ms"], 23.2)
        self.assertEqual(result["web_search_latency_ms"], 34.3)
        self.assertEqual(result["llm_latency_ms"], 45.4)
        self.assertEqual(result["report_latency_ms"], 5.5)
        self.assertEqual(result["retrieval_version"], "v2")
        self.assertEqual(result["index_version"], "v2")
        self.assertEqual(result["candidate_parent_count"], 1)
        self.assertEqual(result["candidate_chunk_count"], 2)
        self.assertEqual(result["retrieved_chunk_ids"], "knowledge:7:chunk:0,knowledge:7:chunk:1")
