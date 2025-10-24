from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

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

from .common import OUTPUT_JSON, OUTPUT_NUMBER, OUTPUT_TEXT


def _configure_parser(parser: argparse.ArgumentParser) -> None:
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
    parser.set_defaults(func=create_issue_cli, command="create")


def build_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue using a template.",
        prog=prog,
    )
    _configure_parser(parser)
    return parser


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "create",
        description="Create a GitHub issue using a template.",
        help="Create a GitHub issue using a template.",
    )
    _configure_parser(parser)
    return parser


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
