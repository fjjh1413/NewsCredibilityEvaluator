"""Unit tests for web_search_service — RAG quality evaluation, query building,
and evidence merging logic (no external API calls)."""

import datetime
import unittest

from app.services.web.web_search_service import (
    RAG_MIN_SIMILARITY,
    RAG_TOP1_THRESHOLD,
    _is_positive_int,
    _normalize_publish_time,
    _normalize_url,
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
    """Tests for the candidate‑pool merge_evidence function.

    The new contract:
    - No rank_order on candidates.
    - No fuzzy‑title dedup — only strong‑identity dedup within each source.
    - No cross‑source dedup.
    - Input objects are never mutated.
    - Limits are applied after dedup, per source.
    - candidate_id is generated after dedup + limits.
    """

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _rag(title="RAG title", knowledge_id=1, similarity_score=0.9,
             source_name="source_a", source_url=None, publish_time=None,
             rank_order=None, summary="summary"):
        item: dict = {
            "title": title,
            "knowledge_id": knowledge_id,
            "summary": summary,
            "source_name": source_name,
            "similarity_score": similarity_score,
        }
        if source_url is not None:
            item["source_url"] = source_url
        if publish_time is not None:
            item["publish_time"] = publish_time
        if rank_order is not None:
            item["rank_order"] = rank_order
        return item

    @staticmethod
    def _web(title="Web title", url="https://example.com/news",
             site_name="example.com", date_published="2025-01-01",
             similarity_score=0.7, summary="web summary"):
        return WebEvidenceItem(
            title=title,
            url=url,
            summary=summary,
            site_name=site_name,
            date_published=date_published,
            similarity_score=similarity_score,
        )

    # ── no rank_order on candidates ─────────────────────────────────

    def test_candidates_have_no_rank_order(self):
        merged = merge_evidence(
            [self._rag()],
            [self._web()],
        )
        self.assertEqual(len(merged), 2)
        for item in merged:
            self.assertNotIn("rank_order", item, f"candidate should not have rank_order: {item.get('candidate_id')}")

    # ── candidate_id present and unique ──────────────────────────────

    def test_candidate_id_present_and_unique(self):
        merged = merge_evidence(
            [self._rag(knowledge_id=1), self._rag(knowledge_id=2)],
            [self._web(url="https://a.com"), self._web(url="https://b.com")],
        )
        ids = [item["candidate_id"] for item in merged]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate candidate_ids: {ids}")
        for cid in ids:
            self.assertTrue(isinstance(cid, str) and cid, f"empty candidate_id")
        # RAG with knowledge_id
        self.assertIn("kb:1", ids)
        self.assertIn("kb:2", ids)
        # Web
        self.assertTrue(any(cid.startswith("web:") for cid in ids))

    # ── no cross‑source dedup ────────────────────────────────────────

    def test_similar_title_across_sources_both_preserved(self):
        """Titles that look similar but come from different sources are kept."""
        merged = merge_evidence(
            [self._rag(title="某地发生地震")],
            [self._web(title="某地发生地震，官方通报最新伤亡情况")],
        )
        self.assertEqual(len(merged), 2)

    def test_identical_title_across_sources_both_preserved(self):
        merged = merge_evidence(
            [self._rag(title="完全相同的标题")],
            [self._web(title="完全相同的标题", url="https://x.com/1")],
        )
        self.assertEqual(len(merged), 2)

    # ── strong‑identity dedup within RAG ─────────────────────────────

    def test_rag_same_knowledge_id_deduped(self):
        merged = merge_evidence(
            [self._rag(knowledge_id=5, title="A"), self._rag(knowledge_id=5, title="B")],
            [],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["knowledge_id"], 5)

    def test_rag_same_url_deduped(self):
        merged = merge_evidence(
            [
                self._rag(knowledge_id=None, source_url="https://x.com/a", title="T1"),
                self._rag(knowledge_id=None, source_url="https://x.com/a", title="T2"),
            ],
            [],
        )
        self.assertEqual(len(merged), 1)

    def test_rag_same_title_source_publish_time_deduped(self):
        merged = merge_evidence(
            [
                self._rag(knowledge_id=None, title="T", source_name="S",
                          publish_time="2025-01-01"),
                self._rag(knowledge_id=None, title="T", source_name="S",
                          publish_time="2025-01-01"),
            ],
            [],
        )
        self.assertEqual(len(merged), 1)

    def test_rag_same_title_source_different_publish_time_both_kept(self):
        merged = merge_evidence(
            [
                self._rag(knowledge_id=None, title="T", source_name="S",
                          publish_time="2025-01-01"),
                self._rag(knowledge_id=None, title="T", source_name="S",
                          publish_time="2025-06-01"),
            ],
            [],
        )
        self.assertEqual(len(merged), 2)

    def test_rag_empty_identity_not_deduped(self):
        """All-empty title/source/publish_time must not dedup each other."""
        merged = merge_evidence(
            [
                self._rag(knowledge_id=None, title=""),
                self._rag(knowledge_id=None, title=""),
            ],
            [],
        )
        self.assertEqual(len(merged), 2)

    def test_rag_only_title_same_not_deduped(self):
        """title-only match (no source_name, no publish_time) is not deduped."""
        merged = merge_evidence(
            [
                self._rag(knowledge_id=None, title="SameTitle", source_name=""),
                self._rag(knowledge_id=None, title="SameTitle", source_name=""),
            ],
            [],
        )
        self.assertEqual(len(merged), 2)

    # ── strong‑identity dedup within Web ─────────────────────────────

    def test_web_same_url_deduped(self):
        merged = merge_evidence(
            [],
            [
                self._web(url="https://example.com/news/1", title="T1"),
                self._web(url="https://example.com/news/1", title="T2"),
            ],
        )
        self.assertEqual(len(merged), 1)

    def test_web_url_host_case_insensitive_dedup(self):
        merged = merge_evidence(
            [],
            [
                self._web(url="https://EXAMPLE.COM/news"),
                self._web(url="https://example.com/news"),
            ],
        )
        self.assertEqual(len(merged), 1)

    def test_web_url_path_case_preserved_not_merged(self):
        """Path case differences must NOT be merged."""
        merged = merge_evidence(
            [],
            [
                self._web(url="https://x.com/News"),
                self._web(url="https://x.com/news"),
            ],
        )
        self.assertEqual(len(merged), 2)

    def test_web_same_title_source_date_deduped(self):
        merged = merge_evidence(
            [],
            [
                self._web(title="T", site_name="S", date_published="2025-01-01",
                          url=""),
                self._web(title="T", site_name="S", date_published="2025-01-01",
                          url=""),
            ],
        )
        self.assertEqual(len(merged), 1)

    def test_web_only_title_similar_not_deduped(self):
        merged = merge_evidence(
            [],
            [
                self._web(title="Something happened", site_name="", date_published="",
                          url=""),
                self._web(title="Something happened, officials respond", site_name="",
                          date_published="", url=""),
            ],
        )
        self.assertEqual(len(merged), 2)

    def test_web_empty_identity_not_deduped(self):
        merged = merge_evidence(
            [],
            [
                self._web(title="", site_name="", date_published="", url=""),
                self._web(title="", site_name="", date_published="", url=""),
            ],
        )
        self.assertEqual(len(merged), 2)

    # ── limits applied correctly ─────────────────────────────────────

    def test_rag_limit_respected(self):
        items = [self._rag(knowledge_id=i) for i in range(1, 8)]
        merged = merge_evidence(items, [], rag_limit=3)
        rag_count = sum(1 for i in merged if i["source_type"] == "knowledge_base")
        self.assertLessEqual(rag_count, 3)
        self.assertEqual(rag_count, 3)

    def test_web_limit_respected(self):
        items = [self._web(url=f"https://x.com/{i}") for i in range(1, 8)]
        merged = merge_evidence([], items, web_limit=4)
        web_count = sum(1 for i in merged if i["source_type"] == "web_search")
        self.assertLessEqual(web_count, 4)
        self.assertEqual(web_count, 4)

    def test_duplicate_rag_does_not_consume_limit(self):
        """Duplicate (same knowledge_id) RAG should be removed, freeing slots."""
        items = [
            self._rag(knowledge_id=1, title="A"),
            self._rag(knowledge_id=1, title="A dup"),
            self._rag(knowledge_id=2, title="B"),
            self._rag(knowledge_id=3, title="C"),
        ]
        merged = merge_evidence(items, [], rag_limit=3)
        # 4 input → 1 duplicate removed → 3 unique → limit 3 → all 3 fit
        rag_count = sum(1 for i in merged if i["source_type"] == "knowledge_base")
        self.assertEqual(rag_count, 3)

    def test_duplicate_web_does_not_consume_limit(self):
        items = [
            self._web(url="https://x.com/1"),
            self._web(url="https://x.com/1"),  # dup
            self._web(url="https://x.com/2"),
            self._web(url="https://x.com/3"),
        ]
        merged = merge_evidence([], items, web_limit=3)
        web_count = sum(1 for i in merged if i["source_type"] == "web_search")
        self.assertEqual(web_count, 3)

    # ── limit validation ─────────────────────────────────────────────

    def test_negative_rag_limit_rejected(self):
        with self.assertRaises(ValueError):
            merge_evidence([], [], rag_limit=-1)

    def test_negative_web_limit_rejected(self):
        with self.assertRaises(ValueError):
            merge_evidence([], [], web_limit=-1)

    # ── raw_rank_order correctness ───────────────────────────────────

    def test_web_raw_rank_order_equals_original_web_idx(self):
        merged = merge_evidence(
            [],
            [
                self._web(url="https://a.com"),
                self._web(url="https://b.com"),
                self._web(url="https://c.com"),
            ],
        )
        for item in merged:
            cid = item["candidate_id"]
            # web:1 → raw_rank_order 1, web:2 → 2, etc.
            if cid.startswith("web:"):
                expected = int(cid.split(":")[1])
                self.assertEqual(
                    item["raw_rank_order"], expected,
                    f"{cid} raw_rank_order {item['raw_rank_order']} != {expected}"
                )

    def test_rag_raw_rank_order_preserves_original(self):
        merged = merge_evidence(
            [
                self._rag(knowledge_id=10, rank_order=3),
                self._rag(knowledge_id=20, rank_order=7),
            ],
            [],
        )
        # Sort by raw_rank_order for stable assertion
        by_raw = sorted(merged, key=lambda i: i["raw_rank_order"])
        self.assertEqual(by_raw[0]["raw_rank_order"], 3)
        self.assertEqual(by_raw[1]["raw_rank_order"], 7)

    def test_rag_raw_rank_order_falls_back_to_rag_idx(self):
        merged = merge_evidence(
            [self._rag(knowledge_id=1, rank_order=None)],
            [],
        )
        self.assertEqual(merged[0]["raw_rank_order"], 1)

    def test_rag_raw_rank_order_with_true_falls_back(self):
        """bool True is not a positive int; should fall back to rag_idx."""
        merged = merge_evidence(
            [{"title": "T", "knowledge_id": 1, "similarity_score": 0.8,
              "rank_order": True}],
            [],
        )
        self.assertIsNotNone(merged[0].get("raw_rank_order"))

    # ── knowledge_id safety ──────────────────────────────────────────

    def test_knowledge_id_true_not_treated_as_int(self):
        """bool True must NOT generate candidate_id kb:True."""
        merged = merge_evidence(
            [{"title": "T", "knowledge_id": True, "similarity_score": 0.8}],
            [],
        )
        cid = merged[0]["candidate_id"]
        self.assertTrue(cid.startswith("kb:rag:"), f"unexpected cid: {cid}")

    # ── field preservation ───────────────────────────────────────────

    def test_rag_publish_time_preserved(self):
        merged = merge_evidence(
            [self._rag(knowledge_id=1, publish_time="2025-03-15")],
            [],
        )
        self.assertEqual(merged[0].get("publish_time"), "2025-03-15")

    def test_rag_source_url_preserved(self):
        merged = merge_evidence(
            [self._rag(knowledge_id=1, source_url="https://example.com/rag")],
            [],
        )
        self.assertEqual(merged[0]["source_url"], "https://example.com/rag")

    # ── no similarity_score sorting ──────────────────────────────────

    def test_no_similarity_score_sorting(self):
        merged = merge_evidence(
            [
                self._rag(knowledge_id=1, similarity_score=0.3),
                self._rag(knowledge_id=2, similarity_score=0.9),
                self._rag(knowledge_id=3, similarity_score=0.5),
            ],
            [],
        )
        # The list order should not be sorted by similarity_score
        scores = [item["similarity_score"] for item in merged]
        self.assertNotEqual(scores, sorted(scores, reverse=True),
                            "candidates should not be sorted by similarity_score")

    # ── input not mutated ────────────────────────────────────────────

    def test_rag_input_not_mutated(self):
        original = {"title": "Orig", "knowledge_id": 42, "similarity_score": 0.8}
        rag = [dict(original)]
        merge_evidence(rag, [])
        self.assertEqual(rag[0], original)
        self.assertNotIn("source_type", rag[0])
        self.assertNotIn("candidate_id", rag[0])

    def test_web_input_not_mutated(self):
        web_item = self._web(title="W", url="https://x.com/w")
        web = [web_item]
        merge_evidence([], web)
        # WebEvidenceItem is a Pydantic model; we check its fields
        self.assertEqual(web[0].title, "W")
        self.assertNotIn("candidate_id", web[0].model_dump() if hasattr(web[0], "model_dump") else {})

    # ── normalization helpers ────────────────────────────────────────

    def test_normalize_publish_time_none(self):
        self.assertEqual(_normalize_publish_time(None), "")

    def test_normalize_publish_time_datetime(self):
        result = _normalize_publish_time(datetime.datetime(2025, 1, 1, 12, 0, 0))
        self.assertIsInstance(result, str)
        self.assertIn("2025", result)

    def test_normalize_publish_time_string(self):
        result = _normalize_publish_time("2025-01-01")
        self.assertEqual(result, "2025-01-01")

    def test_normalize_url_non_string(self):
        self.assertEqual(_normalize_url(None), "")
        self.assertEqual(_normalize_url(42), "")
        self.assertEqual(_normalize_url(True), "")

    def test_normalize_url_relative_rejected(self):
        self.assertEqual(_normalize_url("/path/only"), "")

    def test_normalize_url_query_preserved(self):
        key = _normalize_url("https://x.com/p?q=A&B")
        self.assertIn("?q=A&B", key)

    def test_normalize_url_trailing_slash_stripped(self):
        key = _normalize_url("https://x.com/page/")
        self.assertEqual(key, "https://x.com/page")

    def test_normalize_url_root_path_slash_kept(self):
        key = _normalize_url("https://x.com/")
        self.assertEqual(key, "https://x.com/")

    # ── empty inputs ─────────────────────────────────────────────────

    def test_empty_web(self):
        rag = [{"title": "证据", "knowledge_id": 1, "similarity_score": 0.9}]
        merged = merge_evidence(rag, [])
        self.assertEqual(len(merged), 1)

    def test_empty_both(self):
        merged = merge_evidence([], [])
        self.assertEqual(len(merged), 0)

    def test_empty_rag_with_web(self):
        merged = merge_evidence([], [self._web()])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source_type"], "web_search")


if __name__ == "__main__":
    unittest.main()
