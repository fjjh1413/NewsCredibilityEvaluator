import math
import unittest

from app.services.embedding_service import EMBEDDING_DIMENSION, embed_text, embed_texts


class EmbeddingServiceTestCase(unittest.TestCase):
    def test_embed_text_is_deterministic_and_normalized(self) -> None:
        first = embed_text("可信 新闻")
        second = embed_text("可信 新闻")

        self.assertEqual(len(first), EMBEDDING_DIMENSION)
        self.assertEqual(first, second)
        norm = math.sqrt(sum(value * value for value in first))
        self.assertAlmostEqual(norm, 1.0)

    def test_embed_empty_text_returns_zero_vector(self) -> None:
        vector = embed_text("   \n\n")

        self.assertEqual(len(vector), EMBEDDING_DIMENSION)
        self.assertTrue(all(value == 0.0 for value in vector))

    def test_embed_texts_handles_multiple_inputs(self) -> None:
        vectors = embed_texts(["title one", "title two"])

        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), EMBEDDING_DIMENSION)


if __name__ == "__main__":
    unittest.main()
