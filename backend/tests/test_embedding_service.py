import importlib
import math
import os
import unittest
from unittest.mock import patch

from app.core.config import DEFAULT_EMBEDDING_DIMENSION, Settings, get_settings
from app.services import embedding_service
from app.services.embedding_service import embed_text, embed_texts


class EmbeddingServiceTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_default_settings_use_hash_embedding_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        self.assertEqual(settings.embedding_provider, "hash")
        self.assertEqual(settings.embedding_dimension, DEFAULT_EMBEDDING_DIMENSION)

    def test_settings_reads_explicit_embedding_dimension(self) -> None:
        with patch.dict(os.environ, {"EMBEDDING_DIMENSION": "384"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.embedding_dimension, 384)

    def test_embedding_dimension_constant_reads_settings_on_import(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "128"},
            clear=True,
        ):
            get_settings.cache_clear()
            reloaded_service = importlib.reload(embedding_service)

        self.assertEqual(reloaded_service.EMBEDDING_DIMENSION, 128)
        get_settings.cache_clear()
        importlib.reload(embedding_service)

    def test_embed_text_is_deterministic_and_normalized(self) -> None:
        first = embed_text("可信 新闻")
        second = embed_text("可信 新闻")

        self.assertEqual(len(first), DEFAULT_EMBEDDING_DIMENSION)
        self.assertEqual(first, second)
        norm = math.sqrt(sum(value * value for value in first))
        self.assertAlmostEqual(norm, 1.0)

    def test_embed_empty_text_returns_zero_vector(self) -> None:
        vector = embed_text("   \n\n")

        self.assertEqual(len(vector), DEFAULT_EMBEDDING_DIMENSION)
        self.assertTrue(all(value == 0.0 for value in vector))

    def test_embed_text_rejects_non_positive_dimension(self) -> None:
        with self.assertRaisesRegex(ValueError, "dimension"):
            embed_text("semantic news", dimension=0)

    def test_embed_texts_handles_multiple_inputs(self) -> None:
        vectors = embed_texts(["title one", "title two"])

        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), DEFAULT_EMBEDDING_DIMENSION)

    def test_hash_provider_runs_with_explicit_default_dimension(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            vector = embed_text("semantic news")

        self.assertEqual(len(vector), 384)

    def test_hash_provider_uses_configured_dimension_by_default(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "128"},
            clear=True,
        ):
            get_settings.cache_clear()
            vector = embed_text("semantic news")

        self.assertEqual(len(vector), 128)

    def test_reserved_provider_does_not_silently_use_hash_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "deepseek", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                embed_text("semantic news")


if __name__ == "__main__":
    unittest.main()
