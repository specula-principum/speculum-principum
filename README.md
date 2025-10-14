# Speculum Principum

The repository includes a lightweight CLI in `main.py` for creating issues and
searching triage queues. GitHub Copilot issues cannot currently be assigned via
the REST API, so the `assign-copilot` GitHub Action handles the handoff instead.

- Add the `ready-for-copilot` label to an issue to trigger
	`.github/workflows/assign-copilot.yml`.
- Optionally override the assignee by setting the repository variable
	`GITHUB_COPILOT_ASSIGNEE` or the `GITHUB_COPILOT_ASSIGNEE` environment
	variable.