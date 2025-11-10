"""Mission evaluation utilities for the Copilot agent runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Mapping, Sequence

from .types import AgentStep, ExecutionContext

if TYPE_CHECKING:  # pragma: no cover - type checking forward declarations
    from .agent import EvaluationResult, MissionEvaluator
    from .missions import Mission


class SimpleMissionEvaluator:
    """Evaluates success using a predicate and optional summary builder."""

    def __init__(
        self,
        *,
        success_condition: Callable[[Sequence[AgentStep]], bool],
        summary_builder: Callable[[Sequence[AgentStep], ExecutionContext], str | None] | None = None,
        failure_reason: str | None = None,
    ) -> None:
        self._success_condition = success_condition
        self._summary_builder = summary_builder
        self._failure_reason = failure_reason or "Mission did not meet success criteria."

    def evaluate(self, mission, steps, context):  # type: ignore[override]
        from .agent import EvaluationResult  # Imported lazily to avoid circular dependency

        del mission  # Mission metadata not needed for simple predicate evaluation

        complete = self._success_condition(steps)
        summary = None
        if complete and self._summary_builder is not None:
            summary = self._summary_builder(steps, context)
        if not complete:
            summary = self._failure_reason
        return EvaluationResult(complete=complete, reason=summary)


def successful_tool_execution(step: AgentStep) -> bool:
    """Return True if the agent step contains a successful tool result."""

    return step.result is not None and step.result.success


class TriageMissionEvaluator:
    """Evaluator that ensures a triage recommendation is present."""

    def __init__(
        self,
        *,
        insights_key: str = "latest_issue_insights",
        failure_reason: str | None = None,
    ) -> None:
        self._insights_key = insights_key
        self._failure_reason = failure_reason or "Issue insights missing; unable to satisfy mission goals."

    def evaluate(self, mission, steps, context):  # type: ignore[override]
        from .agent import EvaluationResult  # Imported lazily to avoid circular dependency

        del mission  # Mission metadata not required for evaluation

        if not any(successful_tool_execution(step) for step in steps):
            return EvaluationResult(complete=False, reason=self._failure_reason)

        insights = _lookup_insights(context.inputs, self._insights_key)
        if insights is None:
            return EvaluationResult(complete=False, reason=self._failure_reason)

        recommendation = getattr(insights, "recommendation", None)
        summary_obj = getattr(insights, "summary", None)
        if recommendation is None or summary_obj is None:
            return EvaluationResult(
                complete=False,
                reason="Triage recommendation not available; transcript would be incomplete.",
            )

        summary_text = summary_obj.as_text()
        recommendation_text = recommendation.as_text()
        combined = f"{summary_text}\n{recommendation_text}"
        return EvaluationResult(complete=True, reason=combined)


def _lookup_insights(inputs: Mapping[str, object], key: str):
    value = inputs.get(key)
    return value