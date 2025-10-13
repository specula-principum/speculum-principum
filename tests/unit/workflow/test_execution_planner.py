"""Unit tests for the workflow execution planner."""

from typing import Dict, List, cast

import pytest

from src.workflow.execution_planner import (
    WorkflowExecutionPlanner,
    WorkflowPlanningError,
    build_plan_created_event,
)
from src.workflow.workflow_matcher import WorkflowCandidate, WorkflowPlan, WorkflowInfo

from .conftest import clone_workflow, make_candidate


@pytest.fixture
def base_workflow_info():
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


def make_candidate(info: WorkflowInfo, *, priority: int, conflict_suffix: str, dependencies=()):
    return WorkflowCandidate(
        workflow_info=info,
        priority=priority,
        conflict_keys=frozenset({f"deliverable:{conflict_suffix}"}),
        dependencies=tuple(dependencies),
    )


def test_single_workflow_creates_single_stage(base_workflow_info):
    candidate = make_candidate(base_workflow_info, priority=10, conflict_suffix="baseline")
    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate,),
        selection_reason="single_match",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    execution_plan = planner.build_execution_plan(plan)

    assert execution_plan.stage_count() == 1
    stage = execution_plan.stages[0]
    assert stage.run_mode == "sequential"
    assert stage.workflow_names() == (candidate.name,)


def test_multiple_workflows_parallel_stage(base_workflow_info):
    workflow_b = clone_workflow(base_workflow_info, name="Secondary Workflow")

    candidate_a = make_candidate(base_workflow_info, priority=5, conflict_suffix="a")
    candidate_b = make_candidate(workflow_b, priority=5, conflict_suffix="b")

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate_a, candidate_b),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    execution_plan = planner.build_execution_plan(plan)

    assert execution_plan.stage_count() == 1
    stage = execution_plan.stages[0]
    assert stage.is_parallel()
    assert set(stage.workflow_names()) == {candidate_a.name, candidate_b.name}


def test_conflicting_workflows_are_sequential(base_workflow_info):
    workflow_b = clone_workflow(base_workflow_info, name="Secondary Workflow")

    conflict_key = "deliverable:shared"
    candidate_a = WorkflowCandidate(
        workflow_info=base_workflow_info,
        priority=1,
        conflict_keys=frozenset({conflict_key}),
        dependencies=(),
    )
    candidate_b = WorkflowCandidate(
        workflow_info=workflow_b,
        priority=2,
        conflict_keys=frozenset({conflict_key}),
        dependencies=(),
    )

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate_a, candidate_b),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    execution_plan = planner.build_execution_plan(plan)

    assert execution_plan.stage_count() == 2
    assert all(stage.run_mode == "sequential" for stage in execution_plan.stages)
    assert execution_plan.stages[0].workflow_names() == (candidate_a.name,)
    assert execution_plan.stages[1].workflow_names() == (candidate_b.name,)


def test_dependencies_force_order(base_workflow_info):
    workflow_b = clone_workflow(base_workflow_info, name="Dependent Workflow")

    candidate_a = make_candidate(base_workflow_info, priority=1, conflict_suffix="a")
    candidate_b = make_candidate(workflow_b, priority=2, conflict_suffix="b", dependencies=(candidate_a.name,))

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate_a, candidate_b),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    execution_plan = planner.build_execution_plan(plan)

    assert execution_plan.stage_count() == 2
    assert execution_plan.stages[0].workflow_names() == (candidate_a.name,)
    assert execution_plan.stages[1].workflow_names() == (candidate_b.name,)


def test_unknown_dependency_raises(base_workflow_info):
    candidate = make_candidate(
        base_workflow_info,
        priority=1,
        conflict_suffix="a",
        dependencies=("missing",),
    )

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate,),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    with pytest.raises(WorkflowPlanningError):
        planner.build_execution_plan(plan)


def test_cycle_detection_raises(base_workflow_info):
    workflow_b = clone_workflow(base_workflow_info, name="Secondary Workflow")

    candidate_a = make_candidate(base_workflow_info, priority=1, conflict_suffix="a", dependencies=("Secondary Workflow",))
    candidate_b = make_candidate(workflow_b, priority=2, conflict_suffix="b", dependencies=("Baseline Workflow",))

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate_a, candidate_b),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    with pytest.raises(WorkflowPlanningError):
        planner.build_execution_plan(plan)


def test_max_parallel_limit(base_workflow_info):
    workflow_b = clone_workflow(base_workflow_info, name="Workflow B")
    workflow_c = clone_workflow(base_workflow_info, name="Workflow C")

    candidate_a = make_candidate(base_workflow_info, priority=1, conflict_suffix="a")
    candidate_b = make_candidate(workflow_b, priority=1, conflict_suffix="b")
    candidate_c = make_candidate(workflow_c, priority=1, conflict_suffix="c")

    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate_a, candidate_b, candidate_c),
        selection_reason="multiple_matches",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner(max_parallel_workflows=2)
    execution_plan = planner.build_execution_plan(plan)

    assert execution_plan.stage_count() == 2
    assert execution_plan.stages[0].is_parallel()
    assert len(execution_plan.stages[0].workflows) == 2
    assert execution_plan.stages[1].workflow_names() == (candidate_c.name,)


def test_plan_created_event_payload(base_workflow_info):
    candidate = make_candidate(base_workflow_info, priority=10, conflict_suffix="baseline")
    plan = WorkflowPlan(
        issue_labels=("site-monitor",),
        candidates=(candidate,),
        selection_reason="single_match",
        selection_message="",
    )

    planner = WorkflowExecutionPlanner()
    execution_plan = planner.build_execution_plan(plan)

    payload = build_plan_created_event(execution_plan, issue_number=123)
    assert payload["event_type"] == "multi_workflow.plan_created"
    assert payload["issue_number"] == 123
    assert payload["stage_count"] == execution_plan.stage_count()
    assert payload["workflow_count"] == execution_plan.workflow_count()
    stages_payload = cast(List[Dict[str, object]], payload["stages"])
    assert stages_payload[0]["workflows"] == list(execution_plan.stages[0].workflow_names())
