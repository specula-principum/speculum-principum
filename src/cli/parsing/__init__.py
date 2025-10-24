from __future__ import annotations

import argparse

from .parse import register as register_parse_command

__all__ = ["register_commands"]


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add parsing-related commands to the main CLI parser."""
    register_parse_command(subparsers)
