# Speculum Principum

`main.py` exposes a single CLI entry point that helps you triage GitHub work and
convert source documents into Markdown artifacts. All commands follow the
pattern `python -m main <command> [options]`.

## GitHub workflow tooling

- **Create issues** – Render a Markdown template (or literal body) and open an
	issue via the REST API:

	```bash
	python -m main --title "Bug report" --template .github/templates/bug.md --var env=prod
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

## Copilot knowledge base tooling

The `copilot` command group streamlines knowledge base workflows for Copilot
agents:

- `python -m main copilot kb-extract --issue <number> [--repo owner/name --token TOKEN --api-url URL --kb-root PATH]` –
	fetch issue context and render a focused extraction brief.
- `python -m main copilot kb-validate [--kb-root PATH --json]` – run structural,
	metadata, and quality checks; exits non-zero on failure, optionally emitting
	JSON.
- `python -m main copilot kb-report --issue <number> [--kb-root PATH --output-dir DIR]` – generate the Markdown quality
	report used in PR reviews.
- `python -m main copilot verify-accuracy --scenario FILE [--kb-root PATH --json --output FILE]` – score KB contents against
	curated gold scenarios, returning precision/recall metrics.
- `python -m main copilot kb-automation --source PATH [--kb-root PATH --mission FILE --extract EXTRACTORS... --issue <number> --metrics-output FILE --report-dir DIR --skip-pipeline-validation]` – execute the
	end-to-end pipeline (process → validate → report) mirroring the GitHub
	workflow.
- `python -m main copilot mcp-serve [--list-tools]` – start the MCP server so
	Copilot agents can call extraction, creation, and validation tools directly.