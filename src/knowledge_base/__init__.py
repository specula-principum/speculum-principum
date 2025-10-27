"""Core data models for knowledge base information architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

import re

__all__ = [
    "DublinCoreMetadata",
    "IAMetadata",
    "KBMetadata",
    "KBDocument",
    "KBRelationship",
    "SourceReference",
    "Taxonomy",
    "TaxonomyTopic",
    "EntityType",
    "RelationshipType",
    "VocabularyTerm",
    "MissionConfig",
    "MissionDetails",
    "InformationArchitecturePlan",
    "LabelingConventions",
    "SearchOptimization",
    "QualityStandards",
    "load_mission_config",
]

_SEGMENT_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _ensure_kebab_case(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} is required.")
    if not _SEGMENT_PATTERN.match(value):
        raise ValueError(f"{label} must be kebab-case: {value!r}")


def _ensure_kb_path(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} is required.")
    for segment in value.split("/"):
        _ensure_kebab_case(segment, f"{label} segment")


def _dedupe_str_sequence(*, values: Sequence[str], label: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if not item:
            raise ValueError(f"{label} entries cannot be blank.")
        if item in seen:
            raise ValueError(f"{label} entries must be unique: {item!r}")
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


@dataclass(slots=True)
class SourceReference:
    """Reference to a source artifact inside the knowledge base."""

    kb_id: str
    pages: Sequence[int] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kb_id", self.kb_id.strip())
        object.__setattr__(self, "pages", tuple(self.pages))

    def validate(self) -> None:
        _ensure_kb_path(self.kb_id, "source kb_id")
        for page in self.pages:
            if not isinstance(page, int) or page <= 0:
                raise ValueError("Source reference pages must be positive integers.")


@dataclass(slots=True)
class DublinCoreMetadata:
    """Subset of Dublin Core metadata used by the project."""

    title: str
    creator: str | None = None
    subject: Sequence[str] = field(default_factory=tuple)
    description: str | None = None
    publisher: str | None = None
    contributor: Sequence[str] = field(default_factory=tuple)
    date: str | None = None
    doc_type: str | None = None
    format: str | None = None
    identifier: str | None = None
    source: str | None = None
    language: str | None = None
    relation: Sequence[str] = field(default_factory=tuple)
    coverage: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "subject", _dedupe_str_sequence(values=self.subject, label="subject"))
        object.__setattr__(self, "contributor", _dedupe_str_sequence(values=self.contributor, label="contributor"))
        object.__setattr__(self, "relation", _dedupe_str_sequence(values=self.relation, label="relation"))

    def validate(self) -> None:
        if not self.title:
            raise ValueError("Dublin Core title is required.")


@dataclass(slots=True)
class IAMetadata:
    """Custom IA metadata tracked for each document."""

    findability_score: float | None = None
    completeness: float | None = None
    depth: int | None = None
    audience: Sequence[str] = field(default_factory=tuple)
    navigation_path: Sequence[str] = field(default_factory=tuple)
    related_by_topic: Sequence[str] = field(default_factory=tuple)
    related_by_entity: Sequence[str] = field(default_factory=tuple)
    last_updated: datetime | None = None
    update_frequency: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "audience", _dedupe_str_sequence(values=self.audience, label="audience"))
        object.__setattr__(self, "navigation_path", tuple(self.navigation_path))
        object.__setattr__(self, "related_by_topic", tuple(self.related_by_topic))
        object.__setattr__(self, "related_by_entity", tuple(self.related_by_entity))

    def validate(self) -> None:
        for name, value in (
            ("findability_score", self.findability_score),
            ("completeness", self.completeness),
        ):
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0 inclusive.")
        if self.depth is not None and not 1 <= self.depth <= 5:
            raise ValueError("depth must be within the progressive disclosure range (1-5).")


@dataclass(slots=True)
class KBMetadata:
    """Combined metadata payload for a knowledge base document."""

    doc_type: str
    primary_topic: str
    dc: DublinCoreMetadata
    ia: IAMetadata
    secondary_topics: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)
    sources: Sequence[SourceReference] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ensure_kebab_case(self.doc_type, "doc_type")
        _ensure_kebab_case(self.primary_topic, "primary_topic")
        object.__setattr__(
            self,
            "secondary_topics",
            _dedupe_str_sequence(values=self.secondary_topics, label="secondary_topics"),
        )
        object.__setattr__(self, "tags", _dedupe_str_sequence(values=self.tags, label="tags"))
        object.__setattr__(self, "sources", tuple(self.sources))

    def validate(self) -> None:
        if self.doc_type in {"concept", "entity", "source"}:
            pass
        # Additional doc types can be supported later but must remain kebab-case.
        if not self.sources:
            raise ValueError("At least one source reference is required.")
        self.dc.validate()
        self.ia.validate()
        for topic in self.secondary_topics:
            _ensure_kebab_case(topic, "secondary_topic")
        for tag in self.tags:
            _ensure_kebab_case(tag, "tag")
        for ref in self.sources:
            ref.validate()


@dataclass(slots=True)
class KBDocument:
    """Knowledge base document with IA-aligned metadata."""

    kb_id: str
    slug: str
    title: str
    metadata: KBMetadata
    aliases: Sequence[str] = field(default_factory=tuple)
    related_concepts: Sequence[str] = field(default_factory=tuple)
    body: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kb_id", self.kb_id.strip())
        object.__setattr__(self, "slug", self.slug.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "aliases", _dedupe_str_sequence(values=self.aliases, label="aliases"))
        object.__setattr__(
            self,
            "related_concepts",
            _dedupe_str_sequence(values=self.related_concepts, label="related_concepts"),
        )

    def validate(self) -> None:
        _ensure_kb_path(self.kb_id, "kb_id")
        _ensure_kebab_case(self.slug, "slug")
        if not self.title:
            raise ValueError("title is required.")
        if self.title != self.metadata.dc.title:
            raise ValueError("Document title must match Dublin Core title.")
        self.metadata.validate()
        for concept_id in self.related_concepts:
            _ensure_kb_path(concept_id, "related_concept")


@dataclass(slots=True)
class KBRelationship:
    """Represents graph edges between knowledge base documents."""

    source: str
    target: str
    relationship_type: str
    weight: float | None = None

    def validate(self) -> None:
        _ensure_kb_path(self.source, "relationship source")
        _ensure_kb_path(self.target, "relationship target")
        _ensure_kebab_case(self.relationship_type, "relationship_type")
        if self.weight is not None and self.weight <= 0:
            raise ValueError("Relationship weight must be positive when provided.")


@dataclass(slots=True)
class TaxonomyTopic:
    """Topic taxonomy node."""

    topic_id: str
    label: str
    definition: str | None = None
    children: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ensure_kebab_case(self.topic_id, "topic_id")
        object.__setattr__(self, "children", tuple(self.children))

    def validate(self, *, known_topics: Mapping[str, "TaxonomyTopic"]) -> None:
        if not self.label:
            raise ValueError(f"Topic {self.topic_id!r} requires a label.")
        for child_id in self.children:
            if child_id not in known_topics:
                raise ValueError(f"Topic {self.topic_id!r} references unknown child {child_id!r}.")


@dataclass(slots=True)
class EntityType:
    """Entity type facet definition."""

    entity_id: str
    label: str
    properties: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ensure_kebab_case(self.entity_id, "entity_id")
        object.__setattr__(self, "properties", _dedupe_str_sequence(values=self.properties, label="entity_properties"))
        if not self.label:
            raise ValueError(f"Entity type {self.entity_id!r} requires a label.")


@dataclass(slots=True)
class RelationshipType:
    """Defines permitted relationship edges."""

    relationship_id: str
    label: str
    inverse: str | None = None

    def __post_init__(self) -> None:
        _ensure_kebab_case(self.relationship_id, "relationship_id")
        if self.inverse is not None:
            _ensure_kebab_case(self.inverse, "inverse_relationship")
        if not self.label:
            raise ValueError(f"Relationship type {self.relationship_id!r} requires a label.")


@dataclass(slots=True)
class VocabularyTerm:
    """Controlled vocabulary term metadata."""

    term_id: str
    preferred_term: str
    alternate_terms: Sequence[str] = field(default_factory=tuple)
    related_terms: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ensure_kebab_case(self.term_id, "term_id")
        if not self.preferred_term:
            raise ValueError(f"Vocabulary term {self.term_id!r} requires a preferred term.")
        object.__setattr__(
            self,
            "alternate_terms",
            _dedupe_str_sequence(values=self.alternate_terms, label="alternate_terms"),
        )
        object.__setattr__(
            self,
            "related_terms",
            _dedupe_str_sequence(values=self.related_terms, label="related_terms"),
        )


@dataclass(slots=True)
class Taxonomy:
    """Top-level taxonomy definition for the knowledge base."""

    version: str | None
    methodology: str | None
    topics: Mapping[str, TaxonomyTopic]
    entity_types: Mapping[str, EntityType]
    relationship_types: Mapping[str, RelationshipType]
    vocabulary: Mapping[str, VocabularyTerm]
    _topic_parents: dict[str, str | None] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._topic_parents = {}

    def validate(self) -> None:
        parents: dict[str, str | None] = {topic_id: None for topic_id in self.topics}
        for topic in self.topics.values():
            topic.validate(known_topics=self.topics)
            for child_id in topic.children:
                if child_id not in parents:
                    raise ValueError(
                        f"Topic {topic.topic_id!r} references unknown child {child_id!r}."
                    )
                if parents[child_id] is not None:
                    raise ValueError(
                        f"Topic {child_id!r} already assigned to parent {parents[child_id]!r}."
                    )
                parents[child_id] = topic.topic_id
        for topic_id in self.topics:
            seen: set[str] = set()
            current: str | None = topic_id
            while current is not None:
                if current in seen:
                    raise ValueError(f"Cycle detected in topic hierarchy at {current!r}.")
                seen.add(current)
                current = parents[current]
        self._topic_parents = parents
        for entity in self.entity_types.values():
            # __post_init__ already validates structure.
            _ = entity
        for rel in self.relationship_types.values():
            if not rel.inverse:
                continue
            inverse = self.relationship_types.get(rel.inverse)
            if inverse is None:
                raise ValueError(
                    f"Relationship {rel.relationship_id!r} references unknown inverse {rel.inverse!r}."
                )
            if inverse.inverse != rel.relationship_id:
                raise ValueError(
                    "Relationship {rel!r} inverse {inv!r} must reference the original "
                    "relationship.".format(rel=rel.relationship_id, inv=rel.inverse)
                )
        for term in self.vocabulary.values():
            _ = term

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Taxonomy":
        topics_payload = payload.get("topics", {})
        topics: dict[str, TaxonomyTopic] = {}
        for topic_id, topic_data in topics_payload.items():
            topics[topic_id] = TaxonomyTopic(
                topic_id=topic_id,
                label=topic_data.get("label", ""),
                definition=topic_data.get("definition"),
                children=topic_data.get("children", ()),
            )

        entities_payload = payload.get("entity_types", {})
        entity_types: dict[str, EntityType] = {}
        for entity_id, entity_data in entities_payload.items():
            entity_types[entity_id] = EntityType(
                entity_id=entity_id,
                label=entity_data.get("label", ""),
                properties=entity_data.get("properties", ()),
            )

        relationships_payload = payload.get("relationship_types", {})
        relationship_types: dict[str, RelationshipType] = {}
        for rel_id, rel_data in relationships_payload.items():
            relationship_types[rel_id] = RelationshipType(
                relationship_id=rel_id,
                label=rel_data.get("label", ""),
                inverse=rel_data.get("inverse"),
            )

        vocabulary_payload = payload.get("vocabulary", {})
        vocabulary: dict[str, VocabularyTerm] = {}
        for term_id, term_data in vocabulary_payload.items():
            vocabulary[term_id] = VocabularyTerm(
                term_id=term_id,
                preferred_term=term_data.get("preferred_term", ""),
                alternate_terms=term_data.get("alternate_terms", ()),
                related_terms=term_data.get("related_terms", ()),
            )

        taxonomy = cls(
            version=payload.get("version"),
            methodology=payload.get("methodology"),
            topics=topics,
            entity_types=entity_types,
            relationship_types=relationship_types,
            vocabulary=vocabulary,
        )
        taxonomy.validate()
        return taxonomy

    def topic_breadcrumb(self, topic_id: str) -> tuple[str, ...]:
        if topic_id not in self.topics:
            raise ValueError(f"Unknown topic {topic_id!r}.")
        if not self._topic_parents:
            self.validate()
        trail: list[str] = []
        current: str | None = topic_id
        while current is not None:
            trail.append(current)
            current = self._topic_parents.get(current)
        return tuple(reversed(trail))

    def validate_assignment(
        self,
        *,
        primary_topic: str,
        secondary_topics: Sequence[str],
    ) -> tuple[str, ...]:
        if primary_topic not in self.topics:
            raise ValueError(f"Primary topic {primary_topic!r} not found in taxonomy.")
        normalized: list[str] = [primary_topic]
        seen: set[str] = {primary_topic}
        for topic_id in secondary_topics:
            if topic_id not in self.topics:
                raise ValueError(f"Secondary topic {topic_id!r} not found in taxonomy.")
            if topic_id in seen:
                raise ValueError(f"Duplicate topic assignment detected for {topic_id!r}.")
            seen.add(topic_id)
            normalized.append(topic_id)
        return tuple(normalized)


from .config import (  # noqa: E402  - composed import placed after class definitions
    InformationArchitecturePlan,
    LabelingConventions,
    MissionConfig,
    MissionDetails,
    QualityStandards,
    SearchOptimization,
    load_mission_config,
)