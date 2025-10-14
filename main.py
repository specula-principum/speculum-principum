#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from src.integrations.github.assign_copilot import (
    AssignmentOutcome,
    assign_issues_to_copilot,
    resolve_copilot_assignee,
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


def build_assign_copilot_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assign labeled issues to the GitHub Copilot code assistant.",
        prog="python -m main assign-copilot",
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
        help="Issue label to search before assigning. Defaults to 'ready-for-copilot'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of labeled issues to evaluate (1-100).",
    )
    parser.add_argument(
        "--assignee",
        help="Override the Copilot login. Defaults to copilot or $GITHUB_COPILOT_ASSIGNEE.",
    )
    parser.add_argument(
        "--output",
        choices=[OUTPUT_TEXT, OUTPUT_JSON],
        default=OUTPUT_TEXT,
        help="Output format: friendly text or JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the assignment plan without performing API calls.",
    )
    parser.add_argument(
        "--include-assigned",
        action="store_true",
        help="Assign even when the Copilot assistant is already on the issue.",
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


def format_assignment_preview(issue_numbers: Iterable[int], assignee: str, mode: str) -> str:
    issues = [int(number) for number in issue_numbers]
    if mode == OUTPUT_JSON:
        return json.dumps({
            "assignee": assignee,
            "issues": issues,
            "dry_run": True,
        }, indent=2)

    formatted = ", ".join(f"#{number}" for number in issues)
    if not formatted:
        formatted = "no issues"
    return f"Would assign {formatted} to {assignee}."


def format_assignment_results(outcomes: Iterable[AssignmentOutcome], mode: str) -> str:
    materialized = list(outcomes)

    if mode == OUTPUT_JSON:
        return json.dumps([
            {
                "number": outcome.number,
                "url": outcome.url,
                "assignees": list(outcome.assignees),
            }
            for outcome in materialized
        ], indent=2)

    lines = []
    for outcome in materialized:
        assignees = ", ".join(outcome.assignees) if outcome.assignees else "unassigned"
        lines.append(f"Assigned #{outcome.number} -> {assignees}")
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


def assign_copilot_cli(args: argparse.Namespace) -> int:
    repository = resolve_repository(args.repo)
    token = resolve_token(args.token)
    assignee = resolve_copilot_assignee(args.assignee)
    limit = args.limit if args.limit is not None else 30
    limit = max(1, min(limit, 100))

    searcher = GitHubIssueSearcher(token=token, repository=repository, api_url=args.api_url)

    try:
        results = searcher.search_by_label(args.label, limit=limit)
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.include_assigned:
        results = [result for result in results if result.assignee != assignee]

    if not results:
        print(f"No open issues labeled '{args.label}' require Copilot assignment.")
        return 0

    issue_numbers = [result.number for result in results]

    if args.dry_run:
        print(format_assignment_preview(issue_numbers, assignee, args.output))
        return 0

    try:
        outcomes = assign_issues_to_copilot(
            token=token,
            repository=repository,
            issue_numbers=issue_numbers,
            api_url=args.api_url,
            assignee=assignee,
        )
    except GitHubIssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_assignment_results(outcomes, args.output))
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

    if raw_args and raw_args[0] == "assign-copilot":
        parser = build_assign_copilot_parser()
        try:
            args = parser.parse_args(raw_args[1:])
        except argparse.ArgumentError as exc:
            parser.error(str(exc))
        return assign_copilot_cli(args)

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