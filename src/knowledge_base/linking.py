"""Link management utilities for IA navigation systems."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from . import KBRelationship, Taxonomy


class RelationshipGraph:
    """Manage bidirectional relationships with taxonomy-aware validation."""

    def __init__(self, *, taxonomy: Taxonomy | None = None) -> None:
        self._taxonomy = taxonomy
        self._edges: dict[tuple[str, str, str], KBRelationship] = {}
        self._adjacency: dict[str, set[str]] = defaultdict(set)

    def add(self, relationship: KBRelationship) -> None:
        """Add a relationship and propagate inverse edges when available."""

        self._register(relationship, propagate=True)

    def add_many(self, relationships: Iterable[KBRelationship]) -> None:
        """Add multiple relationships in sequence."""

        for relationship in relationships:
            self.add(relationship)

    def adjacency(self) -> Mapping[str, tuple[str, ...]]:
        """Return the bidirectional adjacency map sorted for determinism."""

        return {
            node: tuple(sorted(neighbors))
            for node, neighbors in sorted(self._adjacency.items())
        }

    def edges(self) -> tuple[KBRelationship, ...]:
        """Return stored relationships sorted by type and node identifiers."""

        return tuple(
            self._edges[key]
            for key in sorted(self._edges, key=lambda item: (item[0], item[1], item[2]))
        )

    def manifest(self) -> dict[str, object]:
        """Build a canonical manifest for persisting relationship graphs."""

        nodes = list(self.adjacency().keys())
        edges: list[dict[str, object]] = []
        for relationship in self.edges():
            entry: dict[str, object] = {
                "source": relationship.source,
                "target": relationship.target,
                "type": relationship.relationship_type,
            }
            if relationship.weight is not None:
                entry["weight"] = relationship.weight
            edges.append(entry)
        return {
            "nodes": nodes,
            "edges": edges,
        }

    def _register(self, relationship: KBRelationship, *, propagate: bool) -> None:
        relationship.validate()
        self._assert_relationship_type(relationship.relationship_type)

        key = (relationship.relationship_type, relationship.source, relationship.target)
        existing = self._edges.get(key)
        if existing is not None:
            if existing.weight != relationship.weight:
                raise ValueError("Conflicting weight for existing relationship edge.")
            return

        self._edges[key] = relationship
        self._adjacency[relationship.source].add(relationship.target)
        self._adjacency[relationship.target].add(relationship.source)

        if propagate:
            inverse = self._resolve_inverse(relationship.relationship_type)
            if inverse:
                inverse_relationship = KBRelationship(
                    source=relationship.target,
                    target=relationship.source,
                    relationship_type=inverse,
                    weight=relationship.weight,
                )
                self._register(inverse_relationship, propagate=False)

    def _assert_relationship_type(self, relationship_type: str) -> None:
        if self._taxonomy is None:
            return
        if relationship_type not in self._taxonomy.relationship_types:
            raise ValueError(f"Unknown relationship type {relationship_type!r}.")

    def _resolve_inverse(self, relationship_type: str) -> str | None:
        if self._taxonomy is None:
            return None
        relationship = self._taxonomy.relationship_types.get(relationship_type)
        return relationship.inverse if relationship else None


def build_adjacency(relationships: Iterable[KBRelationship]) -> Mapping[str, set[str]]:
    """Construct a bidirectional adjacency list from relationship definitions."""

    graph = RelationshipGraph()
    graph.add_many(relationships)
    return {node: set(neighbors) for node, neighbors in graph.adjacency().items()}
