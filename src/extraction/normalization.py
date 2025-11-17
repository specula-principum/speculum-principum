"""Shared normalization helpers for extraction modules."""
from __future__ import annotations

import re
from typing import Iterable, Tuple

__all__ = ["normalize_ocr_token", "normalize_keyword_sequence"]

# Map digits that commonly leak into OCR glyphs back to plausible characters.
# The tuple stores (lowercase_replacement, uppercase_replacement).
_DIGIT_GLYPH_REPLACEMENTS: dict[str, tuple[str, str]] = {
    "0": ("o", "O"),
    "1": ("l", "I"),
    "5": ("s", "S"),
    "6": ("o", "O"),
    "8": ("b", "B"),
}

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_ocr_token(token: str) -> str:
    """Return a token with common OCR artifacts normalized."""

    if not token:
        return token

    characters = list(token)
    for index, char in enumerate(characters):
        replacement_pair = _DIGIT_GLYPH_REPLACEMENTS.get(char)
        if replacement_pair is None:
            continue
        prev_is_alpha = index > 0 and characters[index - 1].isalpha()
        next_is_alpha = index + 1 < len(characters) and characters[index + 1].isalpha()
        if not (prev_is_alpha or next_is_alpha):
            continue
        lower, upper = replacement_pair
        if prev_is_alpha and characters[index - 1].isupper():
            characters[index] = upper
        elif next_is_alpha and characters[index + 1].isupper():
            characters[index] = upper
        else:
            characters[index] = lower

    normalized = "".join(characters)
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def normalize_keyword_sequence(keywords: Iterable[str]) -> tuple[str, ...]:
    """Normalize OCR noise across a keyword sequence while preserving order."""

    ordered: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        candidate = normalize_ocr_token(keyword)
        if not candidate:
            continue
        if candidate in seen:
            continue
        ordered.append(candidate)
        seen.add(candidate)
    return tuple(ordered)
