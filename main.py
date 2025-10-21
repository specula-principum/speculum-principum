#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
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