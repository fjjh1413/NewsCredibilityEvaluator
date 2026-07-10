import unittest
from types import SimpleNamespace

from app.services.rag.chunker import build_knowledge_chunks, split_text


class RagChunkerTestCase(unittest.TestCase):
    def test_split_text_prefers_paragraphs_and_keeps_overlap(self) -> None:
        text = "第一段内容很长。" * 20 + "\n\n" + "第二段也很长。" * 20

        chunks = split_text(text, chunk_size=120, chunk_overlap=20)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 140 for chunk in chunks))
        self.assertTrue(all(chunk.strip() for chunk in chunks))
        self.assertIn(chunks[0][-20:], chunks[1])

    def test_build_knowledge_chunks_creates_typed_parent_aware_chunks(self) -> None:
        item = SimpleNamespace(
            id=7,
            title="  权威通报标题 ",
            content=("正文第一段。" * 50) + "\n\n" + ("正文第二段。" * 40),
            category="society",
            truth_label="false",
            source_name="官方平台",
            source_url="https://example.com/news/7",
            publish_time=None,
            summary="这是一段摘要",
            keywords="通报, 辟谣",
            debunking_explanation="经核查，该消息不实。",
            risk_level="high",
        )

        chunks = build_knowledge_chunks(item, chunk_size=180, chunk_overlap=30)

        self.assertGreaterEqual(len(chunks), 4)
        self.assertEqual(chunks[0].knowledge_id, 7)
        self.assertEqual(chunks[0].chunk_id, "knowledge:7:chunk:0")
        self.assertEqual(chunks[0].chunk_type, "title_summary")
        self.assertTrue(any(chunk.chunk_type == "content" for chunk in chunks))
        self.assertTrue(any(chunk.chunk_type == "debunking" for chunk in chunks))
        self.assertTrue(all(chunk.parent_title == "权威通报标题" for chunk in chunks))
        self.assertTrue(all(chunk.index_version == "v2" for chunk in chunks))

    def test_build_knowledge_chunks_handles_sparse_items(self) -> None:
        item = {"id": 9, "title": "标题", "content": "", "truth_label": "true"}

        chunks = build_knowledge_chunks(item, chunk_size=100, chunk_overlap=20)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_type, "title_summary")
        self.assertIn("title: 标题", chunks[0].chunk_text)


if __name__ == "__main__":
    unittest.main()
