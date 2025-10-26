"""Tests for the structure extractor."""
from __future__ import annotations

from src.extraction.structure import analyze_structure

SAMPLE_TEXT = """# Introduction

The work begins here.

## Method

As described in Chapter 2, preparation matters.

Footnote appears here.[1]
"""


def test_analyze_structure_returns_headings_and_cross_references() -> None:
    result = analyze_structure(SAMPLE_TEXT)
    data = result.data

    headings = list(data["headings"])
    assert headings[0]["text"] == "Introduction"
    assert headings[0]["level"] == 1
    assert headings[1]["text"] == "Method"
    assert headings[1]["level"] == 2

    assert "Chapter 2" in data["cross_references"]
    assert data["footnotes"] == ("1",)
    assert result.metadata["has_table_of_contents"] is False
    assert result.metadata["cross_reference_count"] == 1
    assert result.metadata["footnote_count"] == 1
