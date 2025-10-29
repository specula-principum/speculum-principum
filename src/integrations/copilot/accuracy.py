"""Accuracy evaluation helpers for Copilot automation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import json

import yaml

from src.integrations.copilot.helpers import gather_kb_documents
from src.knowledge_base import KBDocument

__all__ = [
    "AccuracyMetrics",
    "AccuracyReport",
    "AccuracyScenario",
    "collect_kb_signatures",
    "evaluate_accuracy",
    "load_accuracy_scenario",
    "render_accuracy_report",
]


@dataclass(frozen=True)
class AccuracyScenario:
    """Container describing ground truth expectations for a scenario."""

    name: str
    description: str | None
    concepts: frozenset[str]
    entities: frozenset[str]
    relationships: frozenset[str]


@dataclass(frozen=True)
class AccuracyMetrics:
    """Precision/recall style metrics for a given comparison bucket."""

    category: str
    expected: frozenset[str]
    actual: frozenset[str]
    matches: frozenset[str]
    missing: frozenset[str]
    unexpected: frozenset[str]
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class AccuracyReport:
    """Aggregate accuracy signals for an evaluation scenario."""

    scenario: AccuracyScenario
    concepts: AccuracyMetrics
    entities: AccuracyMetrics
    relationships: AccuracyMetrics

    @property
    def is_successful(self) -> bool:
        """True when all required expectation buckets are satisfied."""

        return (
            not self.concepts.missing
            and not self.entities.missing
            and not self.relationships.missing
            and not self.concepts.unexpected
            and not self.entities.unexpected
            and not self.relationships.unexpected
        )

    @property
    def overall_expected(self) -> int:
        return (
            len(self.concepts.expected)
            + len(self.entities.expected)
            + len(self.relationships.expected)
        )

    @property
    def overall_matches(self) -> int:
        return (
            len(self.concepts.matches)
            + len(self.entities.matches)
            + len(self.relationships.matches)
        )

    @property
    def overall_recall(self) -> float:
        expected = self.overall_expected
        if expected == 0:
            return 1.0
        return self.overall_matches / expected

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": {
                "name": self.scenario.name,
                "description": self.scenario.description,
            },
            "concepts": _metrics_to_dict(self.concepts),
            "entities": _metrics_to_dict(self.entities),
            "relationships": _metrics_to_dict(self.relationships),
            "overall": {
                "expected": self.overall_expected,
                "matches": self.overall_matches,
                "recall": self.overall_recall,
                "success": self.is_successful,
            },
        }


def load_accuracy_scenario(path: Path) -> AccuracyScenario:
    """Load a scenario definition from YAML or JSON."""

    payload = _load_mapping(path)
    name = str(payload.get("name") or path.stem)
    description = payload.get("description")

    expectations = payload.get("expectations") or {}
    if not isinstance(expectations, Mapping):
        raise ValueError("expectations must be a mapping")

    concepts = _extract_id_set(expectations.get("concepts"))
    entities = _extract_id_set(expectations.get("entities"))
    relationships = _extract_relationship_set(expectations.get("relationships"))

    return AccuracyScenario(
        name=name,
        description=str(description) if description is not None else None,
        concepts=concepts,
        entities=entities,
        relationships=relationships,
    )


def collect_kb_signatures(kb_root: Path) -> dict[str, frozenset[str]]:
    """Collect reference identifiers from the knowledge base for comparison."""

    documents = gather_kb_documents(kb_root)
    concepts: set[str] = set()
    entities: set[str] = set()
    relationships: set[str] = set()

    for document in documents:
        _add_document_signatures(document, concepts, entities, relationships)

    return {
        "concepts": frozenset(concepts),
        "entities": frozenset(entities),
        "relationships": frozenset(relationships),
    }


def evaluate_accuracy(scenario: AccuracyScenario, kb_root: Path) -> AccuracyReport:
    """Evaluate the knowledge base against scenario expectations."""

    snapshot = collect_kb_signatures(kb_root)
    concept_metrics = _compute_metrics("concepts", scenario.concepts, snapshot["concepts"])
    entity_metrics = _compute_metrics("entities", scenario.entities, snapshot["entities"])
    relationship_metrics = _compute_metrics("relationships", scenario.relationships, snapshot["relationships"])

    return AccuracyReport(
        scenario=scenario,
        concepts=concept_metrics,
        entities=entity_metrics,
        relationships=relationship_metrics,
    )


def render_accuracy_report(report: AccuracyReport) -> str:
    """Format an accuracy report for display in the CLI."""

    lines: list[str] = [
        f"Scenario: {report.scenario.name}",
        f"Overall Recall: {report.overall_recall:.2f}",
        f"Success: {'yes' if report.is_successful else 'no'}",
    ]

    for metrics in (report.concepts, report.entities, report.relationships):
        lines.append("")
        lines.append(f"{metrics.category.title()}:")
        lines.append(f"  Expected: {len(metrics.expected)}")
        lines.append(f"  Matches: {len(metrics.matches)}")
        lines.append(f"  Missing: {len(metrics.missing)}")
        lines.append(f"  Unexpected: {len(metrics.unexpected)}")
        lines.append(f"  Precision: {metrics.precision:.2f}")
        lines.append(f"  Recall: {metrics.recall:.2f}")
        lines.append(f"  F1: {metrics.f1:.2f}")
        if metrics.missing:
            lines.append("  Missing IDs:")
            lines.extend(f"    - {item}" for item in sorted(metrics.missing))
        if metrics.unexpected:
            lines.append("  Unexpected IDs:")
            lines.extend(f"    - {item}" for item in sorted(metrics.unexpected))

    return "\n".join(lines)


# Internal helpers -----------------------------------------------------


def _load_mapping(path: Path) -> Mapping[str, object]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, Mapping):
        raise ValueError("scenario payload must be a mapping")
    return payload


def _extract_id_set(raw: object) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, Mapping):
        for key in ("must_include", "include", "expected"):
            if key in raw:
                raw = raw[key]
                break
        else:
            raw = list(raw.values())
    if isinstance(raw, str):
        items: Iterable[str] = [raw]
    elif isinstance(raw, Sequence):
        items = [str(entry).strip() for entry in raw if str(entry).strip()]
    else:
        items = [str(raw).strip()]
    normalized = {item for item in (str(token).strip() for token in items) if item}
    return frozenset(normalized)


def _extract_relationship_set(raw: object) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, Mapping):
        for key in ("must_include", "include", "expected"):
            if key in raw:
                raw = raw[key]
                break
        else:
            raw = list(raw.values())
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        items = raw
    else:
        items = [raw]
    normalized: set[str] = set()
    for entry in items:
        normalized.add(_normalise_relationship(entry))
    return frozenset(normalized)


def _normalise_relationship(entry: object) -> str:
    if isinstance(entry, Mapping):
        source = str(entry.get("source") or entry.get("from") or "").strip()
        target = str(entry.get("target") or entry.get("to") or "").strip()
        relation = str(
            entry.get("relation")
            or entry.get("type")
            or entry.get("predicate")
            or "related"
        ).strip()
    else:
        tokens = [token.strip() for token in str(entry).split("|")]
        if len(tokens) == 3:
            source, relation, target = tokens
        elif len(tokens) == 2:
            source, target = tokens
            relation = "related"
        else:
            raise ValueError(
                "relationship entries must follow 'source|relation|target' or mapping format"
            )
    if not source or not target:
        raise ValueError("relationship entries must include source and target")
    if not relation:
        relation = "related"
    return f"{source}|{relation}|{target}"


def _add_document_signatures(
    document: KBDocument,
    concepts: set[str],
    entities: set[str],
    relationships: set[str],
) -> None:
    doc_type = document.metadata.doc_type
    kb_id = document.kb_id
    if doc_type == "concept":
        concepts.add(kb_id)
        for related in document.related_concepts:
            relationships.add(f"{kb_id}|related|{related}")
        for related in document.metadata.ia.related_by_topic:
            relationships.add(f"{kb_id}|topic|{related}")
        for related in document.metadata.ia.related_by_entity:
            relationships.add(f"{kb_id}|entity|{related}")
    elif doc_type == "entity":
        entities.add(kb_id)
        for related in document.metadata.ia.related_by_topic:
            relationships.add(f"{kb_id}|topic|{related}")
        for related in document.metadata.ia.related_by_entity:
            relationships.add(f"{kb_id}|entity|{related}")
    else:
        # Non-concept/entity documents still contribute relationship context.
        for related in document.metadata.ia.related_by_topic:
            relationships.add(f"{kb_id}|topic|{related}")
        for related in document.metadata.ia.related_by_entity:
            relationships.add(f"{kb_id}|entity|{related}")


def _compute_metrics(category: str, expected: frozenset[str], actual: frozenset[str]) -> AccuracyMetrics:
    matches = expected & actual
    missing = expected - actual
    unexpected = actual - expected

    if actual:
        precision = len(matches) / len(actual)
    else:
        precision = 1.0 if not expected else 0.0

    if expected:
        recall = len(matches) / len(expected)
    else:
        recall = 1.0

    if precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return AccuracyMetrics(
        category=category,
        expected=expected,
        actual=actual,
        matches=matches,
        missing=missing,
        unexpected=unexpected,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _metrics_to_dict(metrics: AccuracyMetrics) -> dict[str, object]:
    return {
        "category": metrics.category,
        "expected": len(metrics.expected),
        "actual": len(metrics.actual),
        "matches": len(metrics.matches),
        "missing": sorted(metrics.missing),
        "unexpected": sorted(metrics.unexpected),
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
    }
