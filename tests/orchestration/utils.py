from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.orchestration.planner import Planner
from src.orchestration.types import AgentState, Thought, ThoughtType, ToolCall

@dataclass(frozen=True)
class PlanStep:
    """Represents a deterministic step the agent should take."""

    description: str
    tool_name: str | None = None
    arguments: Mapping[str, object] | None = None
    finish_summary: str | None = None

    def to_thought(self) -> Thought:
        """Convert the plan step into an executable thought."""

        if self.tool_name is None:
            summary = self.finish_summary or self.description
            return Thought(content=summary, type=ThoughtType.FINISH)
        return Thought(
            content=self.description,
            type=ThoughtType.ACTION,
            tool_call=ToolCall(name=self.tool_name, arguments=dict(self.arguments or {})),
        )


class MockPlanner(Planner):
    """Planner that executes a predefined sequence of plan steps."""

    def __init__(self, steps: Sequence[PlanStep], *, default_finish: str = "Plan completed.") -> None:
        self._queue = list(steps)
        self._default_finish = default_finish

    def plan_next(self, state: AgentState) -> Thought:
        if self._queue:
            step = self._queue.pop(0)
            return step.to_thought()
        return Thought(content=self._default_finish, type=ThoughtType.FINISH)
