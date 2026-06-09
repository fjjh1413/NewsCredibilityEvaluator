import hashlib
import math
import re

from app.core.config import get_settings
from app.utils.text_cleaner import clean_text


EMBEDDING_DIMENSION = get_settings().embedding_dimension
HASH_EMBEDDING_PROVIDER = "hash"
RESERVED_EMBEDDING_PROVIDERS = {"deepseek", "local"}


class EmbeddingProviderNotConfiguredError(RuntimeError):
    """Raised when a configured embedding provider has no runnable client."""


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


def _resolve_dimension(dimension: int | None = None) -> int:
    resolved_dimension = (
        get_settings().embedding_dimension if dimension is None else dimension
    )
    if resolved_dimension <= 0:
        raise ValueError("dimension must be greater than 0")
    return resolved_dimension


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


def _raise_reserved_provider_error(provider: str) -> None:
    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is configured but not configured with "
        "a runnable embedding client yet. Set EMBEDDING_PROVIDER=hash to use "
        "the demo fallback, or implement this provider in embedding_service.py."
    )


def embed_text(text: str, dimension: int | None = None) -> list[float]:
    """Embed text with the configured provider while preserving Chroma shape."""

    provider = get_settings().embedding_provider
    resolved_dimension = _resolve_dimension(dimension)

    if provider == HASH_EMBEDDING_PROVIDER:
        return _hash_embed_text(text, dimension=resolved_dimension)
    if provider in RESERVED_EMBEDDING_PROVIDERS:
        _raise_reserved_provider_error(provider)

    raise EmbeddingProviderNotConfiguredError(
        f"Embedding provider '{provider}' is not supported or not configured. "
        "Supported values are hash, deepseek, and local."
    )


def embed_texts(texts: list[str], dimension: int | None = None) -> list[list[float]]:
    return [embed_text(text, dimension=dimension) for text in texts]
