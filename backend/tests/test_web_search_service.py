"""Unit tests for web_search_service — RAG quality evaluation, query building,
and evidence merging logic (no external API calls)."""

import unittest

from app.services.web.web_search_service import (
    RAG_MIN_SIMILARITY,
    RAG_TOP1_THRESHOLD,
    build_search_query,
    merge_evidence,
    should_trigger_web_search,
)
from app.schemas.web_search import WebEvidenceItem


class ShouldTriggerWebSearchTests(unittest.TestCase):
    def test_disabled_when_flag_is_false(self):
        self.assertFalse(
            should_trigger_web_search(
                [{"similarity_score": 0.1}],
                enable_web_search=False,
            )
        )

    def test_triggers_when_no_evidence(self):
        self.assertTrue(
            should_trigger_web_search([], enable_web_search=True)
        )

    def test_triggers_when_top1_below_threshold(self):
        self.assertTrue(
            should_trigger_web_search(
                [{"similarity_score": RAG_TOP1_THRESHOLD - 0.1}],
                enable_web_search=True,
            )
        )

    def test_skips_when_top1_high(self):
        self.assertFalse(
            should_trigger_web_search(
                [{"similarity_score": 0.85}],
                enable_web_search=True,
            )
        )

    def test_triggers_when_moderate_and_few_meaningful_results(self):
        # Only 1 result above RAG_MIN_SIMILARITY (0.3) → triggers
        self.assertTrue(
            should_trigger_web_search(
                [
                    {"similarity_score": 0.50},
                    {"similarity_score": 0.25},  # below RAG_MIN_SIMILARITY → ignored
                ],
                enable_web_search=True,
            )
        )

    def test_skips_when_moderate_but_many_meaningful_results(self):
        # All 3 above RAG_MIN_SIMILARITY (0.3), so no trigger
        self.assertFalse(
            should_trigger_web_search(
                [
                    {"similarity_score": 0.55},
                    {"similarity_score": 0.50},
                    {"similarity_score": 0.45},
                ],
                enable_web_search=True,
            )
        )


class BuildSearchQueryTests(unittest.TestCase):
    def test_title_only(self):
        query = build_search_query("网传某地出现异常天气", [])
        self.assertIn("网传某地出现异常天气", query)

    def test_title_with_keywords(self):
        query = build_search_query("某新闻标题", ["辟谣", "官方", "通报"])
        self.assertIn("某新闻标题", query)
        self.assertIn("辟谣", query)

    def test_empty(self):
        self.assertEqual("", build_search_query("", []))

    def test_truncates_long_title(self):
        long_title = "非常长的标题" * 30
        query = build_search_query(long_title, ["关键词"])
        self.assertLessEqual(len(query), 130)  # 100 + space + keywords


class MergeEvidenceTests(unittest.TestCase):
    def test_rag_first_web_second(self):
        rag = [
            {"title": "RAG证据1", "summary": "摘要1", "similarity_score": 0.9}
        ]
        web = [
            WebEvidenceItem(
                title="网络证据1",
                summary="网络摘要1",
                site_name="example.com",
                url="https://example.com",
                similarity_score=0.7,
            )
        ]
        merged = merge_evidence(rag, web)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["title"], "RAG证据1")
        self.assertEqual(merged[0]["source_type"], "knowledge_base")
        self.assertEqual(merged[1]["title"], "网络证据1")
        self.assertEqual(merged[1]["source_type"], "web_search")
        # rank_order assigned
        self.assertEqual(merged[0]["rank_order"], 1)
        self.assertEqual(merged[1]["rank_order"], 2)

    def test_dedup_web_by_title(self):
        rag = [{"title": "某地出现异常天气官方回应", "similarity_score": 0.8}]
        web = [
            WebEvidenceItem(
                title="某地出现异常天气，官方回应正在核查",
                summary="摘要",
                site_name="example.com",
                url="https://example.com",
                similarity_score=0.6,
            )
        ]
        merged = merge_evidence(rag, web)
        # Titles are very similar → web should be deduped
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source_type"], "knowledge_base")

    def test_empty_web(self):
        rag = [{"title": "证据", "similarity_score": 0.9}]
        merged = merge_evidence(rag, [])
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
