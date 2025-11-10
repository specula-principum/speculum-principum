"""MCP server exposing GitHub orchestration tools for Copilot CLI agent missions."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, TextIO

from src.orchestration.tools import ToolRegistry
from src.orchestration.toolkit import (
    register_github_mutation_tools,
    register_github_pr_tools,
    register_github_read_only_tools,
    register_knowledge_base_tools,
    register_parsing_tools,
)


class OrchestrationMCPServer:
    """MCP server that exposes orchestration tools to GitHub Copilot CLI."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        """Initialize server with tool registry.
        
        Args:
            registry: Optional pre-configured registry. If None, creates and
                     registers all standard orchestration tools.
        """
        if registry is None:
            registry = ToolRegistry()
            # Register all standard tool sets
            register_github_read_only_tools(registry)
            register_github_mutation_tools(registry)
            register_github_pr_tools(registry)
            register_knowledge_base_tools(registry)
            register_parsing_tools(registry)
        
        self._registry = registry

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP-compatible tool descriptions.
        
        Returns:
            List of tool metadata dicts with name, description, and parameters.
        """
        tools = []
        for tool_schema in self._registry.get_tool_schemas():
            tools.append({
                "name": tool_schema["name"],
                "description": tool_schema["description"],
                "inputSchema": tool_schema["parameters"],
            })
        return tools

    def invoke_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Execute a tool and return the result.
        
        Args:
            name: Tool name to invoke.
            arguments: Tool arguments (optional).
            
        Returns:
            Dict with status and result/error.
        """
        if not name:
            return {"status": "error", "error": "Tool name is required"}
        
        try:
            result = self._registry.execute_tool(name, arguments or {})
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }
        
        if result.success:
            return {
                "status": "success",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result.output, indent=2) if result.output else "Success",
                    }
                ],
            }
        else:
            return {
                "status": "error",
                "error": result.error or "Tool execution failed",
            }


def serve_stdio(
    server: OrchestrationMCPServer,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    """Serve MCP requests over stdio (standard MCP transport).
    
    Args:
        server: The MCP server instance.
        input_stream: Input stream (defaults to stdin).
        output_stream: Output stream (defaults to stdout).
    """
    reader = input_stream or sys.stdin
    writer = output_stream or sys.stdout
    
    for raw_line in reader:
        line = raw_line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_json(writer, {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {exc}"}})
            continue
        
        # MCP uses JSON-RPC 2.0
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": server.list_tools(),
                },
            }
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = server.invoke_tool(tool_name, tool_args)
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        
        _write_json(writer, response)


def _write_json(stream: TextIO, payload: Mapping[str, Any]) -> None:
    """Write JSON object to stream and flush."""
    stream.write(json.dumps(payload))
    stream.write("\n")
    stream.flush()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for orchestration MCP server.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv).
        
    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        description="MCP server exposing GitHub orchestration tools for Copilot CLI.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit (for debugging).",
    )
    args = parser.parse_args(argv)
    
    server = OrchestrationMCPServer()
    
    if args.list_tools:
        tools = server.list_tools()
        print(json.dumps({"tools": tools}, indent=2))
        return 0
    
    # Run MCP server over stdio
    serve_stdio(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
