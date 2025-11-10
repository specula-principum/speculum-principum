"""Document structure analysis utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from . import ExtractionResult
from .segments import segment_text

__all__ = ["analyze_structure"]

_CROSS_REFERENCE_PATTERN = re.compile(r"\bChapter\s+\d+\b", re.IGNORECASE)
_FOOTNOTE_PATTERN = re.compile(r"\[(\d+)\]")


def analyze_structure(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Analyze structural patterns within a document."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))

    segments_result = segment_text(text, config=config_map)
    segments = segments_result.data
    counts = segments_result.metadata.get("counts", {})

    headings: list[dict[str, Any]] = []
    for segment in segments:
        if segment.segment_type != "heading":
            continue
        headings.append(
            {
                "text": segment.text,
                "level": segment.level,
                "start_offset": segment.start_offset,
                "end_offset": segment.end_offset,
            }
        )

    cross_references = sorted({match.group(0) for match in _CROSS_REFERENCE_PATTERN.finditer(text)})
    footnotes = sorted({match.group(1) for match in _FOOTNOTE_PATTERN.finditer(text)})
    has_toc = any("contents" in heading["text"].lower() for heading in headings)

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()

    data: dict[str, Any] = {
        "headings": tuple(headings),
        "segment_counts": counts,
        "cross_references": tuple(cross_references),
        "footnotes": tuple(footnotes),
    }
    metadata: dict[str, Any] = {
        "source_path": source_path,
        "has_table_of_contents": has_toc,
        "cross_reference_count": len(cross_references),
        "footnote_count": len(footnotes),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="structure",
        data=data,
        metadata=metadata,
    )
