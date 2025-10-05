"""Tests for preview generation in the GitHub-integrated issue processor."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.core.issue_processor import (
    GitHubIntegratedIssueProcessor,
    IssueData,
    IssueProcessingStatus,
    ProcessingResult,
)
from src.workflow.issue_handoff_builder import (
    DEFAULT_COPILOT_ASSIGNEE,
    IssueHandoffBuilder,
    IssueHandoffPayload,
)


@pytest.mark.unit
def test_generate_preview_result_returns_rendered_sections() -> None:
    processor = object.__new__(GitHubIntegratedIssueProcessor)
    processor.logger = logging.getLogger("speculum.tests")
    processor.git_manager = None

    workflow_info = SimpleNamespace(
        name="Example Workflow",
        description="Provide actionable insight.",
        deliverables=[{"filename": "reports/example-{issue_number}.md"}],
        processing={},
        validation={},
        output={},
    )

    payload = IssueHandoffPayload(
        specialist_guidance="### Persona: Intelligence Analyst\n- **Role**: Analyst",
        copilot_assignment="**Assignee**: @github-copilot[bot]",
        copilot_assignee=DEFAULT_COPILOT_ASSIGNEE,
        copilot_due_iso="2025-10-02T09:00:00Z",
        summary_comment="🚀 Unified handoff summary",
    )

    handoff_builder = Mock(spec=IssueHandoffBuilder)
    handoff_builder.build_handoff.return_value = payload
    processor.handoff_builder = handoff_builder
    processor.workflow_matcher = Mock()
    processor.workflow_matcher.get_available_workflows.return_value = []
    processor.workflow_matcher.get_best_workflow_match.return_value = (workflow_info, "matched")

    timestamp_stub = datetime(2025, 10, 1, 12, 0, tzinfo=timezone.utc)
    issue_data = IssueData(
        number=101,
        title="Example Issue",
        body="## AI Assessment\n- **Summary**: Example\n",
        labels=["site-monitor", "workflow::example", "state::assigned"],
        assignees=[],
        created_at=timestamp_stub,
        updated_at=timestamp_stub,
        url="https://github.com/example/repo/issues/101",
    )

    result = processor.generate_preview_result(issue_data)

    assert result.status == IssueProcessingStatus.PREVIEW
    assert result.workflow_name == "Example Workflow"
    assert result.created_files
    assert result.copilot_assignee == DEFAULT_COPILOT_ASSIGNEE
    assert result.copilot_due_at == "2025-10-02T09:00:00Z"
    assert result.specialist_guidance == payload.specialist_guidance
    assert result.copilot_assignment == payload.copilot_assignment
    assert result.handoff_summary == payload.summary_comment
