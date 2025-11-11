from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.cli.commands.agent import _prepare_agent_inputs


class _DummySearcher:
    def __init__(self, *, token: str, repository: str, api_url: str):
        self.token = token
        self.repository = repository
        self.api_url = api_url

    def search_unlabeled(self, *, limit: int, order: str):
        assert limit == 1
        assert order == "asc"
        return [SimpleNamespace(number=99, url="https://example.com/99")]


class _EmptySearcher:
    def __init__(self, *, token: str, repository: str, api_url: str):
        self.token = token
        self.repository = repository
        self.api_url = api_url

    def search_unlabeled(self, *, limit: int, order: str):
        del limit, order
        return []


def test_prepare_agent_inputs_coerces_numeric_string() -> None:
    inputs, skip, message = _prepare_agent_inputs({"issue_number": "7"})

    assert inputs["issue_number"] == 7
    assert skip is False
    assert message is None


def test_prepare_agent_inputs_auto_selects_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.cli.commands.agent.resolve_repository", lambda value: "octocat/hello-world")
    monkeypatch.setattr("src.cli.commands.agent.resolve_token", lambda value: "token")
    monkeypatch.setattr("src.cli.commands.agent.GitHubIssueSearcher", _DummySearcher)

    inputs, skip, message = _prepare_agent_inputs({"issue_number": "auto"})

    assert skip is False
    assert message is not None and "99" in message
    assert inputs["issue_number"] == 99
    assert inputs["auto_issue_selected"] is True
    assert inputs["auto_issue_url"] == "https://example.com/99"


def test_prepare_agent_inputs_auto_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.cli.commands.agent.resolve_repository", lambda value: "octocat/hello-world")
    monkeypatch.setattr("src.cli.commands.agent.resolve_token", lambda value: "token")
    monkeypatch.setattr("src.cli.commands.agent.GitHubIssueSearcher", _EmptySearcher)

    inputs, skip, message = _prepare_agent_inputs({"issue_number": "auto"})

    assert skip is True
    assert message == "No open unlabeled issues found; skipping mission."
    assert inputs["issue_number"] == "auto"


def test_prepare_agent_inputs_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": ""})

    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": 0})

    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": object()})
