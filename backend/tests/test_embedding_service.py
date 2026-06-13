import importlib
import json
import math
import os
import unittest
from unittest.mock import patch

from app.core.config import DEFAULT_EMBEDDING_DIMENSION, Settings, get_settings
from app.services import embedding_service
from app.services.embedding_service import (
    DeepSeekEmbeddingError,
    DashScopeEmbeddingError,
    embed_text,
    embed_texts,
)


class EmbeddingServiceTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    # ------------------------------------------------------------------
    # settings / dimension
    # ------------------------------------------------------------------

    def test_default_settings_use_dashscope_embedding_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        self.assertEqual(settings.embedding_provider, "dashscope")
        self.assertEqual(settings.embedding_dimension, DEFAULT_EMBEDDING_DIMENSION)
        self.assertEqual(settings.dashscope_embedding_model, "text-embedding-v4")

    def test_settings_reads_explicit_embedding_dimension(self) -> None:
        with patch.dict(os.environ, {"EMBEDDING_DIMENSION": "384"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.embedding_dimension, 384)

    def test_settings_reads_deepseek_embedding_model(self) -> None:
        with patch.dict(
            os.environ,
            {"DEEPSEEK_EMBEDDING_MODEL": "custom-embedding-model"},
            clear=True,
        ):
            settings = Settings()

        self.assertEqual(settings.deepseek_embedding_model, "custom-embedding-model")

    def test_settings_reads_dashscope_embedding_model(self) -> None:
        with patch.dict(
            os.environ,
            {"DASHSCOPE_EMBEDDING_MODEL": "custom-dashscope-embedding"},
            clear=True,
        ):
            settings = Settings()

        self.assertEqual(settings.dashscope_embedding_model, "custom-dashscope-embedding")

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

    # ------------------------------------------------------------------
    # hash provider
    # ------------------------------------------------------------------

    def test_embed_text_is_deterministic_and_normalized(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            first = embed_text("可信 新闻")
            second = embed_text("可信 新闻")

        self.assertEqual(len(first), 384)
        self.assertEqual(first, second)
        norm = math.sqrt(sum(value * value for value in first))
        self.assertAlmostEqual(norm, 1.0)

    def test_embed_empty_text_returns_zero_vector(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            vector = embed_text("   \n\n")

        self.assertEqual(len(vector), 384)
        self.assertTrue(all(value == 0.0 for value in vector))

    def test_embed_text_rejects_non_positive_dimension(self) -> None:
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "hash"}, clear=True):
            get_settings.cache_clear()
            with self.assertRaisesRegex(ValueError, "dimension"):
                embed_text("semantic news", dimension=0)

    def test_embed_texts_handles_multiple_inputs(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "hash", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            vectors = embed_texts(["title one", "title two"])

        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 384)

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

    # ------------------------------------------------------------------
    # reserved provider (local) — still raises
    # ------------------------------------------------------------------

    def test_reserved_provider_does_not_silently_use_hash_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_PROVIDER": "local", "EMBEDDING_DIMENSION": "384"},
            clear=True,
        ):
            get_settings.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                embed_text("semantic news")

    # ------------------------------------------------------------------
    # deepseek provider — missing API key
    # ------------------------------------------------------------------

    def test_deepseek_provider_without_api_key_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "deepseek",
                "EMBEDDING_DIMENSION": "1024",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with self.assertRaisesRegex(DeepSeekEmbeddingError, "API Key"):
                embed_text("semantic news")

    # ------------------------------------------------------------------
    # deepseek provider — mocked API call
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mock_response(embeddings: list[list[float]]) -> bytes:
        data = [
            {"object": "embedding", "index": i, "embedding": emb}
            for i, emb in enumerate(embeddings)
        ]
        return json.dumps({
            "object": "list",
            "data": data,
            "model": "deepseek-embedding-v1",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }).encode("utf-8")

    def test_deepseek_single_text_embedding(self) -> None:
        mock_embedding = [0.1] * 1024
        mock_response = self._build_mock_response([mock_embedding])

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "deepseek",
                "EMBEDDING_DIMENSION": "1024",
                "DEEPSEEK_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                return_value=FakeResponse(mock_response),
            ):
                vector = embed_text("测试新闻标题")

        self.assertEqual(len(vector), 1024)
        self.assertEqual(vector, mock_embedding)

    def test_deepseek_batch_embedding(self) -> None:
        mock_embeddings = [[0.1 * (i + 1)] * 1024 for i in range(3)]
        mock_response = self._build_mock_response(mock_embeddings)

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "deepseek",
                "EMBEDDING_DIMENSION": "1024",
                "DEEPSEEK_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                return_value=FakeResponse(mock_response),
            ):
                vectors = embed_texts(["标题一", "标题二", "标题三"])

        self.assertEqual(len(vectors), 3)
        for i, vector in enumerate(vectors):
            self.assertEqual(len(vector), 1024)
            self.assertEqual(vector, mock_embeddings[i])

    def test_deepseek_handles_api_error(self) -> None:
        error_body = json.dumps({
            "error": {"message": "Invalid API Key", "code": "auth_error"}
        }).encode("utf-8")

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "deepseek",
                "EMBEDDING_DIMENSION": "1024",
                "DEEPSEEK_API_KEY": "sk-invalid",
            },
            clear=True,
        ):
            get_settings.cache_clear()

            def raise_http_error(*_args: object, **_kwargs: object) -> None:
                raise embedding_service.urllib.error.HTTPError(
                    url="https://api.deepseek.com/v1/embeddings",
                    code=401,
                    msg="Unauthorized",
                    hdrs={},
                    fp=FakeResponse(error_body),
                )

            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                side_effect=raise_http_error,
            ):
                with self.assertRaisesRegex(DeepSeekEmbeddingError, "HTTP 401"):
                    embed_text("test")

    # ------------------------------------------------------------------
    # dashscope provider — missing API key
    # ------------------------------------------------------------------

    def test_dashscope_provider_without_api_key_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "dashscope",
                "EMBEDDING_DIMENSION": "1024",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with self.assertRaisesRegex(DashScopeEmbeddingError, "API Key"):
                embed_text("semantic news")

    # ------------------------------------------------------------------
    # dashscope provider — mocked OpenAI-compatible API call
    # ------------------------------------------------------------------

    def test_dashscope_single_text_embedding(self) -> None:
        mock_embedding = [0.2] * 1024
        mock_response = self._build_mock_response([mock_embedding])

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "dashscope",
                "EMBEDDING_DIMENSION": "1024",
                "DASHSCOPE_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                return_value=FakeResponse(mock_response),
            ) as mocked_urlopen:
                vector = embed_text("测试新闻标题")

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url,
            "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        )
        self.assertEqual(payload["model"], "text-embedding-v4")
        self.assertEqual(payload["dimensions"], 1024)
        self.assertEqual(len(vector), 1024)
        self.assertEqual(vector, mock_embedding)

    def test_dashscope_batch_embedding(self) -> None:
        mock_embeddings = [[0.2 * (i + 1)] * 1024 for i in range(3)]
        mock_response = self._build_mock_response(mock_embeddings)

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "dashscope",
                "EMBEDDING_DIMENSION": "1024",
                "DASHSCOPE_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                return_value=FakeResponse(mock_response),
            ):
                vectors = embed_texts(["标题一", "标题二", "标题三"])

        self.assertEqual(len(vectors), 3)
        for i, vector in enumerate(vectors):
            self.assertEqual(len(vector), 1024)
            self.assertEqual(vector, mock_embeddings[i])

    def test_dashscope_handles_api_error(self) -> None:
        error_body = json.dumps({
            "error": {"message": "Invalid API Key", "code": "InvalidApiKey"}
        }).encode("utf-8")

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "dashscope",
                "EMBEDDING_DIMENSION": "1024",
                "DASHSCOPE_API_KEY": "sk-invalid",
            },
            clear=True,
        ):
            get_settings.cache_clear()

            def raise_http_error(*_args: object, **_kwargs: object) -> None:
                raise embedding_service.urllib.error.HTTPError(
                    url="https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
                    code=401,
                    msg="Unauthorized",
                    hdrs={},
                    fp=FakeResponse(error_body),
                )

            with patch.object(
                embedding_service.urllib.request,
                "urlopen",
                side_effect=raise_http_error,
            ):
                with self.assertRaisesRegex(DashScopeEmbeddingError, "HTTP 401"):
                    embed_text("test")


class FakeResponse:
    """Minimal file-like object that returns preset bytes on read()."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


if __name__ == "__main__":
    unittest.main()
