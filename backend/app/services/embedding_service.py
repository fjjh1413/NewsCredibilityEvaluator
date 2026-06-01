import hashlib
import math
import re

from app.utils.text_cleaner import clean_text


EMBEDDING_DIMENSION = 384


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


def embed_text(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Create a deterministic local embedding.

    This is a replaceable placeholder. Later phases can swap this function for
    a real embedding model or API without changing Chroma persistence code.
    """

    if dimension <= 0:
        raise ValueError("dimension must be greater than 0")

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


def embed_texts(texts: list[str], dimension: int = EMBEDDING_DIMENSION) -> list[list[float]]:
    return [embed_text(text, dimension=dimension) for text in texts]
