"""Tests for parsing orchestration tool registrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.orchestration.toolkit import register_parsing_tools
from src.orchestration.tools import ToolRegistry
from src.parsing import utils as parsing_utils
from src.parsing.base import ParsedDocument
from src.parsing.registry import ParserRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_parsing_tools(reg)
    return reg


def test_list_parse_candidates_returns_files(tmp_path: Path, registry: ToolRegistry):
    root = tmp_path / "docs"
    root.mkdir()
    target_pdf = root / "keep.pdf"
    target_pdf.write_text("pdf", encoding="utf-8")
    ignored = root / "ignore.docx"
    ignored.write_text("ignored", encoding="utf-8")

    result = registry.execute_tool(
        "list_parse_candidates",
        {"root": str(root), "suffixes": [".pdf"]},
    )

    assert result.success
    assert result.error is None
    assert result.output == [str(target_pdf.resolve())]


def test_list_parse_candidates_honours_limit(tmp_path: Path, registry: ToolRegistry):
    root = tmp_path / "docs"
    root.mkdir()
    for index in range(5):
        (root / f"file{index}.pdf").write_text("content", encoding="utf-8")

    result = registry.execute_tool(
        "list_parse_candidates",
        {"root": str(root), "suffixes": [".pdf"], "limit": 2},
    )

    assert result.success
    assert result.output is not None
    assert len(result.output) == 2


def test_preview_parse_document_uses_temporary_storage(monkeypatch, tmp_path: Path, registry: ToolRegistry):

    class DummyTextParser:
        name = "dummy-text"

        def detect(self, target):  # type: ignore[override]
            try:
                return target.to_path().suffix.lower() == ".txt"
            except ValueError:
                return False

        def extract(self, target):  # type: ignore[override]
            path = target.to_path()
            checksum = parsing_utils.sha256_path(path)
            document = ParsedDocument(target=target, checksum=checksum, parser_name=self.name)
            document.add_segment(path.read_text(encoding="utf-8"))
            return document

        def to_markdown(self, document):  # type: ignore[override]
            return "\n\n".join(document.segments)

    custom_registry = ParserRegistry()
    custom_registry.register_parser(DummyTextParser(), suffixes=(".txt",), priority=50, replace=True)
    monkeypatch.setattr("src.parsing.runner.registry", custom_registry)

    source = tmp_path / "sample.txt"
    source.write_text("sample preview content", encoding="utf-8")

    result = registry.execute_tool(
        "preview_parse_document",
        {
            "source": str(source),
            "expected_parser": "dummy-text",
            "max_preview_chars": 200,
        },
    )

    assert result.success
    assert result.error is None
    assert result.output is not None
    assert result.output["status"] == "completed"
    assert result.output["parser"] == "dummy-text"
    assert result.output["preview"] is not None
    preview = result.output["preview"]
    assert preview["content"].strip().startswith("sample preview content")
    assert preview["truncated"] is False

