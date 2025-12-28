# Rules for agentic copilot

## Project Context
This is a **template repository** for research projects. Clones receive code updates via the sync workflow while preserving their research content in `evidence/`, `knowledge-graph/`, `reports/`, and `dev_data/`.

**All operations happen on GitHub.com** via Actions, Issues, Discussions, and the GitHub API—no local git commands required.

## Core Rules
1. Do NOT create changes summary documents. And do NOT create explanation documents for work completed.
2. Prefer specific tools over general-purpose CLIs.
3. Call `configure_python_environment` with `.venv` before any Python command.
4. `main.py` is the only CLI entry point.

## GitHub Actions Persistence
Agent missions run in **ephemeral GitHub Actions runners**. File writes to the local filesystem are discarded when the workflow ends.

**Required Pattern:**
- **Reads**: Use local filesystem (files available from `actions/checkout`)
- **Writes**: Use GitHub Contents API via `GitHubStorageClient` or `commit_file()`

**Never** use git CLI commands (`git add`, `git commit`, `git push`) in workflows. All persistence must go through the GitHub API.

Storage classes (`SourceRegistry`, `KnowledgeGraphStorage`) accept an optional `github_client` parameter. When running in Actions, pass a `GitHubStorageClient` instance to persist changes.

```python
from src.integrations.github.storage import get_github_storage_client

# In tool handlers:
github_client = get_github_storage_client()  # Returns None if not in Actions
registry = SourceRegistry(github_client=github_client)
```

## Key Directories
- `src/integrations/github/`: GitHub API utilities including sync, issues, discussions, PRs.
- `src/orchestration/`: Agent runtime, tools, missions, and LLM planner.
- `src/knowledge/`: Entity extraction, aggregation, and storage.
- `src/parsing/`: Document parsing (PDF, DOCX, web, markdown).
- `tests/`: pytest coverage mirroring src structure.
- `config/missions/`: YAML mission definitions for agent workflows.
- `docs/guides/`: Setup and usage documentation.

## Directory Boundaries
**Code directories** (synced from upstream): `src/`, `tests/`, `.github/`, `config/missions/`, `docs/`, `main.py`, `requirements.txt`, `pytest.ini`

**Research directories** (clone-specific, never synced): `evidence/`, `knowledge-graph/`, `reports/`, `dev_data/`, `devops/`

## Evidence Acquisition (MCP Tools)
When you need to **fetch content from external URLs**, use the MCP tools provided by the `evidence-acquisition` server. These tools run **outside the firewall** and have unrestricted network access.

**Available MCP Tools:**
- `fetch_source_content(url)` - Fetch and extract main content as markdown with hash
- `check_source_headers(url)` - Lightweight HEAD request for change detection (ETag, Last-Modified)

**Usage Pattern for Acquisition:**
1. Call `fetch_source_content` to get content from the source URL
2. Parse the JSON response for `content`, `content_hash`, and metadata
3. Store content in `evidence/parsed/` via GitHub API
4. Update `SourceEntry.last_content_hash` in the registry

Do NOT use `curl`, `wget`, or Python `requests` directly—those are blocked by the firewall.