from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp_server.kb_tools import (
    KBToolRegistry,
    PayloadValidationError,
    ToolExecutionError,
    register_kb_tools,
)


@pytest.fixture
def registry() -> KBToolRegistry:
    registry = KBToolRegistry()
    register_kb_tools(registry)
    return registry


def test_registers_expected_tools(registry: KBToolRegistry) -> None:
    names = {definition["name"] for definition in registry.describe()}
    assert names == {"kb_extract_concepts", "kb_create_concept", "kb_validate"}


def test_extract_concepts_returns_terms(registry: KBToolRegistry, tmp_path: Path) -> None:
    source = tmp_path / "treatise.txt"
    source.write_text(
        "The prince must balance mercy with justice. Justice guides the state.",
        encoding="utf-8",
    )

    response = registry.invoke(
        "kb_extract_concepts",
        {"source_path": str(source), "min_frequency": 1, "max_concepts": 5},
    )

    concepts = response.data["concepts"]
    assert concepts, "Expected at least one extracted concept"
    terms = {entry["term"].lower() for entry in concepts}
    assert "justice" in terms


def test_create_concept_and_validate(registry: KBToolRegistry, tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    creation = registry.invoke(
        "kb_create_concept",
        {
            "concept_name": "Royal Justice",
            "definition": "Justice exercised by a prince sustains legitimacy.",
            "sources": ["sources/original-treatise"],
            "related_concepts": ["virtue-of-mercy"],
            "primary_topic": "sovereignty",
            "kb_root": str(kb_root),
        },
    )

    written_path = Path(creation.data["path"]).resolve()
    assert written_path.exists()
    contents = written_path.read_text(encoding="utf-8")
    assert "Royal Justice" in contents
    assert "virtue-of-mercy" in contents

    report = registry.invoke("kb_validate", {"kb_root": str(kb_root)})
    assert report.data["errors"] == []
    assert report.data["documents_valid"] == 1


def test_validate_requires_existing_path(registry: KBToolRegistry) -> None:
    with pytest.raises(ToolExecutionError):
        registry.invoke("kb_validate", {"kb_root": "./does-not-exist"})


def test_create_concept_requires_definition(registry: KBToolRegistry, tmp_path: Path) -> None:
    with pytest.raises(PayloadValidationError):
        registry.invoke(
            "kb_create_concept",
            {"concept_name": "Empty Concept", "definition": "", "sources": ["sources/base"]},
        )
