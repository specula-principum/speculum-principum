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



@dataclass(slots=True)
class ExtractedOrganizations:
    """List of organizations extracted from a source document."""
    
    source_checksum: str
    organizations: List[str]
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_checksum": self.source_checksum,
            "organizations": self.organizations,
            "extracted_at": self.extracted_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExtractedOrganizations":
        extracted_at = datetime.fromisoformat(payload["extracted_at"])
        return cls(
            source_checksum=payload["source_checksum"],
            organizations=payload["organizations"],
            extracted_at=extracted_at,
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class ExtractedConcepts:
    """List of concepts extracted from a source document."""
    
    source_checksum: str
    concepts: List[str]
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_checksum": self.source_checksum,
            "concepts": self.concepts,
            "extracted_at": self.extracted_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExtractedConcepts":
        extracted_at = datetime.fromisoformat(payload["extracted_at"])
        return cls(
            source_checksum=payload["source_checksum"],
            concepts=payload["concepts"],
            extracted_at=extracted_at,
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class EntityAssociation:
    """Represents an association between a person and an organization."""
    
    person_name: str
    organization_name: str
    relationship: str
    evidence: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_name": self.person_name,
            "organization_name": self.organization_name,
            "relationship": self.relationship,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EntityAssociation":
        return cls(
            person_name=payload["person_name"],
            organization_name=payload["organization_name"],
            relationship=payload["relationship"],
            evidence=payload.get("evidence", ""),
            confidence=payload.get("confidence", 1.0),
        )


@dataclass(slots=True)
class ExtractedAssociations:
    """List of associations extracted from a source document."""
    
    source_checksum: str
    associations: List[EntityAssociation]
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_checksum": self.source_checksum,
            "associations": [a.to_dict() for a in self.associations],
            "extracted_at": self.extracted_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExtractedAssociations":
        extracted_at = datetime.fromisoformat(payload["extracted_at"])
        return cls(
            source_checksum=payload["source_checksum"],
            associations=[EntityAssociation.from_dict(a) for a in payload["associations"]],
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
        self._organizations_dir = self.root / "organizations"
        utils.ensure_directory(self._organizations_dir)
        self._concepts_dir = self.root / "concepts"
        utils.ensure_directory(self._concepts_dir)
        self._associations_dir = self.root / "associations"
        utils.ensure_directory(self._associations_dir)

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

    def save_extracted_organizations(self, source_checksum: str, organizations: List[str]) -> None:
        """Save extracted organizations for a given source document."""
        entry = ExtractedOrganizations(source_checksum=source_checksum, organizations=organizations)
        path = self._get_organizations_path(source_checksum)
        
        # Write atomic
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def get_extracted_organizations(self, source_checksum: str) -> ExtractedOrganizations | None:
        """Retrieve extracted organizations for a given source document."""
        path = self._get_organizations_path(source_checksum)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ExtractedOrganizations.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save_extracted_concepts(self, source_checksum: str, concepts: List[str]) -> None:
        """Save extracted concepts for a given source document."""
        entry = ExtractedConcepts(source_checksum=source_checksum, concepts=concepts)
        path = self._get_concepts_path(source_checksum)
        
        # Write atomic
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def get_extracted_concepts(self, source_checksum: str) -> ExtractedConcepts | None:
        """Retrieve extracted concepts for a given source document."""
        path = self._get_concepts_path(source_checksum)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ExtractedConcepts.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save_extracted_associations(self, source_checksum: str, associations: List[EntityAssociation]) -> None:
        """Save extracted associations for a given source document."""
        entry = ExtractedAssociations(source_checksum=source_checksum, associations=associations)
        path = self._get_associations_path(source_checksum)
        
        # Write atomic
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def get_extracted_associations(self, source_checksum: str) -> ExtractedAssociations | None:
        """Retrieve extracted associations for a given source document."""
        path = self._get_associations_path(source_checksum)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ExtractedAssociations.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _get_people_path(self, checksum: str) -> Path:
        """Get the path for the people file corresponding to a checksum."""
        # Use a sharded structure if needed, but flat is fine for now
        return self._people_dir / f"{checksum}.json"

    def _get_organizations_path(self, checksum: str) -> Path:
        """Get the path for the organizations file corresponding to a checksum."""
        return self._organizations_dir / f"{checksum}.json"

    def _get_concepts_path(self, checksum: str) -> Path:
        """Get the path for the concepts file corresponding to a checksum."""
        return self._concepts_dir / f"{checksum}.json"

    def _get_associations_path(self, checksum: str) -> Path:
        """Get the path for the associations file corresponding to a checksum."""
        return self._associations_dir / f"{checksum}.json"
