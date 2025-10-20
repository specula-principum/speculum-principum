# Speculum Principum

The repository includes a lightweight CLI in `main.py` for creating issues,
searching triage queues, and coordinating GitHub Copilot issue handoffs.

## CLI Actions

### create

Create a GitHub issue using a template or literal body.

**Usage:**
```bash
python -m main create --title "Issue Title" [options]
```

**Options:**
- `--title` (required): Title for the new issue
- `--repo`: Target repository in owner/repo form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--template`: Path to the issue body template (default: `.github/templates/hello-world.md`)
- `--body`: Literal body for the issue (overrides `--template` when provided)
- `--var`: Template variable in key=value form (repeat for multiple values)
- `--label`: Label to add to the issue (repeat for multiple labels)
- `--assignee`: Assignee for the issue (repeat for multiple assignees)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise, default: `https://api.github.com`)
- `--output`: Output format: `text` (default), `json`, or `number`
- `--dry-run`: Render the issue but do not create it

**Examples:**
```bash
# Create an issue with a template
python -m main create --title "Bug report" --template .github/templates/bug.md

# Create an issue with template variables
python -m main create --title "Feature request" --var author=john --var priority=high

# Create an issue with labels and assignees
python -m main create --title "Task" --label bug --label urgent --assignee username

# Create an issue with literal body
python -m main create --title "Quick note" --body "This is the issue body"
```

### search

Search GitHub issues by label or assignee.

**Usage:**
```bash
python -m main search [options]
```

**Options:**
- `--repo`: Target repository in owner/repo form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise, default: `https://api.github.com`)
- `--assignee`: Filter by issue assignee (omit to search for unassigned issues)
- `--label`: Filter by a specific label (when provided, overrides the assignee filter)
- `--limit`: Maximum number of results to return, 1-100 (default: 30)
- `--output`: Output format: `json` (default) or `text`

**Examples:**
```bash
# Search for issues with a specific label
python -m main search --label ready-for-copilot

# Search for unassigned issues
python -m main search

# Search for issues assigned to a user
python -m main search --assignee username

# Limit results and output as text
python -m main search --label bug --limit 10 --output text
```

### run-agent

Run a Copilot agent locally for the next issue labeled 'ready-for-copilot' (or a custom label). This command claims the first ready issue, launches the Copilot CLI, pushes the working branch, and opens a pull request.

**Usage:**
```bash
python -m main run-agent [options]
```

**Options:**
- `--repo`: Target repository in owner/repo form (defaults to `$GITHUB_REPOSITORY`)
- `--token`: GitHub token (defaults to `$GITHUB_TOKEN`)
- `--api-url`: Base URL for the GitHub API (set for GitHub Enterprise, default: `https://api.github.com`)
- `--label`: Issue label to target (default: `ready-for-copilot`)
- `--base`: Base branch for the working branch and pull request (defaults to the repository's default branch)
- `--instructions`: Additional free-form guidance appended to the Copilot prompt
- `--copilot-bin`: Copilot CLI executable to invoke (default: `copilot`)
- `--copilot-arg`: Extra flag to pass to the Copilot CLI (repeat for multiple flags)
- `--no-allow-all-tools`: Do not pass `--allow-all-tools` to the Copilot CLI
- `--skip-push`: Skip pushing the branch to origin after the agent run
- `--skip-pr`: Skip creating a pull request after the agent run
- `--draft`: Create the pull request as a draft
- `--keep-label`: Leave the label on the issue instead of removing it after the run

**Examples:**
```bash
# Run agent on the first ready-for-copilot issue
python -m main run-agent

# Run agent with custom label
python -m main run-agent --label needs-automation

# Run agent with custom instructions and base branch
python -m main run-agent --base develop --instructions "Use type hints"

# Run agent and create a draft PR
python -m main run-agent --draft

# Run agent but skip pushing and PR creation
python -m main run-agent --skip-push --skip-pr
```

## Quick Start

Label an issue `ready-for-copilot` so the local tooling can discover it, then run:

```bash
python -m main run-agent
```

This will claim the first ready issue, launch the Copilot CLI, push the working branch, and open a pull request.