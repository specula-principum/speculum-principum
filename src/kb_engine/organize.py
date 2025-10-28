"""Organization management utilities for IA-compliant placement."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from src.knowledge_base import KBDocument
from src.knowledge_base.metadata import render_document
from src.knowledge_base.structure import DEFAULT_STRUCTURE, plan_structure, materialize_structure


class KBOrganizer:
    """Places documents within an information-architecture compliant structure."""

    def __init__(
        self,
        *,
        structure: Mapping[str, object] | None = None,
        index_context: Mapping[str, str] | None = None,
        collision_strategy: str = "backup",
        overwrite_indexes: bool = False,
        auto_index: bool = False,
    ) -> None:
        self._structure = structure or DEFAULT_STRUCTURE
        self._index_context = dict(index_context or {})
        self._collision_strategy = collision_strategy
        self._overwrite_indexes = overwrite_indexes
        self._auto_index = auto_index

    def place_document(self, document: KBDocument, kb_root: Path) -> Path:
        """Determine the correct location for a document, persist it, and return the path."""

        if not isinstance(document, KBDocument):
            raise TypeError("document must be a KBDocument instance")
        document.validate()

        kb_root = kb_root.expanduser()
        kb_root.mkdir(parents=True, exist_ok=True)

        relative = Path(document.kb_id)
        if relative.is_absolute():
            raise ValueError("kb_id must be a relative path")
        if relative.name != document.slug:
            raise ValueError("Document slug must match final kb_id segment")

        target_dir = kb_root / relative.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document.slug}.md"

        payload = render_document(document)
        self._write_with_collision(target_path, payload)

        if self._auto_index:
            self.ensure_indexes(kb_root)

        return target_path

    def ensure_indexes(self, kb_root: Path) -> Sequence[Path]:
        """Create or update navigation indexes within the knowledge base."""

        kb_root = kb_root.expanduser()
        kb_root.mkdir(parents=True, exist_ok=True)
        plan = plan_structure(kb_root, structure=self._structure, context=self._index_context)
        materialize_structure(plan, force=self._overwrite_indexes)
        return tuple(item.path for item in plan)

    # Internal helpers -------------------------------------------------

    def _write_with_collision(self, path: Path, payload: str) -> None:
        if not path.exists():
            path.write_text(payload, encoding="utf-8")
            return

        existing = path.read_text(encoding="utf-8")
        if existing == payload:
            return

        strategy = self._collision_strategy.lower()
        if strategy == "error":
            raise FileExistsError(f"Document already exists at {path} with different contents")
        if strategy == "replace":
            path.write_text(payload, encoding="utf-8")
            return
        if strategy == "backup":
            backup = self._create_backup_path(path)
            path.rename(backup)
            path.write_text(payload, encoding="utf-8")
            return

        raise ValueError(f"Unknown collision_strategy '{self._collision_strategy}'.")

    @staticmethod
    def _create_backup_path(path: Path) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        suffix = f".{timestamp}.bak"
        candidate = path.with_name(path.name + suffix)
        counter = 1
        while candidate.exists():
            candidate = path.with_name(f"{path.name}{suffix}.{counter}")
            counter += 1
        return candidate
