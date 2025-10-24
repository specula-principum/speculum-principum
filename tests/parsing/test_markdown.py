from __future__ import annotations

from datetime import datetime, timezone

from src.parsing.base import ParseTarget, ParsedDocument
from src.parsing.markdown import document_to_markdown


def test_document_to_markdown_renders_front_matter_and_body() -> None:
    target = ParseTarget(source="docs/sample.pdf", media_type="application/pdf")
    document = ParsedDocument(
        target=target,
        checksum="e" * 64,
        parser_name="pdf",
    )
    document.created_at = datetime(2025, 10, 22, 9, 30, tzinfo=timezone.utc)
    document.metadata = {"page_count": 3}
    document.warnings.append("Skipped encrypted page")
    document.extend_segments(["Page one text", "Page two text"])

    markdown = document_to_markdown(document)

    assert markdown.startswith("---\n")
    assert "checksum: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" in markdown
    assert "parser: pdf" in markdown
    assert "- Skipped encrypted page" in markdown
    assert "Page one text" in markdown
    assert "Page two text" in markdown
    assert "segment_count: 2" in markdown
