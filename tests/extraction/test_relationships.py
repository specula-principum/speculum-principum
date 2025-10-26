"""Tests for the relationships extractor."""
from __future__ import annotations

from src.extraction.relationships import extract_relationships


def test_extract_relationships_detects_support_and_opposition() -> None:
    text = (
        "Prince Henry supports the Council of Elders. "
        "The Council of Elders opposes the Rebel Faction."
    )

    result = extract_relationships(
        text,
        config={"source_path": "doc.md", "max_pairs_per_sentence": 4},
    )

    assert result.extractor_name == "relationships"
    assert result.metadata["source_path"] == "doc.md"

    triples = {(rel.subject, rel.object, rel.relation_type) for rel in result.data}
    assert ("Prince Henry", "Council of Elders", "support") in triples
    assert ("Council of Elders", "Rebel Faction", "opposition") in triples


def test_extract_relationships_custom_keywords_and_limits() -> None:
    text = "A treaty between Republic of Venice and Kingdom of France strengthened trade."
    config = {
        "source_path": "doc.md",
        "keywords": {"alliance": ["treaty", "between"]},
        "max_relationships": 1,
    }

    result = extract_relationships(text, config=config)

    assert len(result.data) == 1
    relationship = result.data[0]
    assert relationship.relation_type == "alliance"
    assert "treaty" in relationship.evidence.lower()


def test_extract_relationships_include_self_pairs() -> None:
    text = "Grand Council and Grand Council convened."

    result = extract_relationships(
        text,
        config={"source_path": "doc.md", "include_self_pairs": True, "max_pairs_per_sentence": 2},
    )

    assert any(rel.subject == rel.object for rel in result.data)
