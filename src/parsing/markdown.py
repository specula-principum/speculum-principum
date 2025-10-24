"""Shared Markdown serialization for parsed documents."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime

from .base import ParsedDocument

_FRONT_MATTER_DELIMITER = "---\n"


def document_to_markdown(document: ParsedDocument) -> str:
    """Render a ``ParsedDocument`` into Markdown with YAML front matter."""
    front_matter = _build_front_matter(document)
    body = "\n\n".join(segment.strip("\n") for segment in document.segments)
    if body:
        body = body.rstrip() + "\n"
    return f"{_FRONT_MATTER_DELIMITER}{front_matter}{_FRONT_MATTER_DELIMITER}\n{body}"


def _build_front_matter(document: ParsedDocument) -> str:
    payload: dict[str, object] = {
        "source": document.target.source,
        "checksum": document.checksum,
        "parser": document.parser_name,
        "processed_at": _format_datetime(document.created_at),
        "is_remote": document.target.is_remote,
        "segment_count": len(document.segments),
        "status": "empty" if document.is_empty() else "completed",
    }

    media_type = document.target.media_type
    if media_type is not None:
        payload["media_type"] = media_type

    if document.warnings:
        payload["warnings"] = document.warnings

    if document.metadata:
        payload["metadata"] = document.metadata

    return _serialize_yaml(payload)


def _serialize_yaml(data: object, *, indent: int = 0) -> str:
    buffer: list[str] = []
    _append_yaml(buffer, data, indent)
    return "".join(buffer)


def _append_yaml(buffer: list[str], data: object, indent: int) -> None:
    prefix = " " * indent
    if isinstance(data, Mapping):
        for key, value in data.items():
            buffer.append(f"{prefix}{key}:")
            if _is_scalar(value):
                rendered = _format_scalar(value)
                if rendered is not None:
                    buffer[-1] += f" {rendered}\n"
                else:
                    buffer[-1] += "\n"
            else:
                buffer[-1] += "\n"
                _append_yaml(buffer, value, indent + 2)
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        if not data:
            buffer.append(f"{prefix}[]\n")
            return
        for item in data:
            if _is_scalar(item):
                rendered = _format_scalar(item)
                buffer.append(f"{prefix}- {rendered}\n")
            else:
                buffer.append(f"{prefix}-\n")
                _append_yaml(buffer, item, indent + 2)
    else:
        rendered = _format_scalar(data)
        if rendered is None:
            rendered = json.dumps(data, ensure_ascii=False)
        buffer.append(f"{prefix}{rendered}\n")


def _is_scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _format_scalar(value: object) -> str | None:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "":
            return '""'
        if any(ch in value for ch in "\n:\"'{}[]#&*!|>=%@`"):
            return json.dumps(value, ensure_ascii=False)
        return value
    return None


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat()
