# Rules for agentic copilot
1. Do not create a summary document.
2. Always prefer tools that perform a specific task over general-purpose tools like command-line interfaces.
3. main.py should be the only entry point for CLI usage.
4. Key directories:
	- src/integrations/github: issue creation, search, and copilot automation helpers.
	- src/parsing: document parsing engines, config, storage, and runners.
	- tests/: pytest coverage for GitHub integrations and parsing workflows.