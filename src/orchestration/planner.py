"""Planner implementations and configuration helpers for the agent runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .types import AgentState, Thought, ThoughtType, ToolCall


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


class DeterministicPlanner(Planner):
    """Planner that executes a predefined sequence of plan steps."""

    def __init__(self, steps: Sequence[PlanStep], *, default_finish: str = "Plan completed.") -> None:
        self._queue = list(steps)
        self._default_finish = default_finish

    def plan_next(self, state: AgentState) -> Thought:  # noqa: D401 - interface compat
        del state  # Deterministic planner ignores runtime state
        if self._queue:
            step = self._queue.pop(0)
            return step.to_thought()
        return Thought(content=self._default_finish, type=ThoughtType.FINISH)


@dataclass(frozen=True)
class DeterministicPlan:
    """Container describing a deterministic planner configuration."""

    steps: tuple[PlanStep, ...]
    default_finish: str = "Plan completed."


class PlanConfigError(ValueError):
    """Raised when a deterministic plan configuration is invalid."""


def load_deterministic_plan(
    path: Path,
    *,
    variables: Mapping[str, object] | None = None,
) -> DeterministicPlan:
    """Load a deterministic plan definition from a YAML or JSON file."""

    payload = _load_structured_plan_payload(path)
    default_finish = str(payload.get("default_finish") or "Plan completed.")
    steps_data = payload.get("steps")
    if not isinstance(steps_data, Sequence) or isinstance(steps_data, (str, bytes, bytearray)):
        raise PlanConfigError("Plan configuration must include a 'steps' list.")

    steps: list[PlanStep] = []
    for index, entry in enumerate(steps_data):
        if not isinstance(entry, Mapping):
            raise PlanConfigError(f"Plan step #{index + 1} must be an object.")

        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            raise PlanConfigError(f"Plan step #{index + 1} is missing a description.")

        tool_name = entry.get("tool") or entry.get("tool_name")
        if tool_name is not None and not isinstance(tool_name, str):
            raise PlanConfigError(f"Plan step '{description}' has a non-string tool reference.")

        arguments_data = entry.get("arguments")
        if arguments_data is None:
            resolved_arguments: Mapping[str, object] | None = None
        elif isinstance(arguments_data, Mapping):
            resolved_arguments = _resolve_arguments(arguments_data, variables)
        else:
            raise PlanConfigError(f"Plan step '{description}' arguments must be an object if provided.")

        finish_summary = entry.get("finish_summary")
        if finish_summary is not None and not isinstance(finish_summary, str):
            raise PlanConfigError(f"Plan step '{description}' finish_summary must be a string if provided.")

        steps.append(
            PlanStep(
                description=description,
                tool_name=tool_name,
                arguments=resolved_arguments,
                finish_summary=finish_summary,
            )
        )

    return DeterministicPlan(steps=tuple(steps), default_finish=default_finish)


def _load_structured_plan_payload(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - surfaced to caller
        raise PlanConfigError(f"Failed to read plan file: {path}") from exc

    suffix = path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw) or {}
        else:
            data = json.loads(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:  # pragma: no cover - invalid config
        raise PlanConfigError(f"Plan file '{path}' contains invalid syntax.") from exc

    if not isinstance(data, Mapping):
        raise PlanConfigError("Plan configuration must contain a top-level object.")
    return data


def _resolve_arguments(arguments: Mapping[str, Any], variables: Mapping[str, object] | None) -> Mapping[str, object]:
    resolved: dict[str, object] = {}
    for key, value in arguments.items():
        resolved[key] = _resolve_value(value, variables, key)
    return resolved


def _resolve_value(value: Any, variables: Mapping[str, object] | None, key: str) -> object:
    if isinstance(value, Mapping):
        if "context" in value and set(value.keys()) == {"context"}:
            context_key = value["context"]
            if not isinstance(context_key, str) or not context_key:
                raise PlanConfigError("Context references must specify a non-empty string key.")
            if variables is None:
                raise PlanConfigError(
                    f"Plan references context key '{context_key}' but no variables were supplied."
                )
            if context_key not in variables:
                raise PlanConfigError(f"Plan references missing context key '{context_key}'.")
            return variables[context_key]
        return {sub_key: _resolve_value(sub_value, variables, sub_key) for sub_key, sub_value in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, variables, key) for item in value]
    return value


@dataclass(frozen=True)
class Goal:
    """Represents a goal in a hierarchical plan."""

    description: str
    subgoals: tuple[Goal, ...] = ()
    action: PlanStep | None = None
    completed: bool = False

    def is_atomic(self) -> bool:
        """Return True if this goal has no subgoals."""
        return len(self.subgoals) == 0

    def to_steps(self) -> list[PlanStep]:
        """Flatten the goal hierarchy into a linear sequence of steps."""
        if self.action:
            return [self.action]

        steps: list[PlanStep] = []
        for subgoal in self.subgoals:
            steps.extend(subgoal.to_steps())
        return steps


@dataclass(frozen=True)
class HierarchicalPlan:
    """Container for a hierarchical plan with goal decomposition."""

    root_goal: Goal
    max_depth: int = 3
    allow_dynamic_revision: bool = True

    def validate(self, available_tools: set[str] | None = None) -> list[PlanIssue]:
        """Validate the hierarchical plan structure and tool availability.

        Args:
            available_tools: Set of tool names available to the agent

        Returns:
            List of validation issues found
        """
        issues: list[PlanIssue] = []

        def check_goal(goal: Goal, depth: int) -> None:
            # Check max depth
            if depth > self.max_depth:
                issues.append(
                    PlanIssue(
                        PlanIssue.Severity.ERROR,
                        f"Goal '{goal.description}' exceeds maximum depth {self.max_depth}",
                    )
                )

            # Check that goals either have subgoals OR an action, not both
            if goal.subgoals and goal.action:
                issues.append(
                    PlanIssue(
                        PlanIssue.Severity.ERROR,
                        f"Goal '{goal.description}' has both subgoals and action (must be one or the other)",
                    )
                )

            # Check that leaf goals have actions
            if not goal.subgoals and not goal.action:
                issues.append(
                    PlanIssue(
                        PlanIssue.Severity.WARNING,
                        f"Leaf goal '{goal.description}' has no associated action",
                    )
                )

            # Check tool availability
            if goal.action and goal.action.tool_name and available_tools:
                if goal.action.tool_name not in available_tools:
                    issues.append(
                        PlanIssue(
                            PlanIssue.Severity.ERROR,
                            f"Goal '{goal.description}' references unavailable tool '{goal.action.tool_name}'",
                        )
                    )

            # Recursively check subgoals
            for subgoal in goal.subgoals:
                check_goal(subgoal, depth + 1)

        check_goal(self.root_goal, 0)
        return issues

    def to_linear_plan(self) -> DeterministicPlan:
        """Convert hierarchical plan to a linear deterministic plan."""
        steps = self.root_goal.to_steps()
        return DeterministicPlan(steps=tuple(steps))


class HierarchicalPlanner(Planner):
    """Planner that supports goal decomposition and plan revision."""

    def __init__(self, plan: HierarchicalPlan, available_tools: set[str] | None = None) -> None:
        """Initialize hierarchical planner with a goal hierarchy.

        Args:
            plan: Hierarchical plan structure
            available_tools: Set of available tool names for validation
        """
        self._plan = plan
        self._available_tools = available_tools
        self._current_goal_path: list[int] = [0]  # Track position in goal tree
        self._revision_history: list[str] = []

        # Validate plan on initialization
        issues = self._plan.validate(available_tools)
        errors = [issue for issue in issues if issue.severity == PlanIssue.Severity.ERROR]
        if errors:
            error_messages = "\n".join(str(err) for err in errors)
            raise ValueError(f"Invalid hierarchical plan:\n{error_messages}")

        # Convert to linear plan and create deterministic planner
        linear_plan = self._plan.to_linear_plan()
        self._deterministic_planner = DeterministicPlanner(
            list(linear_plan.steps), default_finish=linear_plan.default_finish
        )

    def plan_next(self, state: AgentState) -> Thought:
        """Produce next thought based on goal hierarchy and current state."""
        # Use the persistent deterministic planner
        return self._deterministic_planner.plan_next(state)

    def revise_plan(self, feedback: str, new_goals: Sequence[Goal]) -> None:
        """Revise the plan based on feedback and new goal decomposition.

        Args:
            feedback: Description of why revision is needed
            new_goals: New subgoals to incorporate
        """
        if not self._plan.allow_dynamic_revision:
            raise RuntimeError("Plan does not allow dynamic revision")

        self._revision_history.append(feedback)
        # Store revision metadata (full implementation would modify goal tree)
        # new_goals would be incorporated into the goal hierarchy here
        _ = new_goals  # Currently unused - placeholder for future enhancement

    def get_current_goal(self) -> Goal:
        """Return the current goal being pursued."""
        goal = self._plan.root_goal
        for index in self._current_goal_path[1:]:
            goal = goal.subgoals[index]
        return goal

    def get_revision_history(self) -> list[str]:
        """Return list of all plan revisions made."""
        return list(self._revision_history)
