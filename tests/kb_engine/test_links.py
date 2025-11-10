"""Tests for the LinkBuilder relationship manager."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pytest
import yaml

from src.kb_engine.links import LinkBuilder
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)
from src.knowledge_base.metadata import render_document


@pytest.fixture()
def kb_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge-base"
    root.mkdir()
    return root


def _metadata(kb_id: str, primary_topic: str, *, tags: Iterable[str]) -> KBMetadata:
    dc = DublinCoreMetadata(
        title=kb_id.split("/")[-1].replace("-", " ").title(),
        description="Auto-generated test document",
        subject=(primary_topic,),
        identifier=kb_id,
        language="en",
    )
    ia = IAMetadata(
        findability_score=0.85,
        completeness=0.9,
        depth=3,
        audience=("researchers",),
        navigation_path=tuple(kb_id.split("/")),
        related_by_topic=(),
        related_by_entity=(),
        last_updated=datetime(2025, 10, 26, 12, 0, 0),
        update_frequency="quarterly",
    )
    source = SourceReference(kb_id="sources/the-prince/introduction", pages=(1,))
    return KBMetadata(
        doc_type="concept",
        primary_topic=primary_topic,
        secondary_topics=("renaissance",),
        tags=tuple(tags),
        dc=dc,
        ia=ia,
        sources=(source,),
    )


def _write_document(root: Path, document: KBDocument) -> Path:
    payload = render_document(document)
    relative = Path(document.kb_id)
    path = (root / relative).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            yaml_block = "\n".join(lines[1:index])
            break
    else:  # pragma: no cover - defensive guard
        raise AssertionError("Front matter terminator not found")
    return yaml.safe_load(yaml_block) or {}


def test_build_concept_graph_creates_edges(kb_root: Path) -> None:
    virtue = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=_metadata("concepts/statecraft/virtue", "statecraft", tags=("virtue", "statecraft")),
        related_concepts=("concepts/statecraft/fortune",),
        body="# Virtue\n\nVirtue governs statecraft and power.\n",
    )
    fortune = KBDocument(
        kb_id="concepts/statecraft/fortune",
        slug="fortune",
        title="Fortune",
        metadata=_metadata("concepts/statecraft/fortune", "statecraft", tags=("fortune", "statecraft")),
        related_concepts=("concepts/statecraft/virtue",),
        body="# Fortune\n\nFortune influences virtue and power.\n",
    )

    _write_document(kb_root, virtue)
    _write_document(kb_root, fortune)

    builder = LinkBuilder()
    graph = builder.build_concept_graph(kb_root)

    assert graph.metrics["concept_count"] == pytest.approx(2.0)
    assert graph.metrics["edge_count"] == pytest.approx(2.0)

    adjacency = graph.adjacency()
    assert adjacency["concepts/statecraft/virtue"] == ("concepts/statecraft/fortune",)
    assert adjacency["concepts/statecraft/fortune"] == ("concepts/statecraft/virtue",)

    weights = {edge.target: edge.weight for edge in graph.edges if edge.source == virtue.kb_id}
    weight = weights[fortune.kb_id]
    assert weight is not None
    assert 0.1 <= weight <= 1.0


def test_generate_backlinks_updates_targets(kb_root: Path) -> None:
    virtue = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=_metadata("concepts/statecraft/virtue", "statecraft", tags=("virtue",)),
        related_concepts=("concepts/statecraft/fortune",),
        body="Virtue body.\n",
    )
    fortune = KBDocument(
        kb_id="concepts/statecraft/fortune",
        slug="fortune",
        title="Fortune",
        metadata=_metadata("concepts/statecraft/fortune", "statecraft", tags=("fortune",)),
        body="Fortune body.\n",
    )

    virtue_path = _write_document(kb_root, virtue)
    fortune_path = _write_document(kb_root, fortune)

    builder = LinkBuilder()
    updated = builder.generate_backlinks(kb_root)

    assert updated == ("concepts/statecraft/fortune",)

    fortune_front_matter = _front_matter(fortune_path)
    ia_section = fortune_front_matter.get("ia")
    if not isinstance(ia_section, dict):
        ia_section = {}
    backlinks = tuple(ia_section.get("related_by_topic", ()))
    assert backlinks == ("concepts/statecraft/virtue",)

    virtue_front_matter = _front_matter(virtue_path)
    virtue_ia = virtue_front_matter.get("ia")
    if not isinstance(virtue_ia, dict):
        virtue_ia = {}
    virtue_backlinks = tuple(virtue_ia.get("related_by_topic", ()))
    assert virtue_backlinks == ()


def test_suggest_related_prioritises_linked_documents(kb_root: Path) -> None:
    virtue = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=_metadata("concepts/statecraft/virtue", "statecraft", tags=("virtue", "statecraft")),
        related_concepts=("concepts/statecraft/fortune",),
        body="Virtue emphasises prudence and power.\n",
    )
    fortune = KBDocument(
        kb_id="concepts/statecraft/fortune",
        slug="fortune",
        title="Fortune",
        metadata=_metadata("concepts/statecraft/fortune", "statecraft", tags=("fortune", "statecraft")),
        related_concepts=(),
        body="Fortune captures chance events influencing power and prudence.\n",
    )
    power = KBDocument(
        kb_id="concepts/statecraft/power",
        slug="power",
        title="Power",
        metadata=_metadata("concepts/statecraft/power", "statecraft", tags=("power",)),
        related_concepts=(),
        body="Power discusses force and structure without direct ties to virtue.\n",
    )

    _write_document(kb_root, virtue)
    _write_document(kb_root, fortune)
    _write_document(kb_root, power)

    builder = LinkBuilder(min_similarity=0.01)
    builder.build_concept_graph(kb_root)

    suggestions = builder.suggest_related("concepts/statecraft/virtue", limit=2)

    assert suggestions[0] == "concepts/statecraft/fortune"
    assert "concepts/statecraft/power" in suggestions


def test_suggest_related_requires_initialisation() -> None:
    builder = LinkBuilder()
    with pytest.raises(RuntimeError):
        builder.suggest_related("concepts/statecraft/virtue")


def test_suggest_related_returns_empty_for_unknown_id(kb_root: Path) -> None:
    virtue = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=_metadata("concepts/statecraft/virtue", "statecraft", tags=("virtue",)),
        related_concepts=(),
        body="Virtue body.\n",
    )
    _write_document(kb_root, virtue)

    builder = LinkBuilder()
    builder.build_concept_graph(kb_root)

    assert builder.suggest_related("concepts/statecraft/unknown") == ()
