"""Tool registry and handlers for the knowledge base MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.extraction.concepts import extract_concepts
from src.integrations.copilot.helpers import validate_kb_changes
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
    registry.register(
        ToolDefinition(
            name="kb_extract_concepts",
            description="Extract high-signal concepts from source text.",
            input_schema={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "min_frequency": {"type": "integer", "default": 2},
                    "max_concepts": {"type": "integer", "default": 50},
                    "window_size": {"type": "integer", "default": 4},
                    "max_related_terms": {"type": "integer", "default": 5},
                    "min_term_length": {"type": "integer", "default": 3},
                    "exclude_stopwords": {"type": "boolean", "default": True},
                },
                "required": ["source_path"],
                "additionalProperties": False,
            },
            handler=_handle_extract_concepts,
        )
    )
    registry.register(
        ToolDefinition(
            name="kb_create_concept",
            description="Create a concept document within the knowledge base.",
            input_schema={
                "type": "object",
                "properties": {
                    "concept_name": {"type": "string"},
                    "definition": {"type": "string"},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "related_concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "primary_topic": {"type": "string", "default": "general"},
                    "topic_path": {"type": "string"},
                    "kb_root": {"type": "string", "default": "knowledge-base"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "secondary_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "analysis": {"type": "string"},
                    "audience": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "navigation_path": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "findability_score": {"type": "number", "default": 0.75},
                    "completeness": {"type": "number", "default": 0.85},
                },
                "required": ["concept_name", "definition", "sources"],
                "additionalProperties": False,
            },
            handler=_handle_create_concept,
        )
    )
    registry.register(
        ToolDefinition(
            name="kb_validate",
            description="Validate knowledge base changes and compute quality metrics.",
            input_schema={
                "type": "object",
                "properties": {
                    "kb_root": {"type": "string", "default": "knowledge-base"},
                    "section": {"type": "string"},
                },
                "required": ["kb_root"],
                "additionalProperties": False,
            },
            handler=_handle_validate,
        )
    )


def _handle_extract_concepts(payload: dict[str, Any]) -> ToolResponse:
    source = Path(payload["source_path"]).expanduser()
    if not source.is_file():
        raise ToolExecutionError(f"Source path does not exist: {source}")
    text = source.read_text(encoding="utf-8")
    config = {
        "source_path": str(source),
        "min_frequency": payload["min_frequency"],
        "max_concepts": payload["max_concepts"],
        "window_size": payload["window_size"],
        "max_related_terms": payload["max_related_terms"],
        "min_term_length": payload["min_term_length"],
        "exclude_stopwords": payload["exclude_stopwords"],
    }
    result = extract_concepts(text, config=config)
    concepts = [
        {
            "term": concept.term,
            "frequency": concept.frequency,
            "positions": list(concept.positions),
            "related_terms": list(concept.related_terms),
        }
        for concept in result.data
    ]
    summary = {
        "total_candidates": int(result.metadata.get("total_candidates", len(concepts))),
        "selected_concepts": len(concepts),
    }
    metadata = {
        "source_path": str(source),
        "checksum": result.checksum,
        "config": {
            key: config[key]
            for key in (
                "min_frequency",
                "max_concepts",
                "window_size",
                "max_related_terms",
                "min_term_length",
                "exclude_stopwords",
            )
        },
    }
    return ToolResponse(data={"concepts": concepts, "summary": summary}, metadata=metadata)


def _handle_create_concept(payload: dict[str, Any]) -> ToolResponse:
    name = payload["concept_name"].strip()
    if not name:
        raise PayloadValidationError("concept_name cannot be blank.")
    definition = payload["definition"].strip()
    if not definition:
        raise PayloadValidationError("definition cannot be blank.")

    sources = _normalise_source_refs(payload["sources"])
    if not sources:
        raise PayloadValidationError("At least one source reference is required.")

    kb_root = Path(payload["kb_root"]).expanduser()
    primary_topic = slugify(payload["primary_topic"])
    topic_path = _normalise_topic_path(payload.get("topic_path"), default=primary_topic)
    slug = slugify(name)
    kb_id = f"concepts/{topic_path}/{slug}"

    destination = kb_root / "concepts" / topic_path
    destination.mkdir(parents=True, exist_ok=True)
    document_path = destination / f"{slug}.md"
    if document_path.exists():
        raise ToolExecutionError(f"Concept document already exists: {document_path}")

    tags = _normalise_slug_sequence(payload.get("tags", []))
    if not tags:
        tags = tuple(dict.fromkeys((primary_topic, slug)))
    secondary_topics = _normalise_slug_sequence(payload.get("secondary_topics", []))
    audience = tuple(item.strip() for item in payload.get("audience", []) if item.strip())
    navigation_path = _normalise_navigation_path(payload.get("navigation_path", []))

    dc = DublinCoreMetadata(
        title=name,
        description=definition,
        subject=(primary_topic.replace("-", " "),),
    )
    ia = IAMetadata(
        findability_score=float(payload["findability_score"]),
        completeness=float(payload["completeness"]),
        audience=audience,
        navigation_path=navigation_path,
    )
    metadata = KBMetadata(
        doc_type="concept",
        primary_topic=primary_topic,
        dc=dc,
        ia=ia,
        secondary_topics=secondary_topics,
        tags=tags,
        sources=sources,
    )
    body = _compose_body(definition, payload.get("analysis"))
    document = KBDocument(
        kb_id=kb_id,
        slug=slug,
        title=name,
        metadata=metadata,
        aliases=tuple(item.strip() for item in payload.get("aliases", []) if item.strip()),
        related_concepts=tuple(item.strip() for item in payload.get("related_concepts", []) if item.strip()),
        body=body,
    )
    document.validate()
    rendered = render_document(document)
    document_path.write_text(rendered, encoding="utf-8")
    metadata_payload = {
        "kb_id": kb_id,
        "primary_topic": primary_topic,
        "path": str(document_path.resolve()),
        "source_count": len(sources),
    }
    return ToolResponse(data={"kb_id": kb_id, "path": str(document_path)}, metadata=metadata_payload)


def _handle_validate(payload: dict[str, Any]) -> ToolResponse:
    kb_root = Path(payload["kb_root"]).expanduser()
    if not kb_root.exists():
        raise ToolExecutionError(f"Knowledge base root does not exist: {kb_root}")
    report = validate_kb_changes(kb_root)
    data = {
        "kb_root": str(report.kb_root),
        "documents_checked": report.documents_checked,
        "documents_valid": report.documents_valid,
        "errors": list(report.errors),
        "warnings": list(report.warnings),
        "quality": {
            "total_documents": report.quality.total_documents,
            "average_completeness": report.quality.average_completeness,
            "average_findability": report.quality.average_findability,
            "below_threshold": list(report.quality.below_threshold),
        },
    }
    metadata = {
        "kb_root": str(kb_root.resolve()),
    }
    if payload.get("section"):
        metadata["section"] = payload["section"]
    return ToolResponse(data=data, metadata=metadata)


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
