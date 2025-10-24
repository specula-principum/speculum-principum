from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

from src.integrations.github.issues import DEFAULT_API_URL, GitHubIssueError, resolve_repository, resolve_token
from src.integrations.github.search_issues import GitHubIssueSearcher, IssueSearchResult

from .common import OUTPUT_JSON, OUTPUT_TEXT


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
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
