"""GitHub CLI commands for issue creation, searching, and running Copilot agents."""
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
from src.integrations.github.search_issues import GitHubIssueSearcher, IssueSearchResult

# Constants
OUTPUT_TEXT = "text"
OUTPUT_JSON = "json"
OUTPUT_NUMBER = "number"

__all__ = [
    "register_commands",
]


def resolve_agent_token(explicit_token: str | None) -> str:
    """Prefer an explicit token, then fall back to the environment."""
    if explicit_token:
        return explicit_token
    return resolve_token(None)


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add GitHub-focused subcommands to the main CLI parser."""
    register_create_command(subparsers)
    register_search_command(subparsers)
    register_pr_commands(subparsers)


# ========================
# CREATE COMMAND
# ========================

def _configure_create_parser(parser: argparse.ArgumentParser) -> None:
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
        default=Path(".github/ISSUE_TEMPLATE/general.md"),
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


def build_create_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue using a template.",
        prog=prog,
    )
    _configure_create_parser(parser)
    return parser


def register_create_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "create",
        description="Create a GitHub issue using a template.",
        help="Create a GitHub issue using a template.",
    )
    _configure_create_parser(parser)
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


def format_create_output(outcome: IssueOutcome, mode: str) -> str:
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
        preview = format_create_output(
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

    print(format_create_output(outcome, args.output))
    return 0


# ========================
# SEARCH COMMAND
# ========================

def register_search_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "search",
        description="Search GitHub issues.",
        help="Search GitHub issues.",
        prog="python -m main search",
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
    parser.set_defaults(func=search_issues_cli, command="search")
    return parser


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


# ========================
# PR COMMANDS
# ========================

def register_pr_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register pull request management commands."""
    
    # Validate PR file scope
    validate_pr_parser = subparsers.add_parser(
        "validate-pr",
        help="Validate PR file scope against sync boundaries.",
    )
    validate_pr_parser.add_argument(
        "--repo",
        required=True,
        help="Target repository in owner/repo form.",
    )
    validate_pr_parser.add_argument(
        "--pr",
        required=True,
        type=int,
        help="Pull request number.",
    )
    validate_pr_parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    validate_pr_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    validate_pr_parser.set_defaults(func=validate_pr_cli)
    
    # Enable auto-merge on PR
    auto_merge_parser = subparsers.add_parser(
        "enable-auto-merge",
        help="Enable auto-merge on a pull request.",
    )
    auto_merge_parser.add_argument(
        "--repo",
        required=True,
        help="Target repository in owner/repo form.",
    )
    auto_merge_parser.add_argument(
        "--pr",
        required=True,
        type=int,
        help="Pull request number.",
    )
    auto_merge_parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    auto_merge_parser.add_argument(
        "--merge-method",
        choices=["MERGE", "SQUASH", "REBASE"],
        default="SQUASH",
        help="Merge method to use.",
    )
    auto_merge_parser.set_defaults(func=enable_auto_merge_cli)
    
    # Approve PR
    approve_pr_parser = subparsers.add_parser(
        "approve-pr",
        help="Approve a pull request.",
    )
    approve_pr_parser.add_argument(
        "--repo",
        required=True,
        help="Target repository in owner/repo form.",
    )
    approve_pr_parser.add_argument(
        "--pr",
        required=True,
        type=int,
        help="Pull request number.",
    )
    approve_pr_parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    approve_pr_parser.add_argument(
        "--body",
        help="Review comment body.",
    )
    approve_pr_parser.set_defaults(func=approve_pr_cli)


def validate_pr_cli(args: argparse.Namespace) -> int:
    """Handler for validate-pr command."""
    from src.integrations.github.sync import validate_pr_file_scope
    
    try:
        token = resolve_token(args.token)
    except GitHubIssueError as err:
        if args.json:
            result = {
                "valid": False,
                "reason": f"Authentication error: {err}",
                "pr_number": args.pr,
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {err}", file=sys.stderr)
        return 1
    
    try:
        is_valid, reason = validate_pr_file_scope(args.repo, args.pr, token)
        
        if args.json:
            result = {
                "valid": is_valid,
                "reason": reason,
                "pr_number": args.pr,
            }
            print(json.dumps(result, indent=2))
        else:
            print(reason)
        
        return 0 if is_valid else 1
    
    except Exception as err:
        if args.json:
            result = {
                "valid": False,
                "reason": f"Validation error: {err}",
                "pr_number": args.pr,
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error validating PR: {err}", file=sys.stderr)
        return 1


def enable_auto_merge_cli(args: argparse.Namespace) -> int:
    """Handler for enable-auto-merge command."""
    from src.integrations.github.pull_requests import (
        enable_pull_request_auto_merge,
        fetch_pull_request,
    )
    
    token = resolve_token(args.token)
    
    try:
        # First fetch the PR to get its node_id
        pr_data = fetch_pull_request(
            token=token,
            repository=args.repo,
            pr_number=args.pr,
        )
        
        node_id = pr_data.get("node_id")
        if not node_id:
            print("Error: Could not get PR node_id", file=sys.stderr)
            return 1
        
        # Enable auto-merge
        result = enable_pull_request_auto_merge(
            token=token,
            pr_node_id=node_id,
            merge_method=args.merge_method,
        )
        
        print(f"✅ Auto-merge enabled on PR #{args.pr}")
        return 0
    
    except Exception as err:
        print(f"Error enabling auto-merge: {err}", file=sys.stderr)
        return 1


def approve_pr_cli(args: argparse.Namespace) -> int:
    """Handler for approve-pr command."""
    from src.integrations.github.pull_requests import approve_pull_request
    
    token = resolve_token(args.token)
    
    try:
        approve_pull_request(
            token=token,
            repository=args.repo,
            pr_number=args.pr,
            body=args.body,
        )
        
        print(f"✅ Approved PR #{args.pr}")
        return 0
    
    except Exception as err:
        print(f"Error approving PR: {err}", file=sys.stderr)
        return 1

