# Speculum Principum

The repository includes a lightweight CLI in `main.py` for creating issues,
searching triage queues, and coordinating GitHub Copilot issue handoffs.

- Label an issue `ready-for-copilot` so the local tooling can discover it.
- Run `python -m main run-agent` locally to claim the first ready issue,
	launch the Copilot CLI, push the working branch, and open a pull request.