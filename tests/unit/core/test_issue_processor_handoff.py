"""Unit tests for GitHub-integrated handoff behavior in the issue processor."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

from src.clients.github_issue_creator import GitHubIssueCreator
from src.core.issue_processor import (
    GitHubIntegratedIssueProcessor,
    IssueProcessingStatus,
    ProcessingResult,
)
from src.utils.markdown_sections import extract_section
from src.workflow.issue_handoff_builder import (
    DEFAULT_COPILOT_ASSIGNEE,
    IssueHandoffPayload,
)


class _FakeIssue:
    def __init__(self, body: str, labels: list[str]) -> None:
        self.number = 101
        self.title = "📄 Example Title"
        self.body = body
        self.html_url = "https://github.com/example/repo/issues/101"
        self.labels = [SimpleNamespace(name=label) for label in labels]
        self.assignees: list[SimpleNamespace] = []
        self._edit_calls: list[dict] = []

    def edit(self, **kwargs) -> None:  # pragma: no cover - exercised in tests
        self._edit_calls.append(kwargs)
        if "body" in kwargs:
            self.body = kwargs["body"]
        if "labels" in kwargs:
            self.labels = [SimpleNamespace(name=label) for label in kwargs["labels"]]

    @property
    def edit_calls(self) -> list[dict]:
        return self._edit_calls


class _FakeGitHub:
    def __init__(self, issue: _FakeIssue) -> None:
        self._issue = issue
        self.assign_calls: list[tuple[int, tuple[str, ...]]] = []

    def get_issue(self, issue_number: int) -> _FakeIssue:
        assert issue_number == self._issue.number
        return self._issue

    def assign_issue(self, issue_number: int, assignees: list[str]) -> None:
        self.assign_calls.append((issue_number, tuple(assignees)))


@pytest.mark.unit
def test_finalize_copilot_handoff_updates_issue_body_labels_and_assignment() -> None:
    existing_body = (
        "# Workflow Intake: Example\n\n"
        "## Discovery\n\n"
        "- **URL**: https://example.com\n\n"
        "## Specialist Guidance\n\n"
        "_Pending unified issue processing._\n\n"
        "## Copilot Assignment\n\n"
        "_Pending unified issue processing._\n"
    )
    initial_labels = [
        "site-monitor",
        "state::assigned",
        "monitor::triage",
        "specialist::intelligence-analyst",
    ]
    fake_issue = _FakeIssue(existing_body, initial_labels)

    payload = IssueHandoffPayload(
        specialist_guidance="### Persona: Intelligence Analyst\n- **Role**: Analyst",
        copilot_assignment="**Assignee**: @github-copilot[bot]\n**Due**: 2025-10-02T09:00:00Z",
        copilot_assignee=DEFAULT_COPILOT_ASSIGNEE,
        copilot_due_iso="2025-10-02T09:00:00Z",
        summary_comment="🚀 Unified handoff summary",
    )

    processor = object.__new__(GitHubIntegratedIssueProcessor)
    processor.logger = logging.getLogger("speculum.tests")
    processor.handoff_builder = SimpleNamespace(build_handoff=Mock(return_value=payload))
    processor.workflow_matcher = Mock()
    processor.workflow_matcher.get_workflow_by_name.return_value = SimpleNamespace(
        name="Example Workflow",
        deliverables=[{"title": "Executive Summary"}],
        processing={},
        description="Provide actionable insight.",
    )
    fake_github = _FakeGitHub(fake_issue)
    processor.github = cast(GitHubIssueCreator, fake_github)

    result = ProcessingResult(
        issue_number=101,
        status=IssueProcessingStatus.COMPLETED,
        workflow_name="Example Workflow",
        created_files=["study/example/report.md"],
    )

    returned_payload = GitHubIntegratedIssueProcessor._finalize_copilot_handoff(  # type: ignore[call-arg]
        processor,
        101,
        result,
    )

    assert returned_payload is payload

    assert fake_issue.edit_calls, "Expected issue.edit to be invoked"
    latest_edit = fake_issue.edit_calls[-1]
    assert "body" in latest_edit
    assert "labels" in latest_edit

    specialist_section = extract_section(fake_issue.body, "Specialist Guidance")
    copilot_section = extract_section(fake_issue.body, "Copilot Assignment")
    assert specialist_section == payload.specialist_guidance
    assert copilot_section == payload.copilot_assignment

    final_labels = sorted(label.name for label in fake_issue.labels)
    assert "state::copilot" in final_labels
    assert "monitor::triage" not in final_labels
    assert any(label.startswith("workflow::") for label in final_labels)

    assert fake_github.assign_calls == [(101, (DEFAULT_COPILOT_ASSIGNEE,))]
    assert result.specialist_guidance == payload.specialist_guidance
    assert result.copilot_assignment == payload.copilot_assignment