from __future__ import annotations

from pathlib import Path

import pytest

from src.knowledge_base.config import MissionConfig
from src.knowledge_base.structure import (
    StructureNode,
    materialize_structure,
    plan_structure,
    render_templates,
)


def test_plan_structure_uses_context(tmp_path: Path) -> None:
    plan = plan_structure(tmp_path, context={"title": "Atlas", "description": "Reference map"})
    index_node = next(item for item in plan if item.path == tmp_path / "index.md")
    assert index_node.content is not None
    assert "Atlas" in index_node.content
    assert "Reference map" in index_node.content


def test_materialize_structure_creates_files(tmp_path: Path) -> None:
    plan = plan_structure(tmp_path)
    materialize_structure(plan)
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "concepts").is_dir()


def test_materialize_structure_force_overwrites(tmp_path: Path) -> None:
    plan = plan_structure(tmp_path)
    materialize_structure(plan)
    index_path = tmp_path / "index.md"
    original = index_path.read_text(encoding="utf-8")
    index_path.write_text("custom content\n", encoding="utf-8")
    materialize_structure(plan)
    assert index_path.read_text(encoding="utf-8") == "custom content\n"
    materialize_structure(plan, force=True)
    assert index_path.read_text(encoding="utf-8") == original


def test_render_templates_requires_context(tmp_path: Path) -> None:
    node = StructureNode(path=tmp_path / "index.md", children=None, template="{missing_value}")
    with pytest.raises(ValueError):
        render_templates(node, {})


def test_initialize_with_mission_context(tmp_path: Path) -> None:
    payload = {
        "mission": {
            "title": "Mission Title",
            "description": "Mission description text",
            "audience": ["students"],
            "goals": ["Understand"],
        },
        "information_architecture": {
            "methodology": "information-architecture",
            "version": "1.0",
            "organization_scheme": "hybrid",
            "organization_types": ["topical"],
            "depth_strategy": "progressive_disclosure",
            "labeling_conventions": {
                "case": "kebab-case",
                "max_length": 50,
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
                "min_completeness": 0.7,
                "min_findability": 0.6,
                "required_metadata": ["title"],
                "link_depth": 2,
            },
        },
    }
    mission = MissionConfig.from_mapping(payload)
    plan = plan_structure(tmp_path, context=mission.structure_context())
    index_node = next(item for item in plan if item.path == tmp_path / "index.md")
    assert index_node.content is not None
    assert "Mission Title" in index_node.content
