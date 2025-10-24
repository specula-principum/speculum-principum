"""Utility helpers shared across parsing components."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

_DEFAULT_CHUNK_SIZE = 1024 * 1024
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def guess_media_type(path: Path) -> str | None:
    media_type, _encoding = mimetypes.guess_type(path)
    return media_type


def sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def sha256_path(path: Path, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def stable_checksum_for_source(source: str) -> str:
    normalized = os.path.normpath(source).encode("utf-8", errors="ignore")
    return hashlib.sha256(normalized).hexdigest()


def slugify(value: str, *, max_length: int = 48) -> str:
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


def normalize_suffixes(
    values: Sequence[str] | str | None,
    *,
    default: Sequence[str] | None = None,
    sort: bool = False,
    preserve_order: bool = True,
) -> tuple[str, ...]:
    """Normalize file suffix tokens to lowercase dotted form.

    Parameters mirror existing call sites so behavior stays consistent:
    - ``default``: returned when input is falsy or normalizes to no tokens.
    - ``sort``: sort the unique suffixes lexicographically when ``True``.
    - ``preserve_order``: keep first-appearance ordering when ``True``.
    """

    if not values:
        cleaned: list[str] = []
    else:
        if isinstance(values, str):
            iterator = [values]
        else:
            iterator = values
        cleaned = []
        for raw in iterator:
            token = str(raw).strip().lower()
            if not token:
                continue
            if not token.startswith("."):
                token = f".{token}"
            cleaned.append(token)

    if not cleaned:
        if default is not None:
            return tuple(default)
        return ()

    if preserve_order:
        cleaned = list(dict.fromkeys(cleaned))
    else:
        cleaned = list(set(cleaned))

    if sort:
        cleaned.sort()

    return tuple(cleaned)


def is_http_url(value: str) -> bool:
    """Return ``True`` when ``value`` looks like an HTTP or HTTPS URL."""

    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
