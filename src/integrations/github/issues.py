"""Helpers for creating GitHub issues programmatically."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib import error, request

DEFAULT_API_URL = "https://api.github.com"
API_VERSION = "2022-11-28"


class GitHubIssueError(RuntimeError):
    """Raised when the GitHub API returns an error."""


@dataclass(frozen=True)
class IssueOutcome:
    """Represents the response from a successful issue creation."""

    number: int
    url: str
    html_url: str

    @classmethod
    def from_api_payload(cls, payload: Mapping[str, object]) -> "IssueOutcome":
        try:
            number = int(payload["number"])  # type: ignore[arg-type]
            url = str(payload["url"])
            html_url = str(payload.get("html_url", url))
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - protective
            raise GitHubIssueError("Unexpected GitHub response payload") from exc
        return cls(number=number, url=url, html_url=html_url)


def normalize_repository(repository: str | None) -> tuple[str, str]:
    """Split an ``owner/repo`` string into its two components."""

    if not repository:
        raise GitHubIssueError("Repository must be provided as 'owner/repo'.")
    owner, sep, name = repository.partition("/")
    if not sep or not owner or not name:
        raise GitHubIssueError(f"Invalid repository format: {repository!r}")
    return owner, name


def resolve_repository(explicit_repo: str | None) -> str:
    """Return the repository name, preferring explicit input over the environment."""

    if explicit_repo:
        return explicit_repo
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise GitHubIssueError(
            "Repository not provided; set --repo or the GITHUB_REPOSITORY environment variable."
        )
    return repo


def resolve_token(explicit_token: str | None) -> str:
    """Return the token, preferring explicit input over the environment."""

    if explicit_token:
        return explicit_token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubIssueError(
            "Token not provided; set --token or the GITHUB_TOKEN environment variable."
        )
    return token


def load_template(template_path: Path) -> str:
    """Read the template file as UTF-8 text."""

    if not template_path.exists():
        raise GitHubIssueError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def render_template(template: str, variables: Mapping[str, str] | None = None) -> str:
    """Inject variables into the template body using ``str.format`` semantics."""

    if not variables:
        return template
    try:
        return template.format(**variables)
    except KeyError as exc:
        missing = ", ".join(sorted(exc.args))
        raise GitHubIssueError(f"Missing template variables: {missing}") from exc


def create_issue(
    *,
    token: str,
    repository: str,
    title: str,
    body: str,
    api_url: str = DEFAULT_API_URL,
    labels: Sequence[str] | None = None,
    assignees: Sequence[str] | None = None,
) -> IssueOutcome:
    """Create a GitHub issue and return the result."""

    owner, name = normalize_repository(repository)
    payload: dict[str, object] = {"title": title, "body": body}
    if labels:
        payload["labels"] = list(labels)
    if assignees:
        payload["assignees"] = list(assignees)

    url = f"{api_url.rstrip('/')}/repos/{owner}/{name}/issues"
    raw_body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=raw_body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)
    req.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with request.urlopen(req) as response:
            response_bytes = response.read()
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc

    data = json.loads(response_bytes.decode("utf-8"))
    return IssueOutcome.from_api_payload(data)