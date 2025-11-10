"""Tests for knowledge base orchestration tool registrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.orchestration.toolkit import register_knowledge_base_tools
from src.orchestration.tools import ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_knowledge_base_tools(reg)
    return reg


def test_plan_structure_returns_planned_nodes(tmp_path: Path, registry: ToolRegistry):
    result = registry.execute_tool(
        "plan_knowledge_base_structure",
        {"root": str(tmp_path), "context": {"title": "Speculum", "description": "KB"}},
    )

    assert result.success
    assert result.error is None
    assert isinstance(result.output, list)
    assert any(entry["is_directory"] for entry in result.output)
    assert any(entry["content"] for entry in result.output if not entry["is_directory"])


def test_plan_structure_validates_root(registry: ToolRegistry):
    result = registry.execute_tool("plan_knowledge_base_structure", {"root": ""})
    assert not result.success
    assert result.error is not None
    assert "Argument validation failed" in result.error


def test_list_required_directories_returns_defaults(registry: ToolRegistry):
    result = registry.execute_tool("list_kb_required_directories", {})
    assert result.success
    assert result.output
    assert "concepts" in result.output


def test_load_mission_config_reads_file(tmp_path: Path, registry: ToolRegistry):
    config_path = tmp_path / "mission.yaml"
    config_path.write_text(
        """
mission:
  title: Speculum KB
  description: A detailed knowledge base for Speculum Principum.
  audience:
    - maintainers
  goals:
    - document systems
information_architecture:
  methodology: standards
  version: "1.0"
  organization_scheme: hierarchical
  organization_types:
    - topical
  depth_strategy: progressive_disclosure
  labeling_conventions:
    case: kebab-case
    max_length: 64
    preferred_language: en
    terminology_source: glossary
  navigation_priority:
    - concept_based
  search_optimization:
    full_text_enabled: true
    metadata_indexing: true
    synonym_expansion: false
    related_content_suggestions: false
  quality_standards:
    min_completeness: 0.5
    min_findability: 0.6
    required_metadata:
      - owner
    link_depth: 1
""".strip(),
        encoding="utf-8",
    )

    result = registry.execute_tool("load_kb_mission_config", {"path": str(config_path)})

    assert result.success
    assert result.error is None
    assert result.output is not None
    assert result.output["structure_context"]["title"] == "Speculum KB"
    assert list(result.output["mission"]["audience"]) == ["maintainers"]


def test_load_mission_config_requires_valid_path(tmp_path: Path, registry: ToolRegistry):
    path = tmp_path / "missing.yaml"
    result = registry.execute_tool("load_kb_mission_config", {"path": str(path)})
    assert not result.success
    assert "does not exist" in (result.error or "")
