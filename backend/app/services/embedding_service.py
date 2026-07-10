import hashlib
import json
import logging
import math
import os
import re
import socket
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings
from app.core.result_cache import cache_key_from_payload, sync_json_cache
from app.utils.text_cleaner import clean_text


logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = get_settings().embedding_dimension
HASH_EMBEDDING_PROVIDER = "hash"
DEEPSEEK_EMBEDDING_PROVIDER = "deepseek"
DASHSCOPE_EMBEDDING_PROVIDER = "dashscope"
RESERVED_EMBEDDING_PROVIDERS: set[str] = {"local"}

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEEPSEEK_API_BASE_ENV = "DEEPSEEK_API_BASE"
DEEPSEEK_EMBEDDING_MODEL_ENV = "DEEPSEEK_EMBEDDING_MODEL"
DEEPSEEK_EMBEDDING_TIMEOUT_ENV = "DEEPSEEK_EMBEDDING_TIMEOUT_SECONDS"
DASHSCOPE_API_KEY_ENV = "DASHSCOPE_API_KEY"
DASHSCOPE_BASE_URL_ENV = "DASHSCOPE_BASE_URL"
DASHSCOPE_EMBEDDING_MODEL_ENV = "DASHSCOPE_EMBEDDING_MODEL"
DASHSCOPE_EMBEDDING_TIMEOUT_ENV = "DASHSCOPE_EMBEDDING_TIMEOUT_SECONDS"

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_EMBEDDING_MODEL = "deepseek-embedding-v1"
DEFAULT_DEEPSEEK_EMBEDDING_TIMEOUT = 30.0
DEFAULT_DEEPSEEK_EMBEDDING_DIMENSION = 1024
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DASHSCOPE_EMBEDDING_MODEL = "text-embedding-v4"
DEFAULT_DASHSCOPE_EMBEDDING_TIMEOUT = 30.0


class EmbeddingProviderNotConfiguredError(RuntimeError):
    """Raised when a configured embedding provider has no runnable client."""


class DeepSeekEmbeddingError(RuntimeError):
    """Raised when the DeepSeek embeddings API call fails."""


class DashScopeEmbeddingError(RuntimeError):
    """Raised when the DashScope embeddings API call fails."""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[一-鿿]|[a-zA-Z0-9_]+", text.lower())


def _resolve_dimension(dimension: int | None = None) -> int:
    resolved_dimension = (
        get_settings().embedding_dimension if dimension is None else dimension
    )
    if resolved_dimension <= 0:
        raise ValueError("dimension must be greater than 0")
    return resolved_dimension


# ---------------------------------------------------------------------------
# hash provider (demo fallback)
# ---------------------------------------------------------------------------


def _hash_embed_text(text: str, dimension: int) -> list[float]:
    """Create a deterministic demo fallback embedding.

    DEMO FALLBACK ONLY: this hash-based vector keeps local Chroma upsert/query
    paths runnable, but it does not encode semantic meaning and is not suitable
    for production RAG retrieval quality. Replace this provider with a real
    embedding model/API before using semantic search in production.
    """

    vector = [0.0] * dimension
    tokens = _tokenize(clean_text(text, max_length=None))
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [value / norm for value in vector]


# ---------------------------------------------------------------------------
# DeepSeek embeddings provider
# ---------------------------------------------------------------------------


def _load_deepseek_embedding_config() -> dict[str, Any]:
    """Read DeepSeek embedding configuration from environment variables."""
    settings = get_settings()
    base_url = clean_text(
        os.getenv(DEEPSEEK_BASE_URL_ENV)
        or os.getenv(DEEPSEEK_API_BASE_ENV)
        or DEFAULT_DEEPSEEK_BASE_URL,
        max_length=None,
    )
    api_key = clean_text(os.getenv(DEEPSEEK_API_KEY_ENV), max_length=None)
    model = clean_text(
        os.getenv(DEEPSEEK_EMBEDDING_MODEL_ENV)
        or settings.deepseek_embedding_model
        or DEFAULT_DEEPSEEK_EMBEDDING_MODEL,
        max_length=None,
    )
    timeout = _read_deepseek_embedding_timeout()
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
    }


