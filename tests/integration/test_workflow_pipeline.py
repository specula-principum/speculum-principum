"""Integration validation for the refactored workflow pipeline.

This test simulates the monitor → assign → process → Copilot flow using the
shared workflow state helpers and handoff builders introduced during the
refactor. It ensures label transitions, Markdown section updates, and Copilot
handoff metadata stay aligned with the target-state design without requiring
live API calls.
"""

from __future__ import annotations

import re
from typing import Optional

import pytest
from src.utils.markdown_sections import extract_section, upsert_section
from src.workflow.issue_handoff_builder import (
    DEFAULT_COPILOT_ASSIGNEE,
    IssueHandoffBuilder,
)
from src.workflow.workflow_matcher import WorkflowMatcher, WorkflowInfo
from src.workflow.workflow_state_manager import (
    TEMP_DISCOVERY_LABEL,
    SPECIALIST_LABEL_PREFIX,
    WORKFLOW_LABEL_PREFIX,
    WorkflowState,
    ensure_discovery_labels,
    get_state_from_labels,
    is_at_least_state,
    plan_state_transition,
)


def _slugify_label(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workflow"


def _determine_specialist_label(workflow: WorkflowInfo) -> Optional[str]:
    sources = []
    if isinstance(workflow.processing, dict):
        sources.extend(
            workflow.processing.get(key)
            for key in ("specialist_type", "specialist")
        )
    config = getattr(workflow, "config", None)
    if isinstance(config, dict):
        sources.append(config.get("specialist_type"))

    for specialist in sources:
        if isinstance(specialist, str) and specialist.strip():
            return specialist.strip().lower()
    return None


@pytest.mark.integration
def test_end_to_end_pipeline_dry_run() -> None:
    """Validate the unified pipeline transitions in a dry-run setting."""

    base_labels = {"site-monitor", "automated"}
    discovery_plan = ensure_discovery_labels(base_labels)
    discovery_labels = discovery_plan.final_labels

    assert TEMP_DISCOVERY_LABEL in discovery_labels
    assert WorkflowState.DISCOVERY.label in discovery_labels
    assert get_state_from_labels(discovery_labels) == WorkflowState.DISCOVERY

    matcher = WorkflowMatcher("docs/workflow/deliverables")
    available_workflows = matcher.get_available_workflows()
    assert available_workflows, "Expected at least one workflow definition for pipeline validation"
    workflow = available_workflows[0]

    workflow_slug = _slugify_label(workflow.name)
    specialist_core = _determine_specialist_label(workflow) or "intelligence-analyst"

    assignment_plan = plan_state_transition(
        discovery_labels,
        WorkflowState.ASSIGNED,
        ensure_labels=[workflow_slug],
        specialist_labels=[specialist_core],
        clear_temporary=True,
    )
    assignment_labels = assignment_plan.final_labels
    workflow_label = f"{WORKFLOW_LABEL_PREFIX}{workflow_slug}"
    specialist_label = f"{SPECIALIST_LABEL_PREFIX}{specialist_core}"

    assert WorkflowState.ASSIGNED.label in assignment_labels
    assert TEMP_DISCOVERY_LABEL not in assignment_labels
    assert workflow_label in assignment_labels
    assert specialist_label in assignment_labels
    assert is_at_least_state(assignment_labels, WorkflowState.ASSIGNED)

    issue_body = (
        "# Workflow Intake: Example\n\n"
        "## Discovery\n\n"
        "- **Site**: Example\n"
        "- **Title**: Example Title\n"
        "- **URL**: https://example.com\n"
        "- **Source**: example.com\n"
        "- **Detected**: 2025-10-01 00:00 UTC\n\n"
        "> Initial discovery snippet.\n\n"
        "## AI Assessment\n\n"
        "**Summary**\n"
        "- Immediate specialist review recommended.\n\n"
        "**Recommended Workflows**\n"
    f"- {workflow.name} — Confidence: 85% — Rationale: Matches topics cyber threat; indicators high-value target\n\n"
        "**Key Topics**\n"
        "- Topic Alpha\n"
        "- Topic Beta\n\n"
        "**Indicators**\n"
        "- Indicator One\n\n"
        "**Classification**\n"
        "- Urgency: Medium\n"
        "- Content Type: Research\n\n"
        "## Specialist Guidance\n\n"
        "_Pending unified issue processing. Guidance will be generated once the issue reaches `state::assigned`._\n\n"
        "## Copilot Assignment\n\n"
        "_Pending unified issue processing. Copilot will be assigned after specialist guidance is published._\n"
    )

    builder = IssueHandoffBuilder(
        config_path="config.yaml",
        workflow_directory="docs/workflow/deliverables",
    )

    payload = builder.build_handoff(
        issue_title="📄 Example Title",
        issue_url="https://example.com",
        issue_body=issue_body,
        workflow_info=workflow,
        labels=sorted(assignment_labels),
        created_files=["study/example/report.md"],
        metadata={"git_branch": "feature/refactor-dry-run"},
    )

    assert payload.copilot_assignee == DEFAULT_COPILOT_ASSIGNEE
    assert workflow.name in payload.summary_comment
    assert "### Persona:" in payload.specialist_guidance
    assert "**Assignee**" in payload.copilot_assignment

    updated_body = upsert_section(issue_body, "Specialist Guidance", payload.specialist_guidance.strip())
    updated_body = upsert_section(updated_body, "Copilot Assignment", payload.copilot_assignment.strip())

    specialist_section = extract_section(updated_body, "Specialist Guidance")
    copilot_section = extract_section(updated_body, "Copilot Assignment")

    assert specialist_section == payload.specialist_guidance.strip()
    assert copilot_section == payload.copilot_assignment.strip()

    copilot_plan = plan_state_transition(
        assignment_labels,
        WorkflowState.COPILOT_ASSIGNED,
        ensure_labels=[workflow_slug],
        specialist_labels=[specialist_core],
        clear_temporary=True,
    )
    copilot_labels = copilot_plan.final_labels
    assert WorkflowState.COPILOT_ASSIGNED.label in copilot_labels
    assert WorkflowState.ASSIGNED.label not in copilot_labels
    assert is_at_least_state(copilot_labels, WorkflowState.COPILOT_ASSIGNED)

    completion_plan = plan_state_transition(
        copilot_labels,
        WorkflowState.COMPLETED,
        ensure_labels=[workflow_slug],
        specialist_labels=[specialist_core],
        clear_temporary=True,
    )
    completion_labels = completion_plan.final_labels

    assert WorkflowState.COMPLETED.label in completion_labels
    assert is_at_least_state(completion_labels, WorkflowState.COMPLETED)
    assert get_state_from_labels(completion_labels) == WorkflowState.COMPLETED
    assert re.search(r"github-copilot\[bot\]", payload.summary_comment)
