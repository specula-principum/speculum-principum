"""Tests for knowledge base organization and placement."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.kb_engine.organize import KBOrganizer
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)


def _make_metadata(kb_id: str, primary_topic: str) -> KBMetadata:
    dc = DublinCoreMetadata(
        title=kb_id.split("/")[-1].replace("-", " ").title(),
        description="Auto-generated test document",
        subject=(primary_topic,),
        identifier=kb_id,
        language="en",
    )
    ia = IAMetadata(
        findability_score=0.9,
        completeness=0.92,
        depth=3,
        audience=("students",),
        navigation_path=tuple(kb_id.split("/")),
        related_by_topic=(),
        related_by_entity=(),
        last_updated=datetime(2025, 10, 26, 12, 0, 0),
        update_frequency="quarterly",
    )
    sources = (
        SourceReference(kb_id="sources/the-prince/chapter-1", pages=(1,)),
    )
    return KBMetadata(
        doc_type=primary_topic if primary_topic != "people" else "entity",
        primary_topic=primary_topic,
        secondary_topics=("renaissance",),
        tags=(primary_topic,),
        dc=dc,
        ia=ia,
        sources=sources,
    )


def _concept_document() -> KBDocument:
    kb_id = "concepts/statecraft/virtue"
    metadata = _make_metadata(kb_id, "statecraft")
    return KBDocument(
        kb_id=kb_id,
        slug="virtue",
        title="Virtue",
        metadata=metadata,
        related_concepts=("concepts/statecraft/fortune",),
        body="Test body.",
    )


def _entity_document() -> KBDocument:
    kb_id = "entities/people/cesare-borgia"
    metadata = _make_metadata(kb_id, "people")
    return KBDocument(
        kb_id=kb_id,
        slug="cesare-borgia",
        title="Cesare Borgia",
        metadata=metadata,
        aliases=("Duke Valentino",),
        body="Entity body.",
    )


def test_place_document_writes_markdown(tmp_path: Path) -> None:
    organizer = KBOrganizer()
    document = _concept_document()

    path = organizer.place_document(document, tmp_path)

    assert path == tmp_path / "concepts" / "statecraft" / "virtue.md"
    contents = path.read_text(encoding="utf-8")
    assert contents.startswith("---\n")
    assert "slug: virtue" in contents
    assert contents.endswith("Test body.\n")


def test_place_document_handles_existing_identical_file(tmp_path: Path) -> None:
    organizer = KBOrganizer()
    document = _concept_document()
    path = organizer.place_document(document, tmp_path)

    # Place again; should not raise or change contents
    path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    second = organizer.place_document(document, tmp_path)

    assert second == path
    assert len(list(path.parent.glob("virtue.md*"))) == 1


def test_place_document_creates_backup_on_collision(tmp_path: Path) -> None:
    organizer = KBOrganizer()
    document = _concept_document()
    path = tmp_path / "concepts" / "statecraft" / "virtue.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old content", encoding="utf-8")

    result = organizer.place_document(document, tmp_path)

    assert result == path
    backups = sorted(path.parent.glob("virtue.md.*.bak"))
    assert backups, "Expected backup file to be created"
    assert path.read_text(encoding="utf-8").startswith("---\n")


def test_place_document_collision_error(tmp_path: Path) -> None:
    organizer = KBOrganizer(collision_strategy="error")
    document = _concept_document()
    path = tmp_path / "concepts" / "statecraft" / "virtue.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        organizer.place_document(document, tmp_path)


def test_ensure_indexes_materializes_structure(tmp_path: Path) -> None:
    organizer = KBOrganizer()
    created = organizer.ensure_indexes(tmp_path)

    assert (tmp_path / "concepts").exists()
    index_file = tmp_path / "concepts" / "index.md"
    assert index_file in created
    assert index_file.read_text(encoding="utf-8").startswith("# Concepts")


def test_auto_index_updates_after_placement(tmp_path: Path) -> None:
    organizer = KBOrganizer(auto_index=True)
    organizer.place_document(_entity_document(), tmp_path)

    assert (tmp_path / "entities" / "index.md").exists()
