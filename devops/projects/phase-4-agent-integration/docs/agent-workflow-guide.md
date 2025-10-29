# Agent Workflow Guide

This guide explains how GitHub Copilot agents execute the Speculum Principum knowledge-base workflows in Phase 4. It connects the GitHub issue layer to the CLI/MCP tooling and highlights validation expectations so agents can deliver production-ready pull requests.

## Prerequisites

- **Entry point**: All automation runs through `python -m main` in repo root.
- **Issue templates**: Use the Phase 4 templates in `.github/templates/` to ensure required front-matter and labels (`ready-for-copilot`, `kb-*`).
- **Environment**: Python 3.10+ with project dependencies installed (`pip install -r requirements.txt`).
- **Tokens**: `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and optional `GITHUB_COPILOT_ASSIGNEE` must be present for GitHub API calls.

## Workflow Overview

```
GitHub Issue → Copilot Assignment → Context Preparation → Automation CLI/MCP → Validation + Reports → Pull Request
```

Key integration points:

- `src/integrations/github/assign_copilot.py`: issue assignment, branch naming, Copilot prompt composition.
- `src/integrations/copilot/helpers.py`: issue context parsing, KB validation, quality report generation.
- `src/integrations/copilot/commands.py`: CLI wrappers for agents (`kb-extract`, `kb-validate`, `kb-report`, `kb-automation`, `mcp-serve`).
- `src/integrations/github/automation.py`: end-to-end orchestration mirroring GitHub Actions.

## Detailed Flow

### 1. Issue Intake

1. Human files an issue using one of the KB templates.
2. Optional GitHub Action labels it `ready-for-copilot`.
3. Run assignment task to earmark the issue for an agent:
   ```bash
   python -m main assign-copilot --label ready-for-copilot
   ```

### 2. Branch & Prompt Setup

1. `generate_branch_name(issue_number, title)` builds deterministic branch slugs (`copilot/issue-<n>-...`).
2. `compose_agent_prompt(issue, branch_name, extra_instructions)` injects issue body and workflow instructions. Pass the context block from the next step as `extra_instructions`.

### 3. Context Preparation

Render a knowledge-base snapshot and required actions for the agent:
```bash
python -m main copilot kb-extract --issue <number> --kb-root knowledge-base/
```
This calls `prepare_kb_extraction_context`, parsing templates and enumerating KB documents to focus the agent’s work.

### 4. Automated Processing

For fully automated extraction/improvement tasks, prefer the unified command:
```bash
python -m main copilot kb-automation \
  --source evidence/<source_dir> \
  --kb-root knowledge-base/ \
  --issue <number> \
  --report-dir reports/ \
  --metrics-output reports/metrics-<number>.json
```
Parameters:
- `--mission` and `--extract` override pipeline defaults when mission-specific extractors apply.
- `--skip-pipeline-validation` is available for troubleshooting but should stay off in production runs.

### 5. Validation & Reporting

- `python -m main copilot kb-validate --kb-root knowledge-base/` returns non-zero if IA thresholds fail. Use `--json` for structured output.
- `python -m main copilot kb-report --issue <number> --kb-root knowledge-base/` writes `reports/quality-<number>.md`. Both commands rely on `validate_kb_changes` and `generate_quality_report` to enforce:
  - Minimum completeness 0.70
  - Minimum findability 0.60
  - Link and metadata consistency across documents
- `python -m main copilot verify-accuracy --scenario devops/projects/phase-4-agent-integration/scenarios/<name>.yaml --kb-root knowledge-base/` compares KB contents against curated gold sets, highlighting precision/recall gaps before PR handoff. Use `--json` to stream metrics or `--output reports/accuracy-<number>.json` to persist structured data for dashboards.

### 6. MCP Server (Agent Tooling)

Start the MCP server for native Copilot tool access:
```bash
python -m main copilot mcp-serve
```
Use `--list-tools` to enumerate available operations (concept extraction, document creation, validation) defined in `src/mcp_server/kb_tools.py`.

### 7. Pull Request Handoff

1. Validate Git status and commit changes using the automation helpers (`run_issue_with_local_copilot` in `assign_copilot.py`).
2. Push the branch and create or reopen PRs via the GitHub CLI wrappers. Automation scripts capture quality reports and link them in the PR body or comments.

## Testing & Quality Gates

| Test Target | Command | Purpose |
| --- | --- | --- |
| Copilot suite | `python -m pytest tests/integrations/copilot` | Covers CLI commands, helper utilities, and MCP listing |
| Accuracy validation | `python -m pytest tests/integrations/copilot/test_accuracy.py` | Evaluates precision/recall math and CLI scenario wiring without heavy performance loads |
| Mock agent workflow | `python -m pytest tests/integrations/copilot/test_agent_workflows.py` | Simulates branch/prompt orchestration and end-to-end automation outcomes |
| GitHub automation | `python -m pytest tests/integrations/github/test_automation.py` | Ensures CLI automation mirrors GitHub Actions logic |

Recent additions (`tests/integrations/copilot/test_agent_workflows.py`) push Copilot integration coverage above 90%, exercising prompt composition, pipeline orchestration, and validation failure handling without contacting external services.

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `ImportError` involving Copilot helpers | CLI modules imported before `main` initialises paths | Import `main` first in tests/scripts or run via `python -m main ...` |
| Validation warnings (`Below-threshold documents`) | KB metadata missing findability/completeness | Update document front matter or rerun improvement tools |
| MCP server missing tools | Registry not updated | Check `src/mcp_server/kb_tools.py` and rerun with `--list-tools` |
| Automation exits with status 1 | Pipeline errors or validation failures | Inspect stage metrics / errors in terminal output and review generated quality report |

## References

- Phase architecture: `devops/projects/phase-4-agent-integration/README.md`
- Progress tracking: `devops/projects/phase-4-agent-integration/PROGRESS.md`
- Knowledge-base schemas: `config/` directory
- Example reports: `reports/quality-*.md`

Adhering to this workflow keeps agents aligned with the IA thresholds and ensures every PR ships with validation reports and reproducible automation commands.
