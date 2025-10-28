"""Tests for knowledge base document transformation."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.extraction import ExtractedConcept, ExtractedEntity
from src.knowledge_base import SourceReference
from src.kb_engine.transform import KBTransformer, TransformContext


@pytest.fixture()
def sample_context() -> TransformContext:
    source = SourceReference(kb_id="sources/the-prince/chapter-1", pages=(1, 2))
    return TransformContext(
        primary_topic="Statecraft",
        secondary_topics=("Political Theory",),
        default_tags=("Renaissance",),
        audience=("Students", "Researchers"),
        source_references=(source,),
        findability_baseline=0.8,
        completeness_baseline=0.85,
        timestamp=datetime(2025, 10, 26, 12, 0, 0),
    )


def test_create_concept_document_builds_metadata(sample_context: TransformContext) -> None:
    concept = ExtractedConcept(
        term="Virtue",
        frequency=5,
        positions=(3, 15, 42),
        related_terms=("Fortune", "Power"),
        definition="Virtue as practical excellence in governance.",
    )
    transformer = KBTransformer()

    document = transformer.create_concept_document(concept, sample_context)

    assert document.kb_id == "concepts/statecraft/virtue"
    assert document.slug == "virtue"
    assert document.metadata.primary_topic == "statecraft"
    assert document.metadata.dc.description is not None
    assert document.metadata.dc.description.startswith("Virtue as practical excellence")
    assert document.metadata.ia.navigation_path == ("concepts", "statecraft", "virtue")
    assert document.metadata.tags == ("renaissance", "virtue")
    assert document.related_concepts == (
        "concepts/statecraft/fortune",
        "concepts/statecraft/power",
    )
    assert document.body is not None
    assert "**Frequency:** 5" in document.body
    document.validate()


def test_create_entity_document_maps_entity_type(sample_context: TransformContext) -> None:
    entity = ExtractedEntity(
        text="Cesare Borgia",
        entity_type="PERSON",
        start_offset=10,
        end_offset=22,
        confidence=0.94,
        metadata={
            "aliases": ["Duke Valentino"],
            "related_concepts": ["Virtue"],
            "related_entities": ["entities/people/pope-alexander-vi"],
        },
    )
    transformer = KBTransformer()

    document = transformer.create_entity_document(entity, sample_context)

    assert document.kb_id == "entities/people/cesare-borgia"
    assert document.metadata.primary_topic == "people"
    assert document.metadata.tags == ("renaissance", "people", "cesare-borgia")
    assert document.aliases == ("Duke Valentino",)
    assert document.related_concepts == ("concepts/statecraft/virtue",)
    assert document.metadata.ia.related_by_entity == ("entities/people/pope-alexander-vi",)
    assert document.body is not None
    assert "**Confidence:** 0.94" in document.body
    document.validate()


def test_transform_context_requires_sources() -> None:
    with pytest.raises(ValueError):
        TransformContext(primary_topic="statecraft", source_references=())
