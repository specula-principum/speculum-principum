"""Tool registry for the Copilot agent runtime.

This module provides a centralized registry for registering and executing
tools available to the agent. Tools are validated against JSON schemas
before execution to ensure parameter correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping

from jsonschema import Draft7Validator, ValidationError

from .safety import ActionRisk
from .types import ToolResult

Handler = Callable[[Mapping[str, Any]], ToolResult | Any]


class ToolRegistryError(RuntimeError):
    """Raised when tool registration or execution fails."""


@dataclass(frozen=True)
class ToolDefinition:
    """Defines a callable tool available to the agent."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: Handler
    risk_level: ActionRisk = ActionRisk.SAFE


@dataclass(frozen=True)
class ToolExecution:
    """Execution record emitted after running a tool."""

    definition: ToolDefinition
    arguments: Mapping[str, Any]
    result: ToolResult
    risk: ActionRisk


class ToolRegistry:
    """Registry storing all available tools for the agent."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._validators: Dict[str, Draft7Validator] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool with the registry."""

        if tool.name in self._tools:
            raise ToolRegistryError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        schema = tool.parameters
        if isinstance(schema, Mapping) and schema:
            self._validators[tool.name] = Draft7Validator(schema)

    def get_tool(self, name: str) -> ToolDefinition:
        """Return the tool definition for the supplied name."""

        try:
            return self._tools[name]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ToolRegistryError(f"Tool '{name}' is not registered.") from exc

    def get_tool_schemas(self) -> Iterable[Mapping[str, Any]]:
        """Yield JSON-schema compatible metadata for all tools."""

        for tool in self._tools.values():
            yield {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "risk_level": tool.risk_level.value,
            }

    def get_openai_tool_schemas(self) -> list[dict[str, Any]]:
        """Return tool definitions in OpenAI function calling format.
        
        This format is compatible with GitHub Models API and other OpenAI-compatible
        endpoints for LLM function calling.
        """
        tools = []
        for tool in self._tools.values():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return tools

    def execute_tool(self, name: str, arguments: Mapping[str, Any]) -> ToolResult:
        """Execute a tool and return its canonical result."""

        definition = self.get_tool(name)
        return self._execute_definition(definition, arguments)

    def execute_definition(self, definition: ToolDefinition, arguments: Mapping[str, Any]) -> ToolResult:
        """Execute the provided tool definition."""

        return self._execute_definition(definition, arguments)

    def _validation_error_message(self, tool_name: str, exc: ValidationError) -> str:
        path = "".join(f"/{entry}" for entry in exc.absolute_path)
        details = exc.message
        if path:
            return f"Argument validation failed for '{tool_name}' at '{path}': {details}"
        return f"Argument validation failed for '{tool_name}': {details}"

    def _execute_definition(self, definition: ToolDefinition, arguments: Mapping[str, Any]) -> ToolResult:
        payload = dict(arguments)
        validator = self._validators.get(definition.name)
        if validator is not None:
            try:
                validator.validate(payload)
            except ValidationError as exc:
                message = self._validation_error_message(definition.name, exc)
                return ToolResult(success=False, output=None, error=message)
        try:
            raw_result = definition.handler(payload)
        except Exception as exc:  # pragma: no cover - tool handler surface
            raise ToolRegistryError(
                f"Execution of tool '{definition.name}' failed."
            ) from exc
        if isinstance(raw_result, ToolResult):
            return raw_result
        return ToolResult(success=True, output=raw_result, error=None)

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def __iter__(self):  # type: ignore[override]
        return iter(self._tools.values())
