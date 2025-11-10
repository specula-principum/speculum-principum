"""Text segmentation utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Mapping

from . import DocumentSegment, ExtractionResult

__all__ = ["segment_text"]

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(?P<text>.+?)\s*$")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(?P<text>.+)$")
_QUOTE_PATTERN = re.compile(r"^\s*>\s*(?P<text>.+)$")


def segment_text(text: str, *, config: Mapping[str, object] | None = None) -> ExtractionResult:
    """Split raw text into logical document segments."""

    config_map: Dict[str, object] = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))

    segments: List[DocumentSegment] = []
    counts: Dict[str, int] = {}

    current_type: str | None = None
    current_level: int = 0
    current_text_parts: List[str] = []
    segment_start: int | None = None
    segment_end: int | None = None

    def flush() -> None:
        nonlocal current_type, current_text_parts, segment_start, segment_end, current_level
        if current_type is None or not current_text_parts or segment_start is None or segment_end is None:
            current_text_parts = []
            current_type = None
            segment_start = None
            segment_end = None
            current_level = 0
            return

        if current_type == "paragraph":
            text_value = " ".join(part.strip() for part in current_text_parts if part.strip())
        elif current_type == "list":
            text_value = "\n".join(part.strip() for part in current_text_parts if part.strip())
        elif current_type == "quote":
            text_value = "\n".join(current_text_parts).strip()
        else:
            text_value = "\n".join(current_text_parts).strip()

        segment = DocumentSegment(
            segment_type=current_type,
            text=text_value,
            level=current_level,
            start_offset=segment_start,
            end_offset=segment_end,
        )
        segments.append(segment)
        counts[current_type] = counts.get(current_type, 0) + 1

        current_text_parts = []
        current_type = None
        segment_start = None
        segment_end = None
        current_level = 0

    position = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        line_length = len(line)
        line_start = position
        line_end = position + len(line.rstrip("\n"))
        position += line_length

        if not stripped:
            flush()
            continue

        heading_match = _HEADING_PATTERN.match(stripped)
        quote_match = _QUOTE_PATTERN.match(line)
        list_match = _LIST_PATTERN.match(line)

        if heading_match:
            flush()
            heading_text = heading_match.group("text").strip()
            level = len(heading_match.group(1))
            segment = DocumentSegment(
                segment_type="heading",
                text=heading_text,
                level=level,
                start_offset=line_start,
                end_offset=line_end,
            )
            segments.append(segment)
            counts["heading"] = counts.get("heading", 0) + 1
            continue

        if list_match:
            line_type = "list"
            content = list_match.group("text").strip()
        elif quote_match:
            line_type = "quote"
            content = quote_match.group("text").rstrip()
        else:
            line_type = "paragraph"
            content = stripped

        if current_type != line_type:
            flush()
            current_type = line_type
            current_level = 0
            current_text_parts = []
            segment_start = line_start

        current_text_parts.append(content)
        segment_end = line_end

    flush()

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: Dict[str, object] = {
        "counts": counts,
        "segment_types": tuple(sorted(counts)),
        "source_path": source_path,
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="segments",
        data=tuple(segments),
        metadata=metadata,
    )
