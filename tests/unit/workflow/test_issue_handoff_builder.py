from datetime import datetime

from src.workflow.issue_handoff_builder import IssueHandoffBuilder
from src.workflow.workflow_matcher import WorkflowInfo

def _make_workflow_info() -> WorkflowInfo:
    return WorkflowInfo(
        path="tests/fixtures/workflows/test.yaml",
        name="Test Workflow",
        description="Scenario-driven workflow for validation",
        version="1.0",
        trigger_labels=["test-workflow"],
        deliverables=[
            {
                "name": "deliverable",
                "title": "Primary Deliverable",
                "description": "Produce the primary analysis document.",
            }
        ],
        processing={},
        validation={},
        output={},
    )


def _build_issue_body() -> str:
    return (
        "# Workflow Intake: Example\n\n"
        "## Discovery\n\n"
        "- **URL**: https://example.com\n"
        "- **Detected**: 2025-09-30 12:00 UTC\n\n"
        "## AI Assessment\n\n"
        "**Summary**\n"
        "- Example summary insight.\n\n"
        "**Recommended Workflows**\n"
    "- Test Workflow — Confidence: 90% — Rationale: Matches topics market intel; indicators threat signal\n\n"
        "**Classification**\n"
        "- Urgency: Medium\n"
        "- Content Type: Research\n\n"
        "## Specialist Guidance\n\n"
        "(placeholder)\n\n"
        "## Copilot Assignment\n\n"
        "(placeholder)\n"
    )


def test_build_handoff_generates_sections():
    builder = IssueHandoffBuilder(
        config_path="config.yaml",
        workflow_directory="docs/workflow/deliverables",
    )
    workflow_info = _make_workflow_info()
    issue_body = _build_issue_body()

    payload = builder.build_handoff(
        issue_title="Example Issue",
        issue_url="https://github.com/example/repo/issues/1",
        issue_body=issue_body,
        workflow_info=workflow_info,
        labels=["site-monitor", "workflow::test-workflow"],
        created_files=["study/issue_1/primary_deliverable.md"],
        metadata={"git_branch": "feature/issue-1"},
    )

    assert payload.specialist_guidance.startswith("### Persona:")
    assert "### Key Insights from AI Assessment" in payload.specialist_guidance
    assert "### Required Actions" in payload.specialist_guidance
    assert "Recommended workflow: Test Workflow (90%; Matches topics market intel; indicators threat signal)" in payload.specialist_guidance
    assert "## Specialist Guidance" not in payload.specialist_guidance

    assert payload.copilot_assignment.startswith("**Assignee**: @github-copilot[bot]")
    assert "## Copilot Assignment" not in payload.copilot_assignment

    assert "Test Workflow" in payload.summary_comment
    # Ensure due timestamp is ISO-like
    datetime.fromisoformat(payload.copilot_due_iso)
