"""Tests for hierarchical planning capabilities."""

import pytest

from src.orchestration.planner import (
    Goal,
    HierarchicalPlan,
    HierarchicalPlanner,
    PlanIssue,
    PlanStep,
)
from src.orchestration.types import AgentState, ExecutionContext
from src.orchestration.missions import Mission


@pytest.fixture
def simple_mission():
    """Create a simple test mission."""
    return Mission(
        id="test_mission",
        goal="Test goal",
        max_steps=10,
        constraints=[],
        success_criteria=[],
    )


def test_goal_is_atomic():
    """Test that atomic goals (no subgoals) are identified correctly."""
    atomic_goal = Goal(
        description="Atomic goal",
        action=PlanStep(description="Do something", tool_name="test_tool", arguments={}),
    )
    assert atomic_goal.is_atomic()

    composite_goal = Goal(
        description="Composite goal",
        subgoals=(
            Goal(description="Sub 1"),
            Goal(description="Sub 2"),
        ),
    )
    assert not composite_goal.is_atomic()


def test_goal_to_steps_atomic():
    """Test converting atomic goal to steps."""
    step = PlanStep(description="Fetch data", tool_name="fetch", arguments={"id": 1})
    goal = Goal(description="Get data", action=step)

    steps = goal.to_steps()
    assert len(steps) == 1
    assert steps[0] == step


def test_goal_to_steps_hierarchical():
    """Test converting hierarchical goal structure to linear steps."""
    root_goal = Goal(
        description="Complete workflow",
        subgoals=(
            Goal(
                description="Step 1",
                action=PlanStep(description="First", tool_name="tool1", arguments={}),
            ),
            Goal(
                description="Step 2",
                action=PlanStep(description="Second", tool_name="tool2", arguments={}),
            ),
            Goal(
                description="Step 3",
                action=PlanStep(description="Third", tool_name="tool3", arguments={}),
            ),
        ),
    )

    steps = root_goal.to_steps()
    assert len(steps) == 3
    assert steps[0].tool_name == "tool1"
    assert steps[1].tool_name == "tool2"
    assert steps[2].tool_name == "tool3"


def test_goal_to_steps_nested():
    """Test converting deeply nested goal structure."""
    root_goal = Goal(
        description="Root",
        subgoals=(
            Goal(
                description="Branch 1",
                subgoals=(
                    Goal(
                        description="Leaf 1.1",
                        action=PlanStep(description="A", tool_name="toolA", arguments={}),
                    ),
                    Goal(
                        description="Leaf 1.2",
                        action=PlanStep(description="B", tool_name="toolB", arguments={}),
                    ),
                ),
            ),
            Goal(
                description="Branch 2",
                action=PlanStep(description="C", tool_name="toolC", arguments={}),
            ),
        ),
    )

    steps = root_goal.to_steps()
    assert len(steps) == 3
    assert steps[0].tool_name == "toolA"
    assert steps[1].tool_name == "toolB"
    assert steps[2].tool_name == "toolC"


def test_hierarchical_plan_validation_success():
    """Test that valid plans pass validation."""
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Main goal",
            subgoals=(
                Goal(
                    description="Sub 1",
                    action=PlanStep(description="Do A", tool_name="tool_a", arguments={}),
                ),
                Goal(
                    description="Sub 2",
                    action=PlanStep(description="Do B", tool_name="tool_b", arguments={}),
                ),
            ),
        )
    )

    issues = plan.validate(available_tools={"tool_a", "tool_b"})
    assert len(issues) == 0


