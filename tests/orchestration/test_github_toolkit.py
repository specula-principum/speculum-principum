"""Tests for GitHub orchestration tool registrations."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pytest

from src.integrations.github.issues import GitHubIssueError
from src.integrations.github.search_issues import IssueSearchResult
from src.orchestration.toolkit import register_github_read_only_tools
from src.orchestration.tools import ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_github_read_only_tools(reg)
    return reg


def test_get_issue_details_returns_normalized_payload(monkeypatch, registry: ToolRegistry):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    sample_payload: dict[str, Any] = {
        "number": 42,
        "title": "Sample issue",
        "state": "open",
        "body": "Body text",
        "html_url": "https://github.com/octo/repo/issues/42",
        "labels": [{"name": "bug"}, {"name": "triage"}],
        "assignees": [{"login": "octocat"}],
        "user": {"login": "author"},
        "created_at": "2025-10-01T00:00:00Z",
        "updated_at": "2025-10-02T00:00:00Z",
        "comments": 3,
    }

    monkeypatch.setattr(
        "src.integrations.github.issues.fetch_issue",
        lambda *, token, repository, issue_number: sample_payload,
    )
    monkeypatch.setattr(
        "src.integrations.github.issues.fetch_issue_comments",
        lambda *, token, repository, issue_number: [],
    )

    result = registry.execute_tool("get_issue_details", {"issue_number": 42})

    assert result.success
    assert result.error is None
    assert result.output == {
        "number": 42,
        "title": "Sample issue",
        "state": "open",
        "body": "Body text",
        "url": "https://github.com/octo/repo/issues/42",
        "author": "author",
        "labels": ["bug", "triage"],
        "assignees": ["octocat"],
        "created_at": "2025-10-01T00:00:00Z",
        "updated_at": "2025-10-02T00:00:00Z",
        "closed_at": None,
        "comments": [],
    }


def test_get_issue_details_handles_errors(monkeypatch, registry: ToolRegistry):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def _raise(*, token, repository, issue_number):  # type: ignore[unused-argument]
        raise GitHubIssueError("boom")

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _raise)

    result = registry.execute_tool("get_issue_details", {"issue_number": 7})

    assert not result.success
    assert result.error == "boom"


def test_get_issue_details_validates_issue_number(registry: ToolRegistry):
    result = registry.execute_tool("get_issue_details", {"issue_number": 0})
    assert not result.success
    assert result.error is not None
    assert "Argument validation failed" in result.error


def test_search_issues_by_label_returns_serialized_payload(monkeypatch, registry: ToolRegistry):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    captured: Dict[str, Any] = {}

    class DummySearcher:
        def __init__(self, *, token: str, repository: str, api_url: str) -> None:
            captured["token"] = token
            captured["repository"] = repository
            captured["api_url"] = api_url

        def search_by_label(self, label: str, *, limit: int) -> List[IssueSearchResult]:
            captured["label"] = label
            captured["limit"] = limit
            return [
                IssueSearchResult(number=1, title="Bug", state="open", url="https://example/1", assignee=None),
            ]

    monkeypatch.setattr("src.orchestration.toolkit.github.GitHubIssueSearcher", DummySearcher)

    result = registry.execute_tool("search_issues_by_label", {"label": "bug", "limit": 5})

    assert result.success
    assert result.error is None
    assert result.output == [
        {
            "number": 1,
            "title": "Bug",
            "state": "open",
            "url": "https://example/1",
            "assignee": None,
        }
    ]
    assert captured["label"] == "bug"
    assert captured["limit"] == 5
    assert captured["repository"] == "octo/repo"


def test_search_issues_assigned_supports_unassigned(monkeypatch, registry: ToolRegistry):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    class DummySearcher:
        def __init__(self, *, token: str, repository: str, api_url: str) -> None:
            self.token = token
            self.repository = repository
            self.api_url = api_url

        def search_assigned(self, assignee: str | None, *, limit: int) -> Iterable[IssueSearchResult]:
            assert assignee is None
            assert limit == 30
            return [
                IssueSearchResult(number=7, title="Needs triage", state="open", url="https://example/7", assignee=None)
            ]

    monkeypatch.setattr("src.orchestration.toolkit.github.GitHubIssueSearcher", DummySearcher)

    result = registry.execute_tool("search_issues_assigned", {})

    assert result.success
    assert result.error is None
    assert result.output == [
        {
            "number": 7,
            "title": "Needs triage",
            "state": "open",
            "url": "https://example/7",
            "assignee": None,
        }
    ]


def test_get_ready_for_copilot_issue_returns_none_when_missing(monkeypatch, registry: ToolRegistry):
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    class DummySearcher:
        def __init__(self, *, token: str, repository: str, api_url: str) -> None:
            self.token = token
            self.repository = repository
            self.api_url = api_url

        def search_by_label(self, label: str, *, limit: int) -> list[IssueSearchResult]:
            assert label == "ready-for-copilot"
            assert limit == 1
            return []

    monkeypatch.setattr("src.orchestration.toolkit.github.GitHubIssueSearcher", DummySearcher)

    result = registry.execute_tool("get_ready_for_copilot_issue", {})

    assert result.success
    assert result.error is None
    assert result.output == {"label": "ready-for-copilot", "issue": None}


def test_render_issue_template_renders_body(monkeypatch, tmp_path, registry: ToolRegistry):
    template_path = tmp_path / "template.md"
    template_path.write_text("Hello {name}!", encoding="utf-8")

    result = registry.execute_tool(
        "render_issue_template",
        {"template_path": str(template_path), "variables": {"name": "Copilot"}},
    )

    assert result.success
    assert result.error is None
    assert result.output == "Hello Copilot!"