"""Core parsing interfaces and data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol


class ParserError(RuntimeError):
    """Raised when a parser fails to extract content from a target."""


@dataclass(frozen=True)
class ParseTarget:
    """Describes the origin that a parser should operate on."""

    source: str
    is_remote: bool = False
    media_type: str | None = None

    def to_path(self) -> Path:
        """Return the source as a ``Path`` when the target is local."""
        if self.is_remote:
            raise ValueError("Remote targets do not map to filesystem paths")
        return Path(self.source)


@dataclass(slots=True)
class ParsedDocument:
    """Represents the structured output from a parser."""

    target: ParseTarget
    checksum: str
    parser_name: str
    segments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_segment(self, segment: str) -> None:
        self.segments.append(segment)

    def extend_segments(self, items: Iterable[str]) -> None:
        self.segments.extend(items)

    def is_empty(self) -> bool:
        return not any(segment.strip() for segment in self.segments)


class DocumentParser(Protocol):
    """Contract shared by all concrete parsers."""

    @property
    def name(self) -> str:
        ...

    def detect(self, target: ParseTarget) -> bool:
        ...

    def extract(self, target: ParseTarget) -> ParsedDocument:
        ...

    def to_markdown(self, document: ParsedDocument) -> str:
        ...
