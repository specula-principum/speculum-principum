"""Utility helpers for the knowledge base engine."""
from __future__ import annotations

import re

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 48) -> str:
    """Return a filesystem-safe slug derived from ``value``.

    This mirrors the behavior of ``src.parsing.utils.slugify`` without importing
    the broader parsing package (which in turn pulls in optional dependencies
    during test collection).
    """

    candidate = value.encode("ascii", errors="ignore").decode().lower()
    candidate = candidate.replace("\\", "/")
    candidate = candidate.rsplit("/", 1)[-1]
    candidate = _SLUG_PATTERN.sub("-", candidate).strip("-")
    if not candidate:
        candidate = "document"
    if len(candidate) > max_length:
        candidate = candidate[:max_length].rstrip("-")
        if not candidate:
            candidate = "document"
    return candidate


__all__ = ["slugify"]
