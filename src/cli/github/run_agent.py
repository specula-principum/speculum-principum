from __future__ import annotations

import argparse
import sys

from src.integrations.github.assign_copilot import (
    DEFAULT_ALLOWED_COPILOT_TOOLS,
    run_issue_with_local_copilot,
)
from src.integrations.github.issues import DEFAULT_API_URL, GitHubIssueError, resolve_repository
from src.integrations.github.search_issues import GitHubIssueSearcher

from .common import DEFAULT_READY_LABEL, resolve_agent_token


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "run-agent",
        description="Run a Copilot agent locally for the next issue labeled 'ready-for-copilot'.",
        help="Run a Copilot agent for the next ready issue.",
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
    parser.set_defaults(func=run_agent_cli, command="run-agent")
    return parser


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
        print(
            "\nNo repository changes detected after the agent run; skipping commit, push, and pull request steps."
        )

    if outcome.push_output:
        print("\nGit push output:\n" + outcome.push_output)
    if outcome.pr_output:
        print("\nPull request creation output:\n" + outcome.pr_output)

    if not args.keep_label:
        label_status = "removed" if outcome.label_removed else "already absent"
        print(f"\nLabel '{args.label}' {label_status}.")

    return 0
