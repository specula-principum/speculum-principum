from __future__ import annotations

from typing import Any, cast

import pytest

from src.knowledge_base import KBRelationship, Taxonomy
from src.knowledge_base.linking import RelationshipGraph, build_adjacency


@pytest.fixture
def sample_taxonomy() -> Taxonomy:
    return Taxonomy.from_dict(
        {
            "version": "1.0.0",
            "methodology": "information-architecture",
            "topics": {},
            "entity_types": {},
            "relationship_types": {
                "influences": {"label": "Influences", "inverse": "influenced-by"},
                "influenced-by": {"label": "Influenced By", "inverse": "influences"},
                "related-to": {"label": "Related To"},
            },
            "vocabulary": {},
        }
    )


def test_relationship_graph_adds_inverse_edges(sample_taxonomy: Taxonomy) -> None:
    graph = RelationshipGraph(taxonomy=sample_taxonomy)
    relationship = KBRelationship(
        source="concepts/statecraft/virtue",
        target="concepts/statecraft/fortune",
        relationship_type="influences",
        weight=0.75,
    )
    graph.add(relationship)

    adjacency = graph.adjacency()
    assert adjacency["concepts/statecraft/virtue"] == ("concepts/statecraft/fortune",)
    assert adjacency["concepts/statecraft/fortune"] == ("concepts/statecraft/virtue",)

    manifest = graph.manifest()
    edges = cast(list[dict[str, Any]], manifest["edges"])
    edge_types = {
        (edge["source"], edge["target"], edge["type"]) for edge in edges
    }
    assert (
        "concepts/statecraft/virtue",
        "concepts/statecraft/fortune",
        "influences",
    ) in edge_types
    assert (
        "concepts/statecraft/fortune",
        "concepts/statecraft/virtue",
        "influenced-by",
    ) in edge_types
    weights = {edge["type"]: edge["weight"] for edge in edges if "weight" in edge}
    assert weights["influences"] == pytest.approx(0.75)
    assert weights["influenced-by"] == pytest.approx(0.75)


def test_relationship_graph_rejects_unknown_relationship(sample_taxonomy: Taxonomy) -> None:
    graph = RelationshipGraph(taxonomy=sample_taxonomy)
    with pytest.raises(ValueError, match="Unknown relationship type"):
        graph.add(
            KBRelationship(
                source="concepts/statecraft/virtue",
                target="concepts/statecraft/fortune",
                relationship_type="unsupported",
            )
        )


def test_relationship_graph_conflicting_weight_raises(sample_taxonomy: Taxonomy) -> None:
    graph = RelationshipGraph(taxonomy=sample_taxonomy)
    first = KBRelationship(
        source="concepts/statecraft/virtue",
        target="concepts/statecraft/fortune",
        relationship_type="related-to",
        weight=0.5,
    )
    graph.add(first)
    with pytest.raises(ValueError, match="Conflicting weight"):
        graph.add(
            KBRelationship(
                source="concepts/statecraft/virtue",
                target="concepts/statecraft/fortune",
                relationship_type="related-to",
                weight=0.9,
            )
        )


def test_build_adjacency_returns_bidirectional_sets() -> None:
    relationships = (
        KBRelationship(
            source="concepts/statecraft/virtue",
            target="concepts/statecraft/fortune",
            relationship_type="related-to",
        ),
    )
    adjacency = build_adjacency(relationships)
    assert adjacency["concepts/statecraft/virtue"] == {"concepts/statecraft/fortune"}
    assert adjacency["concepts/statecraft/fortune"] == {"concepts/statecraft/virtue"}
