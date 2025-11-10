"""Transformation layer for the knowledge base engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from src.extraction import ExtractedConcept, ExtractedEntity
from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)
from src.knowledge_base.metadata import assert_quality_thresholds
from .utils import slugify


def _dedupe_preserve_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class TransformContext:
    """Configuration shared when transforming extraction outputs."""

    primary_topic: str
    source_references: Sequence[SourceReference]
    secondary_topics: Sequence[str] = field(default_factory=tuple)
    default_tags: Sequence[str] = field(default_factory=tuple)
    audience: Sequence[str] = field(default_factory=lambda: ("general",))
    language: str = "en"
    concept_root: str = "concepts"
    entity_root: str = "entities"
    entity_type_mapping: Mapping[str, str] = field(
        default_factory=lambda: {"PERSON": "people", "ORG": "organizations", "DATE": "timeline"}
    )
    findability_baseline: float = 0.75
    completeness_baseline: float = 0.85
    depth: int = 3
    update_frequency: str | None = "quarterly"
    timestamp: datetime | None = None

    def __post_init__(self) -> None:  # noqa: D401 - dataclass validation
        if not self.source_references:
            raise ValueError("TransformContext requires at least one source reference.")
        normalised_primary = slugify(self.primary_topic)
        normalised_secondary = _dedupe_preserve_order(
            slugify(value) for value in self.secondary_topics if str(value).strip()
        )
        normalised_tags = _dedupe_preserve_order(
            slugify(value) for value in self.default_tags if str(value).strip()
        )
        normalised_audience = _dedupe_preserve_order(
            slugify(value) for value in self.audience if str(value).strip()
        )
        normalised_concept_root = slugify(self.concept_root)
        normalised_entity_root = slugify(self.entity_root)

        mapping: dict[str, str] = {}
        for raw_key, raw_value in self.entity_type_mapping.items():
            key = str(raw_key).strip().upper()
            if not key:
                continue
            label = str(raw_value).strip()
            mapping[key] = slugify(label or key.lower())

        if not 0.0 <= self.findability_baseline <= 1.0:
            raise ValueError("findability_baseline must be within [0.0, 1.0].")
        if not 0.0 <= self.completeness_baseline <= 1.0:
            raise ValueError("completeness_baseline must be within [0.0, 1.0].")
        if self.depth <= 0:
            raise ValueError("depth must be positive.")

        references: list[SourceReference] = []
        for ref in self.source_references:
            if not isinstance(ref, SourceReference):  # pragma: no cover - defensive
                raise TypeError("source_references must contain SourceReference instances.")
            references.append(ref)

        object.__setattr__(self, "primary_topic", normalised_primary)
        object.__setattr__(self, "secondary_topics", normalised_secondary)
        object.__setattr__(self, "default_tags", normalised_tags)
        object.__setattr__(self, "audience", normalised_audience)
        object.__setattr__(self, "concept_root", normalised_concept_root)
        object.__setattr__(self, "entity_root", normalised_entity_root)
        object.__setattr__(self, "entity_type_mapping", mapping)
        object.__setattr__(self, "source_references", tuple(references))
        object.__setattr__(self, "language", self.language.lower())


class KBTransformer:
    """Converts extraction results to structured knowledge base documents."""

    def create_concept_document(self, concept: ExtractedConcept, context: TransformContext) -> KBDocument:
        """Generate a concept document from extracted data."""

        slug = slugify(concept.term)
        kb_id = f"{context.concept_root}/{context.primary_topic}/{slug}"
        related_concepts = self._related_concept_ids(concept.related_terms, context)
        tags = self._build_tags(context, extra=(slug,))
        metadata = self._build_metadata(
            title=concept.term,
            description=concept.definition or self._default_concept_description(concept),
            kb_id=kb_id,
            doc_type="concept",
            primary_topic=context.primary_topic,
            navigation_path=(context.concept_root, context.primary_topic, slug),
            related_by_topic=related_concepts,
            related_by_entity=(),
            context=context,
            tags=tags,
        )

        body = self._render_concept_body(concept)
        document = KBDocument(
            kb_id=kb_id,
            slug=slug,
            title=concept.term,
            metadata=metadata,
            related_concepts=related_concepts,
            body=body,
        )
        document.validate()
        assert_quality_thresholds(metadata)
        return document

    def create_entity_document(self, entity: ExtractedEntity, context: TransformContext) -> KBDocument:
        """Generate an entity document from extracted data."""

        category = self._map_entity_type(entity.entity_type, context)
        slug = slugify(entity.text)
        kb_id = f"{context.entity_root}/{category}/{slug}"
        related_concepts = self._related_concept_ids(
            self._extract_related_concepts(entity.metadata), context
        )
        related_entities = self._normalise_kb_ids(self._extract_related_entities(entity.metadata))
        tags = self._build_tags(context, extra=(category, slug))
        aliases = self._extract_aliases(entity.metadata)
        description = self._default_entity_description(entity)

        metadata = self._build_metadata(
            title=entity.text,
            description=description,
            kb_id=kb_id,
            doc_type="entity",
            primary_topic=category,
            navigation_path=(context.entity_root, category, slug),
            related_by_topic=related_concepts,
            related_by_entity=related_entities,
            context=context,
            tags=tags,
        )

        body = self._render_entity_body(entity)
        document = KBDocument(
            kb_id=kb_id,
            slug=slug,
            title=entity.text,
            metadata=metadata,
            aliases=aliases,
            related_concepts=related_concepts,
            body=body,
        )
        document.validate()
        assert_quality_thresholds(metadata)
        return document

    # Helpers ---------------------------------------------------------

    def _build_metadata(
        self,
        *,
        title: str,
        description: str,
        kb_id: str,
        doc_type: str,
        primary_topic: str,
        navigation_path: Sequence[str],
        related_by_topic: Sequence[str],
        related_by_entity: Sequence[str],
        context: TransformContext,
        tags: Sequence[str],
    ) -> KBMetadata:
        dc = DublinCoreMetadata(
            title=title,
            subject=(primary_topic,),
            description=description,
            identifier=kb_id,
            language=context.language,
            source=context.source_references[0].kb_id,
        )
        ia = IAMetadata(
            findability_score=self._score_with_bonus(context.findability_baseline, related_by_topic),
            completeness=context.completeness_baseline,
            depth=context.depth,
            audience=context.audience,
            navigation_path=tuple(navigation_path),
            related_by_topic=tuple(related_by_topic),
            related_by_entity=tuple(related_by_entity),
            last_updated=context.timestamp or datetime.utcnow(),
            update_frequency=context.update_frequency,
        )
        metadata = KBMetadata(
            doc_type=doc_type,
            primary_topic=primary_topic,
            secondary_topics=context.secondary_topics,
            tags=tags,
            dc=dc,
            ia=ia,
            sources=context.source_references,
        )
        metadata.validate()
        return metadata

    @staticmethod
    def _score_with_bonus(baseline: float, related: Sequence[str]) -> float:
        bonus = min(0.2, 0.02 * len(related))
        score = baseline + bonus
        return min(1.0, round(score, 2))

    @staticmethod
    def _default_concept_description(concept: ExtractedConcept) -> str:
        occurrence = "occurrence" if concept.frequency == 1 else "occurrences"
        return f"Concept detected with {concept.frequency} {occurrence} in source."

    @staticmethod
    def _default_entity_description(entity: ExtractedEntity) -> str:
        return (
            f"Entity '{entity.text}' detected as {entity.entity_type.title()} "
            f"with confidence {entity.confidence:.2f}."
        )

    @staticmethod
    def _render_concept_body(concept: ExtractedConcept) -> str:
        lines: list[str] = [f"# {concept.term}", ""]
        lines.append(f"**Frequency:** {concept.frequency}")
        if concept.positions:
            position_preview = ", ".join(str(pos) for pos in concept.positions[:10])
            lines.append(f"**Positions:** {position_preview}")
        if concept.definition:
            lines.extend(["", "## Definition", concept.definition])
        if concept.related_terms:
            lines.extend(["", "## Related Terms"])
            for term in concept.related_terms:
                lines.append(f"- {term}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_entity_body(entity: ExtractedEntity) -> str:
        lines: list[str] = [f"# {entity.text}", ""]
        lines.append(f"**Type:** {entity.entity_type.title()}")
        lines.append(f"**Confidence:** {entity.confidence:.2f}")
        if entity.metadata:
            lines.extend(["", "## Attributes"])
            for key, value in sorted(entity.metadata.items()):
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        return "\n".join(lines) + "\n"

    def _build_tags(self, context: TransformContext, *, extra: Sequence[str]) -> tuple[str, ...]:
        tokens = list(context.default_tags)
        tokens.extend(extra)
        normalised = [slugify(token) for token in tokens if token]
        return _dedupe_preserve_order(normalised)

    def _map_entity_type(self, entity_type: str, context: TransformContext) -> str:
        key = entity_type.upper()
        mapped = context.entity_type_mapping.get(key)
        if mapped is not None:
            return mapped
        return slugify(entity_type)

    def _related_concept_ids(self, terms: Sequence[str], context: TransformContext) -> tuple[str, ...]:
        related: list[str] = []
        for term in terms:
            term = term.strip()
            if not term:
                continue
            if "/" in term:
                related.append(term)
                continue
            related.append(f"{context.concept_root}/{context.primary_topic}/{slugify(term)}")
        return _dedupe_preserve_order(related)

    @staticmethod
    def _extract_related_concepts(metadata: Mapping[str, object]) -> Sequence[str]:
        raw = metadata.get("related_concepts")
        if raw is None:
            return ()
        if isinstance(raw, str):
            return (raw,)
        try:
            return tuple(str(value) for value in raw)  # type: ignore[arg-type]
        except TypeError:
            return ()

    @staticmethod
    def _extract_related_entities(metadata: Mapping[str, object]) -> Sequence[str]:
        raw = metadata.get("related_entities")
        if raw is None:
            return ()
        if isinstance(raw, str):
            return (raw,)
        try:
            return tuple(str(value) for value in raw)  # type: ignore[arg-type]
        except TypeError:
            return ()

    @staticmethod
    def _extract_aliases(metadata: Mapping[str, object]) -> tuple[str, ...]:
        aliases = []
        for key in ("aliases", "alternate_names", "also_known_as"):
            raw = metadata.get(key)
            if raw is None:
                continue
            if isinstance(raw, str):
                aliases.append(raw.strip())
                continue
            try:
                aliases.extend(str(value).strip() for value in raw)  # type: ignore[arg-type]
            except TypeError:
                continue
        aliases = [alias for alias in aliases if alias]
        return _dedupe_preserve_order(aliases)

    @staticmethod
    def _normalise_kb_ids(values: Sequence[str]) -> tuple[str, ...]:
        cleaned = []
        for value in values:
            token = value.strip()
            if not token:
                continue
            cleaned.append(token)
        return _dedupe_preserve_order(cleaned)
