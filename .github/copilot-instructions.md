# Rules for agentic copilot
1. Do not create a summary document.
2. Always prefer tools that perform a specific task over general-purpose tools like command-line interfaces.
3. Always call `configure_python_environment` with `.venv` before executing any Python-related command or tool.
4. main.py should be the only entry point for CLI usage.
5. Key directories:
	- src/integrations/github: issue creation, search, and Copilot automation helpers.
	- src/integrations/copilot: CLI helpers, validation utilities, and accuracy tooling for agent workflows.
	- src/mcp_server: Model Context Protocol server and tool registry for Copilot integrations.
	- src/parsing: document parsing engines, config, storage, and runners.
	- tests/: pytest coverage for GitHub integrations, Copilot tooling, parsing workflows, and MCP server.