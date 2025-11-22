"""CLI commands for document parsing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.parsing.config import load_parsing_config
from src.parsing.runner import parse_single_target, scan_and_parse
from src.parsing.storage import ParseStorage


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add parsing-focused subcommands to the main CLI parser."""
    parser = subparsers.add_parser(
        "parse",
        description="Parse documents into markdown artifacts.",
        help="Parse documents into markdown artifacts.",
    )
    
    subcommand_parsers = parser.add_subparsers(dest="parse_command", metavar="COMMAND")
    subcommand_parsers.required = True
    # parse pdf
    _register_pdf_command(subcommand_parsers)
    
    # parse docx
    _register_docx_command(subcommand_parsers)
    
    # parse web
    _register_web_command(subcommand_parsers)
    
    # parse scan
    _register_scan_command(subcommand_parsers)


def _register_pdf_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register 'parse pdf' command."""
    parser = subparsers.add_parser(
        "pdf",
        help="Parse one or more PDF files.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Path(s) to PDF file(s) to parse.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Override output directory for parsed artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to parsing configuration file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess files even if already parsed.",
    )
    parser.set_defaults(func=parse_pdf_cli, command="parse", parse_command="pdf")


def _register_docx_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register 'parse docx' command."""
    parser = subparsers.add_parser(
        "docx",
        help="Parse one or more DOCX files.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Path(s) to DOCX file(s) to parse.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Override output directory for parsed artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to parsing configuration file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess files even if already parsed.",
    )
    parser.set_defaults(func=parse_docx_cli, command="parse", parse_command="docx")


def _register_web_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register 'parse web' command."""
    parser = subparsers.add_parser(
        "web",
        help="Parse HTTP(S) URLs or local HTML files.",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="URL(s) or path(s) to HTML file(s) to parse.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Override output directory for parsed artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to parsing configuration file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess sources even if already parsed.",
    )
    parser.set_defaults(func=parse_web_cli, command="parse", parse_command="web")


def _register_scan_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register 'parse scan' command."""
    parser = subparsers.add_parser(
        "scan",
        help="Scan a directory and parse matching files.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path("./evidence"),
        help="Directory to scan (default: ./evidence).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Override output directory for parsed artifacts.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to parsing configuration file.",
    )
    parser.add_argument(
        "--suffix",
        action="append",
        dest="suffixes",
        help="File suffix to include (can be specified multiple times).",
    )
    parser.add_argument(
        "--include",
        action="append",
        dest="include_patterns",
        help="Glob pattern to include (can be specified multiple times).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude_patterns",
        help="Glob pattern to exclude (can be specified multiple times).",
    )
    parser.add_argument(
        "--recursive/--no-recursive",
        dest="recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to scan subdirectories (default: True).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of files to parse.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess files even if already parsed.",
    )
    parser.add_argument(
        "--clear-config-suffixes",
        action="store_true",
        help="Ignore suffix patterns from config file.",
    )
    parser.add_argument(
        "--clear-config-include",
        action="store_true",
        help="Ignore include patterns from config file.",
    )
    parser.add_argument(
        "--clear-config-exclude",
        action="store_true",
        help="Ignore exclude patterns from config file.",
    )
    parser.set_defaults(func=parse_scan_cli, command="parse", parse_command="scan")


def parse_pdf_cli(args: argparse.Namespace) -> int:
    """Execute PDF parsing."""
    return _parse_files_cli(args, expected_parser="pdf")


def parse_docx_cli(args: argparse.Namespace) -> int:
    """Execute DOCX parsing."""
    return _parse_files_cli(args, expected_parser="docx")


def parse_web_cli(args: argparse.Namespace) -> int:
    """Execute web/HTML parsing."""
    sources = args.sources
    return _parse_files_cli(args, expected_parser=None, sources=sources)


