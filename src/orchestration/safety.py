"""Safety and approval gate logic for the Copilot agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, Iterable, Mapping

from .types import ExecutionContext, ToolCall

if TYPE_CHECKING:  # pragma: no cover - type checking aid
    from .missions import Mission
    from .tools import ToolExecution


class ActionRisk(Enum):
    """Risk classification applied to each tool."""

    SAFE = "safe"
    REVIEW = "review"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ApprovalDecision:
    """Represents the outcome of a safety approval check."""

    approved: bool
    reason: str | None
    risk: ActionRisk

    @classmethod
    def approved_decision(cls, *, risk: ActionRisk) -> "ApprovalDecision":
        return cls(approved=True, reason=None, risk=risk)

    @classmethod
    def denied(cls, *, risk: ActionRisk, reason: str) -> "ApprovalDecision":
        return cls(approved=False, reason=reason, risk=risk)


ApprovalCallback = Callable[["ToolCall", "Mission", ExecutionContext, ActionRisk], ApprovalDecision]


class SafetyValidator:
    """Validates tool executions and enforces approval requirements."""

    def __init__(
        self,
        *,
        risk_overrides: Mapping[str, ActionRisk] | None = None,
        approval_callback: ApprovalCallback | None = None,
    ) -> None:
        self._risk_overrides: Dict[str, ActionRisk] = dict(risk_overrides or {})
        self._approval_callback = approval_callback
        self._audit_log: list["ToolExecution"] = []

    def classify(self, tool_name: str) -> ActionRisk:
        """Return the risk classification for the tool."""

        return self._risk_overrides.get(tool_name, ActionRisk.SAFE)

    def check_action(
        self,
        tool_call: "ToolCall",
        mission: "Mission",
        context: ExecutionContext,
    ) -> ApprovalDecision:
        """Determine whether the tool call is permitted."""

        risk = self.classify(tool_call.name)
        if risk is ActionRisk.SAFE:
            return ApprovalDecision.approved_decision(risk=risk)
        if self._approval_callback is None:
            return ApprovalDecision.denied(
                risk=risk,
                reason=f"Tool '{tool_call.name}' requires approval but no approval callback is configured.",
            )
        return self._approval_callback(tool_call, mission, context, risk)

    def audit_log(self, execution: "ToolExecution") -> None:
        """Record a tool execution for later review."""

        self._audit_log.append(execution)

    def iter_audit_log(self) -> Iterable["ToolExecution"]:
        """Yield previously recorded tool executions."""

        yield from self._audit_log
