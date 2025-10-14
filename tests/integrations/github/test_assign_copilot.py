from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.github.assign_copilot import (  # noqa: E402
    CopilotHandoffResult,
    IssueDetails,
    assign_issues_to_copilot,
    compose_agent_prompt,
    generate_branch_name,
    handoff_issue_to_copilot,
)


def test_generate_branch_name_slugifies_title() -> None:
    branch = generate_branch_name(12, "Fix: Spaces & Accents à la carte")
    assert branch.startswith("copilot/issue-12-fix-spaces-accents-a-la-carte")
    assert " " not in branch


def test_compose_agent_prompt_includes_context() -> None:
    issue = IssueDetails(
        number=7,
        title="Improve logging",
        body="Please improve logging details.\n",
        url="https://example.test/7",
        labels=("ready-for-copilot", "enhancement"),
    )

    prompt = compose_agent_prompt(issue, "copilot/issue-7-improve-logging", "Focus on auth flows.")

    assert "Improve logging" in prompt
    assert "Issue URL" in prompt
    assert "ready-for-copilot" in prompt
    assert "Focus on auth flows" in prompt


def test_handoff_issue_to_copilot_runs_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_fetch_issue_details(**kwargs: Any) -> IssueDetails:
        calls.setdefault("fetch", []).append(kwargs)
        return IssueDetails(
            number=kwargs["issue_number"],
            title="Refactor subsystem",
            body="Detailed steps",
            url="https://example.test/1",
            labels=("ready-for-copilot",),
        )

    def fake_create_branch_for_issue(**kwargs: Any) -> None:
        calls.setdefault("branch", []).append(kwargs)

    def fake_create_agent_task(**kwargs: Any) -> str:
        calls.setdefault("agent", []).append(kwargs)
        return "https://github.com/org/repo/actions/runs/1"

    def fake_remove_issue_label(**kwargs: Any) -> bool:
        calls.setdefault("remove", []).append(kwargs)
        return True

    monkeypatch.setattr(
        "src.integrations.github.assign_copilot.fetch_issue_details",
        fake_fetch_issue_details,
    )
    monkeypatch.setattr(
        "src.integrations.github.assign_copilot.create_branch_for_issue",
        fake_create_branch_for_issue,
    )
    monkeypatch.setattr(
        "src.integrations.github.assign_copilot.create_agent_task",
        fake_create_agent_task,
    )
    monkeypatch.setattr(
        "src.integrations.github.assign_copilot.remove_issue_label",
        fake_remove_issue_label,
    )

    outcome = handoff_issue_to_copilot(
        token="token",
        repository="octocat/hello-world",
        issue_number=1,
        label="ready-for-copilot",
        api_url="https://api.example.test",
        base_branch="main",
        extra_instructions="Please keep changes minimal.",
    )

    assert isinstance(outcome, CopilotHandoffResult)
    assert outcome.issue_number == 1
    assert outcome.branch_name.startswith("copilot/issue-1-refactor-subsystem")
    assert outcome.agent_output == "https://github.com/org/repo/actions/runs/1"
    assert outcome.label_removed is True
    assert calls["branch"][0]["base_branch"] == "main"
    assert calls["agent"][0]["base_branch"] == "main"


def test_assign_issues_to_copilot_processes_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    handoff_calls: list[int] = []

    def fake_handoff_issue_to_copilot(**kwargs: Any) -> CopilotHandoffResult:
        handoff_calls.append(kwargs["issue_number"])
        return CopilotHandoffResult(
            issue_number=kwargs["issue_number"],
            branch_name=f"copilot/issue-{kwargs['issue_number']}",
            agent_output="ok",
            label_removed=True,
        )

    monkeypatch.setattr(
        "src.integrations.github.assign_copilot.handoff_issue_to_copilot",
        fake_handoff_issue_to_copilot,
    )

    outcomes = assign_issues_to_copilot(
        token="token",
        repository="octocat/hello-world",
        issue_numbers=[10, 11],
        label="ready-for-copilot",
    )

    assert [out.issue_number for out in outcomes] == [10, 11]
    assert handoff_calls == [10, 11]
