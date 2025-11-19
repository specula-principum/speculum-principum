"""Tool registry and handlers for the knowledge base MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.kb_engine.utils import slugify
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)
from src.knowledge_base.metadata import render_document

ToolHandler = Callable[[dict[str, Any]], "ToolResponse"]


class PayloadValidationError(ValueError):
    """Raised when an input payload fails schema validation."""


class ToolExecutionError(RuntimeError):
    """Raised when a tool handler cannot satisfy the request."""


@dataclass(frozen=True)
class ToolResponse:
    """Structured payload returned from a tool invocation."""

    data: Mapping[str, Any]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ToolDefinition:
    """Registered MCP tool and its handler."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: ToolHandler


class KBToolRegistry:
    """Lightweight registry that validates and executes MCP tools."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._definitions.values())

    def describe(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.input_schema,
            }
            for definition in self._definitions.values()
        )

    def invoke(self, name: str, payload: Mapping[str, Any]) -> ToolResponse:
        try:
            definition = self._definitions[name]
        except KeyError as exc:
            raise ToolExecutionError(f"Unknown tool: {name}") from exc
        normalised = _normalise_payload(definition.input_schema, payload)
        return definition.handler(normalised)


def register_kb_tools(registry: KBToolRegistry) -> None:
    pass






def _normalise_payload(schema: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise PayloadValidationError("Payload must be an object.")
    if schema.get("type") != "object":
        raise PayloadValidationError("Schemas must describe JSON objects.")
    properties: Mapping[str, Mapping[str, Any]] = schema.get("properties", {})
    required: Sequence[str] = schema.get("required", ())
    normalised: dict[str, Any] = {}
    for field, prop_schema in properties.items():
        if "default" in prop_schema:
            normalised[field] = prop_schema["default"]
    for field in required:
        if field not in payload:
            raise PayloadValidationError(f"Missing required field: {field}")
    for field, value in payload.items():
        if field not in properties:
            if not schema.get("additionalProperties", True):
                raise PayloadValidationError(f"Unexpected field: {field}")
            normalised[field] = value
            continue
        normalised[field] = _coerce_value(field, value, properties[field])
    return normalised


def _coerce_value(field: str, value: Any, schema: Mapping[str, Any]) -> Any:
    expected = schema.get("type")
    if expected == "string":
        if not isinstance(value, str):
            raise PayloadValidationError(f"Field '{field}' must be a string.")
        return value
    if expected == "integer":
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:
            raise PayloadValidationError(f"Field '{field}' must be an integer.") from exc
        return coerced
    if expected == "number":
        try:
            coerced = float(value)
        except (TypeError, ValueError) as exc:
            raise PayloadValidationError(f"Field '{field}' must be a number.") from exc
        return coerced
    if expected == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise PayloadValidationError(f"Field '{field}' must be a boolean.")
    if expected == "array":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise PayloadValidationError(f"Field '{field}' must be an array.")
        item_schema = schema.get("items")
        if item_schema:
            return [_coerce_value(f"{field}[{index}]", item, item_schema) for index, item in enumerate(value)]
        return list(value)
    if expected == "object":
        if not isinstance(value, Mapping):
            raise PayloadValidationError(f"Field '{field}' must be an object.")
        return dict(value)
    return value


def _normalise_source_refs(values: Sequence[str]) -> tuple[SourceReference, ...]:
    references: list[SourceReference] = []
    for entry in values:
        token = str(entry).strip()
        if not token:
            raise PayloadValidationError("Source references cannot be blank.")
        segments = [slugify(segment) for segment in token.split("/") if segment]
        if not segments:
            raise PayloadValidationError("Source references cannot be empty.")
        kb_id = "/".join(segments)
        references.append(SourceReference(kb_id=kb_id, pages=()))
    return tuple(references)


def _normalise_topic_path(raw: str | None, *, default: str) -> str:
    if raw is None:
        return default
    segments = [slugify(segment) for segment in raw.split("/") if segment]
    return "/".join(segments) if segments else default


def _normalise_slug_sequence(values: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in values:
        token = slugify(str(entry))
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return tuple(ordered)


def _normalise_navigation_path(values: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for entry in values:
        token = str(entry).strip()
        if token:
            ordered.append(token)
    return tuple(ordered)


def _compose_body(definition: str, analysis: str | None) -> str:
    parts = [definition.strip()]
    if analysis:
        trimmed = analysis.strip()
        if trimmed:
            parts.append(trimmed)
    return "\n\n".join(parts) if parts else ""