def test_hierarchical_plan_validation_max_depth():
    """Test that plans exceeding max depth generate errors."""
    # Create a deeply nested structure
    deeply_nested = Goal(
        description="Level 0",
        subgoals=(
            Goal(
                description="Level 1",
                subgoals=(
                    Goal(
                        description="Level 2",
                        subgoals=(
                            Goal(
                                description="Level 3",
                                subgoals=(
                                    Goal(
                                        description="Level 4",
                                        action=PlanStep(description="Too deep", tool_name="tool"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    plan = HierarchicalPlan(root_goal=deeply_nested, max_depth=3)
    issues = plan.validate()

    errors = [issue for issue in issues if issue.severity == PlanIssue.Severity.ERROR]
    assert len(errors) > 0
    assert any("exceeds maximum depth" in err.message for err in errors)


def test_hierarchical_plan_validation_both_subgoals_and_action():
    """Test that goals with both subgoals and action generate errors."""
    invalid_goal = Goal(
        description="Invalid",
        subgoals=(Goal(description="Sub"),),
        action=PlanStep(description="Action", tool_name="tool"),
    )

    plan = HierarchicalPlan(root_goal=invalid_goal)
    issues = plan.validate()

    errors = [issue for issue in issues if issue.severity == PlanIssue.Severity.ERROR]
    assert len(errors) > 0
    assert any("has both subgoals and action" in err.message for err in errors)


def test_hierarchical_plan_validation_leaf_without_action():
    """Test that leaf goals without actions generate warnings."""
    incomplete_goal = Goal(
        description="Main",
        subgoals=(Goal(description="Leaf with no action"),),
    )

    plan = HierarchicalPlan(root_goal=incomplete_goal)
    issues = plan.validate()

    warnings = [issue for issue in issues if issue.severity == PlanIssue.Severity.WARNING]
    assert len(warnings) > 0
    assert any("has no associated action" in warn.message for warn in warnings)


def test_hierarchical_plan_validation_unavailable_tool():
    """Test that references to unavailable tools generate errors."""
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Use missing tool",
            action=PlanStep(description="Call it", tool_name="missing_tool", arguments={}),
        )
    )

    issues = plan.validate(available_tools={"tool_a", "tool_b"})

    errors = [issue for issue in issues if issue.severity == PlanIssue.Severity.ERROR]
    assert len(errors) > 0
    assert any("unavailable tool" in err.message for err in errors)


def test_hierarchical_plan_to_linear():
    """Test converting hierarchical plan to linear deterministic plan."""
    hierarchical_plan = HierarchicalPlan(
        root_goal=Goal(
            description="Complete workflow",
            subgoals=(
                Goal(
                    description="First",
                    action=PlanStep(description="Step 1", tool_name="tool1", arguments={"a": 1}),
                ),
                Goal(
                    description="Second",
                    action=PlanStep(description="Step 2", tool_name="tool2", arguments={"b": 2}),
                ),
            ),
        )
    )

    linear_plan = hierarchical_plan.to_linear_plan()

    assert len(linear_plan.steps) == 2
    assert linear_plan.steps[0].tool_name == "tool1"
    assert linear_plan.steps[1].tool_name == "tool2"


def test_hierarchical_planner_initialization_valid(simple_mission):
    """Test that valid hierarchical plans can initialize a planner."""
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Test",
            action=PlanStep(description="Do test", tool_name="test_tool", arguments={}),
        )
    )

    planner = HierarchicalPlanner(plan, available_tools={"test_tool"})
    assert planner is not None


def test_hierarchical_planner_initialization_invalid(simple_mission):
    """Test that invalid plans raise errors during planner initialization."""
    # Plan with unavailable tool
    invalid_plan = HierarchicalPlan(
        root_goal=Goal(
            description="Test",
            action=PlanStep(description="Bad", tool_name="missing_tool", arguments={}),
        )
    )

    with pytest.raises(ValueError, match="Invalid hierarchical plan"):
        HierarchicalPlanner(invalid_plan, available_tools={"other_tool"})


def test_hierarchical_planner_plan_next(simple_mission):
    """Test that hierarchical planner generates thoughts correctly."""
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Workflow",
            subgoals=(
                Goal(
                    description="First step",
                    action=PlanStep(
                        description="Get data", tool_name="get_data", arguments={"id": 123}
                    ),
                ),
                Goal(
                    description="Second step",
                    action=PlanStep(
                        description="Process data", tool_name="process", arguments={"mode": "fast"}
                    ),
                ),
            ),
        )
    )

    planner = HierarchicalPlanner(plan)
    state = AgentState(mission=simple_mission, context=ExecutionContext(), steps=())

    # Get first thought
    thought1 = planner.plan_next(state)
    assert thought1.tool_call is not None
    assert thought1.tool_call.name == "get_data"

    # Get second thought
    thought2 = planner.plan_next(state)
    assert thought2.tool_call is not None
    assert thought2.tool_call.name == "process"


def test_hierarchical_planner_get_current_goal(simple_mission):
    """Test retrieving the current goal being pursued."""
    root_goal = Goal(
        description="Main",
        subgoals=(
            Goal(description="Sub1", action=PlanStep(description="A", tool_name="tool1")),
        ),
    )

    plan = HierarchicalPlan(root_goal=root_goal)
    planner = HierarchicalPlanner(plan)

    current = planner.get_current_goal()
    assert current.description == "Main"


def test_hierarchical_planner_revise_plan(simple_mission):
    """Test plan revision with feedback."""
    plan = HierarchicalPlan(
        root_goal=Goal(description="Test", action=PlanStep(description="A", tool_name="tool")),
        allow_dynamic_revision=True,
    )

    planner = HierarchicalPlanner(plan)
    assert len(planner.get_revision_history()) == 0

    # Revise plan
    new_goal = Goal(description="Revised", action=PlanStep(description="B", tool_name="tool2"))
    planner.revise_plan("Need to handle edge case", [new_goal])

    history = planner.get_revision_history()
    assert len(history) == 1
    assert "Need to handle edge case" in history[0]


def test_hierarchical_planner_revise_plan_not_allowed(simple_mission):
    """Test that revision fails when not allowed."""
    plan = HierarchicalPlan(
        root_goal=Goal(description="Test", action=PlanStep(description="A", tool_name="tool")),
        allow_dynamic_revision=False,
    )

    planner = HierarchicalPlanner(plan)

    with pytest.raises(RuntimeError, match="does not allow dynamic revision"):
        planner.revise_plan("Attempted revision", [])


def test_plan_issue_representation():
    """Test string representation of plan issues."""
    error = PlanIssue(PlanIssue.Severity.ERROR, "Something wrong", step_index=3)
    assert "ERROR" in str(error)
    assert "step 3" in str(error)
    assert "Something wrong" in str(error)

    warning = PlanIssue(PlanIssue.Severity.WARNING, "Be careful")
    assert "WARNING" in str(warning)
    assert "Be careful" in str(warning)


def test_complex_hierarchical_plan():
    """Test a realistic complex hierarchical plan."""
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Triage and process issue",
            subgoals=(
                Goal(
                    description="Gather information",
                    subgoals=(
                        Goal(
                            description="Get issue details",
                            action=PlanStep(
                                description="Fetch issue from GitHub",
                                tool_name="get_issue_details",
                                arguments={"issue_number": 123},
                            ),
                        ),
                        Goal(
                            description="Get related issues",
                            action=PlanStep(
                                description="Search for similar issues",
                                tool_name="search_issues",
                                arguments={"query": "similar"},
                            ),
                        ),
                    ),
                ),
                Goal(
                    description="Analyze and classify",
                    subgoals=(
                        Goal(
                            description="Determine type",
                            action=PlanStep(
                                description="Classify issue type",
                                tool_name="classify",
                                arguments={},
                            ),
                        ),
                    ),
                ),
                Goal(
                    description="Take action",
                    action=PlanStep(
                        description="Apply appropriate label",
                        tool_name="add_label",
                        arguments={"label": "triage"},
                    ),
                ),
            ),
        ),
        max_depth=3,
    )

    # Validate
    issues = plan.validate(
        available_tools={"get_issue_details", "search_issues", "classify", "add_label"}
    )
    assert len([i for i in issues if i.severity == PlanIssue.Severity.ERROR]) == 0

    # Convert to linear
    linear = plan.to_linear_plan()
    assert len(linear.steps) == 4

    # Verify order
    assert linear.steps[0].tool_name == "get_issue_details"
    assert linear.steps[1].tool_name == "search_issues"
    assert linear.steps[2].tool_name == "classify"
    assert linear.steps[3].tool_name == "add_label"
