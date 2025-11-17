from __future__ import annotations

from src.cli.commands.agent import _build_mission_evaluator
from src.orchestration.missions import Mission
from src.orchestration.types import (
    AgentStep,
    ExecutionContext,
    Thought,
    ThoughtType,
    ToolCall,
    ToolResult,
)


def _make_step(name: str, *, success: bool, error: str | None = None) -> AgentStep:
    return AgentStep(
        thought=Thought(
            content=f"Call {name}",
            type=ThoughtType.ACTION,
            tool_call=ToolCall(name=name, arguments={}),
        ),
        result=ToolResult(success=success, output=None if not success else {"ok": True}, error=error),
    )


def test_kb_extraction_requires_successful_copilot_assignment() -> None:
    mission = Mission(id="kb_extraction_full", goal="KB extraction", max_steps=5)
    evaluator = _build_mission_evaluator(mission)

    steps = [
        _make_step(
            "assign_issue_to_copilot",
            success=False,
            error="Insufficient permissions to assign Copilot.",
        ),
        _make_step("post_comment", success=True),
    ]

    result = evaluator.evaluate(mission, steps, ExecutionContext())

    assert not result.complete
    assert result.reason is not None
    assert "assign_issue_to_copilot" in result.reason
    assert "Insufficient permissions" in result.reason


def test_kb_extraction_allows_retry_until_assignment_succeeds() -> None:
    mission = Mission(id="kb_extraction_full", goal="KB extraction", max_steps=5)
    evaluator = _build_mission_evaluator(mission)

    steps = [
        _make_step(
            "assign_issue_to_copilot",
            success=False,
            error="Temporary API issue",
        ),
        _make_step("assign_issue_to_copilot", success=True),
        _make_step("post_comment", success=True),
    ]

    result = evaluator.evaluate(mission, steps, ExecutionContext())

    assert result.complete
    assert result.reason == "Successfully executed 2 action(s)"
