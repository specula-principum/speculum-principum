"""Utility helpers shared across parsing components."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path

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
