"""CLI commands for person extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.integrations.copilot import CopilotClient, CopilotClientError
from src.knowledge.storage import KnowledgeGraphStorage
from src.parsing.config import load_parsing_config
from src.parsing.extraction import PersonExtractor, process_document
from src.parsing.storage import ParseStorage


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add extraction-focused subcommands to the main CLI parser."""
    parser = subparsers.add_parser(
        "extract",
        description="Extract people from parsed documents.",
        help="Extract people from parsed documents.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of documents to process.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess documents even if already extracted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be extracted without saving.",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        help="Root directory for the knowledge graph.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to parsing configuration file.",
    )
    parser.set_defaults(func=extract_cli, command="extract")


def extract_cli(args: argparse.Namespace) -> int:
    """Execute the extraction workflow."""
    
    # Initialize components
    try:
        config = load_parsing_config(args.config)
        storage = ParseStorage(config.output_root)
        kb_storage = KnowledgeGraphStorage(args.kb_root)
        
        # Initialize Copilot client
        # This will raise if token is missing
        client = CopilotClient()
        extractor = PersonExtractor(client)
        
    except (FileNotFoundError, ValueError, CopilotClientError) as exc:
        print(f"Initialization error: {exc}", file=sys.stderr)
        return 1

    # Find candidates
    manifest = storage.manifest()
    candidates = []
    
    for checksum, entry in manifest.entries.items():
        if entry.status != "completed":
            continue
            
        # Check if already extracted
        if not args.force:
            existing = kb_storage.get_extracted_people(checksum)
            if existing:
                continue
                
        candidates.append(entry)

    if not candidates:
        print("No documents found needing extraction.")
        return 0

    print(f"Found {len(candidates)} documents to process.")
    
    # Apply limit
    if args.limit:
        candidates = candidates[:args.limit]
        print(f"Limiting to {len(candidates)} documents.")

    success_count = 0
    fail_count = 0

    for entry in candidates:
        print(f"Processing {entry.source} ({entry.checksum[:8]})...")
        
        if args.dry_run:
            print("  (dry run) would extract people")
            continue

        try:
            people = process_document(entry, storage, kb_storage, extractor)
            print(f"  Extracted {len(people)} people: {', '.join(people[:5])}{'...' if len(people) > 5 else ''}")
            success_count += 1
        except Exception as exc:
            print(f"  Failed: {exc}", file=sys.stderr)
            fail_count += 1

    print(f"\nExtraction complete. Success: {success_count}, Failed: {fail_count}")
    return 1 if fail_count > 0 else 0
