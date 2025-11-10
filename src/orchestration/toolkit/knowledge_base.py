"""Knowledge base tool registrations for the orchestration runtime."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from src.knowledge_base.config import load_mission_config
from src.knowledge_base.structure import plan_structure, required_directories

from ..safety import ActionRisk
from ..tools import ToolDefinition, ToolRegistry
from ..types import ToolResult


def register_knowledge_base_tools(registry: ToolRegistry) -> None:
    """Register safe knowledge base utilities with the registry."""

    registry.register_tool(
        ToolDefinition(
            name="plan_knowledge_base_structure",
            description="Plan the default knowledge base structure under the provided root.",
            parameters={
                "type": "object",
                "properties": {
                    "root": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Filesystem path used as the knowledge base root.",
                    },
                    "context": {
                        "type": "object",
                        "description": "Optional template context overrides for structure rendering.",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["root"],
                "additionalProperties": False,
            },
            handler=_plan_structure_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="list_kb_required_directories",
            description="List directory names that must exist within the knowledge base root.",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_required_directories_handler,
            risk_level=ActionRisk.SAFE,
        )
    )

    registry.register_tool(
        ToolDefinition(
            name="load_kb_mission_config",
            description="Load and validate the knowledge base mission configuration file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional override for the mission configuration path.",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_load_mission_config_handler,
            risk_level=ActionRisk.SAFE,
        )
    )


def _plan_structure_handler(args: Mapping[str, Any]) -> ToolResult:
    root_arg = args.get("root")
    if not isinstance(root_arg, str) or not root_arg.strip():
        return ToolResult(success=False, output=None, error="root must be a non-empty string.")

    context_arg = args.get("context")
    if context_arg is not None and not isinstance(context_arg, Mapping):
        return ToolResult(success=False, output=None, error="context must be an object when provided.")

    context: Mapping[str, str] | None = None
    if isinstance(context_arg, Mapping):
        context = {str(key): str(value) for key, value in context_arg.items()}

    root_path = Path(root_arg).expanduser()
    try:
        plan = plan_structure(root_path, context=context)
    except ValueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))

    output = [
        {
            "path": str(item.path),
            "is_directory": item.is_directory,
            "content": item.content,
        }
        for item in plan
    ]
    return ToolResult(success=True, output=output, error=None)


def _list_required_directories_handler(args: Mapping[str, Any]) -> ToolResult:
    if args:  # JSON Schema prevents extras but guard defensively.
        return ToolResult(success=False, output=None, error="This tool does not accept arguments.")
    directories = list(required_directories())
    return ToolResult(success=True, output=directories, error=None)


def _load_mission_config_handler(args: Mapping[str, Any]) -> ToolResult:
    path_arg = args.get("path")
    if path_arg is not None and (not isinstance(path_arg, str) or not path_arg.strip()):
        return ToolResult(success=False, output=None, error="path must be a non-empty string when provided.")

    path = Path(path_arg).expanduser() if isinstance(path_arg, str) else None
    try:
        config = load_mission_config(path)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        return ToolResult(success=False, output=None, error=str(exc))

    output = {
        "mission": asdict(config.mission),
        "information_architecture": asdict(config.information_architecture),
        "structure_context": config.structure_context(),
    }
    return ToolResult(success=True, output=output, error=None)


__all__ = ["register_knowledge_base_tools"]
