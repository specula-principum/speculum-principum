"""Parsing tool registrations for the orchestration runtime."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from src.parsing.runner import collect_parse_candidates, parse_single_target
from src.parsing.storage import ParseStorage

from ..safety import ActionRisk
from ..tools import ToolDefinition, ToolRegistry
from ..types import ToolResult


def register_parsing_tools(registry: ToolRegistry) -> None:
    """Register read-only parsing tools with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="list_parse_candidates",
            description="Scan a directory and return documents that match the parsing filters without executing parsers.",
            parameters={
                "type": "object",
                "properties": {
                    "root": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Directory to scan for parseable documents.",
                    },
                    "suffixes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional file suffix filters (e.g. .pdf). Defaults to configured suffixes when omitted.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Recurse into subdirectories (default: true).",
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns that candidate paths must match (relative to root).",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns that will exclude candidate paths (relative to root).",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Maximum number of candidates to return.",
                    },
                },
                "required": ["root"],
                "additionalProperties": False,
            },
            handler=_list_parse_candidates_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="preview_parse_document",
            description="Extract a single document using a temporary storage area and return a Markdown preview.",
            parameters={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "minLength": 1,
                        "description": "File path or URL to parse.",
                    },
                    "expected_parser": {
                        "type": "string",
                        "description": "Optional parser name that must match the detected parser.",
                    },
                    "media_type": {
                        "type": "string",
                        "description": "Explicit media type hint for parser selection.",
                    },
                    "is_remote": {
                        "type": "boolean",
                        "description": "Indicate whether the source should be treated as remote.",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Reprocess even if the document checksum is unchanged (default: false).",
                    },
                    "max_preview_chars": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20000,
                        "description": "Maximum number of characters to include in the Markdown preview (default: 5000).",
                    },
                },
                "required": ["source"],
                "additionalProperties": False,
            },
            handler=_preview_parse_document_handler,
            risk_level=ActionRisk.SAFE,
        )
    )


def _list_parse_candidates_handler(args: Mapping[str, Any]) -> ToolResult:
    root_arg = args.get("root")
    if not isinstance(root_arg, str) or not root_arg.strip():
        return ToolResult(success=False, output=None, error="root must be a non-empty string.")

    root = root_arg.strip()
    suffixes = _optional_string_sequence(args.get("suffixes"))
    include_patterns = _optional_string_sequence(args.get("include_patterns"))
    exclude_patterns = _optional_string_sequence(args.get("exclude_patterns"))

    recursive_value = args.get("recursive")
    recursive = recursive_value if isinstance(recursive_value, bool) else True

    limit_value = args.get("limit")
    limit = int(limit_value) if isinstance(limit_value, int) else None

    try:
        candidates = collect_parse_candidates(
            root,
            suffixes=suffixes,
            recursive=recursive,
            storage_root=None,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
    except FileNotFoundError as exc:
        return ToolResult(success=False, output=None, error=str(exc))

    if limit is not None:
        candidates = candidates[:limit]

    return ToolResult(
        success=True,
        output=[str(path) for path in candidates],
        error=None,
    )


def _preview_parse_document_handler(args: Mapping[str, Any]) -> ToolResult:
    source_arg = args.get("source")
    if not isinstance(source_arg, str) or not source_arg.strip():
        return ToolResult(success=False, output=None, error="source must be a non-empty string.")

    source = source_arg.strip()
    expected_parser_arg = args.get("expected_parser")
    expected_parser = expected_parser_arg.strip() if isinstance(expected_parser_arg, str) and expected_parser_arg.strip() else None
    media_type_arg = args.get("media_type")
    media_type = media_type_arg.strip() if isinstance(media_type_arg, str) and media_type_arg.strip() else None

    force = bool(args.get("force", False))
    is_remote_value = args.get("is_remote")
    is_remote = is_remote_value if isinstance(is_remote_value, bool) else None

    max_preview_chars = args.get("max_preview_chars")
    preview_limit = int(max_preview_chars) if isinstance(max_preview_chars, int) else 5000
    if preview_limit <= 0:
        preview_limit = 1

    with TemporaryDirectory(prefix="parse-preview-") as temp_dir:
        storage = ParseStorage(Path(temp_dir))
        outcome = parse_single_target(
            source,
            storage=storage,
            expected_parser=expected_parser,
            force=force,
            media_type=media_type,
            is_remote=is_remote,
        )

        if outcome.status == "error":
            message = outcome.error or "Parsing failed."
            return ToolResult(success=False, output=None, error=message)

        artifact_info = None
        if outcome.artifact_path:
            artifact_path = storage.root / outcome.artifact_path
            if artifact_path.exists():
                preview_file = artifact_path
                parent_directory = artifact_path.parent
                if parent_directory.exists():
                    candidates = sorted(parent_directory.glob("page-*.md"))
                    if not candidates:
                        candidates = sorted(parent_directory.glob("segment-*.md"))
                    if candidates:
                        preview_file = candidates[0]
                try:
                    content = preview_file.read_text(encoding="utf-8")
                except OSError:
                    content = ""
                preview_source = _strip_markdown_front_matter(content)
                if not preview_source.strip():
                    preview_source = content
                truncated = len(preview_source) > preview_limit
                preview_text = preview_source[:preview_limit]
                try:
                    relative_preview_path = str(preview_file.relative_to(storage.root))
                except ValueError:
                    relative_preview_path = str(preview_file)
                artifact_info = {
                    "relative_path": relative_preview_path,
                    "content": preview_text,
                    "truncated": truncated,
                }

        payload = {
            "status": outcome.status,
            "parser": outcome.parser,
            "artifact_path": outcome.artifact_path,
            "warnings": list(outcome.warnings),
            "checksum": outcome.checksum,
            "message": outcome.message,
            "preview": artifact_info,
        }

        return ToolResult(success=True, output=payload, error=None)


def _optional_string_sequence(values: Any) -> Sequence[str] | None:
    if values is None:
        return None
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
        items = [str(value) for value in values if str(value).strip()]
        return tuple(items) if items else None
    return None


def _strip_markdown_front_matter(markdown: str) -> str:
    if not markdown.startswith("---"):
        return markdown
    closing_marker = "\n---\n"
    closing_index = markdown.find(closing_marker, 3)
    if closing_index == -1:
        return markdown
    remaining = markdown[closing_index + len(closing_marker) :]
    return remaining.lstrip("\n")


__all__ = ["register_parsing_tools"]
