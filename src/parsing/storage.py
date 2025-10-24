"""Persistence helpers for parsed document artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import utils
from .base import ParsedDocument
from .markdown import document_to_markdown

_MANIFEST_VERSION = 1
_DEFAULT_MANIFEST = "manifest.json"


@dataclass(slots=True)
class ManifestEntry:
    source: str
    checksum: str
    parser: str
    artifact_path: str
    processed_at: datetime
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "checksum": self.checksum,
            "parser": self.parser,
            "artifact_path": self.artifact_path,
            "processed_at": self.processed_at.isoformat(),
            "status": self.status,
            "metadata": self.metadata,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManifestEntry":
        processed_at = datetime.fromisoformat(payload["processed_at"])
        return cls(
            source=payload["source"],
            checksum=payload["checksum"],
            parser=payload["parser"],
            artifact_path=payload["artifact_path"],
            processed_at=processed_at,
            status=payload.get("status", "completed"),
            metadata=payload.get("metadata", {}),
            warnings=payload.get("warnings", []),
        )


@dataclass(slots=True)
class Manifest:
    version: int = _MANIFEST_VERSION
    entries: dict[str, ManifestEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "entries": [entry.to_dict() for entry in self.entries.values()],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Manifest":
        version = payload.get("version", _MANIFEST_VERSION)
        entries_payload = payload.get("entries", [])
        entries = {
            item["checksum"]: ManifestEntry.from_dict(item)
            for item in entries_payload
        }
        return cls(version=version, entries=entries)

    def get(self, checksum: str) -> ManifestEntry | None:
        return self.entries.get(checksum)

    def upsert(self, entry: ManifestEntry) -> None:
        self.entries[entry.checksum] = entry


class ParseStorage:
    def __init__(self, root: Path, *, manifest_filename: str = _DEFAULT_MANIFEST) -> None:
        self.root = Path(root)
        self.root = self.root if self.root.is_absolute() else self.root.resolve()
        self._manifest_filename = manifest_filename
        utils.ensure_directory(self.root)
        self._manifest = self._load_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.root / self._manifest_filename

    def manifest(self) -> Manifest:
        return self._manifest

    def should_process(self, checksum: str) -> bool:
        entry = self._manifest.get(checksum)
        if entry is None:
            return True
        return entry.status != "completed"

    def record_entry(self, entry: ManifestEntry) -> None:
        self._manifest.upsert(entry)
        self._write_manifest()

    def persist_document(self, document: ParsedDocument) -> ManifestEntry:
        """Write the document to disk and record a manifest entry."""

        checksum = document.checksum
        processed_at = document.created_at
        artifact_path = self.make_artifact_path(
            document.target.source,
            checksum,
            processed_at=processed_at,
        )

        markdown = document_to_markdown(document)
        utils.ensure_directory(artifact_path.parent)
        tmp_path = artifact_path.with_name(artifact_path.name + ".tmp")
        tmp_path.write_text(markdown, encoding="utf-8")
        tmp_path.replace(artifact_path)

        entry = ManifestEntry(
            source=document.target.source,
            checksum=checksum,
            parser=document.parser_name,
            artifact_path=self.relative_artifact_path(artifact_path),
            processed_at=processed_at,
            status="empty" if document.is_empty() else "completed",
            metadata=document.metadata,
            warnings=document.warnings,
        )

        self.record_entry(entry)
        return entry

    def make_artifact_path(
        self,
        source: str,
        checksum: str,
        *,
        processed_at: datetime | None = None,
        suffix: str = ".md",
    ) -> Path:
        processed_at = processed_at or datetime.now(timezone.utc)
        year_folder = processed_at.strftime("%Y")
        slug = utils.slugify(source)
        fingerprint = checksum[:12] or utils.stable_checksum_for_source(source)[:12]
        filename = f"{slug}-{fingerprint}{suffix}"
        directory = self.root / year_folder
        utils.ensure_directory(directory)
        return directory / filename

    def relative_artifact_path(self, absolute_path: Path) -> str:
        return str(absolute_path.relative_to(self.root))

    def _load_manifest(self) -> Manifest:
        path = self.manifest_path
        if not path.exists():
            return Manifest()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Manifest.from_dict(raw)

    def _write_manifest(self) -> None:
        payload = self._manifest.to_dict()
        tmp_path = self.manifest_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.manifest_path)
