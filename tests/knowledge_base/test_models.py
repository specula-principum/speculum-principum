from __future__ import annotations

import pytest

from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBMetadata,
    KBDocument,
    KBRelationship,
    SourceReference,
    Taxonomy,
)
from src.knowledge_base.cli import initialize_knowledge_base
from src.knowledge_base.linking import build_adjacency
from src.knowledge_base.metadata import assert_quality_thresholds, completeness_score
from src.knowledge_base.structure import iter_structure, required_directories
from src.knowledge_base.taxonomy import load_taxonomy
from src.knowledge_base.validation import validate_documents


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
        navigation_path=("concepts", "statecraft", "virtue"),
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


def test_document_validation_accepts_valid_document(sample_metadata: KBMetadata) -> None:
    document = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=sample_metadata,
        aliases=("virtu",),
        related_concepts=("concepts/statecraft/fortune",),
    )
    document.validate()


def test_document_validation_rejects_slug_with_caps(sample_metadata: KBMetadata) -> None:
    document = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="Virtue",
        title="Virtue",
        metadata=sample_metadata,
    )
    with pytest.raises(ValueError):
        document.validate()


def test_metadata_requires_sources(sample_metadata: KBMetadata) -> None:
    metadata = KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        dc=sample_metadata.dc,
        ia=sample_metadata.ia,
        secondary_topics=sample_metadata.secondary_topics,
        tags=sample_metadata.tags,
        sources=(),
    )
    with pytest.raises(ValueError):
        metadata.validate()


def test_ia_metadata_range_checks(sample_metadata: KBMetadata) -> None:
    ia = IAMetadata(findability_score=0.5, completeness=1.5)
    with pytest.raises(ValueError):
        ia.validate()


def test_duplicate_secondary_topics_not_allowed(sample_metadata: KBMetadata) -> None:
    with pytest.raises(ValueError):
        KBMetadata(
            doc_type="concept",
            primary_topic="statecraft",
            secondary_topics=("ethics", "ethics"),
            tags=("virtue",),
            dc=sample_metadata.dc,
            ia=sample_metadata.ia,
            sources=sample_metadata.sources,
        )


def test_completeness_score_falls_back_when_missing(sample_metadata: KBMetadata) -> None:
    metadata = KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        dc=sample_metadata.dc,
        ia=IAMetadata(findability_score=0.7),
        tags=("virtue",),
        sources=sample_metadata.sources,
    )
    score = completeness_score(metadata)
    assert 0.0 < score <= 1.0


def test_quality_thresholds_enforced(sample_metadata: KBMetadata) -> None:
    metadata = KBMetadata(
        doc_type="concept",
        primary_topic="statecraft",
        dc=sample_metadata.dc,
        ia=IAMetadata(findability_score=0.5),
        tags=("virtue",),
        sources=sample_metadata.sources,
    )
    with pytest.raises(ValueError):
        assert_quality_thresholds(metadata)


def test_validate_documents_executes_full_validation_flow(sample_metadata: KBMetadata) -> None:
    document = KBDocument(
        kb_id="concepts/statecraft/virtue",
        slug="virtue",
        title="Virtue",
        metadata=sample_metadata,
    )
    validate_documents((document,))


def test_taxonomy_from_dict_validates_children() -> None:
    payload = {
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
    taxonomy = Taxonomy.from_dict(payload)
    taxonomy.validate()


def test_build_adjacency_returns_bidirectional_edges() -> None:
    rel = KBRelationship(
        source="concepts/statecraft/virtue",
        target="concepts/statecraft/fortune",
        relationship_type="contrasts",
    )
    graph = build_adjacency((rel,))
    assert graph["concepts/statecraft/virtue"] == {"concepts/statecraft/fortune"}
    assert graph["concepts/statecraft/fortune"] == {"concepts/statecraft/virtue"}


def test_iter_structure_enumerates_blueprint(tmp_path_factory: pytest.TempPathFactory) -> None:
    root = tmp_path_factory.mktemp("kb-root")
    nodes = list(iter_structure(root))
    assert nodes, "Structure blueprint should yield nodes."
    assert all(node.path.is_relative_to(root) for node in nodes)


def test_required_directories_matches_defaults() -> None:
    directories = required_directories()
    for required in ("concepts", "entities", "sources", "relationships", "meta"):
        assert required in directories


def test_initialize_knowledge_base_returns_paths(tmp_path_factory: pytest.TempPathFactory) -> None:
    root = tmp_path_factory.mktemp("kb-root")
    planned = initialize_knowledge_base(root)
    assert planned
    assert all(path.is_relative_to(root) for path in planned)


def test_load_taxonomy_reads_yaml(tmp_path_factory: pytest.TempPathFactory) -> None:
    taxonomy_yaml = tmp_path_factory.mktemp("kb") / "taxonomy.yaml"
    taxonomy_yaml.write_text(
        (
            'version: "1.0.0"\n'
            'methodology: information-architecture\n'
            "topics:\n"
            "  statecraft:\n"
            "    label: 'Statecraft'\n"
            "    definition: 'Governance practice'\n"
            "  virtue:\n"
            "    label: 'Virtue'\n"
            "entity_types:\n"
            "  person:\n"
            "    label: 'Person'\n"
            "relationship_types:\n"
            "  influences:\n"
            "    label: 'Influences'\n"
            "    inverse: 'influenced-by'\n"
            "  influenced-by:\n"
            "    label: 'Influenced By'\n"
            "    inverse: 'influences'\n"
            "vocabulary:\n"
            "  statecraft:\n"
            "    preferred_term: 'statecraft'\n"
        ),
        encoding="utf-8",
    )
    taxonomy = load_taxonomy(taxonomy_yaml)
    assert "statecraft" in taxonomy.topics
