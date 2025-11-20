"""Mission definitions and loading utilities for the Copilot agent runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


IMPLICIT_ALLOWED_TOOLS = frozenset({"copilot_cli_session"})


@dataclass(frozen=True)
class Mission:
    """Specification of a goal the agent should accomplish."""

    id: str
    goal: str
    max_steps: int
    constraints: Sequence[str] = field(default_factory=tuple)
    success_criteria: Sequence[str] = field(default_factory=tuple)
    allowed_tools: Sequence[str] | None = None
    requires_approval: bool = False

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Return ``True`` if the tool is permitted for this mission."""

        if tool_name in IMPLICIT_ALLOWED_TOOLS:
            return True
        if self.allowed_tools is None:
            return True
        return tool_name in self.allowed_tools


def create_ephemeral_mission(goal: str) -> Mission:
    """Create a temporary mission from a goal string."""
    return Mission(
        id="ephemeral_mission",
        goal=goal,
        max_steps=10,
        constraints=(),
        success_criteria=(),
        allowed_tools=None,  # Allow all tools
        requires_approval=False,
    )


def load_mission(path: Path) -> Mission:
    """Load a mission configuration from a YAML file."""

    payload = _load_payload(path)

    mission_id = _require_string(payload, "id")
    goal = _require_string(payload, "goal")
    max_steps = _require_int(payload, "max_steps", minimum=1)

    constraints = _string_sequence(payload.get("constraints"), label="constraints")
    success_criteria = _string_sequence(payload.get("success_criteria"), label="success_criteria")
    allowed_tools_value = payload.get("allowed_tools")
    allowed_tools = (
        None
        if allowed_tools_value is None
        else _string_sequence(allowed_tools_value, label="allowed_tools")
    )
    requires_approval = bool(payload.get("requires_approval", False))

    return Mission(
        id=mission_id,
        goal=goal,
        max_steps=max_steps,
        constraints=constraints,
        success_criteria=success_criteria,
        allowed_tools=allowed_tools,
        requires_approval=requires_approval,
    )


def _load_payload(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read mission file: {path}") from exc

    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Mission file '{path}' contains invalid YAML.") from exc

    if not isinstance(data, Mapping):
        raise ValueError("Mission definition must be a mapping.")
    return data


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Mission field '{key}' must be a non-empty string.")
    return value.strip()


def _require_int(payload: Mapping[str, Any], key: str, *, minimum: int) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Mission field '{key}' must be an integer >= {minimum}.")
    if value < minimum:
        raise ValueError(f"Mission field '{key}' must be >= {minimum}.")
    return value


def _string_sequence(value: Any, *, label: str) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        entries: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Mission field '{label}' must contain non-empty strings.")
            entries.append(item.strip())
        return tuple(entries)
    raise ValueError(f"Mission field '{label}' must be a sequence of strings.")


__all__ = [
    "Mission",
    "load_mission",
    "create_ephemeral_mission",
]
