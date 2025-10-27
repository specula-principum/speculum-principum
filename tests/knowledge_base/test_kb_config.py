from __future__ import annotations

from pathlib import Path

import pytest

from src.knowledge_base.config import MissionConfig, load_mission_config


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_mission_config_parses_valid_file(tmp_path: Path) -> None:
    mission_yaml = tmp_path / "mission.yaml"
    _write_yaml(
        mission_yaml,
        (
            'mission:\n'
            '  title: "Sample KB"\n'
            '  description: "Structured IA knowledge base."\n'
            '  audience:\n'
            '    - analysts\n'
            '    - researchers\n'
            '  goals:\n'
            '    - "Deliver reusable knowledge structures"\n'
            '    - "Support rapid discovery"\n'
            'information_architecture:\n'
            '  methodology: information-architecture\n'
            '  version: "1.0"\n'
            '  organization_scheme: hybrid\n'
            '  organization_types:\n'
            '    - topical\n'
            '    - chronological\n'
            '  depth_strategy: progressive_disclosure\n'
            '  labeling_conventions:\n'
            '    case: kebab-case\n'
            '    max_length: 80\n'
            '    preferred_language: en\n'
            '    terminology_source: config/taxonomy.yaml\n'
            '  navigation_priority:\n'
            '    - concept_based\n'
            '    - source_based\n'
            '  search_optimization:\n'
            '    full_text_enabled: true\n'
            '    metadata_indexing: true\n'
            '    synonym_expansion: true\n'
            '    related_content_suggestions: true\n'
            '  quality_standards:\n'
            '    min_completeness: 0.8\n'
            '    min_findability: 0.7\n'
            '    required_metadata:\n'
            '      - title\n'
            '      - primary_topic\n'
            '    link_depth: 2\n'
        ),
    )
    config = load_mission_config(mission_yaml)
    assert config.mission.title == "Sample KB"
    assert config.information_architecture.organization_scheme == "hybrid"
    assert config.information_architecture.labeling_conventions.case == "kebab-case"
    assert config.structure_context()["title"] == "Sample KB"


def test_load_mission_config_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_mission_config(missing)


def test_quality_standards_enforce_limits() -> None:
    payload = {
        "mission": {
            "title": "Demo",
            "description": "Mission description text",
            "audience": ["students"],
            "goals": ["Understand IA"],
        },
        "information_architecture": {
            "methodology": "information-architecture",
            "version": "1.0",
            "organization_scheme": "hybrid",
            "organization_types": ["topical"],
            "depth_strategy": "progressive_disclosure",
            "labeling_conventions": {
                "case": "kebab-case",
                "max_length": 80,
                "preferred_language": "en",
                "terminology_source": "config/taxonomy.yaml",
            },
            "navigation_priority": ["concept_based"],
            "search_optimization": {
                "full_text_enabled": True,
                "metadata_indexing": True,
                "synonym_expansion": True,
                "related_content_suggestions": True,
            },
            "quality_standards": {
                "min_completeness": 1.1,
                "min_findability": 0.5,
                "required_metadata": ["title"],
                "link_depth": 2,
            },
        },
    }
    with pytest.raises(ValueError):
        MissionConfig.from_mapping(payload)


def test_navigation_priority_allows_only_known_values() -> None:
    payload = {
        "mission": {
            "title": "Demo",
            "description": "Mission description text",
            "audience": ["students"],
            "goals": ["Understand IA"],
        },
        "information_architecture": {
            "methodology": "information-architecture",
            "version": "1.0",
            "organization_scheme": "hybrid",
            "organization_types": ["topical"],
            "depth_strategy": "progressive_disclosure",
            "labeling_conventions": {
                "case": "kebab-case",
                "max_length": 80,
                "preferred_language": "en",
                "terminology_source": "config/taxonomy.yaml",
            },
            "navigation_priority": ["unknown"],
            "search_optimization": {
                "full_text_enabled": True,
                "metadata_indexing": True,
                "synonym_expansion": True,
                "related_content_suggestions": True,
            },
            "quality_standards": {
                "min_completeness": 0.8,
                "min_findability": 0.7,
                "required_metadata": ["title"],
                "link_depth": 2,
            },
        },
    }
    with pytest.raises(ValueError):
        MissionConfig.from_mapping(payload)
