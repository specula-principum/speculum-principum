"""Register Copilot workflow commands with the CLI."""

from __future__ import annotations

import argparse

from src.integrations.copilot.commands import register_copilot_commands as _register

__all__ = ["register_commands"]


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Proxy registration to the integrations layer."""

    _register(subparsers)
