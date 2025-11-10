"""Minimal Model Context Protocol server exposing knowledge base tools."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, TextIO

from .kb_tools import (
    KBToolRegistry,
    PayloadValidationError,
    ToolExecutionError,
    ToolResponse,
    register_kb_tools,
)


class MCPServer:
    """Serve MCP tool requests over a simple JSON/stdio transport."""

    def __init__(self, registry: KBToolRegistry | None = None) -> None:
        self._registry = registry or KBToolRegistry()
        if registry is None:
            register_kb_tools(self._registry)

    def list_tools(self) -> tuple[dict[str, Any], ...]:
        return self._registry.describe()

    def invoke_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not name:
            return {"status": "error", "error": "Tool name is required."}
        try:
            response: ToolResponse = self._registry.invoke(name, arguments or {})
        except PayloadValidationError as exc:
            return {"status": "error", "error": str(exc)}
        except ToolExecutionError as exc:
            return {"status": "error", "error": str(exc)}
        return {
            "status": "ok",
            "data": dict(response.data),
            "metadata": dict(response.metadata),
        }


def serve_stdio(
    server: MCPServer,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    reader = input_stream or sys.stdin
    writer = output_stream or sys.stdout
    for raw in reader:
        line = raw.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_json(writer, {"status": "error", "error": f"Invalid JSON: {exc}"})
            continue
        command = request.get("command")
        if command == "list_tools":
            response = {"status": "ok", "tools": server.list_tools()}
        elif command == "call_tool":
            name = request.get("name", "")
            arguments = request.get("arguments")
            response = server.invoke_tool(str(name), arguments)
        else:
            response = {"status": "error", "error": f"Unsupported command: {command}"}
        _write_json(writer, response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Speculum Principum MCP server for Copilot agents.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit.",
    )
    args = parser.parse_args(argv)

    server = MCPServer()
    if args.list_tools:
        for info in server.list_tools():
            print(json.dumps(info, indent=2))
        return 0

    serve_stdio(server)
    return 0


def _write_json(stream: TextIO, payload: Mapping[str, Any]) -> None:
    stream.write(json.dumps(payload))
    stream.write("\n")
    stream.flush()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
