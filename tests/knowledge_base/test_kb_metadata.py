from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest

from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBMetadata,
    KBDocument,
    SourceReference,
)
from src.knowledge_base.metadata import (
    assert_quality_thresholds,
    document_front_matter,
    metadata_payload,
    render_document,
)


@pytest.fixture
def sample_metadata() -> KBMetadata:
    dc = DublinCoreMetadata(
        title="Virtue",
        creator="Niccolo Machiavelli",
        subject=("statecraft",),
        identifier="concepts/statecraft/virtue",
        language="en",
    )
    ia = IAMetadata(
        findability_score=0.8,
        completeness=0.9,
        depth=3,
        audience=("students", "researchers"),
        navigation_path=("concepts", "statecraft"),
        related_by_topic=("concepts/statecraft/fortune",),
        related_by_entity=("entities/people/cesare-borgia",),
        last_updated=datetime(2025, 10, 25, 12, 0, 0),
        update_frequency="quarterly",
    )
    sources = (
        SourceReference(
            kb_id="sources/the-prince/chapters/chapter-15",
            pages=(15, 16),
        ),
    )
    return KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        secondary_topics=("political-theory",),
        tags=("virtue", "machiavelli"),
        dc=dc,
        ia=ia,
        sources=sources,
    )


def test_metadata_payload_serialises_sequences(sample_metadata: KBMetadata) -> None:
    payload = metadata_payload(sample_metadata)
    assert payload["secondary_topics"] == ["political-theory"]
    sources = cast(list[dict[str, Any]], payload["sources"])
    dc = cast(dict[str, Any], payload["dublin_core"])
    ia = cast(dict[str, Any], payload["ia"])
    assert sources[0]["pages"] == [15, 16]
    assert dc["subject"] == ["statecraft"]
    assert ia["navigation_path"] == ["concepts", "statecraft"]
    assert ia["last_updated"] == "2025-10-25T12:00:00"


def test_document_front_matter_combines_document_fields(sample_metadata: KBMetadata) -> None:
    document = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=sample_metadata,
        aliases=("virtu",),
        related_concepts=("concepts/statecraft/fortune",),
        body="# Heading\n",
    )
    front_matter = document_front_matter(document)
    assert front_matter["title"] == "Virtue"
    assert front_matter["aliases"] == ["virtu"]
    assert front_matter["type"] == "concept"


def test_render_document_outputs_yaml_front_matter(sample_metadata: KBMetadata) -> None:
    document = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=sample_metadata,
        body="Content body.",
    )
    rendered = render_document(document)
    assert rendered.startswith("---\n")
    assert "slug: virtue" in rendered
    assert rendered.endswith("Content body.\n")


def test_assert_quality_thresholds_rejects_low_findability(sample_metadata: KBMetadata) -> None:
    sample_metadata.ia = IAMetadata(findability_score=0.5)
    with pytest.raises(ValueError):
        assert_quality_thresholds(sample_metadata)
