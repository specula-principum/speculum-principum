"""Shared fixtures and helpers for workflow unit tests."""

from dataclasses import replace
from typing import Iterable

import pytest

from src.workflow.workflow_matcher import WorkflowCandidate, WorkflowInfo


@pytest.fixture
def base_workflow_info() -> WorkflowInfo:
    return WorkflowInfo(
        path="test.yaml",
        name="Baseline Workflow",
        description="",
        version="1.0.0",
        trigger_labels=["site-monitor"],
        deliverables=[{"name": "summary", "template": "summary.md"}],
        processing={},
        validation={},
        output={"folder_structure": "study/{issue_number}/baseline"},
    )


def clone_workflow(info: WorkflowInfo, *, name: str) -> WorkflowInfo:
    return replace(info, name=name)


def make_candidate(
    info: WorkflowInfo,
    *,
    priority: int,
    conflict_suffix: str,
    dependencies: Iterable[str] = (),
) -> WorkflowCandidate:
    return WorkflowCandidate(
        workflow_info=info,
        priority=priority,
        conflict_keys=frozenset({f"deliverable:{conflict_suffix}"}),
        dependencies=tuple(dependencies),
    )
