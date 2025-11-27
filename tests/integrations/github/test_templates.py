from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
EXTRACT_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-extraction-request.md"
IMPROVE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-quality-improvement.md"
CONCEPT_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-add-concept.md"
ENTITY_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-add-entity.md"


# Skip all tests in this module until the KB templates are implemented
pytestmark = pytest.mark.skip(reason="KB issue templates not yet implemented")


def _load_template_parts(path: Path) -> tuple[str, str]:
    template_text = path.read_text(encoding="utf-8")
    lines = template_text.splitlines()
    assert lines and lines[0] == "---", "Template must start with front matter delimiter."

    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            front_matter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return front_matter, body

    raise AssertionError("Template front matter must end with closing delimiter.")


def test_kb_extract_template_front_matter():
    front_matter, _ = _load_template_parts(EXTRACT_TEMPLATE)
    data = yaml.safe_load(front_matter)

    assert data["title"] == "Extract knowledge from {source_name}"
    assert set(data["labels"]) == {"ready-for-copilot", "kb-extraction", "automated"}


def test_kb_extract_template_body_contains_required_sections():
    _, body = _load_template_parts(EXTRACT_TEMPLATE)

    expected_sections = [
        "## Task: Extract Knowledge from Source Material",
        "### Extraction Requirements",
        "### Output Requirements",
        "### Quality Standards",
        "### Tools to Use",
        "### Success Criteria",
        "### Notes",
    ]

    for section in expected_sections:
        assert section in body, f"Missing section heading: {section}"


def test_kb_extract_template_includes_cli_commands():
    _, body = _load_template_parts(EXTRACT_TEMPLATE)

    assert "python -m main kb process" in body
    assert "python -m main kb metrics" in body
    assert "python -m main kb validate" in body
    assert "--kb-root knowledge-base/" in body


def test_kb_improve_template_front_matter():
    front_matter, _ = _load_template_parts(IMPROVE_TEMPLATE)
    data = yaml.safe_load(front_matter)

    assert data["title"] == "Improve quality of {kb_section}"
    assert set(data["labels"]) == {"ready-for-copilot", "kb-quality", "automated"}


def test_kb_improve_template_body_contains_required_sections():
    _, body = _load_template_parts(IMPROVE_TEMPLATE)

    expected_sections = [
        "## Task: Improve Knowledge Base Quality",
        "### Quality Issues Identified",
        "### Improvement Actions",
        "### Tools to Use",
        "### Success Criteria",
        "### Notes",
    ]

    for section in expected_sections:
        assert section in body, f"Missing section heading: {section}"


def test_kb_improve_template_includes_cli_commands():
    _, body = _load_template_parts(IMPROVE_TEMPLATE)

    assert "python -m main kb metrics" in body
    assert "python -m main kb improve" in body
    assert "--section {kb_section}" in body
    assert "--kb-root knowledge-base/" in body


def test_kb_add_concept_template_front_matter():
    front_matter, _ = _load_template_parts(CONCEPT_TEMPLATE)
    data = yaml.safe_load(front_matter)

    assert data["title"] == "Add concept: {concept_name}"
    assert set(data["labels"]) == {"ready-for-copilot", "kb-concept", "manual"}


def test_kb_add_concept_template_body_contains_required_sections():
    _, body = _load_template_parts(CONCEPT_TEMPLATE)

    expected_sections = [
        "## Task: Add New Concept to Knowledge Base",
        "### Requirements",
        "### Document Location",
        "### Metadata Requirements",
        "### Tools to Use",
        "### Success Criteria",
        "### Notes",
    ]

    for section in expected_sections:
        assert section in body, f"Missing section heading: {section}"


def test_kb_add_concept_template_includes_cli_commands_and_metadata():
    _, body = _load_template_parts(CONCEPT_TEMPLATE)

    assert "```yaml" in body
    assert "kb_id: concepts/{topic_path}/{concept_slug}" in body
    assert "python -m main extract concepts" in body
    assert "python -m main kb create-concept" in body
    assert "python -m main kb validate" in body
    assert "--kb-root knowledge-base/" in body


def test_kb_add_entity_template_front_matter():
    front_matter, _ = _load_template_parts(ENTITY_TEMPLATE)
    data = yaml.safe_load(front_matter)

    assert data["title"] == "Add entity: {entity_name}"
    assert set(data["labels"]) == {"ready-for-copilot", "kb-entity", "manual"}


def test_kb_add_entity_template_body_contains_required_sections():
    _, body = _load_template_parts(ENTITY_TEMPLATE)

    expected_sections = [
        "## Task: Add New Entity to Knowledge Base",
        "### Requirements",
        "### Document Location",
        "### Metadata Requirements",
        "### Tools to Use",
        "### Success Criteria",
        "### Notes",
    ]

    for section in expected_sections:
        assert section in body, f"Missing section heading: {section}"


def test_kb_add_entity_template_includes_cli_commands_and_metadata():
    _, body = _load_template_parts(ENTITY_TEMPLATE)

    assert "kb_id: entities/{entity_type_slug}/{entity_slug}" in body
    assert "python -m main extract entities" in body
    assert "python -m main kb create-entity" in body
    assert "python -m main kb validate" in body
    assert "--kb-root knowledge-base/" in body