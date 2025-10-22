from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.github import assign_copilot


class _FakeHTTPResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_run_copilot_prompt_allows_default_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(assign_copilot.subprocess, "run", fake_run)

    assign_copilot.run_copilot_prompt(token="token", prompt="Do the thing", allowed_tools=None)

    command = captured["command"]
    assert "--allow-all-tools" not in command
    for tool in assign_copilot.DEFAULT_ALLOWED_COPILOT_TOOLS:
        assert ["--allow-tool", tool] in _pairwise(command)


def test_run_copilot_prompt_deduplicates_allowed_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(assign_copilot.subprocess, "run", fake_run)

    assign_copilot.run_copilot_prompt(
        token="token",
        prompt="Safety",
        allowed_tools=(
            "write",
            "write",
            "github-mcp-server(web_search)",
            "github-mcp-server(web_search)",
        ),
    )

    command = captured["command"]
    assert command.count("--allow-tool") == 2


def test_run_copilot_prompt_with_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(assign_copilot.subprocess, "run", fake_run)

    assign_copilot.run_copilot_prompt(token="token", prompt="Minimal", allowed_tools=())

    command = captured["command"]
    assert "--allow-tool" not in command


def _pairwise(items: list[str]) -> list[list[str]]:
    return [items[idx:idx + 2] for idx in range(len(items) - 1)]


def test_create_pull_request_detects_existing_before_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps([
        {
            "number": 112,
            "html_url": "https://example.test/pr/112",
            "state": "open",
        }
    ]).encode()

    def fake_urlopen(_req: object) -> _FakeHTTPResponse:
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(assign_copilot.request, "urlopen", fake_urlopen)

    def fake_run_gh_command(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("create should not be attempted when PR already exists")

    monkeypatch.setattr(assign_copilot, "run_gh_command", fake_run_gh_command)

    message = assign_copilot.create_pull_request_for_branch(
        token="token",
        repository="owner/repo",
        branch_name="copilot/issue-95-update-readme",
        api_url="https://api.github.com",
    )

    assert message == "Pull request already exists: #112 https://example.test/pr/112"


def test_create_pull_request_returns_existing_after_cli_error(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [
        json.dumps([]).encode(),
        json.dumps([
            {
                "number": 113,
                "html_url": "https://example.test/pr/113",
                "state": "open",
            }
        ]).encode(),
    ]

    def fake_urlopen(_req: object) -> _FakeHTTPResponse:
        if not payloads:
            raise AssertionError("unexpected extra pull request lookup")
        return _FakeHTTPResponse(payloads.pop(0))

    monkeypatch.setattr(assign_copilot.request, "urlopen", fake_urlopen)

    def fake_run_gh_command(*_args: object, **_kwargs: object) -> None:
        raise assign_copilot.GitHubIssueError(
            "Command 'gh pr create --head branch --repo owner/repo --fill' failed: "
            "a pull request for branch \"branch\" already exists: https://example.test/pr/113"
        )

    monkeypatch.setattr(assign_copilot, "run_gh_command", fake_run_gh_command)

    message = assign_copilot.create_pull_request_for_branch(
        token="token",
        repository="owner/repo",
        branch_name="branch",
        api_url="https://api.github.com",
    )

    assert message == "Pull request already exists: #113 https://example.test/pr/113"


def test_create_pull_request_reopens_closed_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps([
        {
            "number": 17,
            "html_url": "https://example.test/pr/17",
            "state": "closed",
        }
    ]).encode()

    def fake_urlopen(_req: object) -> _FakeHTTPResponse:
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(assign_copilot.request, "urlopen", fake_urlopen)

    captured: dict[str, list[str]] = {}

    def fake_run_gh_command(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(assign_copilot, "run_gh_command", fake_run_gh_command)

    message = assign_copilot.create_pull_request_for_branch(
        token="token",
        repository="owner/repo",
        branch_name="branch",
        api_url="https://api.github.com",
    )

    assert message == "Reopened existing pull request: #17 https://example.test/pr/17"
    assert captured["args"][:2] == ["pr", "reopen"]
