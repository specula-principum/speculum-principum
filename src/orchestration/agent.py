"""Agent runtime implementation for the Copilot orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .missions import Mission
from .safety import SafetyValidator
from .tools import ToolDefinition, ToolExecution, ToolRegistry, ToolRegistryError
from .types import (
    AgentState,
    AgentStep,
    ExecutionContext,
    MissionOutcome,
    MissionStatus,
    Thought,
    ThoughtType,
    ToolCall,
    ToolResult,
)
from .planner import Planner



@dataclass(frozen=True)
class EvaluationResult:
    """Outcome returned by the mission evaluator."""

    complete: bool
    reason: str | None = None


class MissionEvaluator(Protocol):
    """Interface for mission completion evaluation."""

    def evaluate(self, mission: Mission, steps: Sequence[AgentStep], context: ExecutionContext) -> EvaluationResult:
        """Assess progress and determine if the mission is complete."""
        raise NotImplementedError


class AgentRuntimeError(RuntimeError):
    """Raised when the agent encounters an unrecoverable error."""


class AgentRuntime:
    """Coordinates planner reasoning, tool execution, and safety checks."""

    def __init__(
        self,
        *,
        planner: Planner,
        tools: ToolRegistry,
        safety: SafetyValidator,
        evaluator: MissionEvaluator,
    ) -> None:
        self._planner = planner
        self._tools = tools
        self._safety = safety
        self._evaluator = evaluator

    def execute_mission(self, mission: Mission, context: ExecutionContext) -> MissionOutcome:
        """Run the agent loop until the mission completes or fails."""

        state = AgentState(mission=mission, context=context)
        steps: list[AgentStep] = []

        for _ in range(mission.max_steps):
            thought = self._planner.plan_next(state)
            if thought.type is ThoughtType.FINISH:
                return self._complete_with_evaluation(mission, steps, context, thought)
            if thought.tool_call is None:
                raise AgentRuntimeError("Planner produced an action thought without a tool call.")
            step, blocked_reason = self._execute_tool_thought(mission, context, thought)
            steps.append(step)
            if blocked_reason is not None:
                summary = blocked_reason or "Action blocked by safety validator."
                return MissionOutcome(status=MissionStatus.BLOCKED, steps=tuple(steps), summary=summary)
            state = state.with_step(step)
            # NOTE: Mid-loop evaluation removed to support autonomous LLM planners.
            # The planner decides when to finish via FINISH thoughts. The evaluator
            # only validates success AFTER the planner indicates completion.

        evaluation = self._evaluator.evaluate(mission, steps, context)
        status = MissionStatus.SUCCEEDED if evaluation.complete else MissionStatus.FAILED
        summary = evaluation.reason or "Mission reached maximum allowed steps."
        return MissionOutcome(status=status, steps=tuple(steps), summary=summary)

    def _complete_with_evaluation(
        self,
        mission: Mission,
        steps: Sequence[AgentStep],
        context: ExecutionContext,
        thought: Thought,
    ) -> MissionOutcome:
        evaluation = self._evaluator.evaluate(mission, steps, context)
        status = MissionStatus.SUCCEEDED if evaluation.complete else MissionStatus.FAILED
        summary = evaluation.reason or thought.content
        return MissionOutcome(status=status, steps=tuple(steps), summary=summary)

    def _execute_tool_thought(
        self,
        mission: Mission,
        context: ExecutionContext,
        thought: Thought,
    ) -> tuple[AgentStep, str | None]:
        tool_call = thought.tool_call
        if tool_call is None:  # pragma: no cover - defensive guard
            raise AgentRuntimeError("Tool execution requested without tool call data.")
        if not mission.is_tool_allowed(tool_call.name):
            raise AgentRuntimeError(f"Tool '{tool_call.name}' is not permitted for mission '{mission.id}'.")
        decision = self._safety.check_action(tool_call, mission, context)
        if not decision.approved:
            return self._blocked_step(thought, decision.reason), decision.reason
        definition = self._tools.get_tool(tool_call.name)
        result = self._execute_tool_definition(definition, tool_call)
        execution = ToolExecution(
            definition=definition,
            arguments=tool_call.arguments,
            result=result,
            risk=decision.risk,
        )
        self._safety.audit_log(execution)
        return AgentStep(thought=thought, result=result), None

    def _execute_tool_definition(self, definition: ToolDefinition, tool_call: ToolCall) -> ToolResult:
        try:
            return self._tools.execute_definition(definition, tool_call.arguments)
        except ToolRegistryError as exc:  # pragma: no cover - bubbled failure
            return ToolResult(success=False, output=None, error=str(exc))

    def _blocked_step(self, thought: Thought, reason: str | None) -> AgentStep:
        summary = reason or "Action blocked by safety validator."
        result = ToolResult(success=False, output=None, error=summary)
        return AgentStep(thought=thought, result=result)
