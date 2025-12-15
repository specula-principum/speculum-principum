"""CLI commands for repository sync operations."""

from __future__ import annotations

import argparse
import json
import os
import sys

from src.integrations.github.issues import (
    GitHubIssueError,
    resolve_repository,
    resolve_token,
)
from src.integrations.github.sync import notify_downstream_repos, sync_from_upstream


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register sync commands."""
    
    # Sync from upstream command
    sync_parser = subparsers.add_parser(
        "sync-upstream",
        help="Sync code directories from upstream template repository.",
    )
    sync_parser.add_argument(
        "--downstream-repo",
        help="Downstream repository (format: owner/repo). Defaults to current repo.",
    )
    sync_parser.add_argument(
        "--upstream-repo",
        required=True,
        help="Upstream repository (format: owner/repo).",
    )
    sync_parser.add_argument(
        "--upstream-branch",
        help="Upstream branch to sync from (defaults to repository default branch).",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report changes without creating PR.",
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync - overwrite local modifications without validation.",
    )
    sync_parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    sync_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    sync_parser.set_defaults(func=sync_upstream_cli)
    
    # Notify downstream repos command
    notify_parser = subparsers.add_parser(
        "notify-downstream",
        help="Notify downstream repositories of upstream changes.",
    )
    notify_parser.add_argument(
        "--upstream-repo",
        help="Upstream repository (format: owner/repo). Defaults to current repo.",
    )
    notify_parser.add_argument(
        "--upstream-branch",
        default="main",
        help="Upstream branch name.",
    )
    notify_parser.add_argument(
        "--release-tag",
        help="Release tag name.",
    )
    notify_parser.add_argument(
        "--org",
        help="Target organization to search (defaults to upstream repo org).",
    )
    notify_parser.add_argument(
        "--secret",
        help="HMAC secret. Defaults to $SYNC_SIGNATURE_SECRET.",
    )
    notify_parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GH_TOKEN or $GITHUB_TOKEN.",
    )
    notify_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show which repos would be notified.",
    )
    notify_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    notify_parser.set_defaults(func=notify_downstream_cli)


def sync_upstream_cli(args: argparse.Namespace) -> int:
    """Handler for sync-upstream command."""
    try:
        token = resolve_token(args.token)
        downstream_repo = resolve_repository(args.downstream_repo)
    except GitHubIssueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    
    upstream_repo = args.upstream_repo
    upstream_branch = args.upstream_branch or None
    dry_run = args.dry_run
    force_sync = args.force
    
    if not args.json:
        print(f"Syncing from {upstream_repo} to {downstream_repo}")
        print(f"Upstream branch: {upstream_branch or '(default)'}")
        print(f"Dry run: {dry_run}")
        print(f"Force sync: {force_sync}")
        print()
    
    try:
        result = sync_from_upstream(
            downstream_repo=downstream_repo,
            upstream_repo=upstream_repo,
            downstream_token=token,
            upstream_token=token,
            upstream_branch=upstream_branch,
            dry_run=dry_run,
            force_sync=force_sync,
            verbose=not args.json,
        )
        
        if args.json:
            output = {
                "changes_count": len(result.changes),
                "has_changes": result.has_changes,
                "dry_run": result.dry_run,
                "error": result.error,
                "pr_url": result.pr_url,
                "pr_number": result.pr_number,
                "branch_name": result.branch_name,
            }
            print(json.dumps(output, indent=2))
        else:
            print(result.summary())
            print()
            
            if result.error:
                print(f"Error: {result.error}")
                return 1
            
            if result.pr_url:
                print(f"Created PR: {result.pr_url}")
        
        return 0 if not result.error else 1
    
    except Exception as err:
        if args.json:
            print(json.dumps({"error": str(err)}, indent=2), file=sys.stderr)
        else:
            print(f"Error during sync: {err}", file=sys.stderr)
        return 1


def notify_downstream_cli(args: argparse.Namespace) -> int:
    """Handler for notify-downstream command."""
    # Resolve token - try GH_TOKEN first, then GITHUB_TOKEN
    token = args.token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: No token provided. Use --token or set GH_TOKEN/GITHUB_TOKEN", file=sys.stderr)
        return 1
    
    # Resolve secret
    secret = args.secret or os.environ.get("SYNC_SIGNATURE_SECRET")
    if not secret:
        print("Error: SYNC_SIGNATURE_SECRET not set", file=sys.stderr)
        print("Generate a secret with: openssl rand -hex 32", file=sys.stderr)
        return 1
    
    try:
        upstream_repo = resolve_repository(args.upstream_repo)
    except GitHubIssueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    
    upstream_branch = args.upstream_branch
    release_tag = args.release_tag or "manual"
    target_org = args.org or None
    dry_run = args.dry_run
    
    if not args.json:
        print(f"Upstream: {upstream_repo}")
        print(f"Branch: {upstream_branch}")
        print(f"Release: {release_tag}")
        print(f"Dry run: {dry_run}")
        if target_org:
            print(f"Target org: {target_org}")
        print()
    
    try:
        results = notify_downstream_repos(
            upstream_repo=upstream_repo,
            upstream_branch=upstream_branch,
            secret=secret,
            token=token,
            org=target_org,
            release_tag=release_tag,
            dry_run=dry_run,
        )
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print()
            print("=" * 50)
            print(f"Results: {results['success']} succeeded, {results['failed']} failed")
            print("=" * 50)
        
        return 0 if results["failed"] == 0 else 1
    
    except Exception as err:
        if args.json:
            print(json.dumps({"error": str(err)}, indent=2), file=sys.stderr)
        else:
            print(f"Error during notification: {err}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        return 1
