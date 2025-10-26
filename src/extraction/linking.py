"""Link generation utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Mapping

from . import ExtractionResult

__all__ = ["generate_links"]

_HEADING_PATTERN = re.compile(r"(?m)^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<target>[^)]+)\)")
_SEE_ALSO_PATTERN = re.compile(r"see also\s+(?P<target>[A-Z][A-Za-z0-9\s,]+?)(?:[.;]|\n|$)", re.IGNORECASE)
_CAPITALIZED_PHRASE_PATTERN = re.compile(r"\b([A-Z][A-Za-z']+(?:\s+[A-Z][A-Za-z']+){0,3})\b")


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9\s-]", "", value).strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    return normalized or "section"


def _coerce_int(value: object, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        return minimum
    if maximum is not None and coerced > maximum:
        return maximum
    return coerced


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def generate_links(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Build outbound link suggestions, anchors, and related mentions."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    max_links = _coerce_int(config_map.get("max_links"), 25, minimum=0)
    max_mentions = _coerce_int(config_map.get("max_mentions"), 10, minimum=0)
    include_mentions = _coerce_bool(config_map.get("include_mentions"), True)
    include_anchor_offsets = _coerce_bool(config_map.get("include_anchor_offsets"), True)

    anchors: list[dict[str, object]] = []
    for match in _HEADING_PATTERN.finditer(text):
        title = match.group("title").strip()
        if not title:
            continue
        level = len(match.group("hashes"))
        anchors.append(
            {
                "title": title,
                "slug": _slugify(title),
                "level": level,
                "start_offset": match.start() if include_anchor_offsets else None,
                "end_offset": match.end() if include_anchor_offsets else None,
            }
        )

    outbound_links: list[dict[str, object]] = []
    for match in _MARKDOWN_LINK_PATTERN.finditer(text):
        label = match.group("label").strip()
        target = match.group("target").strip()
        if not target:
            continue
        outbound_links.append(
            {
                "label": label or target,
                "target": target,
                "context": text[max(match.start() - 40, 0) : match.end() + 40].strip(),
                "confidence": 0.9 if target.startswith("http") else 0.8,
                "start_offset": match.start() if include_anchor_offsets else None,
            }
        )

    see_also_links: list[dict[str, object]] = []
    for match in _SEE_ALSO_PATTERN.finditer(text):
        raw_target = match.group("target").strip().rstrip(",")
        see_also_links.append(
            {
                "target": raw_target,
                "context": text[max(match.start() - 40, 0) : match.end() + 40].strip(),
                "confidence": 0.7,
            }
        )

    if max_links:
        outbound_links = outbound_links[:max_links]
        see_also_links = see_also_links[:max_links]

    mentions: list[dict[str, object]] = []
    if include_mentions and max_mentions:
        counts: dict[str, int] = {}
        for match in _CAPITALIZED_PHRASE_PATTERN.finditer(text):
            phrase = match.group(1).strip()
            if len(phrase.split()) == 1 and phrase.isupper():
                continue
            counts[phrase] = counts.get(phrase, 0) + 1
        sorted_mentions = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:max_mentions]
        for phrase, count in sorted_mentions:
            mentions.append(
                {
                    "phrase": phrase,
                    "occurrences": count,
                }
            )

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()

    data: dict[str, object] = {
        "anchors": tuple(anchors),
        "outbound_links": tuple(outbound_links),
        "see_also": tuple(see_also_links),
        "mentions": tuple(mentions),
    }

    metadata: dict[str, object] = {
        "source_path": source_path,
        "anchor_count": len(anchors),
        "outbound_count": len(outbound_links),
        "see_also_count": len(see_also_links),
        "mention_count": len(mentions),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="linking",
        data=data,
        metadata=metadata,
    )
