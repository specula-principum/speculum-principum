"""Tests for the segments extractor."""
from __future__ import annotations

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
