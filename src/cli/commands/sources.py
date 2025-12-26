"""CLI commands for source management and discovery.

Workflow:
1. discover-sources: Scan parsed documents for URLs and rank by credibility
2. --propose: Create GitHub Discussions in 'Sources' category for proposals
3. Agent posts credibility assessment to Discussion
4. Human approves via /approve-source command -> Issue created
5. Agent implements via implement_approved_source -> source registered
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.knowledge.source_discovery import SourceDiscoverer
from src.knowledge.storage import SourceRegistry


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add source-focused subcommands to the main CLI parser."""

    # discover-sources command
    discover_parser = subparsers.add_parser(
        "discover-sources",
        description="Discover potential sources from parsed documents.",
        help="Scan parsed documents for URLs and rank by credibility.",
    )
    discover_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show candidates without creating proposal Discussions.",
    )
    discover_parser.add_argument(
        "--propose",
        action="store_true",
        help="Create GitHub Discussions for top candidates (requires --limit).",
    )
    discover_parser.add_argument(
        "--checksum",
        type=str,
        help="Limit discovery to a specific document checksum.",
    )
    discover_parser.add_argument(
        "--domain-filter",
        type=str,
        help="Regex pattern to filter domains (e.g., '\\.gov$|\\.edu$').",
    )
    discover_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of candidates to show (default: 20).",
    )
    discover_parser.add_argument(
        "--kb-root",
        type=Path,
        help="Root directory for the knowledge graph.",
    )
    discover_parser.add_argument(
        "--parsed-root",
        type=Path,
        help="Root directory for parsed documents.",
    )
    discover_parser.set_defaults(func=discover_sources_cli, command="discover-sources")

    # list-sources command
    list_parser = subparsers.add_parser(
        "list-sources",
        description="List registered sources in the registry.",
        help="Show all sources in the source registry.",
    )
    list_parser.add_argument(
        "--status",
        type=str,
        choices=["active", "deprecated", "pending_review"],
        help="Filter by source status.",
    )
    list_parser.add_argument(
        "--type",
        type=str,
        choices=["primary", "derived", "reference"],
        dest="source_type",
        help="Filter by source type.",
    )
    list_parser.add_argument(
        "--kb-root",
        type=Path,
        help="Root directory for the knowledge graph.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output in JSON format.",
    )
    list_parser.set_defaults(func=list_sources_cli, command="list-sources")


def discover_sources_cli(args: argparse.Namespace) -> int:
    """Execute the source discovery workflow.
    
    Scans parsed documents for URLs, ranks by credibility score,
    and optionally creates GitHub Discussions for proposals.
    
    With --propose: Creates Discussion in 'Sources' category for each candidate.
    With --dry-run: Shows candidates without creating Discussions.
    """
    from src import paths

    # Initialize discoverer
    parsed_root = args.parsed_root or (paths.get_evidence_root() / "parsed")
    discoverer = SourceDiscoverer(parsed_root=parsed_root)

    # Get registered sources to exclude
    kb_root = args.kb_root or paths.get_knowledge_graph_root()
    registry = SourceRegistry(root=kb_root)
    registered_urls = registry.get_all_urls()

    print(f"Scanning for source URLs in {parsed_root}...")
    print(f"Excluding {len(registered_urls)} already-registered sources.")
    print()

    # Discover URLs
    if args.checksum:
        results = discoverer.discover_from_document(
            checksum=args.checksum,
            registered_sources=registered_urls,
            domain_filter=args.domain_filter,
        )
    else:
        results = discoverer.discover_all(
            registered_sources=registered_urls,
            domain_filter=args.domain_filter,
            limit=args.limit,
        )

    if not results:
        print("No new source candidates found.")
        return 0

    print(f"Found {len(results)} candidate source(s):\n")

    for i, (url, score) in enumerate(results, start=1):
        print(f"{i:3}. [{score:.2f}] {url.url}")
        print(f"     Domain: {url.domain} ({url.domain_type})")
        print(f"     Found in: {url.source_checksum}")
        if url.link_text:
            print(f"     Link text: {url.link_text[:60]}{'...' if len(url.link_text) > 60 else ''}")
        print()

    if args.dry_run:
        print("--dry-run specified: No proposal Discussions created.")
    elif args.propose:
        print("Creating proposal Discussions for candidates...")
        print("(Discussion creation via --propose not yet implemented)")
    else:
        print("Use --propose to create GitHub Discussions for these candidates.")
        print("Use --dry-run to preview without creating Discussions.")

    return 0


def list_sources_cli(args: argparse.Namespace) -> int:
    """Execute the list sources workflow."""
    from src import paths
    import json

    # Initialize registry
    kb_root = args.kb_root or paths.get_knowledge_graph_root()
    registry = SourceRegistry(root=kb_root)

    # Get sources with filters
    sources = registry.list_sources(
        status=args.status,
        source_type=args.source_type,
    )

    if not sources:
        if args.output_json:
            print("[]")
        else:
            print("No sources found in registry.")
        return 0

    if args.output_json:
        output = [s.to_dict() for s in sources]
        print(json.dumps(output, indent=2, default=str))
        return 0

    # Pretty print
    print(f"Found {len(sources)} source(s):\n")

    for source in sources:
        status_icon = {
            "active": "✓",
            "deprecated": "✗",
            "pending_review": "?",
        }.get(source.status, " ")

        print(f"[{status_icon}] {source.name}")
        print(f"    URL: {source.url}")
        print(f"    Type: {source.source_type} | Status: {source.status}")
        print(f"    Credibility: {source.credibility_score:.2f}")
        if source.proposal_discussion:
            print(f"    Proposal Discussion: #{source.proposal_discussion}")
        if source.implementation_issue:
            print(f"    Implementation Issue: #{source.implementation_issue}")
        print()

    return 0
