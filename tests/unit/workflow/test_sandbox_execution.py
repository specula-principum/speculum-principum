"""Tests for sandbox execution stubs."""

from src.workflow.execution_planner import WorkflowExecutionPlanner
from src.workflow.sandbox_execution import execute_workflow_in_sandbox, prepare_sandbox
from src.workflow.workflow_matcher import WorkflowPlan

from .conftest import make_candidate


def test_prepare_sandbox_returns_context(tmp_path, base_workflow_info):
    candidate = make_candidate(base_workflow_info, priority=5, conflict_suffix="example")
    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate,),
        selection_reason="single_match",
        selection_message="",
    )

    run_spec = WorkflowExecutionPlanner().build_execution_plan(plan).stages[0].workflows[0]
    context = prepare_sandbox(tmp_path, run_spec)

    assert context.workflow_name == candidate.name
    assert context.sandbox_root == tmp_path / run_spec.sandbox_slug
    assert context.workspace_path == context.sandbox_root


def test_execute_workflow_in_sandbox_returns_placeholder(tmp_path, base_workflow_info):
    candidate = make_candidate(base_workflow_info, priority=5, conflict_suffix="example")
    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate,),
        selection_reason="single_match",
        selection_message="",
    )

    run_spec = WorkflowExecutionPlanner().build_execution_plan(plan).stages[0].workflows[0]
    context = prepare_sandbox(tmp_path, run_spec)
    result = execute_workflow_in_sandbox(context)

    assert result.workflow_name == candidate.name
    assert result.status == "pending"
    assert result.sandbox_path == context.sandbox_root
    assert "placeholder" in (result.message or "")
