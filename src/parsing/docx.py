"""DOCX parser implementation using python-docx."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Any, Iterable, Iterator, Sequence

from docx import Document as load_docx
from docx.document import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from . import utils
from .base import ParsedDocument, ParseTarget, ParserError
from .markdown import document_to_markdown
from .registry import registry


@dataclass(slots=True)
class DocxParser:
    """Concrete :class:`DocumentParser` for DOCX sources."""

    name: str = "docx"

    def detect(self, target: ParseTarget) -> bool:
        if target.is_remote:
            return False
        try:
            path = target.to_path()
        except ValueError:
            return False
        if not path.exists() or not path.is_file():
            return False
        if path.suffix.lower() == ".docx":
            return True
        media_type = target.media_type or utils.guess_media_type(path)
        if not media_type:
            return False
        return media_type.lower() == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def extract(self, target: ParseTarget) -> ParsedDocument:
        path = self._require_local_file(target)
        checksum = utils.sha256_path(path)
        document = ParsedDocument(target=target, checksum=checksum, parser_name=self.name)

        try:
            docx_document = load_docx(str(path))
        except (PackageNotFoundError, ValueError, OSError) as exc:
            raise ParserError(f"Failed to read DOCX '{path}': {exc}") from exc

        blocks = list(_iter_document_blocks(docx_document))
        paragraph_count = sum(isinstance(block, DocxParagraph) for block in blocks)
        table_count = sum(isinstance(block, DocxTable) for block in blocks)

        metadata = _extract_core_properties(docx_document)
        metadata.update(
            {
                "paragraph_count": paragraph_count,
                "table_count": table_count,
                "file_size": path.stat().st_size,
            }
        )
        document.metadata.update(metadata)

        for block in blocks:
            if isinstance(block, DocxParagraph):
                rendered = _paragraph_to_markdown(block)
                if rendered:
                    document.add_segment(rendered)
            elif isinstance(block, DocxTable):
                rendered_table = _table_to_markdown(block)
                if rendered_table:
                    document.add_segment(rendered_table)
                else:
                    document.warnings.append("Encountered empty table while parsing DOCX")
            else:  # pragma: no cover - defensive branch for unforeseen block types
                document.warnings.append(f"Unsupported DOCX element: {type(block)!r}")

        if not document.segments:
            document.warnings.append("DOCX file contained no extractable content")

        return document

    def to_markdown(self, document: ParsedDocument) -> str:
        return document_to_markdown(document)

    @staticmethod
    def _require_local_file(target: ParseTarget) -> Path:
        if target.is_remote:
            raise ParserError("DOCX parser currently supports local files only")
        try:
            path = target.to_path()
        except ValueError as exc:
            raise ParserError(str(exc)) from exc
        if not path.exists():
            raise ParserError(f"DOCX file '{path}' does not exist")
        if not path.is_file():
            raise ParserError(f"DOCX target '{path}' is not a file")
        return path


def _iter_document_blocks(doc: DocxDocument) -> Iterator[DocxParagraph | DocxTable]:
    """Yield block-level elements preserving document order."""

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield DocxParagraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield DocxTable(child, doc)


def _paragraph_to_markdown(paragraph: DocxParagraph) -> str | None:
    text = paragraph.text.strip()
    if not text:
        return None

    heading_level = _detect_heading_level(paragraph)
    if heading_level:
        return f"{'#' * heading_level} {text}"

    if _is_list_item(paragraph):
        indent_level = _list_indent_level(paragraph)
        bullet = "-"
        return f"{'  ' * indent_level}{bullet} {text}"

    return text


def _detect_heading_level(paragraph: DocxParagraph) -> int | None:
    style = paragraph.style
    if style is None or not style.name:
        return None
    name = style.name.lower()
    if name.startswith("heading"):
        parts = name.split()
        if len(parts) >= 2 and parts[1].isdigit():
            level = int(parts[1])
            if 1 <= level <= 6:
                return level
    return None


def _is_list_item(paragraph: DocxParagraph) -> bool:
    style = getattr(paragraph.style, "name", "") or ""
    if "list" in style.lower():
        return True

    base_style = getattr(paragraph.style, "base_style", None)
    while base_style is not None:
        name = getattr(base_style, "name", "") or ""
        if "list" in name.lower():
            return True
        base_style = getattr(base_style, "base_style", None)

    numbering = getattr(paragraph, "style", None)
    if numbering is not None:
        outline_level = getattr(paragraph.paragraph_format, "outline_level", None)
        if outline_level is not None:
            return True

    return False


def _list_indent_level(paragraph: DocxParagraph) -> int:
    indent = paragraph.paragraph_format.left_indent
    if indent is None:
        return 0
    try:
        points = indent.pt
    except AttributeError:
        try:
            points = float(indent)
        except (TypeError, ValueError):
            return 0
    if points <= 0:
        return 0
    return min(int(points // 18), 4)


def _table_to_markdown(table: DocxTable) -> str:
    rows = list(table.rows)
    if not rows:
        return ""

    serialized_rows = [_serialize_table_row(row.cells) for row in rows]
    header = serialized_rows[0]
    body_rows = serialized_rows[1:]

    separator = ["---" for _ in header]

    lines = [
        _format_table_line(header),
        _format_table_line(separator),
    ]
    lines.extend(_format_table_line(row) for row in body_rows)
    return "\n".join(lines)


def _serialize_table_row(cells: Sequence[Any]) -> list[str]:
    rendered: list[str] = []
    for cell in cells:
        text = getattr(cell, "text", "")
        rendered.append(text.replace("\n", " ").strip())
    return rendered


def _format_table_line(values: Iterable[str]) -> str:
    return "| " + " | ".join(value or "" for value in values) + " |"


def _extract_core_properties(doc: DocxDocument) -> dict[str, Any]:
    props = doc.core_properties
    mapping = {
        "title": props.title,
        "subject": props.subject,
        "author": props.author,
        "category": props.category,
        "comments": props.comments,
        "created": getattr(props, "created", None),
        "modified": getattr(props, "modified", None),
        "keywords": props.keywords,
    }
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        if value in (None, ""):
            continue
        if isinstance(value, datetime):
            sanitized[key] = value.isoformat()
        else:
            sanitized[key] = value
    return sanitized


docx_parser = DocxParser()
registry.register_parser(
    docx_parser,
    media_types=("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
    suffixes=(".docx",),
    priority=8,
    replace=True,
)

__all__ = ["DocxParser", "docx_parser"]
