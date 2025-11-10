"""Tests for quality analysis utilities."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from src.kb_engine.quality import QualityAnalyzer
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)


def _metadata(kb_id: str, primary_topic: str) -> KBMetadata:
    dc = DublinCoreMetadata(
        title=kb_id.split("/")[-1].replace("-", " ").title(),
        description="Auto-generated test document",
        subject=(primary_topic,),
        identifier=kb_id,
        language="en",
    )
    ia = IAMetadata(
        findability_score=0.75,
        completeness=0.8,
        depth=3,
        audience=("researchers",),
        navigation_path=tuple(kb_id.split("/")),
        related_by_topic=("concepts/statecraft/fortune",),
        related_by_entity=(),
        last_updated=datetime(2025, 10, 26, 12, 0, 0),
        update_frequency="quarterly",
    )
    sources = (
        SourceReference(kb_id="sources/the-prince/chapter-1", pages=(1, 2)),
    )
    return KBMetadata(
        doc_type="concept",
        primary_topic=primary_topic,
        secondary_topics=("renaissance",),
        tags=(primary_topic,),
        dc=dc,
        ia=ia,
        sources=sources,
    )


def test_calculate_completeness_applies_bonuses() -> None:
    kb_id = "concepts/statecraft/virtue"
    metadata = _metadata(kb_id, "statecraft")
    document = KBDocument(
        kb_id=kb_id,
        slug="virtue",
        title="Virtue",
        metadata=metadata,
        aliases=("virtu",),
        related_concepts=("concepts/statecraft/fortune",),
        body="Virtue and statecraft." * 50,
    )
    analyzer = QualityAnalyzer()

    score = analyzer.calculate_completeness(document)

    assert metadata.ia.completeness is not None
    assert score > metadata.ia.completeness
    assert score <= 1.0


def _write_document(path: Path, front_matter: dict[str, object], body: str) -> None:
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False)
    if body and not body.endswith("\n"):
        body = f"{body}\n"
    payload = f"---\n{yaml_block}---\n"
    if body:
        payload = f"{payload}\n{body}"
    path.write_text(payload, encoding="utf-8")


def test_calculate_findability_rewards_link_context(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    kb_id = "concepts/statecraft/virtue"
    front = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": kb_id,
        "type": "concept",
        "tags": ["statecraft", "virtue"],
        "related_concepts": ["concepts/statecraft/fortune"],
        "aliases": ["virtu"],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [1]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": [
                "concepts/statecraft/fortune",
                "concepts/statecraft/power",
            ],
            "findability_score": 0.6,
            "completeness": 0.85,
        },
    }
    body = "# Virtue\n\nVirtue balances fortune and power.\n"
    path = (kb_root / kb_id).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_document(path, front, body)

    analyzer = QualityAnalyzer()
    score = analyzer.calculate_findability(kb_id, kb_root)

    assert score > 0.6
    assert score <= 1.0


def test_identify_gaps_flags_missing_metadata(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    kb_id = "concepts/statecraft/fortune"
    front = {
        "title": "Fortune",
        "slug": "fortune",
        "kb_id": kb_id,
        "type": "concept",
        "related_concepts": [],
        "sources": [],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "fortune"],
            "related_by_topic": [],
            "findability_score": 0.5,
            "completeness": 0.6,
        },
    }
    body = "Brief fortune entry.\n"
    path = (kb_root / kb_id).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_document(path, front, body)

    analyzer = QualityAnalyzer()
    gaps = analyzer.identify_gaps(kb_root)

    issues = {gap.issue for gap in gaps}
    assert "missing-sources" in issues
    assert "missing-tags" in issues
    assert "missing-related-concepts" in issues
    assert "missing-backlinks" in issues
    assert "body-too-short" in issues
    assert "findability-below-threshold" in issues
    assert "completeness-below-threshold" in issues

    severities = {gap.issue: gap.severity for gap in gaps}
    assert severities["missing-sources"] == "error"
    assert severities["body-too-short"] == "warning"
