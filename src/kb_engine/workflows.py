"""High-level workflows for the knowledge base engine."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import csv
import json
import logging
import shutil
import statistics
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, MutableMapping, Sequence, cast
from xml.etree import ElementTree as ET

from src.extraction.config import ExtractionConfig, load_default_or_empty
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    MissionConfig,
    SourceReference,
)
from src.kb_engine.config import PipelineConfig, load_pipeline_config
from src.kb_engine.extraction import ExtractionBundle, ExtractionCoordinator
from src.kb_engine.links import LinkBuilder
from src.kb_engine.models import (
    DocumentArtifact,
    KBGraphExportResult,
    KBImprovementResult,
    KBProcessingResult,
    KBQualityReportResult,
    KBUpdateResult,
    PipelineStage,
    PipelineStageError,
    ProcessingContext,
    QualityGap,
    StageResult,
)
from src.kb_engine.organize import KBOrganizer
from src.kb_engine.pipeline import KBPipeline
from src.kb_engine.quality import QualityAnalyzer
from src.kb_engine.stages import QualityStage
from src.kb_engine.transform import KBTransformer, TransformContext
from .utils import slugify

try:  # pragma: no cover - dependency guarded for environments missing PyYAML
    import yaml
except ImportError:  # pragma: no cover - surfaced when dependency unavailable
    yaml = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return default


def _coerce_optional_float(value: Any, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return default


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return default


def _coerce_optional_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        return default


def _extra_dict(context: ProcessingContext) -> dict[str, Any]:
    return cast(dict[str, Any], context.extra)


def _ensure_section(context: ProcessingContext, key: str) -> MutableMapping[str, Any]:
    extra = _extra_dict(context)
    section = extra.setdefault(key, {})
    if not isinstance(section, MutableMapping):
        raise PipelineStageError(f"context.extra['{key}'] must be a mapping")
    return cast(MutableMapping[str, Any], section)


def _get_section(context: ProcessingContext, key: str) -> Mapping[str, Any]:
    extra = _extra_dict(context)
    section = extra.get(key, {})
    if isinstance(section, Mapping):
        return section
    return {}


def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text if text.endswith("\n") else f"{text}\n"

    if yaml is None:
        raise PipelineStageError("PyYAML is required to parse parsed evidence artifacts")

    try:
        terminator = lines.index("---", 1)
    except ValueError as exc:  # pragma: no cover - malformed artifact
        raise PipelineStageError(f"Unterminated YAML front matter in {path.name}") from exc

    front_block = "\n".join(lines[1:terminator])
    body_lines = lines[terminator + 1 :]
    front = yaml.safe_load(front_block) or {}
    if not isinstance(front, dict):  # pragma: no cover - defensive guard
        raise PipelineStageError(f"Front matter in {path.name} must be a mapping")
    body = "\n".join(body_lines)
    if body and not body.endswith("\n"):
        body = f"{body}\n"
    return front, body


def _iter_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        token = values.strip()
        return (token,) if token else ()
    if isinstance(values, Sequence):
        items: list[str] = []
        for entry in values:
            if isinstance(entry, str):
                token = entry.strip()
            else:
                token = str(entry).strip()
            if token:
                items.append(token)
        return tuple(items)
    token = str(values).strip()
    return (token,) if token else ()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        try:
            return datetime.fromisoformat(token)
        except ValueError:  # pragma: no cover - fallback for alternate formats
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(token, fmt)
                except ValueError:
                    continue
    return None


def _build_source_reference(payload: Any) -> SourceReference | None:
    if not isinstance(payload, Mapping):
        return None
    kb_id_raw = payload.get("kb_id")
    if not kb_id_raw:
        return None
    kb_id = str(kb_id_raw).strip()
    if not kb_id:
        return None

    pages_raw = payload.get("pages")
    pages: list[int] = []
    if isinstance(pages_raw, Sequence):
        for item in pages_raw:
            try:
                pages.append(int(item))
            except (TypeError, ValueError):  # pragma: no cover - ignore invalid pages
                continue

    return SourceReference(kb_id=kb_id, pages=tuple(pages))


def _build_document_from_front(front: Mapping[str, Any], body: str, *, path: Path) -> KBDocument:
    kb_id = str(front.get("kb_id") or "").strip()
    if not kb_id:
        raise ValueError(f"{path.name}: missing kb_id in front matter")

    doc_type = str(front.get("type") or front.get("doc_type") or "").strip()
    if not doc_type:
        raise ValueError(f"{kb_id}: missing type in front matter")

    slug = str(front.get("slug") or Path(kb_id).name).strip()
    title = str(front.get("title") or slug).strip()
    if not title:
        raise ValueError(f"{kb_id}: missing title in front matter")

    primary_topic_raw = front.get("primary_topic")
    primary_topic = str(primary_topic_raw).strip() if isinstance(primary_topic_raw, str) else ""
    if not primary_topic:
        segments = [segment for segment in kb_id.split("/") if segment]
        if len(segments) >= 2:
            primary_topic = segments[1]
        elif segments:
            primary_topic = segments[0]
    if not primary_topic:
        raise ValueError(f"{kb_id}: unable to derive primary_topic")

    secondary_topics = _iter_strings(front.get("secondary_topics"))
    tags = _iter_strings(front.get("tags"))
    subject_tokens = _iter_strings(front.get("subject"))
    if not subject_tokens and primary_topic:
        subject_tokens = (primary_topic,)

    description_raw = front.get("description") or front.get("summary") or front.get("abstract")
    description = str(description_raw).strip() if isinstance(description_raw, str) else None
    if description == "":
        description = None

    creator_raw = front.get("creator")
    creator = str(creator_raw).strip() if isinstance(creator_raw, str) and creator_raw.strip() else None
    contributor = _iter_strings(front.get("contributor"))
    relation = _iter_strings(front.get("relation"))

    source_field = front.get("source")
    source_value = str(source_field).strip() if isinstance(source_field, str) and source_field.strip() else None

    publisher_raw = front.get("publisher")
    publisher = str(publisher_raw).strip() if isinstance(publisher_raw, str) and publisher_raw.strip() else None

    dc = DublinCoreMetadata(
        title=title,
        creator=creator,
        subject=subject_tokens,
        description=description,
        contributor=contributor,
        relation=relation,
        identifier=kb_id,
        source=source_value,
        publisher=publisher,
        language=str(front.get("language") or "en").strip() or "en",
        doc_type=doc_type,
    )

    ia_payload = front.get("ia") if isinstance(front.get("ia"), Mapping) else {}
    ia_mapping = cast(Mapping[str, Any], ia_payload)

    audience = _iter_strings(ia_mapping.get("audience"))
    navigation_path = _iter_strings(ia_mapping.get("navigation_path"))
    related_by_topic = _iter_strings(ia_mapping.get("related_by_topic"))
    related_by_entity = _iter_strings(ia_mapping.get("related_by_entity"))

    ia = IAMetadata(
        findability_score=_coerce_optional_float(ia_mapping.get("findability_score")),
        completeness=_coerce_optional_float(ia_mapping.get("completeness")),
        depth=_coerce_optional_int(ia_mapping.get("depth")),
        audience=audience,
        navigation_path=navigation_path,
        related_by_topic=related_by_topic,
        related_by_entity=related_by_entity,
        last_updated=_parse_datetime(ia_mapping.get("last_updated")),
        update_frequency=(
            str(ia_mapping.get("update_frequency")).strip()
            if ia_mapping.get("update_frequency")
            else None
        ),
    )

    sources_payload = front.get("sources")
    source_refs: list[SourceReference] = []
    if isinstance(sources_payload, Sequence):
        for item in sources_payload:
            reference = _build_source_reference(item)
            if reference is not None:
                source_refs.append(reference)

    metadata = KBMetadata(
        doc_type=doc_type,
        primary_topic=primary_topic,
        dc=dc,
        ia=ia,
        secondary_topics=secondary_topics,
        tags=tags,
        sources=tuple(source_refs),
    )

    document = KBDocument(
        kb_id=kb_id,
        slug=slug,
        title=title,
        metadata=metadata,
        aliases=_iter_strings(front.get("aliases")),
        related_concepts=_iter_strings(front.get("related_concepts")),
        body=body,
    )
    return document


def _load_existing_document(kb_root: Path, kb_id: str) -> dict[str, Any] | None:
    token = kb_id.strip()
    if not token:
        raise ValueError("kb_id is required for update workflows")

    relative = Path(token)
    if relative.is_absolute():
        raise ValueError("kb_id must be a relative knowledge base path")

    doc_path = (kb_root.expanduser() / relative).with_suffix(".md")
    if not doc_path.exists():
        return None

    front_matter, body = _parse_markdown(doc_path)
    return {
        "kb_id": token,
        "path": doc_path,
        "front_matter": front_matter,
        "body": body,
    }


def _append_unique(container: defaultdict[str, list[str]], key: str, message: str) -> None:
    messages = container[key]
    if message not in messages:
        messages.append(message)


def _candidate_tags_from_kb_id(kb_id: str) -> tuple[str, ...]:
    parts = [slugify(segment) for segment in kb_id.split("/") if segment]
    ordered: list[str] = []
    for token in parts[-3:]:
        if token not in ordered:
            ordered.append(token)
    return tuple(ordered)


def _build_gap_suggestions(
    gaps: Sequence[QualityGap],
    *,
    builder: LinkBuilder,
    suggest_tags: bool,
) -> dict[str, tuple[str, ...]]:
    suggestions: defaultdict[str, list[str]] = defaultdict(list)
    for gap in gaps:
        kb_id = gap.kb_id
        issue = gap.issue

        if issue == "missing-tags":
            _append_unique(suggestions, kb_id, "add descriptive tags")
            if suggest_tags:
                candidates = _candidate_tags_from_kb_id(kb_id)
                if candidates:
                    _append_unique(
                        suggestions,
                        kb_id,
                        "tag-suggestions: " + ", ".join(candidates),
                    )
        elif issue == "missing-backlinks":
            _append_unique(suggestions, kb_id, "review backlinks for related coverage")
            related = tuple(builder.suggest_related(kb_id))
            if related:
                _append_unique(
                    suggestions,
                    kb_id,
                    "link-to: " + ", ".join(related[:5]),
                )
        elif issue == "findability-below-threshold":
            _append_unique(
                suggestions,
                kb_id,
                "add navigation paths or backlinks to raise findability",
            )
        elif issue == "completeness-below-threshold":
            _append_unique(
                suggestions,
                kb_id,
                "expand content and metadata fields to improve completeness",
            )
        elif issue == "missing-sources":
            _append_unique(
                suggestions,
                kb_id,
                "add source references with citations",
            )
        else:
            _append_unique(suggestions, kb_id, f"investigate gap: {issue}")

    return {kb_id: tuple(messages) for kb_id, messages in suggestions.items()}


def _write_improvement_report(path: Path, result: KBImprovementResult) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    def _serialise_gap(gap: QualityGap) -> dict[str, Any]:
        details = {
            key: (str(value) if isinstance(value, Path) else value)
            for key, value in gap.details.items()
        }
        return {
            "kb_id": gap.kb_id,
            "issue": gap.issue,
            "severity": gap.severity,
            "details": details,
        }

    payload = {
        "kb_root": str(result.kb_root),
        "success": result.success,
        "metrics": dict(result.metrics),
        "fixes_applied": list(result.fixes_applied),
        "gaps": [_serialise_gap(gap) for gap in result.gaps],
        "suggestions": {key: list(value) for key, value in result.suggestions.items()},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _export_graph_to_graphml(graph, path: Path) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("graphml", attrib={"xmlns": "http://graphml.graphdrawing.org/xmlns"})
    ET.SubElement(
        root,
        "key",
        attrib={"id": "label", "for": "edge", "attr.name": "label", "attr.type": "string"},
    )
    ET.SubElement(
        root,
        "key",
        attrib={"id": "weight", "for": "edge", "attr.name": "weight", "attr.type": "double"},
    )
    graph_element = ET.SubElement(root, "graph", attrib={"id": "knowledge-graph", "edgedefault": "directed"})

    for concept in graph.concepts:
        ET.SubElement(graph_element, "node", attrib={"id": concept})

    for edge in graph.edges:
        edge_element = ET.SubElement(
            graph_element,
            "edge",
            attrib={"source": edge.source, "target": edge.target},
        )
        label_data = ET.SubElement(edge_element, "data", attrib={"key": "label"})
        label_data.text = edge.relationship_type
        if edge.weight is not None:
            weight_data = ET.SubElement(edge_element, "data", attrib={"key": "weight"})
            weight_data.text = str(edge.weight)

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _escape_dot_token(token: str) -> str:
    return token.replace("\\", "\\\\").replace("\"", "\\\"")


def _export_graph_to_dot(graph, path: Path) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["digraph KnowledgeGraph {"]
    for concept in graph.concepts:
        lines.append(f'  "{_escape_dot_token(concept)}";')
    for edge in graph.edges:
        label = _escape_dot_token(edge.relationship_type)
        segment = f'  "{_escape_dot_token(edge.source)}" -> "{_escape_dot_token(edge.target)}" [label="{label}"'
        if edge.weight is not None:
            segment += f", weight={edge.weight}"
        segment += "];"
        lines.append(segment)
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _export_graph_to_csv(graph, path: Path) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "type", "weight"])
        for edge in graph.edges:
            writer.writerow(
                [
                    edge.source,
                    edge.target,
                    edge.relationship_type,
                    "" if edge.weight is None else edge.weight,
                ]
            )


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


class SourceAnalysisStage:
    """Collect textual segments from parsed evidence directories."""

    name = "analysis"

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:
        del previous
        source_dir = context.source_path.expanduser()
        if not source_dir.is_dir():
            raise PipelineStageError(f"source_path '{source_dir}' is not a directory")

        segments: list[str] = []
        warnings: list[str] = []
        pages: list[int] = []

        for path in sorted(source_dir.glob("*.md")):
            if path.name == "index.md":
                continue
            try:
                front, body = _parse_markdown(path)
            except PipelineStageError as exc:
                warnings.append(f"{path.name}: {exc}")
                continue
            text = body.strip()
            if text:
                segments.append(text)
            metadata = front.get("metadata")
            if isinstance(metadata, Mapping):
                page_number = metadata.get("page_number") or metadata.get("segment_number")
                try:
                    if page_number is not None:
                        pages.append(int(page_number))
                except (TypeError, ValueError):  # pragma: no cover - defensive logging
                    warnings.append(f"{path.name}: invalid page metadata {page_number!r}")

        full_text = "\n\n".join(segments)
        source_slug = slugify(source_dir.name)
        reference = SourceReference(kb_id=f"sources/{source_slug}", pages=tuple(sorted(set(pages))))
        reference.validate()

        analysis_section = _ensure_section(context, "analysis")
        analysis_section.update(
            {
                "text": full_text,
                "segments": tuple(segments),
                "source_slug": source_slug,
                "source_reference": reference,
            }
        )

        metrics = {
            "segments": float(len(segments)),
            "characters": float(len(full_text)),
        }
        if not segments:
            warnings.append("no textual segments discovered")
        return StageResult(stage=self.name, metrics=metrics, warnings=tuple(warnings))


class ExtractionStage:
    """Run configured extractors against aggregated source text."""

    name = "extraction"

    def __init__(self, coordinator: ExtractionCoordinator, *, config: ExtractionConfig) -> None:
        self._coordinator = coordinator
        self._config = config

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:
        del previous
        analysis = _get_section(context, "analysis")
        text = analysis.get("text", "")
        if not isinstance(text, str):
            raise PipelineStageError("analysis stage did not provide textual content")

        if context.extractors:
            bundle = self._coordinator.extract_selective(
                text,
                context.extractors,
                self._config,
                source_path=str(context.source_path),
            )
        else:
            bundle = self._coordinator.extract_all(
                text,
                self._config,
                source_path=str(context.source_path),
            )

        extraction_section = _ensure_section(context, "extraction")
        extraction_section["bundle"] = bundle

        total_duration = sum(summary.duration for summary in bundle.summaries)
        metrics = {
            "extractors_total": float(len(bundle.summaries)),
            "failures": float(len(bundle.failures)),
            "duration": float(round(total_duration, 3)),
        }
        notes = tuple(summary.extractor for summary in bundle.summaries[:5])
        warnings = tuple(f"{name}: {error}" for name, error in bundle.failures.items())
        return StageResult(stage=self.name, metrics=metrics, notes=notes, warnings=warnings)


class TransformationStage:
    """Convert extraction bundles into knowledge base documents."""

    name = "transformation"

    def __init__(
        self,
        transformer: KBTransformer,
        *,
        mission: MissionConfig | None,
        options: Mapping[str, Any],
    ) -> None:
        self._transformer = transformer
        self._mission = mission
        self._options = dict(options)

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:
        del previous
        bundle = self._require_bundle(context)
        analysis = _get_section(context, "analysis")
        reference = analysis.get("source_reference")
        if not isinstance(reference, SourceReference):
            raise PipelineStageError("analysis stage did not provide source reference")

        transform_context = self._build_context(reference)
        min_concept_frequency = _coerce_int(self._options.get("min_concept_frequency"), default=1)
        min_entity_confidence = _coerce_float(self._options.get("min_entity_confidence"), default=0.0)

        documents: list[KBDocument] = []
        artifacts: list[DocumentArtifact] = []
        warnings: list[str] = []

        concept_result = bundle.results.get("concepts")
        concept_count = 0
        if concept_result and isinstance(concept_result.data, Sequence):
            for concept in concept_result.data:
                frequency = getattr(concept, "frequency", 0)
                if frequency < min_concept_frequency:
                    continue
                document = self._transformer.create_concept_document(concept, transform_context)
                if not self._include_document(context, document.kb_id):
                    continue
                documents.append(document)
                concept_count += 1
                artifacts.append(
                    DocumentArtifact(
                        kb_id=document.kb_id,
                        path=context.kb_root / f"{document.kb_id}.md",
                        doc_type=document.metadata.doc_type,
                        metadata={"title": document.title},
                    )
                )

        entity_result = bundle.results.get("entities")
        entity_count = 0
        if entity_result and isinstance(entity_result.data, Sequence):
            for entity in entity_result.data:
                confidence = getattr(entity, "confidence", 0.0)
                if confidence < min_entity_confidence:
                    continue
                document = self._transformer.create_entity_document(entity, transform_context)
                if not self._include_document(context, document.kb_id):
                    continue
                documents.append(document)
                entity_count += 1
                artifacts.append(
                    DocumentArtifact(
                        kb_id=document.kb_id,
                        path=context.kb_root / f"{document.kb_id}.md",
                        doc_type=document.metadata.doc_type,
                        metadata={"title": document.title},
                    )
                )

        update_target = self._target_kb_id(context)
        if update_target and not any(doc.kb_id == update_target for doc in documents):
            warnings.append(f"target '{update_target}' not generated")

        _ensure_section(context, "transformation")["documents"] = tuple(documents)
        metrics = {
            "concepts": float(concept_count),
            "entities": float(entity_count),
        }
        return StageResult(stage=self.name, artifacts=tuple(artifacts), metrics=metrics, warnings=tuple(warnings))

    def _include_document(self, context: ProcessingContext, kb_id: str) -> bool:
        target = self._target_kb_id(context)
        if target is None:
            return True
        return target == kb_id

    @staticmethod
    def _target_kb_id(context: ProcessingContext) -> str | None:
        update_section = _get_section(context, "update")
        target = update_section.get("target_kb_id")
        if not isinstance(target, str):
            return None
        token = target.strip()
        return token or None

    def _require_bundle(self, context: ProcessingContext) -> ExtractionBundle:
        extraction = _get_section(context, "extraction")
        bundle = extraction.get("bundle")
        if not isinstance(bundle, ExtractionBundle):
            raise PipelineStageError("extraction stage did not produce a bundle")
        return bundle

    def _build_context(self, reference: SourceReference) -> TransformContext:
        mission = self._mission
        primary_topic_override = self._options.get("primary_topic")
        if isinstance(primary_topic_override, str) and primary_topic_override.strip():
            primary_topic = slugify(primary_topic_override)
        elif mission is not None:
            primary_topic = slugify(mission.mission.title)
        else:
            primary_topic = "source"

        findability = _coerce_optional_float(self._options.get("findability_baseline"))
        completeness = _coerce_optional_float(self._options.get("completeness_baseline"))
        depth = _coerce_optional_int(self._options.get("depth"))

        if mission is not None:
            secondary_topics = tuple(slugify(value) for value in mission.information_architecture.organization_types)
            default_tags = (slugify(mission.mission.title),)
            audience = mission.mission.audience
            if findability is None:
                findability = mission.information_architecture.quality_standards.min_findability
            if completeness is None:
                completeness = mission.information_architecture.quality_standards.min_completeness
            if depth is None:
                depth = mission.information_architecture.quality_standards.link_depth
        else:
            secondary_topics = ()
            default_tags = (primary_topic,)
            audience = ("general",)
            if findability is None:
                findability = 0.6
            if completeness is None:
                completeness = 0.7
            if depth is None:
                depth = 3

        return TransformContext(
            primary_topic=primary_topic,
            secondary_topics=secondary_topics,
            default_tags=default_tags,
            audience=audience,
            source_references=(reference,),
            findability_baseline=float(findability),
            completeness_baseline=float(completeness),
            depth=int(depth),
            timestamp=datetime.utcnow(),
        )


class OrganizationStage:
    """Persist transformed documents into the knowledge base."""

    name = "organization"

    def __init__(self, organizer: KBOrganizer, *, ensure_indexes: bool) -> None:
        self._organizer = organizer
        self._ensure_indexes = ensure_indexes

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:
        del previous
        transformation = _get_section(context, "transformation")
        documents = transformation.get("documents", ())
        if not isinstance(documents, Sequence) or not documents:
            return StageResult(stage=self.name, metrics={"documents": 0.0})

        written: list[Path] = []
        artifacts: list[DocumentArtifact] = []
        for document in documents:
            if not isinstance(document, KBDocument):
                raise PipelineStageError("transformation stage produced an invalid document payload")
            try:
                path = self._organizer.place_document(document, context.kb_root)
            except Exception as exc:  # noqa: BLE001 - wrapped into pipeline error
                raise PipelineStageError(f"Failed to place document {document.kb_id}: {exc}") from exc
            written.append(path)
            artifacts.append(
                DocumentArtifact(
                    kb_id=document.kb_id,
                    path=path,
                    doc_type=document.metadata.doc_type,
                    metadata={"title": document.title},
                )
            )

        if self._ensure_indexes:
            self._organizer.ensure_indexes(context.kb_root)

        _ensure_section(context, "organization")["paths"] = tuple(written)
        metrics = {"documents": float(len(written))}
        return StageResult(stage=self.name, artifacts=tuple(artifacts), metrics=metrics)


@dataclass(slots=True)
class LinkingOptions:
    build_graph: bool
    generate_backlinks: bool
    min_similarity: float


class ConditionalLinkingStage:
    """Linking stage that honours workflow configuration flags."""

    name = "linking"

    def __init__(self, builder: LinkBuilder, options: LinkingOptions) -> None:
        self._builder = builder
        self._options = options

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:
        del previous
        metrics: dict[str, float] = {}
        notes: list[str] = []

        if self._options.build_graph:
            graph = self._builder.build_concept_graph(context.kb_root)
            metrics["concepts"] = float(len(graph.concepts))
            metrics["edges"] = float(len(graph.edges))
            notes.extend(f"edge:{edge.source}->{edge.target}" for edge in graph.edges[:3])
        if self._options.generate_backlinks:
            backlinks = self._builder.generate_backlinks(context.kb_root)
            metrics["backlinks_updated"] = float(len(backlinks))
            notes.extend(f"backlink:{kb_id}" for kb_id in backlinks[:3])
        if not metrics:
            notes.append("linking-disabled")
        return StageResult(stage=self.name, metrics=metrics, notes=tuple(notes))


# ---------------------------------------------------------------------------
# Workflow assembly
# ---------------------------------------------------------------------------


def _normalize_collision_strategy(value: Any) -> str:
    token = str(value).strip().lower()
    if token == "append_hash":
        return "backup"
    if token in {"", "backup", "replace", "error"}:
        return token or "backup"
    return "backup"


def _build_extraction_coordinator(section: Mapping[str, Any]) -> tuple[ExtractionCoordinator, ExtractionConfig]:
    enabled_raw = section.get("enabled_tools")
    if isinstance(enabled_raw, str):
        enabled_tools = (enabled_raw,)
    elif isinstance(enabled_raw, Sequence):
        enabled_tools = tuple(str(item) for item in enabled_raw)
    else:
        enabled_tools = ()

    config_raw = section.get("config") if isinstance(section, Mapping) else None
    if isinstance(config_raw, Mapping):
        extraction_config = ExtractionConfig.from_mapping(config_raw)
    else:
        extraction_config = load_default_or_empty()

    coordinator = ExtractionCoordinator(
        enabled_tools=enabled_tools,
        parallel_execution=bool(section.get("parallel_execution", True)),
        cache_results=bool(section.get("cache_results", True)),
        cache_ttl=_coerce_optional_float(section.get("cache_ttl"), default=86_400.0),
    )
    return coordinator, extraction_config


def _build_organizer(section: Mapping[str, Any]) -> tuple[KBOrganizer, bool]:
    collision_strategy = _normalize_collision_strategy(section.get("collision_strategy", "backup"))
    auto_index = str(section.get("index_generation", "auto")).lower() == "auto"
    organizer = KBOrganizer(collision_strategy=collision_strategy, auto_index=auto_index)
    ensure_indexes = not auto_index
    return organizer, ensure_indexes


def _build_linking(section: Mapping[str, Any]) -> tuple[LinkBuilder, LinkingOptions]:
    build_graph = bool(section.get("build_concept_graph", True))
    generate_backlinks = bool(section.get("generate_backlinks", True))
    min_similarity = _coerce_float(section.get("similarity_threshold"), default=0.05)
    builder = LinkBuilder(min_similarity=min_similarity)
    options = LinkingOptions(build_graph=build_graph, generate_backlinks=generate_backlinks, min_similarity=min_similarity)
    return builder, options


def _build_quality_analyzer(
    section: Mapping[str, Any],
    *,
    completeness_override: float | None = None,
    findability_override: float | None = None,
    min_body_length_override: int | None = None,
) -> QualityAnalyzer:
    completeness = _coerce_float(section.get("required_completeness"), default=0.7)
    findability = _coerce_float(section.get("required_findability"), default=0.6)
    min_body_length = _coerce_int(section.get("min_body_length"), default=80)

    if completeness_override is not None:
        completeness = float(completeness_override)
    if findability_override is not None:
        findability = float(findability_override)
    if min_body_length_override is not None:
        min_body_length = int(min_body_length_override)

    return QualityAnalyzer(
        min_body_length=min_body_length,
        completeness_floor=completeness,
        findability_floor=findability,
    )


def build_process_pipeline(
    config: PipelineConfig,
    *,
    mission: MissionConfig | None,
    validate: bool,
) -> KBPipeline:
    coordinator, extraction_config = _build_extraction_coordinator(config.extraction)
    organizer, ensure_indexes = _build_organizer(config.organization)
    builder, linking_options = _build_linking(config.linking)
    transformer = KBTransformer()

    stages: list[PipelineStage] = [
        SourceAnalysisStage(),
        ExtractionStage(coordinator, config=extraction_config),
        TransformationStage(transformer, mission=mission, options=config.transformation),
        OrganizationStage(organizer, ensure_indexes=ensure_indexes),
    ]

    if linking_options.build_graph or linking_options.generate_backlinks:
        stages.append(ConditionalLinkingStage(builder, linking_options))

    quality_required = bool(config.quality.get("validate_on_creation", False)) or validate
    if quality_required:
        analyzer = _build_quality_analyzer(config.quality)
        stages.append(QualityStage(analyzer))

    return KBPipeline(tuple(stages))


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------


def _resolve_metrics_path(pipeline_config: PipelineConfig, override: Path | None) -> Path | None:
    if override is not None:
        return override.expanduser()
    configured = pipeline_config.metrics_output
    if configured is None:
        return None
    return configured.expanduser()


def _flatten_stage_metrics(stages: Sequence[StageResult]) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for stage in stages:
        for key, value in stage.metrics.items():
            aggregated[f"{stage.stage}.{key}"] = value
    return aggregated


def _write_metrics(path: Path, result: KBProcessingResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "success": result.success,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "metrics": _flatten_stage_metrics(result.stages),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_update_metrics(path: Path, result: KBUpdateResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kb_id": result.kb_id,
        "success": result.success,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "metrics": _flatten_stage_metrics(result.stages),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _summarize_durations(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {
            "iterations": 0,
            "total_seconds": 0.0,
            "mean_seconds": 0.0,
            "median_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
        }

    total = sum(values)
    mean = total / len(values)
    median = statistics.median(values)
    fastest = min(values)
    slowest = max(values)

    return {
        "iterations": len(values),
        "total_seconds": round(total, 6),
        "mean_seconds": round(mean, 6),
        "median_seconds": round(median, 6),
        "min_seconds": round(fastest, 6),
        "max_seconds": round(slowest, 6),
    }


@dataclass(slots=True)
class ProcessOptions:
    """Input options for the process workflow."""

    source_path: Path
    kb_root: Path
    mission_path: Path | None
    extractors: Sequence[str] | None = None
    validate: bool = False
    metrics_path: Path | None = None


def run_process_workflow(
    options: ProcessOptions,
    *,
    config: PipelineConfig | None = None,
    mission: MissionConfig | None = None,
) -> KBProcessingResult:
    pipeline_config = config or load_pipeline_config(None)
    mission_config = mission

    if mission_config is None and options.mission_path is not None:
        from src.knowledge_base.config import load_mission_config

        mission_config = load_mission_config(options.mission_path)

    options.kb_root.mkdir(parents=True, exist_ok=True)

    pipeline = build_process_pipeline(pipeline_config, mission=mission_config, validate=options.validate)
    result = pipeline.process_source(
        options.source_path,
        kb_root=options.kb_root,
        mission_config=options.mission_path,
        extractors=options.extractors,
        validate=options.validate,
        extra={"mission": mission_config, "pipeline_config": pipeline_config},
    )

    metrics_path = _resolve_metrics_path(pipeline_config, options.metrics_path)
    if metrics_path is not None:
        _write_metrics(metrics_path, result)

    return result


@dataclass(slots=True)
class UpdateOptions:
    """Input options for the update workflow."""

    kb_id: str
    source_path: Path
    kb_root: Path
    mission_path: Path | None
    extractors: Sequence[str] | None = None
    validate: bool = False
    reextract: bool = True
    rebuild_links: bool = False
    metrics_path: Path | None = None


def _prepare_update_config(config: PipelineConfig, *, rebuild_links: bool) -> PipelineConfig:
    payload = config.to_dict()
    pipeline_section = payload.setdefault("pipeline", {})
    linking_section = pipeline_section.setdefault("linking", {})
    toggle = bool(rebuild_links)
    linking_section["build_concept_graph"] = toggle
    linking_section["generate_backlinks"] = toggle
    return PipelineConfig.from_mapping(payload)


def run_update_workflow(
    options: UpdateOptions,
    *,
    config: PipelineConfig | None = None,
    mission: MissionConfig | None = None,
) -> KBUpdateResult:
    pipeline_config = config or load_pipeline_config(None)
    mission_config = mission

    if mission_config is None and options.mission_path is not None:
        from src.knowledge_base.config import load_mission_config

        mission_config = load_mission_config(options.mission_path)

    options.kb_root.mkdir(parents=True, exist_ok=True)

    existing_document = _load_existing_document(options.kb_root, options.kb_id)
    if existing_document is None:
        raise FileNotFoundError(
            f"Knowledge base document '{options.kb_id}' not found under '{options.kb_root}'"
        )

    effective_config = _prepare_update_config(pipeline_config, rebuild_links=options.rebuild_links)
    pipeline = build_process_pipeline(effective_config, mission=mission_config, validate=options.validate)

    extra: dict[str, Any] = {
        "mission": mission_config,
        "pipeline_config": pipeline_config,
        "update": {
            "target_kb_id": options.kb_id,
            "reextract": options.reextract,
            "rebuild_links": options.rebuild_links,
            "existing_document": existing_document,
        },
    }

    context = ProcessingContext(
        options.source_path,
        options.kb_root,
        options.mission_path,
        tuple(options.extractors or ()),
        options.validate,
        extra,
    )

    result = pipeline.update_existing(options.kb_id, context=context)

    metrics_path = _resolve_metrics_path(effective_config, options.metrics_path)
    if metrics_path is not None:
        _write_update_metrics(metrics_path, result)

    return result


@dataclass(slots=True)
class BenchmarkOptions:
    """Options for benchmarking the knowledge base pipeline."""

    source_path: Path
    iterations: int = 3
    mission_path: Path | None = None
    extractors: Sequence[str] | None = None
    validate: bool = False
    scratch_root: Path | None = None
    retain_artifacts: bool = False


@dataclass(frozen=True, slots=True)
class KBBenchmarkIteration:
    """Captured metrics for a single benchmark iteration."""

    iteration: int
    duration_seconds: float
    stage_durations: Mapping[str, float]
    documents: float
    warnings: Sequence[str]
    errors: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_durations", dict(self.stage_durations))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))

    @property
    def success(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class KBBenchmarkResult:
    """Aggregated benchmark statistics across iterations."""

    source_path: Path
    iterations: Sequence[KBBenchmarkIteration]
    total_summary: Mapping[str, float]
    stage_summaries: Mapping[str, Mapping[str, float]]
    stage_names: Sequence[str]
    artifacts_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "iterations", tuple(self.iterations))
        object.__setattr__(self, "total_summary", dict(self.total_summary))
        object.__setattr__(self, "stage_summaries", {key: dict(value) for key, value in self.stage_summaries.items()})
        object.__setattr__(self, "stage_names", tuple(self.stage_names))

    @property
    def success(self) -> bool:
        return all(iteration.success for iteration in self.iterations)

    @property
    def iteration_count(self) -> int:
        return len(self.iterations)


def run_benchmark_workflow(
    options: BenchmarkOptions,
    *,
    config: PipelineConfig | None = None,
    mission: MissionConfig | None = None,
) -> KBBenchmarkResult:
    if options.iterations <= 0:
        raise ValueError("iterations must be a positive integer")

    pipeline_config = config or load_pipeline_config(None)

    config_payload = pipeline_config.to_dict()
    monitoring = dict(config_payload.get("monitoring", {}))
    monitoring.pop("metrics_output", None)
    config_payload["monitoring"] = monitoring
    benchmark_config = PipelineConfig.from_mapping(config_payload)

    mission_config = mission
    if mission_config is None and options.mission_path is not None:
        from src.knowledge_base.config import load_mission_config

        mission_config = load_mission_config(options.mission_path)

    source_path = options.source_path.expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"source_path '{source_path}' does not exist")

    if options.mission_path is not None and mission_config is None:
        raise ValueError("Mission configuration could not be loaded")

    if options.scratch_root is None:
        scratch_root = Path(tempfile.mkdtemp(prefix="kb-benchmark-"))
        cleanup_root = not options.retain_artifacts
    else:
        scratch_root = options.scratch_root.expanduser()
        scratch_root.mkdir(parents=True, exist_ok=True)
        cleanup_root = False

    iterations: list[KBBenchmarkIteration] = []
    total_samples: list[float] = []
    stage_samples: defaultdict[str, list[float]] = defaultdict(list)

    for index in range(1, options.iterations + 1):
        iteration_root = scratch_root / f"iteration-{index:02d}"
        if iteration_root.exists():
            shutil.rmtree(iteration_root, ignore_errors=True)
        iteration_root.mkdir(parents=True, exist_ok=True)

        pipeline = build_process_pipeline(benchmark_config, mission=mission_config, validate=options.validate)

        started = perf_counter()
        result = pipeline.process_source(
            source_path,
            kb_root=iteration_root,
            mission_config=options.mission_path,
            extractors=options.extractors,
            validate=options.validate,
            extra={"mission": mission_config, "pipeline_config": benchmark_config},
        )
        duration = perf_counter() - started

        total_samples.append(duration)

        stage_durations: dict[str, float] = {}
        for stage in result.stages:
            stage_duration = float(stage.metrics.get("duration_seconds", 0.0))
            stage_durations[stage.stage] = stage_duration
            stage_samples[stage.stage].append(stage_duration)

        documents = 0.0
        for stage in result.stages:
            documents += float(stage.metrics.get("documents", 0.0))

        iterations.append(
            KBBenchmarkIteration(
                iteration=index,
                duration_seconds=round(duration, 6),
                stage_durations=stage_durations,
                documents=documents,
                warnings=result.warnings,
                errors=result.errors,
            )
        )

        if not options.retain_artifacts:
            shutil.rmtree(iteration_root, ignore_errors=True)

    stage_names = tuple(iterations[0].stage_durations.keys()) if iterations else tuple()
    total_summary = _summarize_durations(total_samples)
    stage_summaries = {stage: _summarize_durations(values) for stage, values in stage_samples.items()}

    if cleanup_root:
        shutil.rmtree(scratch_root, ignore_errors=True)

    return KBBenchmarkResult(
        source_path=source_path,
        iterations=tuple(iterations),
        total_summary=total_summary,
        stage_summaries=stage_summaries,
        stage_names=stage_names,
        artifacts_root=scratch_root,
    )


@dataclass(slots=True)
class ImproveOptions:
    """Options for the quality improvement workflow."""

    kb_root: Path
    min_completeness: float | None = None
    min_findability: float | None = None
    fix_links: bool = False
    suggest_tags: bool = False
    report_path: Path | None = None


def run_improve_workflow(
    options: ImproveOptions,
    *,
    config: PipelineConfig | None = None,
) -> KBImprovementResult:
    pipeline_config = config or load_pipeline_config(None)

    kb_root = options.kb_root.expanduser()
    if not kb_root.exists():
        raise FileNotFoundError(f"kb_root '{kb_root}' does not exist")

    analyzer = _build_quality_analyzer(
        pipeline_config.quality,
        completeness_override=options.min_completeness,
        findability_override=options.min_findability,
    )
    gaps = tuple(analyzer.identify_gaps(kb_root))

    builder, _ = _build_linking(pipeline_config.linking)
    graph = builder.build_concept_graph(kb_root)

    metrics: dict[str, float] = {
        "gaps_total": float(len(gaps)),
        "gaps_errors": float(sum(1 for gap in gaps if gap.severity == "error")),
        "gaps_warnings": float(sum(1 for gap in gaps if gap.severity == "warning")),
        "gaps_info": float(
            sum(1 for gap in gaps if gap.severity not in {"error", "warning"})
        ),
        "concepts": float(len(graph.concepts)),
        "edges": float(len(graph.edges)),
    }

    fixes_applied: list[str] = []
    if options.fix_links:
        backlinks = builder.generate_backlinks(kb_root)
        metrics["backlinks_updated"] = float(len(backlinks))
        fixes_applied.append(f"backlinks:{len(backlinks)}")

    suggestions = _build_gap_suggestions(
        gaps,
        builder=builder,
        suggest_tags=options.suggest_tags,
    )

    report_path = options.report_path.expanduser() if options.report_path else None

    result = KBImprovementResult(
        kb_root=kb_root,
        gaps=gaps,
        fixes_applied=tuple(fixes_applied),
        suggestions=suggestions,
        metrics=metrics,
        report_path=report_path,
    )

    if report_path is not None:
        _write_improvement_report(report_path, result)

    return result


def _summarize_metric(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {
            "count": 0.0,
            "total": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "stdev": 0.0,
        }

    total = float(sum(values))
    count = float(len(values))
    mean = statistics.mean(values)
    median = statistics.median(values)
    minimum = min(values)
    maximum = max(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0

    return {
        "count": count,
        "total": round(total, 6),
        "mean": round(mean, 6),
        "median": round(median, 6),
        "min": round(minimum, 6),
        "max": round(maximum, 6),
        "stdev": round(float(stdev), 6),
    }


@dataclass(slots=True)
class QualityReportOptions:
    """Options for the knowledge base quality report workflow."""

    kb_root: Path
    output_path: Path | None = None
    min_completeness: float | None = None
    min_findability: float | None = None
    min_body_length: int | None = None
    include_meta: bool = False


def run_quality_report_workflow(
    options: QualityReportOptions,
    *,
    config: PipelineConfig | None = None,
) -> KBQualityReportResult:
    pipeline_config = config or load_pipeline_config(None)

    kb_root = options.kb_root.expanduser()
    if not kb_root.exists():
        raise FileNotFoundError(f"kb_root '{kb_root}' does not exist")

    analyzer = _build_quality_analyzer(
        pipeline_config.quality,
        completeness_override=options.min_completeness,
        findability_override=options.min_findability,
        min_body_length_override=options.min_body_length,
    )

    documents_total = 0
    document_types: Counter[str] = Counter()
    completeness_samples: list[float] = []
    findability_samples: list[float] = []
    sources_samples: list[float] = []
    tags_samples: list[float] = []
    body_length_samples: list[float] = []
    invalid_documents: list[dict[str, Any]] = []

    for path in sorted(kb_root.rglob("*.md")):
        relative = path.relative_to(kb_root)
        if not relative.parts:
            continue
        if relative.parts[0].startswith("."):
            continue
        if not options.include_meta and relative.parts[0] == "meta":
            continue

        try:
            front, body = _parse_markdown(path)
        except PipelineStageError as exc:
            invalid_documents.append({"path": str(path), "reason": str(exc)})
            continue

        if not front:
            invalid_documents.append({"path": str(path), "reason": "missing front matter"})
            continue

        try:
            document = _build_document_from_front(front, body, path=path)
        except ValueError as exc:
            invalid_documents.append({"path": str(path), "reason": str(exc)})
            continue

        try:
            completeness = analyzer.calculate_completeness(document)
        except Exception as exc:  # pragma: no cover - defensive guard
            invalid_documents.append(
                {"path": str(path), "kb_id": document.kb_id, "reason": f"completeness: {exc}"}
            )
            continue

        try:
            findability = analyzer.calculate_findability(document.kb_id, kb_root)
        except Exception as exc:  # pragma: no cover - defensive guard
            invalid_documents.append(
                {"path": str(path), "kb_id": document.kb_id, "reason": f"findability: {exc}"}
            )
            continue

        documents_total += 1
        document_types[document.metadata.doc_type] += 1
        completeness_samples.append(float(completeness))
        findability_samples.append(float(findability))
        sources_samples.append(float(len(document.metadata.sources)))
        tags_samples.append(float(len(document.metadata.tags)))
        body_length_samples.append(float(len((document.body or "").strip())))

    gaps = tuple(analyzer.identify_gaps(kb_root))
    gap_counts: dict[str, int] = {"total": len(gaps)}
    gap_counts.update(Counter(gap.severity for gap in gaps))

    generated_at = datetime.utcnow()
    if options.output_path is not None:
        output_path = options.output_path.expanduser()
    else:
        timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        output_path = kb_root / "reports" / f"kb-quality-report-{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    completeness_stats = _summarize_metric(completeness_samples)
    findability_stats = _summarize_metric(findability_samples)
    sources_stats = _summarize_metric(sources_samples)
    tags_stats = _summarize_metric(tags_samples)
    body_stats = _summarize_metric(body_length_samples)

    completeness_stats["missing"] = float(max(0, documents_total - len(completeness_samples)))
    findability_stats["missing"] = float(max(0, documents_total - len(findability_samples)))

    metrics: dict[str, dict[str, float]] = {
        "completeness": completeness_stats,
        "findability": findability_stats,
        "sources_per_document": sources_stats,
        "tags_per_document": tags_stats,
        "body_length_characters": body_stats,
    }

    gap_payload: list[dict[str, Any]] = []
    for gap in gaps:
        details = {
            key: (str(value) if isinstance(value, Path) else value)
            for key, value in gap.details.items()
        }
        gap_payload.append(
            {
                "kb_id": gap.kb_id,
                "issue": gap.issue,
                "severity": gap.severity,
                "details": details,
            }
        )

    invalid_payload = [
        {
            **{key: (str(value) if isinstance(value, Path) else value) for key, value in entry.items()},
        }
        for entry in invalid_documents
    ]

    document_types_payload = dict(sorted(document_types.items()))

    report_payload = {
        "generated_at": generated_at.replace(microsecond=0).isoformat() + "Z",
        "kb_root": str(kb_root),
        "documents": {
            "total": documents_total,
            "by_type": document_types_payload,
        },
        "metrics": metrics,
        "gaps": {
            "counts": gap_counts,
            "items": gap_payload,
        },
        "invalid_documents": invalid_payload,
        "output_path": str(output_path),
    }

    output_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

    result = KBQualityReportResult(
        kb_root=kb_root,
        output_path=output_path,
        generated_at=generated_at,
        documents_total=documents_total,
        document_types=document_types_payload,
        metrics={name: {metric: float(value) for metric, value in stats.items()} for name, stats in metrics.items()},
        gap_counts=gap_counts,
        gaps=gaps,
        invalid_documents=invalid_payload,
    )
    return result


@dataclass(slots=True)
class ExportGraphOptions:
    """Options for exporting the knowledge graph."""

    kb_root: Path
    output_path: Path
    format: str = "json"


def run_export_graph_workflow(
    options: ExportGraphOptions,
    *,
    config: PipelineConfig | None = None,
) -> KBGraphExportResult:
    pipeline_config = config or load_pipeline_config(None)

    kb_root = options.kb_root.expanduser()
    if not kb_root.exists():
        raise FileNotFoundError(f"kb_root '{kb_root}' does not exist")

    builder, _ = _build_linking(pipeline_config.linking)
    graph = builder.build_concept_graph(kb_root)

    fmt = options.format.lower()
    output_path = options.output_path.expanduser()

    if fmt == "json":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = graph.manifest()
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    elif fmt in {"graphml", "gml"}:
        _export_graph_to_graphml(graph, output_path)
    elif fmt in {"dot", "graphviz"}:
        _export_graph_to_dot(graph, output_path)
    elif fmt in {"csv", "edge-list", "edgelist"}:
        _export_graph_to_csv(graph, output_path)
    else:
        raise ValueError(f"Unsupported graph export format: {options.format}")

    return KBGraphExportResult(
        kb_root=kb_root,
        output_path=output_path,
        format=fmt,
        nodes=len(graph.concepts),
        edges=len(graph.edges),
    )


__all__ = [
    "ProcessOptions",
    "build_process_pipeline",
    "run_process_workflow",
    "UpdateOptions",
    "run_update_workflow",
    "BenchmarkOptions",
    "run_benchmark_workflow",
    "KBBenchmarkResult",
    "ImproveOptions",
    "run_improve_workflow",
    "QualityReportOptions",
    "run_quality_report_workflow",
    "ExportGraphOptions",
    "run_export_graph_workflow",
]
