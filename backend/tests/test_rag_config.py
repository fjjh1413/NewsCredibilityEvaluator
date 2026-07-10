import os
import unittest
from unittest.mock import patch

from app.core.config import get_settings


class RagConfigTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_rag_config_defaults_to_v1_with_safe_chunk_settings(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()

            settings = get_settings()

        self.assertEqual(settings.rag_index_version, "v1")
        self.assertFalse(settings.rag_retrieval_debug)
        self.assertEqual(settings.rag_chunk_size, 700)
        self.assertEqual(settings.rag_chunk_overlap, 100)
        self.assertEqual(settings.rag_dense_top_n, 50)
        self.assertEqual(settings.rag_parent_top_k, 15)
        self.assertEqual(settings.rag_chunks_per_parent, 2)

    def test_rag_index_version_rejects_unknown_values(self) -> None:
        with patch.dict(os.environ, {"RAG_INDEX_VERSION": "experimental"}, clear=True):
            get_settings.cache_clear()

            settings = get_settings()

        self.assertEqual(settings.rag_index_version, "v1")

    def test_rag_config_reads_explicit_values(self) -> None:
        env = {
            "RAG_INDEX_VERSION": "hybrid",
            "RAG_RETRIEVAL_DEBUG": "true",
            "RAG_CHUNK_SIZE": "900",
            "RAG_CHUNK_OVERLAP": "120",
            "RAG_DENSE_TOP_N": "40",
            "RAG_PARENT_TOP_K": "12",
            "RAG_CHUNKS_PER_PARENT": "3",
            "RAG_LEXICAL_ENABLED": "false",
            "RAG_MMR_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            get_settings.cache_clear()

            settings = get_settings()

        self.assertEqual(settings.rag_index_version, "hybrid")
        self.assertTrue(settings.rag_retrieval_debug)
        self.assertEqual(settings.rag_chunk_size, 900)
        self.assertEqual(settings.rag_chunk_overlap, 120)
        self.assertEqual(settings.rag_dense_top_n, 40)
        self.assertEqual(settings.rag_parent_top_k, 12)
        self.assertEqual(settings.rag_chunks_per_parent, 3)
        self.assertFalse(settings.rag_lexical_enabled)
        self.assertFalse(settings.rag_mmr_enabled)


if __name__ == "__main__":
    unittest.main()
