from __future__ import annotations

from datetime import datetime

import pytest

from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    KBRelationship,
    SourceReference,
    Taxonomy,
)
from src.knowledge_base.validation import (
    QualityMetrics,
    calculate_quality_metrics,
    validate_documents,
    validate_relationships,
)


@pytest.fixture
def sample_document() -> KBDocument:
    dc = DublinCoreMetadata(
        title="Virtue",
        creator="Niccolo Machiavelli",
        subject=("statecraft",),
        identifier="concepts/statecraft/virtue",
    )
    ia = IAMetadata(
        findability_score=0.8,
        completeness=0.9,
        depth=3,
        navigation_path=("concepts", "statecraft"),
        last_updated=datetime(2025, 10, 25, 12, 0, 0),
    )
    metadata = KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        dc=dc,
        ia=ia,
        sources=(
            SourceReference(
                kb_id="sources/the-prince/chapters/chapter-15",
                pages=(15,),
            ),
        ),
    )
    return KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=metadata,
    )


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
            },
            "vocabulary": {},
        }
    )


def test_validate_documents_returns_sequence(sample_document: KBDocument) -> None:
    result = validate_documents([sample_document])
    assert result == (sample_document,)


def test_validate_documents_raises_on_quality_failure(sample_document: KBDocument) -> None:
    sample_document.metadata.ia = IAMetadata(findability_score=0.4)
    with pytest.raises(ValueError):
        validate_documents([sample_document])


def test_validate_relationships_requires_known_nodes(
    sample_document: KBDocument,
    sample_taxonomy: Taxonomy,
) -> None:
    relationship = KBRelationship(
        source="concepts/statecraft/missing",
        target="concepts/statecraft/virtue",
        relationship_type="influences",
    )
    with pytest.raises(ValueError, match="Unknown relationship source"):
        validate_relationships([relationship], known_ids=[sample_document.kb_id], taxonomy=sample_taxonomy)


def test_validate_relationships_returns_graph(
    sample_document: KBDocument,
    sample_taxonomy: Taxonomy,
) -> None:
    related = KBRelationship(
        source="concepts/statecraft/virtue",
        target="concepts/statecraft/fortune",
        relationship_type="influences",
    )
    graph = validate_relationships(
        [related],
        known_ids=[sample_document.kb_id, "concepts/statecraft/fortune"],
        taxonomy=sample_taxonomy,
    )
    adjacency = graph.adjacency()
    assert adjacency["concepts/statecraft/virtue"] == ("concepts/statecraft/fortune",)
    assert adjacency["concepts/statecraft/fortune"] == ("concepts/statecraft/virtue",)


def test_calculate_quality_metrics_reports_below_threshold(sample_document: KBDocument) -> None:
    failing = IAMetadata(findability_score=0.5)
    failing_metadata = KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        dc=DublinCoreMetadata(title="Fortune"),
        ia=failing,
        sources=(
            SourceReference(
                kb_id="sources/the-prince/chapters/chapter-25",
                pages=(25,),
            ),
        ),
    )
    failing_doc = KBDocument(
        kb_id="concepts/statecraft/fortune",
        slug="fortune",
        title="Fortune",
        metadata=failing_metadata,
    )

    metrics = calculate_quality_metrics([sample_document, failing_doc])
    assert isinstance(metrics, QualityMetrics)
    assert metrics.total_documents == 2
    assert metrics.average_completeness >= 0.5
    assert metrics.average_findability == 0.65
    assert metrics.below_threshold == ("concepts/statecraft/fortune",)


def test_calculate_quality_metrics_handles_empty_input() -> None:
    metrics = calculate_quality_metrics([])
    assert metrics.total_documents == 0
    assert metrics.average_completeness == 0.0
    assert metrics.average_findability == 0.0
    assert metrics.below_threshold == ()
