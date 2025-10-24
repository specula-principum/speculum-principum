"""PDF parser implementation using the pypdf library."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from . import utils
from .base import ParsedDocument, ParseTarget, ParserError
from .markdown import document_to_markdown
from .registry import registry


@dataclass(slots=True)
class PdfParser:
    """Concrete :class:`DocumentParser` for PDF sources."""

    name: str = "pdf"

    def detect(self, target: ParseTarget) -> bool:
        if target.is_remote:
            return False
        try:
            path = target.to_path()
        except ValueError:
            return False
        if not path.exists() or not path.is_file():
            return False
        if path.suffix.lower() == ".pdf":
            return True
        media_type = target.media_type or utils.guess_media_type(path)
        return bool(media_type and media_type.lower() == "application/pdf")

    def extract(self, target: ParseTarget) -> ParsedDocument:
        path = self._require_local_file(target)

        checksum = utils.sha256_path(path)
        document = ParsedDocument(target=target, checksum=checksum, parser_name=self.name)

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:  # pragma: no cover - library-specific failure path
            raise ParserError(f"Failed to read PDF '{path}': {exc}") from exc

        if reader.is_encrypted:
            if not self._try_decrypt(reader):
                raise ParserError(f"PDF '{path}' is encrypted and could not be decrypted")

        self._populate_metadata(document, reader, path)
        self._extract_pages(document, reader)
        return document

    def to_markdown(self, document: ParsedDocument) -> str:
        return document_to_markdown(document)

    @staticmethod
    def _require_local_file(target: ParseTarget) -> Path:
        if target.is_remote:
            raise ParserError("PDF parser currently supports local files only")
        try:
            path = target.to_path()
        except ValueError as exc:
            raise ParserError(str(exc)) from exc
        if not path.exists():
            raise ParserError(f"PDF file '{path}' does not exist")
        if not path.is_file():
            raise ParserError(f"PDF target '{path}' is not a file")
        return path

    @staticmethod
    def _try_decrypt(reader: PdfReader) -> bool:
        try:
            reader.decrypt("")
        except (PdfReadError, ValueError):  # pragma: no cover - depends on encrypted fixture availability
            return False
        return not reader.is_encrypted

    def _populate_metadata(self, document: ParsedDocument, reader: PdfReader, path: Path) -> None:
        pdf_meta = getattr(reader, "metadata", None) or {}
        document.metadata.update(
            {
                "page_count": len(reader.pages),
                "file_size": path.stat().st_size,
                "pdf_metadata": _normalize_pdf_metadata(pdf_meta),
            }
        )

    def _extract_pages(self, document: ParsedDocument, reader: PdfReader) -> None:
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = _extract_page_text(page)
            except PdfReadError as exc:  # pragma: no cover - rare backend failure
                document.warnings.append(f"Failed to extract page {index}: {exc}")
                continue

            cleaned = text.strip()
            if cleaned:
                document.add_segment(cleaned)
            else:
                document.warnings.append(f"Page {index} yielded no extractable text")


def _normalize_pdf_metadata(metadata: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(metadata, dict):
        items = metadata.items()
    else:
        items = getattr(metadata, "items", lambda: [])()

    for key, value in items:
        if not isinstance(key, str):
            continue
        key = key.lstrip("/")
        if value is None:
            continue
        result[key] = str(value)
    return result


def _extract_page_text(page: Any) -> str:
    try:
        text = page.extract_text(
            extraction_mode="layout",
            layout_mode_space_vertically=False,
            layout_mode_strip_rotated=False,
        )
    except TypeError:
        try:
            text = page.extract_text(extraction_mode="layout")
        except TypeError:
            text = page.extract_text()

    if not text:
        return ""

    cleaned = text.replace("\u00a0", " ")
    return _normalize_layout_text(cleaned)


_INTRALINE_WHITESPACE_PATTERN = re.compile(r"[^\S\n]+")


def _normalize_layout_text(text: str) -> str:
    """Collapse excessive spacing without losing paragraph structure."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    trimmed_lines: list[str] = []
    for raw in lines:
        token = raw.strip()
        if not token:
            trimmed_lines.append("")
            continue
        collapsed = _INTRALINE_WHITESPACE_PATTERN.sub(" ", token)
        trimmed_lines.append(collapsed)

    result: list[str] = []
    previous_blank = False
    for line in trimmed_lines:
        if not line:
            if result and not previous_blank:
                result.append("")
            previous_blank = True
            continue
        result.append(line)
        previous_blank = False

    return "\n".join(result).strip()


pdf_parser = PdfParser()
registry.register_parser(
    pdf_parser,
    media_types=("application/pdf",),
    suffixes=(".pdf",),
    priority=10,
    replace=True,
)

__all__ = ["PdfParser", "pdf_parser"]