def _read_deepseek_embedding_timeout() -> float:
    raw_value = os.getenv(DEEPSEEK_EMBEDDING_TIMEOUT_ENV)
    if not raw_value:
        return DEFAULT_DEEPSEEK_EMBEDDING_TIMEOUT
    try:
        timeout = float(raw_value)
    except ValueError:
        return DEFAULT_DEEPSEEK_EMBEDDING_TIMEOUT
    return timeout if timeout > 0 else DEFAULT_DEEPSEEK_EMBEDDING_TIMEOUT


def _build_embeddings_url(base_url: str) -> str:
    """Build the DeepSeek embeddings API URL from the configured base URL."""
    normalized = clean_text(base_url, max_length=None).rstrip("/")
    if not normalized:
        normalized = DEFAULT_DEEPSEEK_BASE_URL
    if normalized.endswith("/embeddings"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/embeddings"
    return f"{normalized}/v1/embeddings"


def _deepseek_embed_batch(texts: list[str]) -> list[list[float]]:
    """Call the DeepSeek embeddings API for a batch of texts.

    Returns a list of embedding vectors in the same order as the input texts.
    Each embedding is a list of floats with the dimension determined by the
    configured model (typically 1024 for deepseek-embedding-v1).
    """
    if not texts:
        return []

    config = _load_deepseek_embedding_config()
    if not config["api_key"]:
        raise DeepSeekEmbeddingError(
            "DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY。"
        )

    url = _build_embeddings_url(config["base_url"])
    payload = {
        "model": config["model"],
        "input": texts,
        "encoding_format": "float",
    }

    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=config["timeout"],
        ) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        message = _extract_deepseek_error_message(error_body) or clean_text(exc.reason)
        raise DeepSeekEmbeddingError(
            f"DeepSeek Embedding API HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise DeepSeekEmbeddingError(
            f"DeepSeek Embedding API 网络连接异常：{exc.reason}"
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise DeepSeekEmbeddingError(
            "DeepSeek Embedding API 请求超时"
        ) from exc
    except Exception as exc:
        raise DeepSeekEmbeddingError(
            f"DeepSeek Embedding API 调用失败：{type(exc).__name__}: {exc}"
        ) from exc

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DeepSeekEmbeddingError(
            "DeepSeek Embedding API 返回不是有效 JSON"
        ) from exc

    return _parse_embeddings_response(parsed, expected_count=len(texts))


def _parse_embeddings_response(
    response_data: dict[str, Any],
    expected_count: int,
) -> list[list[float]]:
    """Extract embedding vectors from the API response.

    Handles both OpenAI-compatible format (``data`` array with ``embedding``
    field) and the ``data[0].embedding`` nested form.
    """
    data = response_data.get("data")
    if not isinstance(data, list) or not data:
        raise DeepSeekEmbeddingError(
            "DeepSeek Embedding API 返回数据为空，缺少 data 字段。"
        )

    vectors: list[list[float]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        embedding = item.get("embedding")
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], (int, float)):
            vectors.append([float(v) for v in embedding])

    if not vectors:
        raise DeepSeekEmbeddingError(
            "DeepSeek Embedding API 未返回有效的 embedding 向量。"
        )

    if len(vectors) != expected_count:
        logger.warning(
            "DeepSeek embedding batch returned %d vectors but %d were requested.",
            len(vectors),
            expected_count,
        )

    return vectors


# ---------------------------------------------------------------------------
# DashScope embeddings provider
# ---------------------------------------------------------------------------


def _load_dashscope_embedding_config() -> dict[str, Any]:
    """Read DashScope embedding configuration from environment variables."""
    settings = get_settings()
    base_url = clean_text(
        os.getenv(DASHSCOPE_BASE_URL_ENV) or DEFAULT_DASHSCOPE_BASE_URL,
        max_length=None,
    )
    api_key = clean_text(os.getenv(DASHSCOPE_API_KEY_ENV), max_length=None)
    model = clean_text(
        os.getenv(DASHSCOPE_EMBEDDING_MODEL_ENV)
        or settings.dashscope_embedding_model
        or DEFAULT_DASHSCOPE_EMBEDDING_MODEL,
        max_length=None,
    )
    timeout = _read_dashscope_embedding_timeout()
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
    }


