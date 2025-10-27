"""Knowledge base CLI command registration."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.knowledge_base.cli import initialize_knowledge_base
from src.knowledge_base.config import load_mission_config
from src.knowledge_base.taxonomy import load_taxonomy


def _handle_init(args: argparse.Namespace) -> int:
    """Preview the files that would be created for knowledge base initialization."""

    root = Path(args.root).expanduser()
    mission_config = None
    mission_path = Path(args.mission).expanduser() if args.mission else Path("config/mission.yaml")
    if mission_path.exists():
        try:
            mission_config = load_mission_config(mission_path)
        except (FileNotFoundError, ImportError, ValueError) as exc:
            print(f"mission config validation failed: {exc}", file=sys.stderr)
            return 1
    elif args.mission:
        print(f"mission config '{mission_path}' does not exist", file=sys.stderr)
        return 1

    context: dict[str, str] = {}
    if args.title is not None:
        context["title"] = args.title
    if args.description is not None:
        context["description"] = args.description
    context_payload = context or None

    paths = initialize_knowledge_base(
        root,
        apply=args.apply,
        context=context_payload,
        mission=mission_config,
    )
    for path in paths:
        print(path)
    return 0


def _handle_validate_taxonomy(args: argparse.Namespace) -> int:
    """Validate a taxonomy definition file and report issues."""

    taxonomy_path = Path(args.taxonomy).expanduser()
    try:
        load_taxonomy(taxonomy_path)
    except ValueError as exc:  # Defensive: surface schema errors via exit code.
        print(f"taxonomy validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register knowledge base commands with the global CLI."""

    parser = subparsers.add_parser(
        "kb",
        help="Experimental knowledge base tooling (Phase 2).",
        description=(
            "Knowledge base workflows are under active development."
        ),
    )
    kb_subparsers = parser.add_subparsers(dest="kb_command", metavar="KB_COMMAND")
    kb_subparsers.required = True

    init_parser = kb_subparsers.add_parser(
        "init",
        help="Display the IA structure blueprint for a knowledge base root.",
    )
    init_parser.add_argument(
        "--root",
        default="knowledge-base",
        help="Path to the knowledge base root (default: knowledge-base).",
    )
    init_parser.add_argument(
        "--mission",
        help="Path to mission configuration. Defaults to config/mission.yaml when present.",
    )
    init_parser.add_argument(
        "--title",
        help="Override the mission title for this run.",
    )
    init_parser.add_argument(
        "--description",
        help="Override the mission description for this run.",
    )
    init_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the planned structure to disk instead of previewing paths.",
    )
    init_parser.set_defaults(func=_handle_init)

    validate_parser = kb_subparsers.add_parser(
        "validate-taxonomy",
        help="Validate a taxonomy YAML file against IA rules.",
    )
    validate_parser.add_argument(
        "--taxonomy",
        default="config/taxonomy.yaml",
        help="Path to the taxonomy definition (default: config/taxonomy.yaml).",
    )
    validate_parser.set_defaults(func=_handle_validate_taxonomy)
