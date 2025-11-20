"""Integration test ensuring the agent executes a three-step reasoning loop."""

from __future__ import annotations

from typing import Mapping

from src.orchestration.agent import AgentRuntime, EvaluationResult
from src.orchestration.missions import Mission
from src.orchestration.safety import SafetyValidator
from src.orchestration.tools import ToolDefinition, ToolRegistry
from src.orchestration.types import ExecutionContext, MissionStatus, ToolResult
from tests.orchestration.utils import MockPlanner, PlanStep


def test_agent_executes_three_step_reasoning_loop():
    registry = ToolRegistry()
    counter: dict[str, int] = {"value": 0}

    def _record_step(args: Mapping[str, object]) -> ToolResult:
        counter["value"] += 1
        return ToolResult(success=True, output={"label": args["label"], "step": counter["value"]})

    registry.register_tool(
        ToolDefinition(
            name="record_step",
            description="Record that a reasoning step has executed successfully.",
            parameters={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Name of the reasoning step.",
                    }
                },
                "required": ["label"],
                "additionalProperties": False,
            },
            handler=_record_step,
        )
    )

    mission = Mission(
        id="three-step-demo",
        goal="Execute three safe reasoning steps.",
        max_steps=3,
        success_criteria=("Three successful steps recorded.",),
        allowed_tools=("record_step",),
    )

    planner = MockPlanner(
        steps=[
            PlanStep(description="Step one", tool_name="record_step", arguments={"label": "one"}),
            PlanStep(description="Step two", tool_name="record_step", arguments={"label": "two"}),
            PlanStep(description="Step three", tool_name="record_step", arguments={"label": "three"}),
        ]
    )

    class _ThreeStepEvaluator:
        def evaluate(self, mission, steps, context):  # type: ignore[override]
            del mission, context
            success_steps = [step for step in steps if step.result is not None and step.result.success]
            complete = len(success_steps) >= 3
            summary = "Three-step reasoning loop completed." if complete else None
            return EvaluationResult(complete=complete, reason=summary)

    runtime = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=SafetyValidator(),
        evaluator=_ThreeStepEvaluator(),
    )

    outcome = runtime.execute_mission(mission, ExecutionContext())

    assert outcome.status is MissionStatus.SUCCEEDED
    assert len(outcome.steps) == 3
    assert all(step.result is not None and step.result.success for step in outcome.steps)
    assert counter["value"] == 3
    assert outcome.summary == "Three-step reasoning loop completed."
