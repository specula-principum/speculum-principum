from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.github.assign_copilot import (  # noqa: E402
    AssignmentOutcome,
    COPILOT_ASSIGNEE,
    COPILOT_ASSIGNMENT_UNSUPPORTED_ERROR,
    assign_issue,
    assign_issue_to_copilot,
    assign_issues_to_copilot,
    resolve_copilot_assignee,
)
from src.integrations.github.issues import GitHubIssueError  # noqa: E402


class DummyResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def make_issue_payload(number: int = 42, assignees: list[str] | None = None) -> dict[str, Any]:
    raw_assignees = assignees if assignees is not None else [COPILOT_ASSIGNEE]
    return {
        "number": number,
        "html_url": f"https://example.test/{number}",
        "assignees": [{"login": login} for login in raw_assignees],
    }


def test_assign_issue_posts_to_assignees(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return DummyResponse(make_issue_payload(assignees=["octocat"]))

    monkeypatch.setattr("src.integrations.github.assign_copilot.request.urlopen", fake_urlopen)

    outcome = assign_issue(
        token="token",
        repository="octocat/hello-world",
        issue_number=99,
        assignees=["octocat"],
    )

    assert captured["url"].endswith("/issues/99/assignees")
    assert captured["method"] == "POST"
    assert captured["payload"] == {"assignees": ["octocat"]}
    assert isinstance(outcome, AssignmentOutcome)
    assert outcome.assignees == ("octocat",)


def test_assign_issue_errors_when_github_ignores_assignee(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: Any):
        return DummyResponse(make_issue_payload(assignees=[]))

    monkeypatch.setattr("src.integrations.github.assign_copilot.request.urlopen", fake_urlopen)

    with pytest.raises(GitHubIssueError):
        assign_issue(
            token="token",
            repository="octocat/hello-world",
            issue_number=1,
            assignees=[COPILOT_ASSIGNEE],
        )


def test_assign_issue_requires_positive_issue_number() -> None:
    with pytest.raises(GitHubIssueError):
        assign_issue(
            token="token",
            repository="octocat/hello-world",
            issue_number=0,
            assignees=[COPILOT_ASSIGNEE],
        )


def test_assign_issue_to_copilot_raises_informative_error() -> None:
    with pytest.raises(GitHubIssueError) as excinfo:
        assign_issue_to_copilot(
            token="token",
            repository="octocat/hello-world",
            issue_number=1,
        )

    assert "cannot be assigned via the REST API" in str(excinfo.value)
    assert "ready-for-copilot" in str(excinfo.value)


def test_assign_issues_to_copilot_raises_informative_error() -> None:
    with pytest.raises(GitHubIssueError) as excinfo:
        assign_issues_to_copilot(
            token="token",
            repository="octocat/hello-world",
            issue_numbers=[1, 2, 3],
        )

    assert str(excinfo.value) == COPILOT_ASSIGNMENT_UNSUPPORTED_ERROR.format(login=COPILOT_ASSIGNEE)


def test_resolve_copilot_assignee_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_COPILOT_ASSIGNEE", "ignored")
    assert resolve_copilot_assignee("custom-user") == "custom-user"


def test_resolve_copilot_assignee_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_COPILOT_ASSIGNEE", "env-user")
    assert resolve_copilot_assignee(None) == "env-user"


def test_resolve_copilot_assignee_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_COPILOT_ASSIGNEE", raising=False)
    assert resolve_copilot_assignee(None) == COPILOT_ASSIGNEE


def test_assign_issue_rejects_blank_assignee() -> None:
    with pytest.raises(GitHubIssueError):
        assign_issue(
            token="token",
            repository="octocat/hello-world",
            issue_number=5,
            assignees=[""],
        )
