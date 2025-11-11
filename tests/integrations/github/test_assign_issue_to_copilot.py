from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.integrations.github.issues import (
    GitHubIssueError,
    assign_issue_to_copilot,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


def test_assign_issue_to_copilot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[SimpleNamespace] = []

    def fake_urlopen(req):  # type: ignore[no-untyped-def]
        body = json.loads(req.data.decode("utf-8"))
        calls.append(SimpleNamespace(url=req.full_url, payload=body))

        if "suggestedActors" in body.get("query", ""):
            return _FakeResponse(
                {
                    "data": {
                        "repository": {
                            "issue": {"id": "ISSUE_ID"},
                            "suggestedActors": {
                                "nodes": [
                                    {
                                        "login": "copilot-swe-agent",
                                        "id": "BOT_ID",
                                    }
                                ]
                            },
                        }
                    }
                }
            )
        assert body["variables"]["assignableId"] == "ISSUE_ID"
        assert body["variables"]["actorIds"] == ["BOT_ID"]
        return _FakeResponse(
            {
                "data": {
                    "replaceActorsForAssignable": {
                        "assignable": {"id": "ISSUE_ID"}
                    }
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assign_issue_to_copilot(token="token", repository="octo-org/octo-repo", issue_number=42)

    assert len(calls) == 2
    assert calls[0].url == "https://api.github.com/graphql"
    assert "suggestedActors" in calls[0].payload["query"]
    assert calls[1].url == "https://api.github.com/graphql"
    assert "replaceActorsForAssignable" in calls[1].payload["query"]


def test_assign_issue_to_copilot_missing_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req):  # type: ignore[no-untyped-def]
        body = json.loads(req.data.decode("utf-8"))
        if "suggestedActors" in body.get("query", ""):
            return _FakeResponse(
                {
                    "data": {
                        "repository": {
                            "issue": {"id": "ISSUE_ID"},
                            "suggestedActors": {"nodes": []},
                        }
                    }
                }
            )
        pytest.fail("Secondary mutation should not be called when agent is missing")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(GitHubIssueError, match="Copilot coding agent is not enabled"):
        assign_issue_to_copilot(token="token", repository="octo-org/octo-repo", issue_number=1)


def test_assign_issue_to_copilot_ghe_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []

    def fake_urlopen(req):  # type: ignore[no-untyped-def]
        seen_urls.append(req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        if "suggestedActors" in body.get("query", ""):
            return _FakeResponse(
                {
                    "data": {
                        "repository": {
                            "issue": {"id": "ISSUE_ID"},
                            "suggestedActors": {
                                "nodes": [
                                    {
                                        "login": "copilot-swe-agent",
                                        "id": "BOT_ID",
                                    }
                                ]
                            },
                        }
                    }
                }
            )
        return _FakeResponse(
            {
                "data": {
                    "replaceActorsForAssignable": {
                        "assignable": {"id": "ISSUE_ID"}
                    }
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assign_issue_to_copilot(
        token="token",
        repository="octo-org/octo-repo",
        issue_number=7,
        api_url="https://ghe.example.com/api/v3",
    )

    assert all(url == "https://ghe.example.com/api/graphql" for url in seen_urls)
