"""Tests for the concepts extractor."""
from __future__ import annotations

from src.extraction.concepts import extract_concepts


def test_extract_concepts_returns_frequent_terms() -> None:
    text = (
        "Power and virtue shape governance. "
        "The power to rule demands prudence and virtue. "
        "Prudence guides power and statecraft."
    )

    result = extract_concepts(text, config={"source_path": "doc.md", "max_related_terms": 3})

    assert result.extractor_name == "concepts"
    assert result.metadata["source_path"] == "doc.md"

    concept_map = {concept.term.lower(): concept for concept in result.data}

    power = concept_map["power"]
    assert power.frequency == 3
    assert len(power.positions) == 3
    assert {term.lower() for term in power.related_terms} >= {"virtue", "prudence"}

    virtue = concept_map["virtue"]
    assert virtue.frequency == 2


def test_extract_concepts_stopword_handling() -> None:
    text = "And logic and reason and logic."  # three 'and', two 'logic'

    exclude_result = extract_concepts(text, config={"source_path": "doc.md"})
    exclude_terms = {concept.term.lower() for concept in exclude_result.data}
    assert "and" not in exclude_terms

    include_result = extract_concepts(
        text,
        config={"source_path": "doc.md", "exclude_stopwords": "false"},
    )
    include_terms = {concept.term.lower() for concept in include_result.data}
    assert "and" in include_terms


def test_extract_concepts_respects_limits_and_conversions() -> None:
    text = "Alpha Beta Gamma Alpha Beta Gamma"
    config = {
        "source_path": "doc.md",
        "min_frequency": "1",
        "max_concepts": "1",
        "window_size": "1",
        "max_related_terms": "2",
        "min_term_length": "5",
    }

    result = extract_concepts(text, config=config)

    assert len(result.data) == 1
    concept = result.data[0]
    assert concept.term == "Alpha"
    assert concept.frequency == 2
    assert result.metadata["selected_concepts"] == 1
    assert result.metadata["total_candidates"] >= 2
