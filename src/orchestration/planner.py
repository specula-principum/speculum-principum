"""Planner implementations and configuration helpers for the agent runtime."""

from __future__ import annotations

from enum import Enum

from .types import AgentState, Thought


class PlanIssue:
    """Validation issue found in a plan."""

    class Severity(Enum):
        """Severity level of a plan issue."""

        WARNING = "warning"
        ERROR = "error"

    def __init__(self, severity: Severity, message: str, step_index: int | None = None) -> None:
        self.severity = severity
        self.message = message
        self.step_index = step_index

    def __repr__(self) -> str:
        location = f" (step {self.step_index})" if self.step_index is not None else ""
        return f"{self.severity.value.upper()}{location}: {self.message}"


class Planner:
    """Interface for generating agent thoughts based on mission state."""

    def plan_next(self, state: AgentState) -> Thought:  # pragma: no cover - interface
        """Produce the next thought for the agent to execute."""
        raise NotImplementedError