def _read_dashscope_embedding_timeout() -> float:
    raw_value = os.getenv(DASHSCOPE_EMBEDDING_TIMEOUT_ENV)
    if not raw_value:
        return DEFAULT_DASHSCOPE_EMBEDDING_TIMEOUT
    try:
        timeout = float(raw_value)
    except ValueError:
        return DEFAULT_DASHSCOPE_EMBEDDING_TIMEOUT
    return timeout if timeout > 0 else DEFAULT_DASHSCOPE_EMBEDDING_TIMEOUT


def _build_dashscope_embeddings_url(base_url: str) -> str:
    normalized = clean_text(base_url, max_length=None).rstrip("/")
    if not normalized:
        normalized = DEFAULT_DASHSCOPE_BASE_URL
    if normalized.endswith("/embeddings"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/embeddings"
    return f"{normalized}/compatible-mode/v1/embeddings"


def _dashscope_embed_batch(
    texts: list[str],
    dimension: int | None = None,
) -> list[list[float]]:
    """Call DashScope text-embedding-v4 through the OpenAI-compatible API."""
    if not texts:
        return []

    config = _load_dashscope_embedding_config()
    if not config["api_key"]:
        raise DashScopeEmbeddingError(
            "DashScope API Key 未配置，请设置环境变量 DASHSCOPE_API_KEY。"
        )

    resolved_dimension = _resolve_dimension(dimension)
    url = _build_dashscope_embeddings_url(config["base_url"])
    payload = {
        "model": config["model"],
        "input": texts,
        "dimensions": resolved_dimension,
    }

    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=config["timeout"],
        ) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        message = _extract_deepseek_error_message(error_body) or clean_text(exc.reason)
        raise DashScopeEmbeddingError(
            f"DashScope Embedding API HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise DashScopeEmbeddingError(
            f"DashScope Embedding API 网络连接异常：{exc.reason}"
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise DashScopeEmbeddingError(
            "DashScope Embedding API 请求超时"
        ) from exc
    except Exception as exc:
        raise DashScopeEmbeddingError(
            f"DashScope Embedding API 调用失败：{type(exc).__name__}: {exc}"
        ) from exc

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DashScopeEmbeddingError(
            "DashScope Embedding API 返回不是有效 JSON"
        ) from exc

    return _parse_dashscope_embeddings_response(parsed, expected_count=len(texts))


def _parse_dashscope_embeddings_response(
    response_data: dict[str, Any],
    expected_count: int,
) -> list[list[float]]:
    data = response_data.get("data")
    if not isinstance(data, list) or not data:
        raise DashScopeEmbeddingError(
            "DashScope Embedding API 返回数据为空，缺少 data 字段。"
        )

    vectors: list[list[float]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        embedding = item.get("embedding")
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], (int, float)):
            vectors.append([float(v) for v in embedding])

    if not vectors:
        raise DashScopeEmbeddingError(
            "DashScope Embedding API 未返回有效的 embedding 向量。"
        )

    if len(vectors) != expected_count:
        logger.warning(
            "DashScope embedding batch returned %d vectors but %d were requested.",
            len(vectors),
            expected_count,
        )

    return vectors


def _extract_deepseek_error_message(response_body: str) -> str:
    """Extract a human-readable error message from an API error response."""
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return clean_text(response_body, max_length=1000)

    error = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(error, dict):
        return clean_text(
            error.get("message") or error.get("code") or json.dumps(error, ensure_ascii=False),
            max_length=1000,
        )
    if isinstance(error, str):
        return clean_text(error, max_length=1000)
    return clean_text(json.dumps(parsed, ensure_ascii=False), max_length=1000)


# ---------------------------------------------------------------------------
# reserved provider guard
# ---------------------------------------------------------------------------


def _raise_reserved_provider_error(provider: str) -> None:
    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is configured but not configured with "
        "a runnable embedding client yet. Set EMBEDDING_PROVIDER=hash to use "
        "the demo fallback, or implement this provider in embedding_service.py."
    )


