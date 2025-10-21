from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.github import assign_copilot


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
