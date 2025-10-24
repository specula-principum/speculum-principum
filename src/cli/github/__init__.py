from __future__ import annotations

import argparse

from .create import build_parser as build_create_parser, register as register_create_command
from .run_agent import register as register_run_agent_command
from .search import register as register_search_command

__all__ = [
    "build_default_create_parser",
    "register_commands",
]

def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add GitHub-focused subcommands to the main CLI parser."""
    register_create_command(subparsers)
    register_search_command(subparsers)
    register_run_agent_command(subparsers)


def build_default_create_parser() -> argparse.ArgumentParser:
    """Construct the standalone parser used when `create` is the implicit command."""
    return build_create_parser(prog="python -m main")
