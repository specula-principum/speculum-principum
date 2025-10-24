"""Tests for the PDF parser implementation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.parsing import registry
from src.parsing.base import ParseTarget, ParserError
from src.parsing.pdf import PdfParser, _normalize_layout_text, pdf_parser


def _write_pdf(path: Path, text: str) -> None:
    content = _build_pdf_bytes(text)
    path.write_bytes(content)


def _build_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT\n/F1 24 Tf\n72 720 Td\n({escaped}) Tj\nET\n"

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    stream_bytes = stream.encode("latin-1")
    obj4 = (
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
        + stream_bytes
        + b"endstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj6 = b"6 0 obj\n<< /Producer (speculum-principum tests) >>\nendobj\n"

    header = b"%PDF-1.4\n"
    objects = [obj1, obj2, obj3, obj4, obj5, obj6]

    content = bytearray()
    content.extend(header)

    offsets = [0]
    for obj in objects:
        offsets.append(len(content))
        content.extend(obj)

    xref_pos = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010} 00000 n \n".encode("ascii"))

    trailer = (
        f"trailer\n<< /Root 1 0 R /Info 6 0 R /Size {len(offsets)} >>\n".encode("ascii")
        + f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    content.extend(trailer)
    return bytes(content)


def test_pdf_parser_extracts_text_and_metadata(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(pdf_path, "Hello PDF World")

    parser = PdfParser()
    target = ParseTarget(source=str(pdf_path))

    assert parser.detect(target)

    document = parser.extract(target)

    assert document.segments
    assert "Hello PDF World" in document.segments[0]
    assert document.metadata["page_count"] == 1
    assert document.metadata["file_size"] == pdf_path.stat().st_size
    assert document.metadata["pdf_metadata"].get("Producer") is not None

    markdown = parser.to_markdown(document)
    assert "Hello PDF World" in markdown


def test_pdf_parser_handles_missing_file(tmp_path) -> None:
    parser = PdfParser()
    missing = tmp_path / "missing.pdf"
    target = ParseTarget(source=str(missing))

    with pytest.raises(ParserError):
        parser.extract(target)


def test_pdf_parser_registration(tmp_path) -> None:
    pdf_path = tmp_path / "with-registry.pdf"
    _write_pdf(pdf_path, "Registry Lookup")
    target = ParseTarget(source=str(pdf_path))

    parser = registry.require_parser(target)

    assert parser.name == pdf_parser.name
    document = parser.extract(target)
    assert document.segments


def test_pdf_parser_warns_when_page_is_empty(tmp_path) -> None:
    pdf_path = tmp_path / "empty.pdf"
    _write_pdf(pdf_path, "   ")

    parser = PdfParser()
    target = ParseTarget(source=str(pdf_path))

    document = parser.extract(target)

    assert document.is_empty()
    assert any("no extractable text" in warning for warning in document.warnings)


def test_normalize_layout_text_collapses_excess_spacing() -> None:
    messy = "  Line    one   with   gaps\r\n\n   Second\tline \n Third   line   "
    cleaned = _normalize_layout_text(messy)
    assert cleaned == "Line one with gaps\n\nSecond line\nThird line"