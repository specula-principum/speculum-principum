"""Parsing CLI commands for converting documents to Markdown."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from src.parsing.config import load_parsing_config
from src.parsing.runner import parse_single_target, scan_and_parse
from src.parsing.storage import ParseStorage

__all__ = ["register_commands"]


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add parsing-related commands to the main CLI parser."""
    register_parse_command(subparsers)


def register_parse_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "parse",
        description="Parse documents into Markdown artifacts.",
        help="Parse documents into Markdown artifacts.",
    )
    _configure_parser(parser)
    return parser


def build_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse documents into Markdown artifacts.",
        prog=prog,
    )
    _configure_parser(parser)
    return parser


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Directory for Markdown outputs (overrides configuration).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to a parsing YAML config (default: config/parsing.yaml when present).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even when an identical checksum exists in the manifest.",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    pdf_parser = subcommands.add_parser("pdf", help="Parse one or more PDF files.")
    pdf_parser.add_argument("paths", nargs="+", type=Path, help="PDF files to parse.")

    docx_parser = subcommands.add_parser("docx", help="Parse one or more DOCX files.")
    docx_parser.add_argument("paths", nargs="+", type=Path, help="DOCX files to parse.")

    web_parser = subcommands.add_parser("web", help="Parse HTTP URLs or local HTML files.")
    web_parser.add_argument("sources", nargs="+", help="URL or file path to parse.")

    scan_parser = subcommands.add_parser("scan", help="Scan a directory for parseable documents.")
    scan_parser.add_argument(
        "--root",
        type=Path,
        default=Path("evidence"),
        help="Directory to scan for documents (defaults to ./evidence).",
    )
    scan_parser.add_argument(
        "--suffix",
        action="append",
        default=[],
        help="File suffix to include (e.g. .pdf). Repeat to supply multiple values.",
    )
    scan_parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Recursively scan subdirectories (default controlled by configuration).",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to process during scanning.",
    )
    scan_parser.add_argument(
        "--include",
        action="append",
        dest="include",
        metavar="PATTERN",
        help="Glob pattern relative to the scan root to include. Repeat to supply multiple patterns.",
    )
    scan_parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude",
        metavar="PATTERN",
        help="Glob pattern relative to the scan root to exclude. Repeat to supply multiple patterns.",
    )
    scan_parser.add_argument(
        "--clear-config-suffixes",
        action="store_true",
        help="Ignore suffix patterns defined in the parsing config when combining with --suffix.",
    )
    scan_parser.add_argument(
        "--clear-config-include",
        action="store_true",
        help="Ignore include patterns from the parsing config when combining with --include.",
    )
    scan_parser.add_argument(
        "--clear-config-exclude",
        action="store_true",
        help="Ignore exclude patterns from the parsing config when combining with --exclude.",
    )
    scan_parser.set_defaults(include=None, exclude=None)

    parser.set_defaults(func=parse_cli, command="parse")


def parse_cli(args: argparse.Namespace) -> int:
    try:
        config = load_parsing_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_root = args.output_root if args.output_root is not None else config.output_root
    output_root = Path(output_root).expanduser().resolve()
    storage = ParseStorage(output_root)
    outcomes = []

    if args.command == "pdf":
        for path in args.paths:
            resolved = path.expanduser().resolve()
            outcome = parse_single_target(
                resolved,
                storage=storage,
                expected_parser="pdf",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "docx":
        for path in args.paths:
            resolved = path.expanduser().resolve()
            outcome = parse_single_target(
                resolved,
                storage=storage,
                expected_parser="docx",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "web":
        for token in args.sources:
            candidate = Path(token).expanduser()
            source = candidate.resolve() if candidate.exists() else token
            outcome = parse_single_target(
                source,
                storage=storage,
                expected_parser="web",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "scan":
        suffixes = _merge_cli_sequences(
            config.scan.suffixes,
            args.suffix,
            clear=args.clear_config_suffixes,
        )
        recursive = config.scan.recursive if args.recursive is None else bool(args.recursive)
        include_patterns = _merge_cli_sequences(
            config.scan.include,
            args.include,
            clear=args.clear_config_include,
        )
        exclude_patterns = _merge_cli_sequences(
            config.scan.exclude,
            args.exclude,
            clear=args.clear_config_exclude,
        )
        try:
            results = scan_and_parse(
                args.root,
                storage=storage,
                suffixes=suffixes,
                recursive=recursive,
                force=args.force,
                limit=args.limit,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not results:
            print(
                f"No documents found under {args.root.expanduser().resolve()} matching the requested filters."
            )
            return 0
        for outcome in results:
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    else:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported parse subcommand: {args.command}")

    return 1 if any(item.status == "error" for item in outcomes) else 0


def _emit_parse_outcome(outcome) -> None:
    status = outcome.status
    parser_name = outcome.parser or "unknown"
    if status == "error":
        message = outcome.error or "Parsing failed"
        print(f"[error] {outcome.source}: {message}", file=sys.stderr)
        return

    artifact = f" -> {outcome.artifact_path}" if outcome.artifact_path else ""
    memo = f" ({outcome.message})" if outcome.message else ""
    print(f"[{status}] {outcome.source} via {parser_name}{artifact}{memo}")
    for warning in outcome.warnings:
        print(f"  warning: {warning}")


def _merge_cli_sequences(
    config_values: Iterable[str],
    cli_values: Iterable[str] | None,
    *,
    clear: bool,
) -> tuple[str, ...]:
    merged: list[str] = []
    if not clear:
        for value in config_values:
            token = str(value).strip()
            if token:
                merged.append(token)
    if cli_values:
        for value in cli_values:
            token = str(value).strip()
            if token:
                merged.append(token)
    seen: set[str] = set()
    ordered: list[str] = []
    for value in merged:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)
