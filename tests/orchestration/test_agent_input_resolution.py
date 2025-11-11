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

class _LabelFilterSearcher:
    last_instance: _LabelFilterSearcher | None = None

    def __init__(self, *, token: str, repository: str, api_url: str):
        self.token = token
        self.repository = repository
        self.api_url = api_url
        self.required: list[str] | None = None
        self.excluded: list[str] | None = None
        type(self).last_instance = self

    def search_with_label_filters(
        self,
        *,
        required_labels,
        excluded_labels,
        limit: int,
        sort,
        order: str,
    ):
        assert limit == 1
        assert order == "asc"
        assert sort == "created"
        self.required = list(required_labels or [])
        self.excluded = list(excluded_labels or [])
        return [SimpleNamespace(number=123, url="https://example.com/123")]

    def search_unlabeled(self, *, limit: int, order: str):
        raise AssertionError("search_unlabeled should not be called when labels are provided")


class _EmptyLabelFilterSearcher(_LabelFilterSearcher):
    def search_with_label_filters(
        self,
        *,
        required_labels,
        excluded_labels,
        limit: int,
        sort,
        order: str,
    ):
        super().search_with_label_filters(
            required_labels=required_labels,
            excluded_labels=excluded_labels,
            limit=limit,
            sort=sort,
            order=order,
        )
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


def test_prepare_agent_inputs_auto_with_required_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    _LabelFilterSearcher.last_instance = None
    monkeypatch.setattr("src.cli.commands.agent.resolve_repository", lambda value: "octocat/hello-world")
    monkeypatch.setattr("src.cli.commands.agent.resolve_token", lambda value: "token")
    monkeypatch.setattr("src.cli.commands.agent.GitHubIssueSearcher", _LabelFilterSearcher)

    inputs, skip, message = _prepare_agent_inputs({
        "issue_number": "auto",
        "required_labels": "kb-extraction, ready-for-copilot",
        "exclude_labels": "kb-extracted",
    })

    searcher = _LabelFilterSearcher.last_instance
    assert searcher is not None
    assert searcher.required == ["kb-extraction", "ready-for-copilot"]
    assert searcher.excluded == ["kb-extracted"]

    assert skip is False
    assert inputs["issue_number"] == 123
    assert inputs["required_labels"] == ["kb-extraction", "ready-for-copilot"]
    assert inputs["exclude_labels"] == ["kb-extracted"]
    assert message is not None and "matching labels" in message


def test_prepare_agent_inputs_auto_with_required_labels_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _EmptyLabelFilterSearcher.last_instance = None
    monkeypatch.setattr("src.cli.commands.agent.resolve_repository", lambda value: "octocat/hello-world")
    monkeypatch.setattr("src.cli.commands.agent.resolve_token", lambda value: "token")
    monkeypatch.setattr("src.cli.commands.agent.GitHubIssueSearcher", _EmptyLabelFilterSearcher)

    inputs, skip, message = _prepare_agent_inputs({
        "issue_number": "auto",
        "required_labels": ["kb-extraction", "ready-for-copilot"],
        "exclude_labels": ["kb-extracted"],
    })

    assert skip is True
    assert message == "No open issues found with required labels (kb-extraction, ready-for-copilot); skipping mission."
    assert inputs["issue_number"] == "auto"
    assert inputs["required_labels"] == ["kb-extraction", "ready-for-copilot"]
    assert inputs["exclude_labels"] == ["kb-extracted"]


def test_prepare_agent_inputs_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": ""})

    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": 0})

    with pytest.raises(ValueError):
        _prepare_agent_inputs({"issue_number": object()})
