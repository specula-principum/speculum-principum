"""CLI integration scaffolding for the knowledge base engine."""
from __future__ import annotations

import argparse


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register kb-engine commands with the global CLI dispatcher."""

    parser = subparsers.add_parser(
        "kb-engine",
        help="Phase 3 knowledge base engine workflows (experimental).",
        description=(
            "Knowledge base engine commands are under active development "
            "and currently operate as placeholders."
        ),
    )
    engine_subparsers = parser.add_subparsers(dest="kb_engine_command", metavar="ENGINE_COMMAND")
    engine_subparsers.required = True

    process_parser = engine_subparsers.add_parser(
        "process",
        help="Process parsed evidence into the knowledge base (placeholder).",
    )
    process_parser.set_defaults(func=_not_implemented("process"))

    update_parser = engine_subparsers.add_parser(
        "update",
        help="Update an existing knowledge base entry (placeholder).",
    )
    update_parser.set_defaults(func=_not_implemented("update"))

    improve_parser = engine_subparsers.add_parser(
        "improve",
        help="Run quality improvement routines (placeholder).",
    )
    improve_parser.set_defaults(func=_not_implemented("improve"))

    export_parser = engine_subparsers.add_parser(
        "export-graph",
        help="Export knowledge graph data (placeholder).",
    )
    export_parser.set_defaults(func=_not_implemented("export-graph"))


def _not_implemented(command: str):
    """Return a callable that raises a NotImplementedError for a command."""

    def _handler(_: argparse.Namespace) -> int:
        raise NotImplementedError(f"kb-engine {command} command is not implemented yet")

    return _handler
