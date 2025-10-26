"""Named entity extraction utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Mapping

from . import ExtractedEntity, ExtractionResult

__all__ = ["extract_entities"]

_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_UPPERCASE_ORG_PATTERN = re.compile(r"\b([A-Z]{3,})\b")
_DATE_PATTERN = re.compile(r"\b(\d{3,4})\b")
_ORG_SUFFIXES = {"Company", "Corporation", "Council", "Institute", "University", "Republic", "Agency"}


def extract_entities(
    text: str,
    *,
    entity_types: Iterable[str] | None = None,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Identify entities present in the supplied text using lightweight heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    if entity_types is not None:
        requested_types = {str(item) for item in entity_types}
    else:
        configured_types = config_map.get("entity_types")
        if configured_types is None:
            requested_types = {"PERSON", "ORG", "DATE"}
        elif isinstance(configured_types, str):
            requested_types = {configured_types}
        else:
            try:
                requested_types = {str(item) for item in configured_types}  # type: ignore[arg-type]
            except TypeError:
                requested_types = {"PERSON", "ORG", "DATE"}
    if not requested_types:
        requested_types = {"PERSON", "ORG", "DATE"}

    threshold_value = config_map.get("confidence_threshold", 0.7)
    if isinstance(threshold_value, (int, float, str)):
        try:
            threshold = float(threshold_value)
        except ValueError:
            threshold = 0.7
    else:
        threshold = 0.7

    entities: list[ExtractedEntity] = []
    seen_positions: set[tuple[int, int, str]] = set()

    def add_entity(
        *,
        text_value: str,
        entity_type: str,
        start: int,
        end: int,
        confidence: float,
        metadata: Mapping[str, object],
    ) -> None:
        if entity_type not in requested_types:
            return
        if confidence < threshold:
            return
        key = (start, end, entity_type)
        if key in seen_positions:
            return
        seen_positions.add(key)
        entities.append(
            ExtractedEntity(
                text=text_value,
                entity_type=entity_type,
                start_offset=start,
                end_offset=end,
                confidence=confidence,
                metadata=dict(metadata),
            )
        )

    for match in _PERSON_PATTERN.finditer(text):
        candidate = match.group(1).strip()
        tokens = candidate.split()
        last_token = tokens[-1]
        entity_type = "PERSON"
        if last_token in _ORG_SUFFIXES or last_token.isupper():
            entity_type = "ORG"
        if entity_type == "PERSON" and len(tokens) < 2:
            continue
        add_entity(
            text_value=candidate,
            entity_type=entity_type,
            start=match.start(1),
            end=match.end(1),
            confidence=0.92 if entity_type == "PERSON" else 0.88,
            metadata={"pattern": "capitalized_sequence", "token_count": len(tokens)},
        )

    for match in _UPPERCASE_ORG_PATTERN.finditer(text):
        token = match.group(1)
        add_entity(
            text_value=token,
            entity_type="ORG",
            start=match.start(1),
            end=match.end(1),
            confidence=0.87,
            metadata={"pattern": "uppercase_token"},
        )

    for match in _DATE_PATTERN.finditer(text):
        token = match.group(1)
        add_entity(
            text_value=token,
            entity_type="DATE",
            start=match.start(1),
            end=match.end(1),
            confidence=0.9,
            metadata={"pattern": "year"},
        )

    entities.sort(key=lambda entity: (entity.start_offset, entity.end_offset, entity.entity_type))

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        "detected_count": len(entities),
        "source_path": source_path,
        "entity_types": tuple(sorted(requested_types)),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="entities",
        data=tuple(entities),
        metadata=metadata,
    )
