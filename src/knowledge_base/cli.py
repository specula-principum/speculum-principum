"""CLI support functions for knowledge base operations."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .config import MissionConfig
from .structure import materialize_structure, plan_structure


def initialize_knowledge_base(
    root: Path,
    *,
    apply: bool = False,
    context: Mapping[str, str] | None = None,
    mission: MissionConfig | None = None,
) -> list[Path]:
    """Return the planned IA structure and optionally materialize it."""

    combined_context: dict[str, str] = {}
    if mission is not None:
        combined_context.update(mission.structure_context())
    if context is not None:
        combined_context.update(context)
    plan_context = combined_context or None
    plan = plan_structure(root, context=plan_context)
    if apply:
        materialize_structure(plan)
    return [item.path for item in plan]
