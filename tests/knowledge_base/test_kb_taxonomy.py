from __future__ import annotations

import pytest

from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBMetadata,
    SourceReference,
    Taxonomy,
)
from src.knowledge_base.taxonomy import (
    TopicAssignment,
    apply_topics,
    assign_topics,
    iter_topic_pairs,
    load_taxonomy,
    validate_taxonomy_payload,
)


@pytest.fixture
def sample_payload() -> dict[str, object]:
    return {
        "version": "1.0.0",
        "methodology": "information-architecture",
        "topics": {
            "statecraft": {
                "label": "Statecraft",
                "definition": "Governance practice",
                "children": ["virtue"],
            },
            "virtue": {
                "label": "Virtue",
                "definition": "Virtu concept",
            },
        },
        "entity_types": {
            "person": {"label": "Person", "properties": ["birth_date"]},
        },
        "relationship_types": {
            "influences": {"label": "Influences", "inverse": "influenced-by"},
            "influenced-by": {"label": "Influenced By", "inverse": "influences"},
        },
        "vocabulary": {
            "statecraft": {
                "preferred_term": "statecraft",
                "alternate_terms": ["art-of-government"],
                "related_terms": ["governance"],
            }
        },
    }


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
        navigation_path=("concepts",),
        related_by_topic=("concepts/statecraft/fortune",),
        related_by_entity=("entities/people/cesare-borgia",),
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


def test_validate_taxonomy_payload_requires_sections() -> None:
    with pytest.raises(ValueError):
        validate_taxonomy_payload({})


def test_validate_taxonomy_payload_rejects_non_kebab_identifier() -> None:
    payload = {
        "topics": {"BadTopic": {}},
        "entity_types": {},
        "relationship_types": {},
        "vocabulary": {},
    }
    with pytest.raises(ValueError):
        validate_taxonomy_payload(payload)


def test_taxonomy_detects_duplicate_parent(sample_payload: dict[str, object]) -> None:
    payload = sample_payload.copy()
    payload["topics"] = {
        "statecraft": {
            "label": "Statecraft",
            "children": ["virtue"],
        },
        "political-theory": {
            "label": "Political Theory",
            "children": ["virtue"],
        },
        "virtue": {
            "label": "Virtue",
        },
    }
    with pytest.raises(ValueError):
        Taxonomy.from_dict(payload)


def test_taxonomy_requires_reciprocal_relationship_inverse(sample_payload: dict[str, object]) -> None:
    payload = sample_payload.copy()
    payload["relationship_types"] = {
        "influences": {"label": "Influences", "inverse": "influenced-by"},
        "influenced-by": {"label": "Influenced By", "inverse": "related-to"},
        "related-to": {"label": "Related To"},
    }

    with pytest.raises(ValueError, match="must reference the original"):
        Taxonomy.from_dict(payload)


def test_assign_topics_returns_breadcrumb(sample_payload: dict[str, object]) -> None:
    taxonomy = Taxonomy.from_dict(sample_payload)
    assignment = assign_topics(taxonomy, primary="statecraft", secondary=("virtue",))
    assert isinstance(assignment, TopicAssignment)
    assert assignment.primary == "statecraft"
    assert assignment.secondary == ("virtue",)
    assert assignment.breadcrumb == ("statecraft",)


def test_assign_topics_rejects_unknown_secondary(sample_payload: dict[str, object]) -> None:
    taxonomy = Taxonomy.from_dict(sample_payload)
    with pytest.raises(ValueError):
        assign_topics(taxonomy, primary="statecraft", secondary=("unknown",))


def test_apply_topics_updates_navigation_path(
    sample_payload: dict[str, object], sample_metadata: KBMetadata
) -> None:
    taxonomy = Taxonomy.from_dict(sample_payload)
    assignment = assign_topics(taxonomy, primary="statecraft", secondary=("virtue",))
    updated = apply_topics(sample_metadata, assignment)
    assert updated.primary_topic == "statecraft"
    assert updated.secondary_topics == ("virtue",)
    assert updated.ia.navigation_path == ("statecraft",)


def test_iter_topic_pairs_yields_relationships(sample_payload: dict[str, object]) -> None:
    taxonomy = Taxonomy.from_dict(sample_payload)
    pairs = set(iter_topic_pairs(taxonomy))
    assert ("statecraft", "virtue") in pairs


def test_load_taxonomy_round_trip(tmp_path_factory: pytest.TempPathFactory) -> None:
    path = tmp_path_factory.mktemp("kb") / "taxonomy.yaml"
    path.write_text("version: '1.0.0'\nmethodology: information-architecture\ntopics:\n  statecraft:\n    label: 'Statecraft'\nentity_types: {}\nrelationship_types: {}\nvocabulary: {}\n", encoding="utf-8")
    taxonomy = load_taxonomy(path)
    assert "statecraft" in taxonomy.topics