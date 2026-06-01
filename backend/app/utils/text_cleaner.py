import re
from typing import Any


DEFAULT_MAX_TEXT_LENGTH = 5000


def clean_text(
    value: Any,
    max_length: int | None = DEFAULT_MAX_TEXT_LENGTH,
) -> str:
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(
        re.sub(r"[ \t\f\v]+", " ", line).strip()
        for line in text.split("\n")
    )
    text = re.sub(r"\n+", "\n", text).strip()

    if max_length is not None and max_length >= 0:
        text = text[:max_length].strip()

    return text
