"""Tests for the Copilot agent runtime core loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import pytest

from src.orchestration.agent import AgentRuntime, AgentRuntimeError, EvaluationResult
from src.orchestration.missions import Mission
from src.orchestration.safety import ActionRisk, ApprovalDecision, SafetyValidator
from src.orchestration.tools import ToolDefinition, ToolRegistry
from src.orchestration.types import AgentStep, ExecutionContext, MissionStatus
from tests.orchestration.utils import MockPlanner, PlanStep


@dataclass
class PredicateEvaluator:
    """Evaluator that marks completion when predicate returns true."""

    predicate: Callable[[Sequence[AgentStep]], bool]

    def evaluate(self, mission: Mission, steps: Sequence[AgentStep], context: ExecutionContext):  # type: ignore[override]
        del mission, context
        complete = self.predicate(steps)
        reason = "Goal satisfied" if complete else None
        return EvaluationResult(complete=complete, reason=reason)


def make_echo_tool() -> ToolDefinition:
    return ToolDefinition(
        name="echo",
        description="Return the provided message for validation.",
        parameters={"type": "object", "properties": {"message": {"type": "string"}}},
        handler=lambda args: args["message"],
    )


def make_requires_integer_tool() -> ToolDefinition:
    return ToolDefinition(
        name="needs_int",
        description="Return the provided integer value.",
        parameters={
            "type": "object",
            "properties": {
                "value": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Positive integer payload",
                }
            },
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=lambda args: args["value"],
    )


def test_agent_runtime_executes_tool_and_succeeds():
    registry = ToolRegistry()
    registry.register_tool(make_echo_tool())

    mission = Mission(
        id="demo",
        goal="Echo a message",
        max_steps=3,
        allowed_tools=("echo",),
    )

    planner = MockPlanner(
        steps=[
            PlanStep(
                description="Call echo",
                tool_name="echo",
                arguments={"message": "done"},
            )
        ],
        default_finish="Stop",
    )

    evaluator = PredicateEvaluator(
        predicate=lambda steps: bool(steps) and steps[-1].result is not None and steps[-1].result.output == "done",
    )

    safety = SafetyValidator()
    runtime = AgentRuntime(planner=planner, tools=registry, safety=safety, evaluator=evaluator)

    outcome = runtime.execute_mission(mission, ExecutionContext())

    assert outcome.status is MissionStatus.SUCCEEDED
    assert outcome.summary == "Goal satisfied"
    assert len(outcome.steps) == 1
    result = outcome.steps[0].result
    assert result is not None and result.success and result.output == "done"
    assert len(tuple(safety.iter_audit_log())) == 1


def test_agent_runtime_rejects_disallowed_tool():
    registry = ToolRegistry()
    registry.register_tool(make_echo_tool())

    mission = Mission(
        id="restricted",
        goal="Do not allow echo",
        max_steps=2,
        allowed_tools=("other",),
    )

    planner = MockPlanner(
        steps=[
            PlanStep(
                description="Try echo",
                tool_name="echo",
                arguments={},
            )
        ],
    )

    evaluator = PredicateEvaluator(predicate=lambda steps: bool(steps))
    safety = SafetyValidator()
    runtime = AgentRuntime(planner=planner, tools=registry, safety=safety, evaluator=evaluator)

    with pytest.raises(AgentRuntimeError):
        runtime.execute_mission(mission, ExecutionContext())


def test_agent_runtime_blocks_when_safety_denies():
    registry = ToolRegistry()
    registry.register_tool(make_echo_tool())

    mission = Mission(
        id="needs-approval",
        goal="Echo requires review",
        max_steps=2,
        allowed_tools=("echo",),
    )

    def deny_callback(tool_call, mission, context, risk):  # type: ignore[unused-argument]
        return ApprovalDecision.denied(risk=risk, reason="Approval required")

    safety = SafetyValidator(
        risk_overrides={"echo": ActionRisk.REVIEW},
        approval_callback=deny_callback,
    )

    planner = MockPlanner(
        steps=[
            PlanStep(
                description="Call echo",
                tool_name="echo",
                arguments={"message": "hi"},
            )
        ],
    )

    evaluator = PredicateEvaluator(predicate=lambda steps: bool(steps))
    runtime = AgentRuntime(planner=planner, tools=registry, safety=safety, evaluator=evaluator)

    outcome = runtime.execute_mission(mission, ExecutionContext())

    assert outcome.status is MissionStatus.BLOCKED
    assert outcome.summary == "Approval required"
    assert len(outcome.steps) == 1
    step = outcome.steps[0]
    assert step.result is not None and not step.result.success
    assert "Approval required" in (step.result.error or "")
    assert len(tuple(safety.iter_audit_log())) == 0


def test_agent_runtime_surfaces_validation_errors():
    registry = ToolRegistry()
    registry.register_tool(make_requires_integer_tool())

    mission = Mission(
        id="invalid-args",
        goal="Invoke tool with invalid arguments",
        max_steps=1,
        allowed_tools=("needs_int",),
    )

    planner = MockPlanner(
        steps=[
            PlanStep(
                description="Call needs_int with a non-integer value",
                tool_name="needs_int",
                arguments={"value": "oops"},
            )
        ],
    )

    evaluator = PredicateEvaluator(
        predicate=lambda steps: bool(steps) and steps[-1].result is not None and steps[-1].result.success,
    )

    safety = SafetyValidator()
    runtime = AgentRuntime(planner=planner, tools=registry, safety=safety, evaluator=evaluator)

    outcome = runtime.execute_mission(mission, ExecutionContext())

    assert outcome.status is MissionStatus.FAILED
    assert len(outcome.steps) == 1
    result = outcome.steps[0].result
    assert result is not None
    assert not result.success
    assert result.error is not None
    assert "Argument validation failed for 'needs_int'" in result.error
