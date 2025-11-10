from __future__ import annotations

import io
import json
from pathlib import Path

from src.mcp_server.kb_server import MCPServer, serve_stdio
from src.mcp_server.kb_tools import KBToolRegistry, register_kb_tools


def _configured_server() -> MCPServer:
    registry = KBToolRegistry()
    register_kb_tools(registry)
    return MCPServer(registry)


def test_server_lists_tools() -> None:
    server = _configured_server()
    tools = server.list_tools()
    names = {tool["name"] for tool in tools}
    assert "kb_extract_concepts" in names


def test_server_invokes_tool(tmp_path: Path) -> None:
    server = _configured_server()
    source = tmp_path / "notes.txt"
    source.write_text("Princes must be prudent and just.", encoding="utf-8")

    response = server.invoke_tool(
        "kb_extract_concepts",
        {"source_path": str(source), "min_frequency": 1, "max_concepts": 3},
    )
    assert response["status"] == "ok"
    assert response["data"]["concepts"]


def test_stdio_loop_handles_requests(tmp_path: Path) -> None:
    server = _configured_server()

    buffer = io.StringIO()
    serve_stdio(server, input_stream=io.StringIO(json.dumps({"command": "list_tools"}) + "\n"), output_stream=buffer)
    buffer.seek(0)
    first = json.loads(buffer.readline())
    assert first["status"] == "ok"

    error_buffer = io.StringIO()
    payload = {
        "command": "call_tool",
        "name": "kb_validate",
        "arguments": {"kb_root": str(tmp_path / "missing")},
    }
    serve_stdio(server, input_stream=io.StringIO(json.dumps(payload) + "\n"), output_stream=error_buffer)
    error_buffer.seek(0)
    second = json.loads(error_buffer.readline())
    assert second["status"] == "error"
