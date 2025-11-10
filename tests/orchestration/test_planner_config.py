"""Tests for deterministic plan configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.orchestration.planner import PlanConfigError, load_deterministic_plan


def write_plan(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_load_plan_resolves_context(tmp_path: Path) -> None:
    plan_path = write_plan(
        tmp_path,
        {
            "default_finish": "All done",
            "steps": [
                {
                    "description": "Fetch issue",
                    "tool": "get_issue_details",
                    "arguments": {
                        "issue_number": {"context": "issue_number"},
                        "repository": {"context": "repository"},
                    },
                }
            ],
        },
    )

    plan = load_deterministic_plan(
        plan_path,
        variables={"issue_number": 42, "repository": "octo/repo"},
    )

    assert plan.default_finish == "All done"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool_name == "get_issue_details"
    assert step.arguments == {"issue_number": 42, "repository": "octo/repo"}


def test_load_plan_missing_context_key(tmp_path: Path) -> None:
    plan_path = write_plan(
        tmp_path,
        {
            "steps": [
                {
                    "description": "Fetch issue",
                    "tool": "get_issue_details",
                    "arguments": {"issue_number": {"context": "issue_number"}},
                }
            ],
        },
    )

    with pytest.raises(PlanConfigError):
        load_deterministic_plan(plan_path, variables={})
