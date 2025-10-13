"""Compatibility layer for GitHub issue helpers.

The CLI now lives in :mod:`main`. This module keeps the public helpers
available under their previous import path for any programmatic callers.
"""

from __future__ import annotations

from .issues import (
    DEFAULT_API_URL,
    GitHubIssueError,
    IssueOutcome,
    create_issue,
    load_template,
    render_template,
    resolve_repository,
    resolve_token,
)

__all__ = [
    "DEFAULT_API_URL",
    "GitHubIssueError",
    "IssueOutcome",
    "create_issue",
    "load_template",
    "render_template",
    "resolve_repository",
    "resolve_token",
]
