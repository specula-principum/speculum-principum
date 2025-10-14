"""Helpers for assigning issues to the GitHub Copilot code assistant."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib import error, request

from .issues import API_VERSION, DEFAULT_API_URL, GitHubIssueError, normalize_repository

COPILOT_ASSIGNEE = "copilot"
COPILOT_ASSIGNEE_ENV = "GITHUB_COPILOT_ASSIGNEE"
COPILOT_ASSIGNMENT_UNSUPPORTED_ERROR = (
    "GitHub Copilot agent '{login}' cannot be assigned via the REST API. "
    "Add the 'ready-for-copilot' label to trigger the 'assign-copilot' GitHub Action, "
    "which assigns the issue using the GitHub CLI."
)


@dataclass(frozen=True)
class AssignmentOutcome:
    """Represents the response from a successful assignment update."""

    number: int
    url: str
    assignees: tuple[str, ...]

    @classmethod
    def from_api_payload(cls, payload: Mapping[str, object]) -> "AssignmentOutcome":
        try:
            number = int(payload["number"])  # type: ignore[arg-type]
            url = str(payload.get("html_url") or payload.get("url"))
            raw_assignees = payload.get("assignees", [])
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - protective
            raise GitHubIssueError("Unexpected GitHub response payload") from exc

        if not url:
            raise GitHubIssueError("Issue payload missing URL field")

        assignees: list[str] = []
        if isinstance(raw_assignees, Sequence):
            for entry in raw_assignees:
                if isinstance(entry, Mapping):
                    login = entry.get("login")
                    if isinstance(login, str):
                        assignees.append(login)

        return cls(number=number, url=url, assignees=tuple(assignees))


def resolve_copilot_assignee(explicit: str | None = None) -> str:
    """Resolve the login to use for Copilot assignments."""

    if explicit is not None:
        candidate = explicit.strip()
        if not candidate:
            raise GitHubIssueError("Assignee override cannot be empty.")
        return candidate

    env_candidate = os.environ.get(COPILOT_ASSIGNEE_ENV, "").strip()
    if env_candidate:
        return env_candidate

    return COPILOT_ASSIGNEE


def assign_issue(
    *,
    token: str,
    repository: str,
    issue_number: int,
    assignees: Sequence[str],
    api_url: str = DEFAULT_API_URL,
) -> AssignmentOutcome:
    """Assign a GitHub issue to the provided logins."""

    if issue_number < 1:
        raise GitHubIssueError("Issue number must be a positive integer.")
    if not assignees:
        raise GitHubIssueError("At least one assignee must be provided.")

    owner, name = normalize_repository(repository)
    expected = [login.strip() for login in assignees if login.strip()]
    if not expected:
        raise GitHubIssueError("Assignee logins cannot be blank.")
    payload: dict[str, object] = {"assignees": list(assignees)}

    url = f"{api_url.rstrip('/')}/repos/{owner}/{name}/issues/{issue_number}/assignees"
    raw_body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=raw_body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)
    req.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with request.urlopen(req) as response:  # type: ignore[no-any-unimported]
            response_bytes = response.read()
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc

    data = json.loads(response_bytes.decode("utf-8"))
    if not isinstance(data, Mapping):  # pragma: no cover - defensive
        raise GitHubIssueError("Unexpected GitHub response payload")
    outcome = AssignmentOutcome.from_api_payload(data)

    missing = [login for login in expected if login not in outcome.assignees]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise GitHubIssueError(
            f"GitHub did not assign the requested user(s) ({missing_str}) to issue #{issue_number}. "
            "Confirm the account has access to the repository."
        )

    return outcome


def assign_issue_to_copilot(
    *,
    token: str,
    repository: str,
    issue_number: int,
    api_url: str = DEFAULT_API_URL,
    assignee: str | None = None,
) -> AssignmentOutcome:
    """Raise an informative error because Copilot cannot be assigned via REST."""

    login = resolve_copilot_assignee(assignee)
    raise GitHubIssueError(COPILOT_ASSIGNMENT_UNSUPPORTED_ERROR.format(login=login))


def assign_issues_to_copilot(
    *,
    token: str,
    repository: str,
    issue_numbers: Sequence[int],
    api_url: str = DEFAULT_API_URL,
    assignee: str | None = None,
) -> list[AssignmentOutcome]:
    """Raise an informative error because Copilot cannot be assigned via REST."""

    login = resolve_copilot_assignee(assignee)
    raise GitHubIssueError(COPILOT_ASSIGNMENT_UNSUPPORTED_ERROR.format(login=login))
