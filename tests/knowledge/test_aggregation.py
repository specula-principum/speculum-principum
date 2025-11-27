"""Unit tests for knowledge graph aggregation utilities."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from src.knowledge.aggregation import (
    AggregatedEntity,
    KnowledgeAggregator,
    build_changelog_comment,
    build_entity_discussion_content,
)
from src.knowledge.storage import (
    EntityAssociation,
    EntityProfile,
    ExtractedAssociations,
    ExtractedProfiles,
    KnowledgeGraphStorage,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_knowledge_graph(tmp_path: Path) -> KnowledgeGraphStorage:
    """Create a temporary knowledge graph storage."""
    return KnowledgeGraphStorage(root=tmp_path)


@pytest.fixture
def sample_profile_machiavelli() -> EntityProfile:
    return EntityProfile(
        name="Niccolo Machiavelli",
        entity_type="Person",
        summary="An influential political philosopher known for 'The Prince'.",
        attributes={
            "birth_date": "May 3, 1469",
            "death_date": "June 22, 1527",
            "nationality": "Italian",
            "notable_work": "The Prince",
        },
        mentions=[
            "THE PRINCE BY NICCOLO MACHIAVELLI",
            "Machiavelli's insights on power",
        ],
        confidence=0.95,
    )


@pytest.fixture
def sample_profile_sforza() -> EntityProfile:
    return EntityProfile(
        name="Francesco Sforza",
        entity_type="Person",
        summary="Duke of Milan who rose from private citizen.",
        attributes={
            "role": "Duke of Milan",
            "method_of_acquisition": "by ability",
        },
        mentions=["as was Milan to Francesco Sforza"],
        confidence=0.85,
    )


@pytest.fixture
def sample_association() -> EntityAssociation:
    return EntityAssociation(
        source="Niccolo Machiavelli",
        target="Lorenzo de' Medici",
        relationship="dedicated work to",
        evidence="NICCOLO MACHIAVELLI TO LORENZO THE MAGNIFICENT",
        source_type="Person",
        target_type="Person",
        confidence=0.9,
    )


@pytest.fixture
def populated_knowledge_graph(
    temp_knowledge_graph: KnowledgeGraphStorage,
    sample_profile_machiavelli: EntityProfile,
    sample_profile_sforza: EntityProfile,
    sample_association: EntityAssociation,
) -> KnowledgeGraphStorage:
    """Create a knowledge graph with sample data."""
    checksum1 = "checksum_source_1"
    checksum2 = "checksum_source_2"

    # Save profiles for first source
    temp_knowledge_graph.save_extracted_profiles(
        checksum1,
        [sample_profile_machiavelli, sample_profile_sforza],
    )

    # Save a second profile for Machiavelli from another source
    machiavelli_second = EntityProfile(
        name="Niccolo Machiavelli",
        entity_type="Person",
        summary="A Renaissance diplomat and political theorist.",
        attributes={
            "occupation": "Diplomat",
            "nationality": "Florentine",
        },
        mentions=["Machiavelli served as a diplomat"],
        confidence=0.8,
    )
    temp_knowledge_graph.save_extracted_profiles(checksum2, [machiavelli_second])

    # Save association
    temp_knowledge_graph.save_extracted_associations(checksum1, [sample_association])

    return temp_knowledge_graph


# =============================================================================
# AggregatedEntity Tests
# =============================================================================


class TestAggregatedEntity:
    def test_average_confidence_single(self, sample_profile_machiavelli: EntityProfile) -> None:
        entity = AggregatedEntity(
            name="Niccolo Machiavelli",
            entity_type="Person",
            profiles=[sample_profile_machiavelli],
        )
        assert entity.average_confidence == 0.95

    def test_average_confidence_multiple(
        self,
        sample_profile_machiavelli: EntityProfile,
        sample_profile_sforza: EntityProfile,
    ) -> None:
        entity = AggregatedEntity(
            name="Test",
            entity_type="Person",
            profiles=[sample_profile_machiavelli, sample_profile_sforza],
        )
        expected = (0.95 + 0.85) / 2
        assert entity.average_confidence == pytest.approx(expected)

    def test_average_confidence_empty(self) -> None:
        entity = AggregatedEntity(name="Empty", entity_type="Person")
        assert entity.average_confidence == 0.0

    def test_merged_summary_uses_highest_confidence(self) -> None:
        low_confidence = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="Low confidence summary",
            confidence=0.5,
        )
        high_confidence = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="High confidence summary",
            confidence=0.9,
        )
        entity = AggregatedEntity(
            name="Test",
            entity_type="Person",
            profiles=[low_confidence, high_confidence],
        )
        assert entity.merged_summary == "High confidence summary"

    def test_merged_attributes_combines_sources(self) -> None:
        profile1 = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="",
            attributes={"a": 1, "b": 2},
            confidence=0.5,
        )
        profile2 = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="",
            attributes={"b": 3, "c": 4},
            confidence=0.9,
        )
        entity = AggregatedEntity(
            name="Test",
            entity_type="Person",
            profiles=[profile1, profile2],
        )
        merged = entity.merged_attributes
        assert merged["a"] == 1
        assert merged["b"] == 3  # Higher confidence wins
        assert merged["c"] == 4

    def test_all_mentions_deduplicates(self) -> None:
        profile1 = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="",
            mentions=["mention 1", "mention 2"],
        )
        profile2 = EntityProfile(
            name="Test",
            entity_type="Person",
            summary="",
            mentions=["mention 2", "mention 3"],
        )
        entity = AggregatedEntity(
            name="Test",
            entity_type="Person",
            profiles=[profile1, profile2],
        )
        assert entity.all_mentions == ["mention 1", "mention 2", "mention 3"]


# =============================================================================
# KnowledgeAggregator Tests
# =============================================================================


class TestKnowledgeAggregator:
    def test_list_all_checksums_empty(self, temp_knowledge_graph: KnowledgeGraphStorage) -> None:
        aggregator = KnowledgeAggregator(temp_knowledge_graph)
        checksums = aggregator.list_all_checksums()
        assert checksums == []

    def test_list_all_checksums_finds_profiles(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)
        checksums = aggregator.list_all_checksums()
        assert "checksum_source_1" in checksums
        assert "checksum_source_2" in checksums

    def test_get_all_profiles(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)
        profiles = aggregator.get_all_profiles()
        # 2 from source 1 + 1 from source 2
        assert len(profiles) == 3
        names = [p.name for p in profiles]
        assert "Niccolo Machiavelli" in names
        assert "Francesco Sforza" in names

    def test_list_entities_all(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)
        entities = aggregator.list_entities()
        assert len(entities) == 2  # Deduplicated
        assert "Niccolo Machiavelli" in entities
        assert "Francesco Sforza" in entities

    def test_list_entities_by_type(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)

        # All are persons in our test data
        persons = aggregator.list_entities(entity_type="Person")
        assert len(persons) == 2

        # No organizations
        orgs = aggregator.list_entities(entity_type="Organization")
        assert len(orgs) == 0

    def test_get_profiles_by_entity(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)

        # Machiavelli has 2 profiles (one from each source)
        profiles = aggregator.get_profiles_by_entity("Niccolo Machiavelli")
        assert len(profiles) == 2

        # Case-insensitive
        profiles_lower = aggregator.get_profiles_by_entity("niccolo machiavelli")
        assert len(profiles_lower) == 2

        # Sforza has 1 profile
        sforza_profiles = aggregator.get_profiles_by_entity("Francesco Sforza")
        assert len(sforza_profiles) == 1

    def test_get_associations_for_entity(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)

        as_source, as_target = aggregator.get_associations_for_entity("Niccolo Machiavelli")
        assert len(as_source) == 1
        assert as_source[0].target == "Lorenzo de' Medici"
        assert len(as_target) == 0

        # Lorenzo is only a target
        lorenzo_source, lorenzo_target = aggregator.get_associations_for_entity("Lorenzo de' Medici")
        assert len(lorenzo_source) == 0
        assert len(lorenzo_target) == 1

    def test_get_aggregated_entity(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)

        entity = aggregator.get_aggregated_entity("Niccolo Machiavelli")
        assert entity is not None
        assert entity.name == "Niccolo Machiavelli"
        assert entity.entity_type == "Person"
        assert len(entity.profiles) == 2
        assert len(entity.associations_as_source) == 1
        assert len(entity.source_checksums) == 2

    def test_get_aggregated_entity_not_found(
        self,
        populated_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        aggregator = KnowledgeAggregator(populated_knowledge_graph)
        entity = aggregator.get_aggregated_entity("Unknown Person")
        assert entity is None


# =============================================================================
# Markdown Generation Tests
# =============================================================================


class TestBuildEntityDiscussionContent:
    def test_basic_content(self, sample_profile_machiavelli: EntityProfile) -> None:
        entity = AggregatedEntity(
            name="Niccolo Machiavelli",
            entity_type="Person",
            profiles=[sample_profile_machiavelli],
            source_checksums=["abc123def456"],
        )
        content = build_entity_discussion_content(entity)

        assert "# Niccolo Machiavelli" in content
        assert "**Type:** Person" in content
        assert "**Confidence:** 95%" in content
        assert "## Summary" in content
        assert "political philosopher" in content
        assert "## Attributes" in content
        assert "birth_date" in content
        assert "## Source Mentions" in content
        assert "## Source Documents" in content
        assert "`abc123def456" in content

    def test_with_associations(self, sample_association: EntityAssociation) -> None:
        entity = AggregatedEntity(
            name="Niccolo Machiavelli",
            entity_type="Person",
            profiles=[
                EntityProfile(
                    name="Niccolo Machiavelli",
                    entity_type="Person",
                    summary="Test",
                )
            ],
            associations_as_source=[sample_association],
        )
        content = build_entity_discussion_content(entity)

        assert "## Associations" in content
        assert "### Outgoing Relationships" in content
        assert "dedicated work to" in content
        assert "Lorenzo de' Medici" in content

    def test_no_checksums_option(self, sample_profile_machiavelli: EntityProfile) -> None:
        entity = AggregatedEntity(
            name="Test",
            entity_type="Person",
            profiles=[sample_profile_machiavelli],
            source_checksums=["abc123"],
        )
        content = build_entity_discussion_content(entity, include_checksums=False)

        assert "## Source Documents" not in content

    def test_empty_entity(self) -> None:
        entity = AggregatedEntity(
            name="Empty Entity",
            entity_type="Organization",
        )
        content = build_entity_discussion_content(entity)

        assert "# Empty Entity" in content
        assert "_No summary available._" in content
        assert "_No attributes available._" in content


class TestBuildChangelogComment:
    def test_basic_comment(self) -> None:
        comment = build_changelog_comment("Niccolo Machiavelli", "Created")
        assert "**Created:**" in comment
        assert "UTC" in comment

    def test_with_details(self) -> None:
        comment = build_changelog_comment(
            "Niccolo Machiavelli",
            "Updated",
            details="Added 3 new associations from source xyz",
        )
        assert "**Updated:**" in comment
        assert "Added 3 new associations" in comment


# =============================================================================
# Integration Tests
# =============================================================================


class TestAggregatorIntegration:
    def test_full_workflow(self, populated_knowledge_graph: KnowledgeGraphStorage) -> None:
        """Test complete workflow: aggregate entity -> generate content."""
        aggregator = KnowledgeAggregator(populated_knowledge_graph)

        # List all entities
        entities = aggregator.list_entities(entity_type="Person")
        assert len(entities) >= 1

        # Aggregate Machiavelli
        entity = aggregator.get_aggregated_entity("Niccolo Machiavelli")
        assert entity is not None

        # Generate discussion content
        content = build_entity_discussion_content(entity)

        # Verify content structure
        assert "# Niccolo Machiavelli" in content
        assert "**Type:** Person" in content
        assert "## Summary" in content
        assert "## Attributes" in content
        assert "## Source Mentions" in content
        assert "_Generated from knowledge graph" in content

    def test_handles_empty_knowledge_graph(
        self,
        temp_knowledge_graph: KnowledgeGraphStorage,
    ) -> None:
        """Test graceful handling of empty knowledge graph."""
        aggregator = KnowledgeAggregator(temp_knowledge_graph)

        assert aggregator.list_all_checksums() == []
        assert aggregator.get_all_profiles() == []
        assert aggregator.list_entities() == []
        assert aggregator.get_aggregated_entity("Anyone") is None
