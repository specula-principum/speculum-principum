"""Model Context Protocol server for knowledge base tooling."""

from __future__ import annotations

from .kb_server import MCPServer, serve_stdio
from .kb_tools import KBToolRegistry, register_kb_tools

__all__ = [
    "MCPServer",
    "serve_stdio",
    "KBToolRegistry",
    "register_kb_tools",
]