def _embed_real_provider_batch(
    provider: str,
    texts: list[str],
    dimension: int | None,
) -> list[list[float]]:
    if provider == DEEPSEEK_EMBEDDING_PROVIDER:
        return _deepseek_embed_batch(texts)
    if provider == DASHSCOPE_EMBEDDING_PROVIDER:
        return _dashscope_embed_batch(texts, dimension=dimension)
    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is not supported or not configured. "
        "Supported values are hash, dashscope, deepseek, and local."
    )


def _embed_real_provider_batch_with_cache(
    provider: str,
    texts: list[str],
    dimension: int | None,
) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    if (
        not getattr(settings, "embedding_cache_enabled", True)
        or not getattr(settings, "redis_enabled", False)
    ):
        return _embed_real_provider_batch(provider, texts, dimension)

    keys = [
        _embedding_cache_key(
            provider=provider,
            text=text,
            dimension=dimension,
            settings=settings,
        )
        for text in texts
    ]
    vectors: list[list[float] | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []

    for index, key in enumerate(keys):
        cached = sync_json_cache.get_json(
            namespace="embedding",
            key=key,
            settings=settings,
        )
        if isinstance(cached, list):
            vectors[index] = [float(value) for value in cached]
        else:
            missing_indices.append(index)
            missing_texts.append(texts[index])

    if missing_texts:
        fresh_vectors = _embed_real_provider_batch(provider, missing_texts, dimension)
        for index, vector in zip(missing_indices, fresh_vectors):
            normalized_vector = [float(value) for value in vector]
            vectors[index] = normalized_vector
            sync_json_cache.set_json(
                namespace="embedding",
                key=keys[index],
                value=normalized_vector,
                ttl_seconds=getattr(settings, "embedding_cache_ttl_seconds", 86400),
                settings=settings,
            )

    return [vector for vector in vectors if vector is not None]


def _embedding_cache_key(
    *,
    provider: str,
    text: str,
    dimension: int | None,
    settings: Any,
) -> str:
    model = (
        settings.deepseek_embedding_model
        if provider == DEEPSEEK_EMBEDDING_PROVIDER
        else settings.dashscope_embedding_model
    )
    return cache_key_from_payload(
        namespace="embedding",
        version="1",
        payload={
            "provider": provider,
            "model": model,
            "dimension": _resolve_dimension(dimension),
            "text": text,
        },
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def embed_text(text: str, dimension: int | None = None) -> list[float]:
    """Embed a single text with the configured embedding provider.

    - ``hash``: deterministic demo fallback (not semantic).
    - ``dashscope``: calls DashScope text-embedding-v4 (semantic, recommended).
    - ``deepseek``: calls the DeepSeek embeddings API (semantic, production-ready).
    """

    provider = get_settings().embedding_provider

    if provider == HASH_EMBEDDING_PROVIDER:
        resolved_dimension = _resolve_dimension(dimension)
        return _hash_embed_text(text, dimension=resolved_dimension)

    if provider in {DEEPSEEK_EMBEDDING_PROVIDER, DASHSCOPE_EMBEDDING_PROVIDER}:
        return _embed_real_provider_batch_with_cache(provider, [text], dimension)[0]

    if provider in RESERVED_EMBEDDING_PROVIDERS:
        _raise_reserved_provider_error(provider)

    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is not supported or not configured. "
        "Supported values are hash, dashscope, deepseek, and local."
    )


def embed_texts(texts: list[str], dimension: int | None = None) -> list[list[float]]:
    """Embed multiple texts with the configured embedding provider.

    For real providers this sends a single batched API call so that multiple
    texts are embedded efficiently in one round-trip.
    """

    provider = get_settings().embedding_provider

    if provider == HASH_EMBEDDING_PROVIDER:
        resolved_dimension = _resolve_dimension(dimension)
        return [_hash_embed_text(text, dimension=resolved_dimension) for text in texts]

    if provider in {DEEPSEEK_EMBEDDING_PROVIDER, DASHSCOPE_EMBEDDING_PROVIDER}:
        return _embed_real_provider_batch_with_cache(provider, texts, dimension)

    if provider in RESERVED_EMBEDDING_PROVIDERS:
        _raise_reserved_provider_error(provider)

    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is not supported or not configured. "
        "Supported values are hash, dashscope, deepseek, and local."
    )
