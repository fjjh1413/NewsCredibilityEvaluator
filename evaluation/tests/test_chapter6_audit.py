from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path


class Chapter6AuditTests(unittest.TestCase):
    def _write_csv(self, root: Path, rows: list[dict[str, str]]) -> Path:
        path = root / "news.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_analyze_news_dataset_reports_counts_without_mutating_input(self) -> None:
        from evaluation.scripts.chapter6.audit_evaluation import analyze_news_dataset

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_csv(
                root,
                [
                    {
                        "sample_id": "S1",
                        "topic_id": "T1",
                        "title": "标题甲",
                        "content": "这是长度足够的第一条测试新闻正文，用于核验只读审计逻辑。",
                        "url": "https://example.com/a",
                        "gold_label": "可信",
                        "gold_label_source": "人工规则",
                    },
                    {
                        "sample_id": "S2",
                        "topic_id": "T2",
                        "title": "标题乙",
                        "content": "这是长度足够的第二条测试新闻正文，用于核验只读审计逻辑。",
                        "url": "https://example.com/b",
                        "gold_label": "存疑",
                        "gold_label_source": "人工规则",
                    },
                ],
            )
            before = path.read_bytes()

            result = analyze_news_dataset(path, check_urls=False)

            self.assertEqual(result["summary"]["sample_count"], 2)
            self.assertEqual(result["summary"]["label_counts"], {"可信": 1, "存疑": 1})
            self.assertEqual(result["summary"]["split_counts"], {"未提供": 2})
            self.assertEqual(path.read_bytes(), before)

    def test_analyze_news_dataset_flags_duplicates_invalid_labels_and_short_content(self) -> None:
        from evaluation.scripts.chapter6.audit_evaluation import analyze_news_dataset

        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(
                Path(directory),
                [
                    {
                        "sample_id": "S1",
                        "topic_id": "T1",
                        "title": "重复标题",
                        "content": "过短",
                        "url": "https://example.com/a",
                        "gold_label": "未知类别",
                        "gold_label_source": "",
                    },
                    {
                        "sample_id": "S2",
                        "topic_id": "T1",
                        "title": "重复标题",
                        "content": "过短",
                        "url": "https://example.com/a",
                        "gold_label": "可信",
                        "gold_label_source": "规则",
                    },
                ],
            )

            result = analyze_news_dataset(path, check_urls=False)
            issue_types = {row["issue_type"] for row in result["issues"]}

            self.assertIn("duplicate_url", issue_types)
            self.assertIn("duplicate_title", issue_types)
            self.assertIn("duplicate_content", issue_types)
            self.assertIn("invalid_label", issue_types)
            self.assertIn("short_content", issue_types)
            self.assertIn("missing_label_basis", issue_types)

    def test_sha256_fingerprints_are_stable(self) -> None:
        from evaluation.scripts.chapter6.audit_evaluation import sha256_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_bytes(b"unchanged")
            first = sha256_file(path)
            second = sha256_file(path)

            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)

    def test_near_duplicate_pairs_respect_threshold(self) -> None:
        from evaluation.scripts.chapter6.audit_evaluation import find_near_duplicate_pairs

        rows = [
            {"sample_id": "S1", "content": "同一事件的新闻正文版本甲，包含共同事实和少量差异。"},
            {"sample_id": "S2", "content": "同一事件的新闻正文版本乙，包含共同事实和少量差异。"},
            {"sample_id": "S3", "content": "完全不同主题的短消息。"},
        ]

        pairs = find_near_duplicate_pairs(rows, field="content", threshold=0.70)

        self.assertEqual([(item["sample_id_a"], item["sample_id_b"]) for item in pairs], [("S1", "S2")])
        self.assertGreaterEqual(pairs[0]["similarity"], 0.70)

    def test_hash_manifest_comparison_reports_changed_and_missing_inputs(self) -> None:
        from evaluation.scripts.chapter6.verify_input_hashes import compare_hash_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unchanged = root / "unchanged.txt"
            changed = root / "changed.txt"
            unchanged.write_bytes(b"same")
            changed.write_bytes(b"before")
            from evaluation.scripts.chapter6.audit_evaluation import sha256_file

            manifest = {
                "unchanged.txt": sha256_file(unchanged),
                "changed.txt": sha256_file(changed),
                "missing.txt": "0" * 64,
            }
            changed.write_bytes(b"after")

            after, rows = compare_hash_manifest(root, manifest)

            status = {row["path"]: row["status"] for row in rows}
            self.assertEqual(status["unchanged.txt"], "unchanged")
            self.assertEqual(status["changed.txt"], "changed")
            self.assertEqual(status["missing.txt"], "missing")
            self.assertEqual(after["missing.txt"], None)


if __name__ == "__main__":
    unittest.main()
