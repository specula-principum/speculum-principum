### Speculum Principum

`main.py` exposes a single CLI entry point that helps you triage GitHub work and
convert source documents into Markdown artifacts. All commands follow the
pattern `python -m main <command> [options]`.

## GitHub workflow tooling

- **Create issues** – Render a Markdown template (or literal body) and open an
	issue via the REST API:

	```bash
	python -m main --title "Bug report" --template .github/ISSUE_TEMPLATE/general.md --var env=prod
	```

	Key flags: `--repo`, `--token`, `--body` (bypass template), repeatable
	`--var`, `--label`, and `--assignee`, plus `--output` for text, JSON, or
	number-only responses, and `--dry-run` to preview without creating.

- **Search issues** – List issues by assignee or label to feed your triage
	queue:

	```bash
	python -m main search --label ready-for-copilot --limit 10 --output text
	```

	If `--label` is omitted the search lists issues assigned to the provided
	`--assignee` (or unassigned when omitted).

- **Run the local Copilot agent** – Claim the next `ready-for-copilot` issue and
	hand it to the Copilot CLI, optionally customizing the model, extra CLI flags,
	and allowed tools:

	```bash
	python -m main run-agent --copilot-model claude-haiku-4.5 --copilot-arg verbose
	```

	Helpful flags include `--label`, `--base`, `--instructions`, tool overrides
	via `--copilot-allow-tool` or `--copilot-no-default-tools`, and workflow
	toggles such as `--skip-push`, `--skip-pr`, `--draft`, and `--keep-label`.

## Document parsing

`python -m main parse` converts supported documents into Markdown stored under a
manifest-managed output directory. Configuration defaults come from
`config/parsing.yaml` when present, and can be overridden per run.

Common options:

- `--output-root PATH` – override the configured artifact directory.
- `--config PATH` – point to an alternate YAML configuration.
- `--force` – reprocess inputs even when an identical checksum was already
	parsed.

Subcommands target specific sources:

- `pdf PATH...` – parse one or more PDF files.
- `docx PATH...` – parse one or more DOCX files.
- `web SOURCE...` – ingest HTTP(S) URLs or local HTML files.
- `scan` – walk a directory (default `./evidence`) and process matching files.

`scan` accepts filters such as `--suffix .pdf`, `--include`/`--exclude` glob
patterns, `--recursive/--no-recursive`, `--limit`, and `--clear-config-*`
switches to ignore patterns defined in the YAML configuration.

Each parsing run streams status lines to stdout indicating the parser, output
artifact path, and warnings. Non-zero exit codes signal at least one failed
parse.

## Using as a Template

This repository is designed to be used as a **template** for research projects. Clone it to create topic-specific research repositories that can receive code updates from this base.

### Quick Start

1. Click **"Use this template"** on GitHub to create your research repository
2. Run the **Initialize Repository** workflow to configure your research topic
3. Add research materials to `evidence/`, build knowledge in `knowledge-graph/`

### Syncing with Upstream

Cloned repositories can receive code updates (bug fixes, new features) while preserving research content:

```bash
# Via GitHub Actions UI:
# Go to Actions → Sync from Upstream → Run workflow
```

**What gets synced:**
- Code: `src/`, `tests/`, `.github/`, `config/missions/`, `docs/`
- Root files: `main.py`, `requirements.txt`, `pytest.ini`

**What stays local:**
- Research: `evidence/`, `knowledge-graph/`, `reports/`, `dev_data/`

The sync creates a Pull Request for review. See [docs/guides/upstream-sync.md](docs/guides/upstream-sync.md) for detailed setup and usage instructions.

## Information Architecture

Coming soon...