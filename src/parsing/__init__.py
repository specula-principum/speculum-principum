"""Document parsing infrastructure primitives."""

from importlib import import_module

from .base import ParsedDocument, ParseTarget, DocumentParser, ParserError
from .markdown import document_to_markdown
from .config import ParsingConfig, ScanConfig, load_parsing_config
from .runner import ParseOutcome, parse_single_target, scan_and_parse
from .docx import DocxParser, docx_parser
from .pdf import PdfParser, pdf_parser
from .web import WebParser, web_parser
from .registry import ParserRegistry, registry
from .storage import ManifestEntry, Manifest, ParseStorage

utils = import_module("src.parsing.utils")

__all__ = [
    "ParsedDocument",
    "ParseTarget",
    "DocumentParser",
    "ParserError",
    "ManifestEntry",
    "Manifest",
    "ParseStorage",
    "ParserRegistry",
    "registry",
    "ParsingConfig",
    "ScanConfig",
    "load_parsing_config",
    "ParseOutcome",
    "parse_single_target",
    "scan_and_parse",
    "DocxParser",
    "docx_parser",
    "PdfParser",
    "pdf_parser",
    "WebParser",
    "web_parser",
    "document_to_markdown",
    "utils",
]