def _parse_files_cli(
    args: argparse.Namespace,
    expected_parser: str | None = None,
    sources: list[str] | None = None,
) -> int:
    """Common logic for parsing individual files."""
    try:
        config = load_parsing_config(args.config)
        
        # Override output root if specified
        if args.output_root:
            config.output_root = Path(args.output_root).expanduser().resolve()
            
        storage = ParseStorage(config.output_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    
    # Get list of sources to parse
    if sources is None:
        sources = [str(p) for p in args.paths]
    
    if not sources:
        print("No sources specified.", file=sys.stderr)
        return 1
    
    print(f"Processing {len(sources)} source(s)...")
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for source in sources:
        outcome = parse_single_target(
            source,
            storage=storage,
            expected_parser=expected_parser,
            force=args.force,
        )
        
        # Print status
        status_marker = "✓" if outcome.succeeded else "✗"
        print(f"{status_marker} [{outcome.parser or 'unknown'}] {outcome.source}")
        
        if outcome.artifact_path:
            print(f"  → {outcome.artifact_path}")
        
        if outcome.message:
            print(f"  {outcome.message}")
            
        if outcome.warnings:
            for warning in outcome.warnings:
                print(f"  ⚠ {warning}")
                
        if outcome.error:
            print(f"  Error: {outcome.error}", file=sys.stderr)
        
        # Update counters
        if outcome.status == "skipped":
            skip_count += 1
        elif outcome.succeeded:
            success_count += 1
        else:
            fail_count += 1
    
    # Print summary
    print(f"\nSummary: {success_count} succeeded, {skip_count} skipped, {fail_count} failed")
    
    return 1 if fail_count > 0 else 0


def parse_scan_cli(args: argparse.Namespace) -> int:
    """Execute directory scanning and parsing."""
    try:
        config = load_parsing_config(args.config)
        
        # Override output root if specified
        if args.output_root:
            config.output_root = Path(args.output_root).expanduser().resolve()
        
        # Build effective scan configuration
        suffixes = None
        if args.clear_config_suffixes:
            suffixes = tuple(args.suffixes) if args.suffixes else None
        elif args.suffixes:
            # Merge with config
            suffixes = tuple(args.suffixes)
        else:
            suffixes = config.scan.suffixes
        
        include_patterns = None
        if args.clear_config_include:
            include_patterns = tuple(args.include_patterns) if args.include_patterns else None
        elif args.include_patterns:
            include_patterns = tuple(args.include_patterns)
        else:
            include_patterns = config.scan.include
        
        exclude_patterns = None
        if args.clear_config_exclude:
            exclude_patterns = tuple(args.exclude_patterns) if args.exclude_patterns else None
        elif args.exclude_patterns:
            exclude_patterns = tuple(args.exclude_patterns)
        else:
            exclude_patterns = config.scan.exclude
        
        recursive = args.recursive if args.recursive is not None else config.scan.recursive
        
        storage = ParseStorage(config.output_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    
    root = args.root
    if not root.exists():
        print(f"Scan root '{root}' does not exist.", file=sys.stderr)
        return 1
    
    print(f"Scanning {root}...")
    
    # Execute scan and parse
    try:
        outcomes = scan_and_parse(
            root,
            storage=storage,
            suffixes=suffixes,
            recursive=recursive,
            force=args.force,
            limit=args.limit,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
    except Exception as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 1
    
    if not outcomes:
        print("No matching files found.")
        return 0
    
    # Print results
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for outcome in outcomes:
        status_marker = "✓" if outcome.succeeded else "✗"
        print(f"{status_marker} [{outcome.parser or 'unknown'}] {outcome.source}")
        
        if outcome.artifact_path:
            print(f"  → {outcome.artifact_path}")
        
        if outcome.message:
            print(f"  {outcome.message}")
            
        if outcome.warnings:
            for warning in outcome.warnings:
                print(f"  ⚠ {warning}")
                
        if outcome.error:
            print(f"  Error: {outcome.error}", file=sys.stderr)
        
        # Update counters
        if outcome.status == "skipped":
            skip_count += 1
        elif outcome.succeeded:
            success_count += 1
        else:
            fail_count += 1
    
    # Print summary
    print(f"\nSummary: {success_count} succeeded, {skip_count} skipped, {fail_count} failed")
    
    return 1 if fail_count > 0 else 0
