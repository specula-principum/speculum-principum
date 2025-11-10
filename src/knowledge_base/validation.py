"""Validation utilities for IA-aligned knowledge base documents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from . import KBDocument, KBRelationship, Taxonomy
from .linking import RelationshipGraph
from .metadata import assert_quality_thresholds, completeness_score


@dataclass(slots=True)
class QualityMetrics:
    """Aggregate quality metrics for a collection of documents."""

    total_documents: int
    average_completeness: float
    average_findability: float
    below_threshold: tuple[str, ...]


def validate_documents(documents: Iterable[KBDocument]) -> tuple[KBDocument, ...]:
    """Validate individual documents and return a concrete sequence."""

    validated: list[KBDocument] = []
    for document in documents:
        document.validate()
        assert_quality_thresholds(document.metadata)
        validated.append(document)
    return tuple(validated)


def validate_relationships(
    relationships: Iterable[KBRelationship],
    *,
    known_ids: Sequence[str],
    taxonomy: Taxonomy | None = None,
) -> RelationshipGraph:
    """Validate and materialize relationships into a graph structure."""

    known = set(known_ids)
    graph = RelationshipGraph(taxonomy=taxonomy)
    for relationship in relationships:
        if relationship.source not in known:
            raise ValueError(f"Unknown relationship source {relationship.source!r}.")
        if relationship.target not in known:
            raise ValueError(f"Unknown relationship target {relationship.target!r}.")
        graph.add(relationship)
    return graph


def calculate_quality_metrics(documents: Iterable[KBDocument]) -> QualityMetrics:
    """Calculate aggregate completeness and findability metrics."""

    validated = tuple(documents)
    if not validated:
        return QualityMetrics(
            total_documents=0,
            average_completeness=0.0,
            average_findability=0.0,
            below_threshold=(),
        )

    completeness_values: list[float] = []
    findability_values: list[float] = []
    below_threshold: list[str] = []

    for document in validated:
        completeness = completeness_score(document.metadata)
        findability = document.metadata.ia.findability_score or 0.0
        completeness_values.append(completeness)
        findability_values.append(findability)
        try:
            document.validate()
            assert_quality_thresholds(document.metadata)
        except ValueError:
            below_threshold.append(document.kb_id)

    total = len(validated)
    average_completeness = round(sum(completeness_values) / total, 2)
    average_findability = round(sum(findability_values) / total, 2)

    return QualityMetrics(
        total_documents=total,
        average_completeness=average_completeness,
        average_findability=average_findability,
        below_threshold=tuple(below_threshold),
    )
