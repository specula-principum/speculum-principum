"""Taxonomy helpers built around the core data models."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from . import KBMetadata, Taxonomy

_SEGMENT_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REQUIRED_ROOT_KEYS: tuple[str, ...] = (
    "topics",
    "entity_types",
    "relationship_types",
    "vocabulary",
)


@dataclass(slots=True, frozen=True)
class TopicAssignment:
    """Validated topic assignment bundle for metadata updates."""

    primary: str
    secondary: tuple[str, ...]
    breadcrumb: tuple[str, ...]


def _ensure_kebab_case(value: str, *, label: str) -> None:
    if not value or not _SEGMENT_PATTERN.match(value):
        raise ValueError(f"{label} must be kebab-case (got {value!r}).")


def validate_taxonomy_payload(payload: Mapping[str, object]) -> None:
    """Perform lightweight schema validation before constructing a taxonomy."""

    if not payload:
        raise ValueError("Taxonomy payload cannot be empty.")
    for key in _REQUIRED_ROOT_KEYS:
        section = payload.get(key)
        if not isinstance(section, Mapping):
            raise ValueError(f"Taxonomy requires mapping section {key!r}.")
        for identifier in section.keys():
            _ensure_kebab_case(str(identifier), label=f"{key} identifier")

    topics = payload.get("topics")
    if isinstance(topics, Mapping):
        for topic_id, params in topics.items():
            if not isinstance(params, Mapping):
                raise ValueError(f"Topic {topic_id!r} must be a mapping.")
            children = params.get("children", ())
            if isinstance(children, Mapping):
                raise ValueError(f"Topic children for {topic_id!r} must be a list of identifiers.")
            for child in children or ():
                _ensure_kebab_case(str(child), label=f"child of {topic_id}")

    relationships = payload.get("relationship_types")
    if isinstance(relationships, Mapping):
        for rel_id, rel_params in relationships.items():
            if not isinstance(rel_params, Mapping):
                raise ValueError(f"Relationship {rel_id!r} must be a mapping.")
            inverse = rel_params.get("inverse")
            if inverse is not None:
                _ensure_kebab_case(str(inverse), label=f"inverse of {rel_id}")


def load_taxonomy(path: Path | str) -> Taxonomy:
    """Load a taxonomy YAML file into a :class:`Taxonomy` instance."""

    target = Path(path)
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Taxonomy definition must be a mapping.")
    validate_taxonomy_payload(data)
    taxonomy = Taxonomy.from_dict(data)
    validate_relationships(taxonomy)
    return taxonomy


def assign_topics(
    taxonomy: Taxonomy,
    *,
    primary: str,
    secondary: Sequence[str] | None = None,
) -> TopicAssignment:
    """Validate and normalize topic assignments against a taxonomy."""

    normalized = taxonomy.validate_assignment(
        primary_topic=primary,
        secondary_topics=secondary or (),
    )
    breadcrumb = taxonomy.topic_breadcrumb(primary)
    return TopicAssignment(
        primary=normalized[0],
        secondary=normalized[1:],
        breadcrumb=breadcrumb,
    )


def apply_topics(metadata: KBMetadata, assignment: TopicAssignment) -> KBMetadata:
    """Return a metadata copy with taxonomy-backed topic assignments."""

    metadata.primary_topic = assignment.primary
    metadata.secondary_topics = assignment.secondary
    metadata.ia = type(metadata.ia)(
        findability_score=metadata.ia.findability_score,
        completeness=metadata.ia.completeness,
        depth=metadata.ia.depth,
        audience=metadata.ia.audience,
        navigation_path=assignment.breadcrumb,
        related_by_topic=metadata.ia.related_by_topic,
        related_by_entity=metadata.ia.related_by_entity,
        last_updated=metadata.ia.last_updated,
        update_frequency=metadata.ia.update_frequency,
    )
    metadata.validate()
    return metadata


def validate_relationships(taxonomy: Taxonomy) -> None:
    """Ensure relationship inverses are symmetrical within the taxonomy."""

    for rel_id, rel in taxonomy.relationship_types.items():
        if not rel.inverse:
            continue

        inverse = taxonomy.relationship_types.get(rel.inverse)
        if inverse is None:
            raise ValueError(
                f"Relationship {rel_id!r} references unknown inverse {rel.inverse!r}."
            )

        if inverse.inverse != rel_id:
            raise ValueError(
                "Relationship {rel!r} inverse {inv!r} must reference the original "
                "relationship.".format(rel=rel_id, inv=rel.inverse)
            )


def iter_topic_pairs(taxonomy: Taxonomy) -> Iterable[tuple[str, str]]:
    """Yield parent-child topic pairs for navigation scaffolding."""

    for topic_id, topic in taxonomy.topics.items():
        for child in topic.children:
            yield topic_id, child
