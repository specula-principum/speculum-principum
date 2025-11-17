"""Text segmentation utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Mapping, Tuple

from . import DocumentSegment, ExtractionResult

__all__ = ["segment_text"]

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(?P<text>.+?)\s*$")
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(?P<text>.+)$")
_QUOTE_PATTERN = re.compile(r"^\s*>\s*(?P<text>.+)$")
_ROMAN_PATTERN = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
_LEADING_NOISE_PATTERN = re.compile(r"^[^0-9A-Za-z]+")
_SECTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?P<prefix>§|sec(?:tion)?\.??|art(?:icle)?\.??|chap(?:ter)?\.??|tit(?:le)?\.??)\s+(?P<body>.+)$",
    re.IGNORECASE,
)
_SECTION_IDENTIFIER_PATTERN = re.compile(
    r"""
    ^
    (
        [IVXLCDM]+(?:\.[IVXLCDM]+)*
        |
        \d+[A-Za-z]?(?:[\-–]\d+[A-Za-z]?)*(?:\.\d+[A-Za-z]?)*(?:\([^)]+\))*
        |
        [A-Z]+\d+
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
_HEADING_KEYWORDS = {
    "appendix",
    "chapter",
    "conclusion",
    "contents",
    "epilogue",
    "introduction",
    "preface",
    "prologue",
}

_SECTION_PREFIX_LABELS = {
    "§": "Section",
    "sec": "Section",
    "sec.": "Section",
    "section": "Section",
    "art": "Article",
    "art.": "Article",
    "article": "Article",
    "chap": "Chapter",
    "chap.": "Chapter",
    "chapter": "Chapter",
    "tit": "Title",
    "tit.": "Title",
    "title": "Title",
}


def _detect_keyword_heading(line: str, *, default_level: int) -> Tuple[str, int] | None:
    """Heuristically detect headings lacking Markdown markers."""

    cleaned = _LEADING_NOISE_PATTERN.sub("", line.strip())
    if not cleaned:
        return None

    tokens = cleaned.split()
    if not tokens:
        return None

    candidate_index = 0
    first_token = tokens[0].rstrip(".:;,")
    if _ROMAN_PATTERN.match(first_token) and len(tokens) > 1:
        candidate_index = 1
    elif first_token.isdigit() and len(tokens) > 1:
        candidate_index = 1

    keyword = tokens[candidate_index].rstrip(".:;,-").lower()
    if keyword not in _HEADING_KEYWORDS:
        return None

    heading_text = " ".join(tokens[candidate_index:]).strip(" .,:;-")
    if not heading_text:
        heading_text = tokens[candidate_index]

    if "(" in heading_text or "[" in heading_text:
        return None

    return heading_text, default_level


def _normalize_structured_heading(prefix: str, identifier: str, title: str | None) -> str:
    prefix_key = prefix.lower().rstrip(".")
    normalized_prefix = _SECTION_PREFIX_LABELS.get(prefix_key, prefix.strip().title())

    identifier_clean = identifier.strip()
    if _ROMAN_PATTERN.fullmatch(identifier_clean):
        identifier_clean = identifier_clean.upper()

    pieces = [normalized_prefix, identifier_clean]
    if title:
        cleaned_title = title.strip(" .;,-")
        if cleaned_title:
            pieces.extend(["-", cleaned_title])

    return " ".join(piece for piece in pieces if piece).strip()


def _split_identifier_and_title(body: str) -> Tuple[str | None, str | None]:
    candidate = body.strip()
    if not candidate:
        return None, None

    separators = [" - ", " – ", " — ", " : ", ": ", "; "]
    for separator in separators:
        if separator in candidate:
            identifier_part, remainder = candidate.split(separator, 1)
            identifier_clean = identifier_part.strip().rstrip(".;,")
            title_clean = remainder.strip()
            return identifier_clean or None, title_clean or None

    parts = candidate.split(None, 1)
    identifier_part = parts[0].rstrip(".;,")
    title_part = parts[1].strip() if len(parts) > 1 else None
    return identifier_part or None, title_part or None


def _detect_structured_heading(line: str, *, default_level: int) -> Tuple[str, int] | None:
    prefix_match = _SECTION_PREFIX_PATTERN.match(line)
    if not prefix_match:
        return None

    prefix = prefix_match.group("prefix") or ""
    body = prefix_match.group("body") or ""
    body = body.strip()
    if not prefix or not body:
        return None

    identifier, title = _split_identifier_and_title(body)
    if not identifier or not _SECTION_IDENTIFIER_PATTERN.fullmatch(identifier):
        return None

    heading_text = _normalize_structured_heading(prefix, identifier, title)

    normalized_prefix = _SECTION_PREFIX_LABELS.get(prefix.lower().rstrip("."), prefix.strip().title())
    if normalized_prefix in {"Chapter", "Article"}:
        level = default_level
    else:
        level = max(default_level + 1, 3)

    return heading_text, level


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
    chapter_level_value = config_map.get("chapter_heading_level", 2)
    try:
        chapter_level = int(chapter_level_value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        chapter_level = 2

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

        structured_heading = _detect_structured_heading(stripped, default_level=chapter_level)
        if structured_heading is not None:
            flush()
            heading_text, level = structured_heading
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

        keyword_heading = _detect_keyword_heading(stripped, default_level=chapter_level)
        if keyword_heading is not None:
            flush()
            heading_text, level = keyword_heading
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
