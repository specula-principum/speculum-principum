# MCP Integration Guide

This guide explains how the Model Context Protocol (MCP) server integrates Speculum Principum tooling with Copilot agents. It covers server architecture, available tools, and operational practices for Phase 4 automation.

## Overview

The MCP server exposes knowledge-base utilities over stdio so Copilot agents can invoke structured tooling without shell access. It complements the CLI commands in `src/integrations/copilot/commands.py` and is launched via `python -m main copilot mcp-serve`.

Key modules:
- `src/mcp_server/kb_server.py`: server bootstrap, transport management, tool registry wiring.
- `src/mcp_server/kb_tools.py`: tool definitions, input schemas, and execution handlers.
- `src/integrations/copilot/helpers.py`: shared validation, context parsing, and quality reporting utilities reused by tool handlers.

## Server Lifecycle

1. **Startup**:
   ```bash
   python -m main copilot mcp-serve
   ```
   Flags:
   - `--list-tools`: enumerate registered tools and exit.

2. **Transport**: Uses line-delimited JSON over stdio per MCP specification. Designed for compatibility with the GitHub Copilot MCP beta.

3. **Tool Registry**: `kb_server.py` imports tool factories from `kb_tools.py`, validates schemas, and registers them with the MCP dispatcher.

4. **Shutdown**: Client disconnect or `SIGINT` stops the stdio loop.

## Tool Catalog

| Tool | Handler | Purpose | Input Schema |
| --- | --- | --- | --- |
| `kb_extract_concepts` | `kb_tools.extract_concepts` | Extract key concepts from source text | `source_path` (string), `min_frequency` (int, default 2), `max_concepts` (int, default 50) |
| `kb_create_concept` | `kb_tools.create_concept_document` | Generate concept document front matter & content | `concept_name` (string), `definition` (string), `sources` (array), `related_concepts` (array) |
| `kb_validate` | `kb_tools.validate_kb` | Run knowledge-base validation & metrics | `kb_root` (string), optional `section` (string) |

Each tool enforces the JSON schema defined in `kb_tools.py` before execution. Invalid payloads return structured error responses.

## Implementation Notes

- **Schema Validation**: Tools leverage `jsonschema`-style validation helpers; update schemas when adding fields to avoid runtime mismatches.
- **Filesystem Access**: Paths are expanded with `Path.expanduser()` and resolved relative to the repository root. Ensure agents provide workspace-aligned paths.
- **Quality Enforcement**: `kb_validate` reuses `validate_kb_changes` and `generate_quality_report`, maintaining consistency with CLI checks.
- **Extensibility**: Add tools by defining a schema and handler in `kb_tools.py`, then registering it in `kb_server.py`’s tool map.

## Agent Integration Steps

1. **Discover Tools**: After starting the server, clients request the tool list. Use `--list-tools` locally to confirm registration.
2. **Invoke Tool**: Client sends MCP `callTool` requests with JSON arguments matching the schema.
3. **Handle Responses**: Successful calls return structured payloads (e.g., metrics, document metadata). Errors include descriptive messages and schema validation feedback.

## Testing & Validation

- **Unit Tests**: `tests/integrations/copilot/test_cli.py::test_copilot_mcp_serve_lists_tools` ensures CLI entry point enumerates tools.
- **Future Work**: Additional server-level tests are recommended once MCP client fixtures are available. For now, rely on CLI coverage and manual verification.
- **Manual Check**: Run `python -m main copilot mcp-serve --list-tools` to confirm the tool registry before agent runs.

## Troubleshooting

| Issue | Resolution |
| --- | --- |
| `kb_extract_concepts` fails | Verify source path exists and dependencies for extraction are installed. Check logs for `PipelineStageError`. |
| Schema validation errors | Confirm client sends required fields. Align payload keys with `kb_tools.py`. |
| No tools listed | Ensure `kb_tools.py` exports tool definitions and no import errors occur at startup. Run CLI command to inspect exceptions. |
| Agent cannot connect | Validate MCP client configuration, and ensure stdio stream isn’t blocked (no extra prints). |

## Change Management

- Update tool schemas and handlers together to avoid drift.
- Document new tools in this guide and in `README.md` deliverables.
- Maintain alignment with GitHub Actions workflows; tools should mirror CLI functionality exposed to automation.

Adhering to this integration model ensures Copilot agents access knowledge-base operations in a consistent, type-safe manner while respecting the project’s architecture.
