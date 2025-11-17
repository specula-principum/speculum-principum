"""Tests for the segments extractor."""
from __future__ import annotations

from pathlib import Path

from src.extraction.segments import segment_text

SAMPLE_TEXT = """# Prelude

The Prince explores power.

- Observe reality
- Adapt strategy

> Fortune favors the prepared mind.
"""


def test_segment_text_detects_heading_paragraph_list_and_quote() -> None:
    result = segment_text(SAMPLE_TEXT)
    segments = list(result.data)

    assert segments[0].segment_type == "heading"
    assert segments[0].text == "Prelude"
    assert segments[0].level == 1

    paragraph = segments[1]
    assert paragraph.segment_type == "paragraph"
    assert paragraph.text == "The Prince explores power."

    list_segment = segments[2]
    assert list_segment.segment_type == "list"
    assert "Observe reality" in list_segment.text
    assert "Adapt strategy" in list_segment.text

    quote = segments[3]
    assert quote.segment_type == "quote"
    assert quote.text == "Fortune favors the prepared mind."

    counts = result.metadata["counts"]
    assert counts == {"heading": 1, "paragraph": 1, "list": 1, "quote": 1}
    for segment in segments:
        assert segment.start_offset >= 0
        assert segment.end_offset >= segment.start_offset


def test_segment_text_detects_structured_governance_headings() -> None:
    fixture_path = Path("tests/extraction/fixtures/governance/section_headings.md")
    text = fixture_path.read_text(encoding="utf-8")

    result = segment_text(text)
    segments = list(result.data)

    heading_texts = [segment.text for segment in segments if segment.segment_type == "heading"]

    assert heading_texts[0] == "Section 1.01 - Purpose and Scope"
    assert heading_texts[1] == "Section 2-104(A)(1) - Emergency Powers"
    assert heading_texts[2] == "Article II - Powers of Council"
    assert heading_texts[3] == "Section 3-12 - Budget Adoption"

    heading_levels = [segment.level for segment in segments if segment.segment_type == "heading"]
    assert heading_levels[0] == 3
    assert heading_levels[1] == 3
    assert heading_levels[2] == 2  # articles align with chapter-level headings
    assert heading_levels[3] == 3

    paragraph_segments = [segment for segment in segments if segment.segment_type == "paragraph"]
    assert len(paragraph_segments) == 4
    assert "emergency authority" in paragraph_segments[1].text
