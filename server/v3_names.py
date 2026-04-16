from __future__ import annotations

import re

_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def slugify(text: str) -> str:
    return _NON_ALPHANUM.sub("-", text.casefold().strip()).strip("-")


def surface_key(value: str) -> str:
    normalized = value.casefold().strip()
    if normalized.isascii():
        return slugify(normalized)
    return _NON_WORD_RE.sub("", normalized)
