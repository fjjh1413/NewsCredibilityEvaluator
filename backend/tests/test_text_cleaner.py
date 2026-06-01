import unittest
from types import SimpleNamespace

from app.services.knowledge_service import build_knowledge_embedding_text
from app.utils.text_cleaner import clean_text


class TextCleanerTestCase(unittest.TestCase):
    def test_clean_text_handles_none_spaces_newlines_and_length(self) -> None:
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text("  hello   world  \n\n\n next\tline  "), "hello world\nnext line")
        self.assertEqual(clean_text("abcdef", max_length=3), "abc")

    def test_build_knowledge_embedding_text_handles_missing_fields(self) -> None:
        item = SimpleNamespace(
            title="  Test   title ",
            content="Line 1\n\n\nLine   2",
            category=None,
            summary=" Short summary ",
            keywords="alpha,  beta",
            truth_label="credible",
        )

        text = build_knowledge_embedding_text(item)

        self.assertIn("title: Test title", text)
        self.assertIn("content: Line 1\nLine 2", text)
        self.assertIn("summary: Short summary", text)
        self.assertIn("keywords: alpha, beta", text)
        self.assertIn("truth_label: credible", text)
        self.assertNotIn("None", text)

    def test_build_knowledge_embedding_text_supports_dict_and_limit(self) -> None:
        item = {
            "title": "Title",
            "content": "abcdef",
            "truth_label": "suspicious",
        }

        text = build_knowledge_embedding_text(item, max_length=20)

        self.assertEqual(text, "title: Title\ncontent")


if __name__ == "__main__":
    unittest.main()
