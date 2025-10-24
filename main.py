#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from src.integrations.github.assign_copilot import (
    DEFAULT_ALLOWED_COPILOT_TOOLS,
    run_issue_with_local_copilot,
)
from src.integrations.github.issues import (
    DEFAULT_API_URL,
    GitHubIssueError,
    IssueOutcome,
    create_issue,
    load_template,
    render_template,
    resolve_repository,
    resolve_token,
)
from src.integrations.github.search_issues import GitHubIssueSearcher, IssueSearchResult
from src.parsing.config import load_parsing_config
from src.parsing.runner import parse_single_target, scan_and_parse
from src.parsing.storage import ParseStorage

OUTPUT_TEXT = "text"
OUTPUT_JSON = "json"
OUTPUT_NUMBER = "number"
DEFAULT_READY_LABEL = "ready-for-copilot"


def resolve_agent_token(explicit_token: str | None) -> str:
    """Prefer an explicit token, then fall back to GITHUB_TOKEN."""

    if explicit_token:
        return explicit_token

    return resolve_token(None)


def parse_variables(pairs: Iterable[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise argparse.ArgumentTypeError(
                f"Invalid variable '{pair}'. Use the form key=value."
            )
        key, value = pair.split("=", 1)
        if not key:
            raise argparse.ArgumentTypeError("Template variable key cannot be empty.")
        variables[key] = value
    return variables


def build_create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a GitHub issue using a template.")
    parser.add_argument("--title", required=True, help="Title for the new issue.")
    parser.add_argument(
        "--repo",
        help="Target repository in owner/repo form. Defaults to $GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Path to the issue body template.",
        default=Path(".github/templates/hello-world.md"),
    )
    parser.add_argument(
        "--body",
        help="Literal body for the issue. Overrides --template when provided.",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        help="Template variable in key=value form. Repeat for multiple values.",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Label to add to the issue. Repeat for multiple labels.",
    )
    parser.add_argument(
        "--assignee",
        action="append",
        default=[],
        help="Assignee for the issue. Repeat for multiple assignees.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Base URL for the GitHub API (set for GitHub Enterprise).",
    )
    parser.add_argument(
        "--output",
        choices=[OUTPUT_TEXT, OUTPUT_JSON, OUTPUT_NUMBER],
        default=OUTPUT_TEXT,
        help="Output format: friendly text, JSON, or number only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the issue but do not create it.",
    )
    return parser


def build_search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search GitHub issues.", prog="python -m main search")
    parser.add_argument(
        "--repo",
        help="Target repository in owner/repo form. Defaults to $GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Base URL for the GitHub API (set for GitHub Enterprise).",
    )
    parser.add_argument(
        "--assignee",
        help="Filter by issue assignee. Omit to search for unassigned issues.",
    )
    parser.add_argument(
        "--label",
        help="Filter by a specific label. When provided, overrides the assignee filter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of results to return (1-100).",
    )
    parser.add_argument(
        "--output",
        choices=[OUTPUT_TEXT, OUTPUT_JSON],
        default=OUTPUT_JSON,
        help="Output format: machine-readable JSON or human-readable text.",
    )
    return parser


def build_run_agent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Copilot agent locally for the next issue labeled 'ready-for-copilot'.",
        prog="python -m main run-agent",
    )
    parser.add_argument(
        "--repo",
        help="Target repository in owner/repo form. Defaults to $GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Base URL for the GitHub API (set for GitHub Enterprise).",
    )
    parser.add_argument(
        "--label",
        default=DEFAULT_READY_LABEL,
        help="Issue label to target. Defaults to 'ready-for-copilot'.",
    )
    parser.add_argument(
        "--base",
        help="Base branch for the working branch and pull request (defaults to the repository's default branch).",
    )
    parser.add_argument(
        "--instructions",
        help="Additional free-form guidance appended to the Copilot prompt.",
    )
    parser.add_argument(
        "--copilot-bin",
        default="copilot",
        help="Copilot CLI executable to invoke. Defaults to 'copilot'.",
    )
    parser.add_argument(
        "--copilot-model",
        default="claude-haiku-4.5",
        help="Model to use for the Copilot agent run. Defaults to 'claude-haiku-4.5'.",
    )
    parser.add_argument(
        "--copilot-arg",
        action="append",
        default=[],
        help="Extra flag to pass to the Copilot CLI. Repeat for multiple flags.",
    )
    parser.add_argument(
        "--copilot-allow-tool",
        action="append",
        default=[],
        help=(
            "Additional tool permission to grant the Copilot CLI. Repeat for multiple "
            "patterns (e.g. shell(git:*))"
        ),
    )
    parser.add_argument(
        "--copilot-no-default-tools",
        action="store_true",
        help="Disable the default Copilot tool permissions (file edits, web search, GitHub issue access, PR creation).",
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Skip pushing the branch to origin after the agent run.",
    )
    parser.add_argument(
        "--skip-pr",
        action="store_true",
        help="Skip creating a pull request after the agent run.",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create the pull request as a draft.",
    )
    parser.add_argument(
        "--keep-label",
        action="store_true",
        help="Leave the label on the issue instead of removing it after the run.",
    )
    return parser


def build_parse_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse documents into Markdown artifacts.",
        prog="python -m main parse",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Directory for Markdown outputs (overrides configuration).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to a parsing YAML config (default: config/parsing.yaml when present).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even when an identical checksum exists in the manifest.",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    pdf_parser = subcommands.add_parser("pdf", help="Parse one or more PDF files.")
    pdf_parser.add_argument("paths", nargs="+", type=Path, help="PDF files to parse.")

    docx_parser = subcommands.add_parser("docx", help="Parse one or more DOCX files.")
    docx_parser.add_argument("paths", nargs="+", type=Path, help="DOCX files to parse.")

    web_parser = subcommands.add_parser("web", help="Parse HTTP URLs or local HTML files.")
    web_parser.add_argument("sources", nargs="+", help="URL or file path to parse.")

    scan_parser = subcommands.add_parser("scan", help="Scan a directory for parseable documents.")
    scan_parser.add_argument(
        "--root",
        type=Path,
        default=Path("evidence"),
        help="Directory to scan for documents (defaults to ./evidence).",
    )
    scan_parser.add_argument(
        "--suffix",
        action="append",
        default=[],
        help="File suffix to include (e.g. .pdf). Repeat to supply multiple values.",
    )
    scan_parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Recursively scan subdirectories (default controlled by configuration).",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to process during scanning.",
    )
    scan_parser.add_argument(
        "--include",
        action="append",
        dest="include",
        metavar="PATTERN",
        help="Glob pattern relative to the scan root to include. Repeat to supply multiple patterns.",
    )
    scan_parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude",
        metavar="PATTERN",
        help="Glob pattern relative to the scan root to exclude. Repeat to supply multiple patterns.",
    )
    scan_parser.add_argument(
        "--clear-config-suffixes",
        action="store_true",
        help="Ignore suffix patterns defined in the parsing config when combining with --suffix.",
    )
    scan_parser.add_argument(
        "--clear-config-include",
        action="store_true",
        help="Ignore include patterns from the parsing config when combining with --include.",
    )
    scan_parser.add_argument(
        "--clear-config-exclude",
        action="store_true",
        help="Ignore exclude patterns from the parsing config when combining with --exclude.",
    )
    scan_parser.set_defaults(include=None, exclude=None)

    return parser


