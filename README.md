# Speculum Principum

The repository includes a lightweight CLI in `main.py` for creating issues, searching triage queues, and coordinating GitHub Copilot issue handoffs.

## CLI Actions

### create
Create a GitHub issue using a template or literal body.

**Usage:** `python -m main create [options]`

**Options:**
- `--title` (required): Title for the new issue
- `--repo`: Target repository in `owner/repo` form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--template`: Path to the issue body template (defaults to `.github/templates/hello-world.md`)
- `--body`: Literal body for the issue (overrides `--template` when provided)
- `--var`: Template variable in `key=value` form (repeat for multiple values)
- `--label`: Label to add to the issue (repeat for multiple labels)
- `--assignee`: Assignee for the issue (repeat for multiple assignees)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise)
- `--output`: Output format (`text`, `json`, or `number`) (defaults to `text`)
- `--dry-run`: Render the issue but do not create it

### search
Search GitHub issues in the repository.

**Usage:** `python -m main search [options]`

**Options:**
- `--repo`: Target repository in `owner/repo` form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise)
- `--assignee`: Filter by issue assignee (omit to search for unassigned issues)
- `--label`: Filter by a specific label (when provided, overrides the assignee filter)
- `--limit`: Maximum number of results to return, 1-100 (defaults to 30)
- `--output`: Output format (`json` or `text`) (defaults to `json`)

### run-agent
Run a Copilot agent locally for the next issue labeled `ready-for-copilot`.

**Usage:** `python -m main run-agent [options]`

**Options:**
- `--repo`: Target repository in `owner/repo` form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise)
- `--label`: Issue label to target (defaults to `ready-for-copilot`)
- `--base`: Base branch for the working branch and pull request (defaults to the repository's default branch)
- `--instructions`: Additional free-form guidance appended to the Copilot prompt
- `--copilot-bin`: Copilot CLI executable to invoke (defaults to `copilot`)
- `--copilot-model`: Model to use for the Copilot agent run (defaults to `claude-haiku-4.5`)
- `--copilot-arg`: Extra flag to pass to the Copilot CLI (repeat for multiple flags)
- `--copilot-allow-tool`: Additional tool permission to grant the Copilot CLI (repeat for multiple patterns, e.g., `shell(git:*)`)
- `--copilot-no-default-tools`: Disable the default Copilot tool permissions (file edits, web search, GitHub issue access, PR creation)
- `--skip-push`: Skip pushing the branch to origin after the agent run
- `--skip-pr`: Skip creating a pull request after the agent run
- `--draft`: Create the pull request as a draft
- `--keep-label`: Leave the label on the issue instead of removing it after the run

## Getting Started

1. Label an issue `ready-for-copilot` so the local tooling can discover it.
2. Run `python -m main run-agent` locally to claim the first ready issue, launch the Copilot CLI, push the working branch, and open a pull request.