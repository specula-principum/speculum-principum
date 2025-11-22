"""Storage for knowledge graph entities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from src.parsing import utils

_DEFAULT_KB_ROOT = Path("knowledge-graph")


@dataclass(slots=True)
class ExtractedPeople:
    """List of people extracted from a source document."""
    
    source_checksum: str
    people: List[str]
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_checksum": self.source_checksum,
            "people": self.people,
            "extracted_at": self.extracted_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExtractedPeople":
        extracted_at = datetime.fromisoformat(payload["extracted_at"])
        return cls(
            source_checksum=payload["source_checksum"],
            people=payload["people"],
            extracted_at=extracted_at,
            metadata=payload.get("metadata", {}),
        )


class KnowledgeGraphStorage:
    """Manages storage of extracted knowledge graph entities."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _DEFAULT_KB_ROOT
        self.root = self.root if self.root.is_absolute() else self.root.resolve()
        utils.ensure_directory(self.root)
        self._people_dir = self.root / "people"
        utils.ensure_directory(self._people_dir)

    def save_extracted_people(self, source_checksum: str, people: List[str]) -> None:
        """Save extracted people for a given source document."""
        entry = ExtractedPeople(source_checksum=source_checksum, people=people)
        path = self._get_people_path(source_checksum)
        
        # Write atomic
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def get_extracted_people(self, source_checksum: str) -> ExtractedPeople | None:
        """Retrieve extracted people for a given source document."""
        path = self._get_people_path(source_checksum)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ExtractedPeople.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _get_people_path(self, checksum: str) -> Path:
        """Get the path for the people file corresponding to a checksum."""
        # Use a sharded structure if needed, but flat is fine for now
        return self._people_dir / f"{checksum}.json"