def _emit_parse_outcome(outcome) -> None:
    status = outcome.status
    parser_name = outcome.parser or "unknown"
    if status == "error":
        message = outcome.error or "Parsing failed"
        print(f"[error] {outcome.source}: {message}", file=sys.stderr)
        return

    artifact = f" -> {outcome.artifact_path}" if outcome.artifact_path else ""
    memo = f" ({outcome.message})" if outcome.message else ""
    print(f"[{status}] {outcome.source} via {parser_name}{artifact}{memo}")
    for warning in outcome.warnings:
        print(f"  warning: {warning}")


def _merge_cli_sequences(
    config_values: Iterable[str],
    cli_values: Iterable[str] | None,
    *,
    clear: bool,
) -> tuple[str, ...]:
    merged: list[str] = []
    if not clear:
        for value in config_values:
            token = str(value).strip()
            if token:
                merged.append(token)
    if cli_values:
        for value in cli_values:
            token = str(value).strip()
            if token:
                merged.append(token)
    seen: set[str] = set()
    ordered: list[str] = []
    for value in merged:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return tuple(ordered)


def parse_cli(args: argparse.Namespace) -> int:
    try:
        config = load_parsing_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_root = args.output_root if args.output_root is not None else config.output_root
    output_root = Path(output_root).expanduser().resolve()
    storage = ParseStorage(output_root)
    outcomes = []

    if args.command == "pdf":
        for path in args.paths:
            resolved = path.expanduser().resolve()
            outcome = parse_single_target(
                resolved,
                storage=storage,
                expected_parser="pdf",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "docx":
        for path in args.paths:
            resolved = path.expanduser().resolve()
            outcome = parse_single_target(
                resolved,
                storage=storage,
                expected_parser="docx",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "web":
        for token in args.sources:
            candidate = Path(token).expanduser()
            source = candidate.resolve() if candidate.exists() else token
            outcome = parse_single_target(
                source,
                storage=storage,
                expected_parser="web",
                force=args.force,
            )
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    elif args.command == "scan":
        suffixes = _merge_cli_sequences(
            config.scan.suffixes,
            args.suffix,
            clear=args.clear_config_suffixes,
        )
        recursive = config.scan.recursive if args.recursive is None else bool(args.recursive)
        include_patterns = _merge_cli_sequences(
            config.scan.include,
            args.include,
            clear=args.clear_config_include,
        )
        exclude_patterns = _merge_cli_sequences(
            config.scan.exclude,
            args.exclude,
            clear=args.clear_config_exclude,
        )
        try:
            results = scan_and_parse(
                args.root,
                storage=storage,
                suffixes=suffixes,
                recursive=recursive,
                force=args.force,
                limit=args.limit,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not results:
            print(
                f"No documents found under {args.root.expanduser().resolve()} matching the requested filters."
            )
            return 0
        for outcome in results:
            outcomes.append(outcome)
            _emit_parse_outcome(outcome)
    else:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported parse subcommand: {args.command}")

    return 1 if any(item.status == "error" for item in outcomes) else 0


def render_body(args: argparse.Namespace, variables: dict[str, str]) -> str:
    if args.body:
        return render_template(args.body, variables)

    template_path: Path = args.template
    template_content = load_template(template_path)
    return render_template(template_content, variables)


def format_output(outcome: IssueOutcome, mode: str) -> str:
    if mode == OUTPUT_JSON:
        return json.dumps({
            "number": outcome.number,
            "url": outcome.url,
            "html_url": outcome.html_url,
        })
    if mode == OUTPUT_NUMBER:
        return str(outcome.number)
    return f"Created issue #{outcome.number}: {outcome.html_url}"


def create_issue_cli(args: argparse.Namespace) -> int:
    repository = resolve_repository(args.repo)
    token = resolve_token(args.token)
    try:
        variables = parse_variables(args.var)
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    body = render_body(args, variables)

    if args.dry_run:
        preview = format_output(
            IssueOutcome(number=0, url="", html_url="(dry run)"),
            args.output,
        )
        print(preview)
        return 0

    try:
        outcome = create_issue(
            token=token,
            repository=repository,
            title=args.title,
            body=body,
            api_url=args.api_url,
            labels=args.label or None,
            assignees=args.assignee or None,
        )
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_output(outcome, args.output))
    return 0


def format_search_results(results: Iterable[IssueSearchResult], mode: str) -> str:
    materialized = list(results)

    if mode == OUTPUT_JSON:
        return json.dumps([result.to_dict() for result in materialized], indent=2)

    lines = []
    for result in materialized:
        assignee = result.assignee or "unassigned"
        lines.append(f"#{result.number} [{result.state}] {result.title} -> {assignee}")
    return "\n".join(lines)


def search_issues_cli(args: argparse.Namespace) -> int:
    repository = resolve_repository(args.repo)
    token = resolve_token(args.token)
    limit = args.limit if args.limit is not None else 30
    limit = max(1, min(limit, 100))

    searcher = GitHubIssueSearcher(token=token, repository=repository, api_url=args.api_url)

    try:
        if args.label:
            results = searcher.search_by_label(args.label, limit=limit)
        else:
            results = searcher.search_assigned(args.assignee, limit=limit)
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_search_results(results, args.output))
    return 0


def run_agent_cli(args: argparse.Namespace) -> int:
    repository = resolve_repository(args.repo)
    token = resolve_agent_token(args.token)

    searcher = GitHubIssueSearcher(token=token, repository=repository, api_url=args.api_url)

    try:
        results = list(searcher.search_by_label(args.label, limit=1))
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not results:
        print(f"No open issues labeled '{args.label}' are available for Copilot.")
        return 0

    issue = results[0]
    print(f"Selected issue #{issue.number}: {issue.title}")

    additional_tools = tuple(tool for tool in args.copilot_allow_tool if tool)
    if args.copilot_no_default_tools:
        allowed_tools = additional_tools
    else:
        base_tools: tuple[str, ...] = DEFAULT_ALLOWED_COPILOT_TOOLS
        if additional_tools:
            ordered: list[str] = []
            for tool in (*base_tools, *additional_tools):
                if tool not in ordered:
                    ordered.append(tool)
            allowed_tools = tuple(ordered)
        else:
            allowed_tools = base_tools

    try:
        outcome = run_issue_with_local_copilot(
            token=token,
            repository=repository,
            issue_number=issue.number,
            label_to_remove=None if args.keep_label else args.label,
            api_url=args.api_url,
            base_branch=args.base,
            extra_instructions=args.instructions,
            copilot_command=args.copilot_bin,
            copilot_model=args.copilot_model,
            copilot_args=args.copilot_arg or None,
            allowed_tools=allowed_tools,
            push_branch_before_pr=not args.skip_push,
            create_pr=not args.skip_pr,
            pr_draft=args.draft,
        )
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Working branch: {outcome.branch_name}")
    print("\nPrompt passed to Copilot CLI:\n")
    print(outcome.prompt)

    if outcome.commit_output:
        print("\nGit commit output:\n" + outcome.commit_output)
    elif not outcome.changes_committed:
        print("\nNo repository changes detected after the agent run; skipping commit, push, and pull request steps.")

    if outcome.push_output:
        print("\nGit push output:\n" + outcome.push_output)
    if outcome.pr_output:
        print("\nPull request creation output:\n" + outcome.pr_output)

    if not args.keep_label:
        label_status = "removed" if outcome.label_removed else "already absent"
        print(f"\nLabel '{args.label}' {label_status}.")

    return 0


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv

    if raw_args and raw_args[0] == "search":
        parser = build_search_parser()
        try:
            args = parser.parse_args(raw_args[1:])
        except argparse.ArgumentError as exc:
            parser.error(str(exc))
        return search_issues_cli(args)

    if raw_args and raw_args[0] == "run-agent":
        parser = build_run_agent_parser()
        try:
            args = parser.parse_args(raw_args[1:])
        except argparse.ArgumentError as exc:
            parser.error(str(exc))
        return run_agent_cli(args)

    if raw_args and raw_args[0] == "parse":
        parser = build_parse_parser()
        try:
            args = parser.parse_args(raw_args[1:])
        except argparse.ArgumentError as exc:
            parser.error(str(exc))
        return parse_cli(args)

    if raw_args and raw_args[0] == "create":
        raw_args = raw_args[1:]

    parser = build_create_parser()
    try:
        args = parser.parse_args(raw_args)
    except argparse.ArgumentError as exc:
        parser.error(str(exc))

    return create_issue_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())