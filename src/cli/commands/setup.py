"""CLI command for repository setup and initialization."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Optional

from src.integrations.github.issues import (
    create_issue,
    post_comment,
    resolve_repository,
    resolve_token,
    get_repository_details,
    GitHubIssueError,
)

SETUP_ISSUE_TITLE = "Project Configuration & Setup"
SETUP_ISSUE_BODY = (
    "This issue tracks the initial configuration of the repository.\n\n"
    "The setup agent will guide you through the process."
)
WELCOME_COMMENT = (
    "Welcome to the repository setup wizard! 🧙‍♂️\n\n"
    "I will help you configure your project. Please provide the following details:\n\n"
    "1. **Source URL**: The URL of the data source you want to track.\n"
    "2. **Topic**: The main topic or category for this data.\n"
    "3. **Frequency**: How often you want to check for updates (e.g., daily, weekly).\n"
    "4. **Model**: The LLM model to use for operations (default: gpt-4o).\n\n"
    "Please reply to this comment with the information above."
)


def _configure_upstream_remote(url: str) -> None:
    """Configure the upstream remote if it doesn't exist."""
    try:
        # Check if upstream exists
        subprocess.run(
            ["git", "remote", "get-url", "upstream"],
            check=True,
            capture_output=True
        )
        print("Upstream remote already exists.")
    except subprocess.CalledProcessError:
        # Add upstream
        print(f"Adding upstream remote: {url}")
        try:
            subprocess.run(
                ["git", "remote", "add", "upstream", url],
                check=True,
                capture_output=True
            )
            print("Fetching from upstream...")
            subprocess.run(["git", "fetch", "upstream"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to configure upstream remote: {e}", file=sys.stderr)


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the setup command."""
    parser = subparsers.add_parser(
        "setup",
        help="Initialize the repository and start the setup workflow.",
    )
    parser.add_argument(
        "--repo",
        help="The repository to setup (format: owner/repo). Defaults to current git repo.",
    )
    parser.set_defaults(func=setup_repo_cli)


def setup_repo_cli(args: argparse.Namespace) -> int:
    """Handler for the setup command."""
    try:
        token = resolve_token(None)
        repo = resolve_repository(args.repo)
    except GitHubIssueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"Initializing setup for repository: {repo}")

    try:
        # Check for template and configure upstream
        details = get_repository_details(token=token, repository=repo)
        template_repo = details.get("template_repository")
        if template_repo:
            template_clone_url = template_repo.get("clone_url")
            if template_clone_url:
                print(f"Repository created from template: {template_repo.get('full_name')}")
                _configure_upstream_remote(template_clone_url)
    except Exception as e:
        print(f"Warning: Failed to configure upstream remote: {e}", file=sys.stderr)

    try:
        # 1. Create the setup issue
        issue = create_issue(
            token=token,
            repository=repo,
            title=SETUP_ISSUE_TITLE,
            body=SETUP_ISSUE_BODY,
            labels=["setup", "wontfix"], # wontfix to prevent auto-closing if configured
        )
        print(f"Created setup issue: {issue.html_url}")

        # 2. Post the welcome comment
        post_comment(
            token=token,
            repository=repo,
            issue_number=issue.number,
            body=WELCOME_COMMENT,
        )
        print("Posted welcome comment.")

    except GitHubIssueError as err:
        print(f"GitHub API Error: {err}", file=sys.stderr)
        return 1

    return 0
