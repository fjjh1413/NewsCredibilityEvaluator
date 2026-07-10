from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path


class Chapter6ArtifactTests(unittest.TestCase):
    def test_embedded_knowledge_text_is_traced_to_samples(self) -> None:
        from evaluation.scripts.chapter6.generate_audit_reports import detect_embedded_knowledge

        news_rows = [
            {"sample_id": "S1", "content": "前文。知识条目中的完整事实句。后文。"},
            {"sample_id": "S2", "content": "另一条没有重合的新闻。"},
        ]
        knowledge_rows = [
            {"knowledge_id": "K1", "content": "知识条目中的完整事实句。"},
        ]

        matches = detect_embedded_knowledge(news_rows, knowledge_rows)

        self.assertEqual(matches, [{"sample_id": "S1", "knowledge_id": "K1"}])

    def test_secret_fields_are_redacted_recursively(self) -> None:
        from evaluation.scripts.chapter6.generate_audit_reports import redact_secrets

        source = {
            "model": "deepseek-chat",
            "api_key": "secret-value",
            "nested": {"database_password": "password-value", "timeout": 30},
        }

        result = redact_secrets(source)

        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["nested"]["database_password"], "[REDACTED]")
        self.assertEqual(result["nested"]["timeout"], 30)
        self.assertNotIn("secret-value", str(result))

    def test_notes_resolve_dynamic_test_counts_in_their_own_scope(self) -> None:
        from evaluation.scripts.chapter6.compose_chapter import build_notes

        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            results = run_dir / "results"
            results.mkdir(parents=True)
            with (results / "test_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["test_group", "passed", "failed", "status"])
                writer.writeheader()
                writer.writerows([
                    {"test_group": "后端自动化测试", "passed": "392", "failed": "0", "status": "通过"},
                    {"test_group": "评测模块测试", "passed": "96", "failed": "0", "status": "通过"},
                    {"test_group": "前端测试", "passed": "14", "failed": "0", "status": "通过"},
                ])
            with (results / "requirements_traceability.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["requirement_id", "conclusion"])
                writer.writeheader()
                writer.writerow({"requirement_id": "FR-U01", "conclusion": "通过"})

            notes = build_notes(Path(directory), run_dir, Path("source.docx"), Path("output.docx"))

            self.assertIn("392项后端测试", notes)
            self.assertIn("96项评测测试", notes)
            self.assertIn("14项前端测试", notes)


if __name__ == "__main__":
    unittest.main()
