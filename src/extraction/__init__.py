"""Core data models for the extraction toolkit."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

__all__ = [
    "ExtractedEntity",
    "ExtractedConcept",
    "ExtractedRelationship",
    "DocumentSegment",
    "ExtractionResult",
]


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    """Represents a detected entity along with its provenance."""

    text: str
    entity_type: str
    start_offset: int
    end_offset: int
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExtractedConcept:
    """Captures an extracted concept or key phrase and related statistics."""

    term: str
    frequency: int
    positions: Sequence[int]
    related_terms: Sequence[str] = ()
    definition: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedRelationship:
    """Represents a detected relationship between two entities or concepts."""

    subject: str
    object: str
    relation_type: str
    evidence: str
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentSegment:
    """Models a logical block of a document, such as a paragraph or heading."""

    segment_type: str
    text: str
    level: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Standard wrapper for extractor outputs and metadata."""

    source_path: str
    checksum: str
    extractor_name: str
    data: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
