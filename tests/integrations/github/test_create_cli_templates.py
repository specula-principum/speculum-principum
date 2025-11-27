from __future__ import annotations

from pathlib import Path

import pytest

import main
from src.integrations.github.issues import IssueOutcome

REPO_ROOT = Path(__file__).resolve().parents[3]

EXTRACT_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-extraction-request.md"
IMPROVE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-quality-improvement.md"
CONCEPT_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-add-concept.md"
ENTITY_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "kb-add-entity.md"


# Skip all tests in this module until the KB templates are implemented
pytestmark = pytest.mark.skip(reason="KB issue templates not yet implemented")


@pytest.fixture(autouse=True)
def _configure_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_example_token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/knowledge")


def _run_template_cli(
    monkeypatch: pytest.MonkeyPatch,
    template: Path,
    *,
    title: str,
    labels: tuple[str, ...],
    variables: dict[str, str],
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _fake_create_issue(**kwargs: object) -> IssueOutcome:
        captured.update(kwargs)
        # Simulate a minimal IssueOutcome without creating real GitHub issues.
        return IssueOutcome(number=123, url="https://api.example/issues/123", html_url="https://github.example/issues/123")

    monkeypatch.setattr("src.cli.commands.github.create_issue", _fake_create_issue)

    argv: list[str] = ["create", "--title", title, "--template", str(template)]
    for label in labels:
        argv.extend(["--label", label])
    for key, value in variables.items():
        argv.extend(["--var", f"{key}={value}"])

    exit_code = main.main(argv)
    assert exit_code == 0
    assert captured["title"] == title
    assert captured["labels"] == list(labels)
    assert captured["repository"] == "example/knowledge"
    assert captured["token"] == "ghs_example_token"

    body = captured["body"]
    assert isinstance(body, str)
    for value in variables.values():
        assert value in body, f"Expected {value!r} to appear in rendered body."
    assert "{{" not in body, "Unresolved template placeholder detected."

    return captured


def test_cli_renders_extract_template(monkeypatch: pytest.MonkeyPatch):
    variables = {
        "source_name": "Doctrine Compendium",
        "source_path": "sources/doctrine.pdf",
        "source_type": "pdf",
        "date": "2025-10-28",
        "min_concept_freq": "3",
        "min_completeness": "0.85",
        "min_findability": "0.80",
        "issue_number": "42",
        "source_slug": "doctrine-compendium",
        "additional_instructions": "Run full validation before submission.",
    }

    captured = _run_template_cli(
        monkeypatch,
        EXTRACT_TEMPLATE,
        title="Extract knowledge from Doctrine Compendium",
        labels=("ready-for-copilot", "kb-extraction", "automated"),
        variables=variables,
    )

    assert "knowledge-base/sources/doctrine-compendium/" in captured["body"]


def test_cli_renders_improve_template(monkeypatch: pytest.MonkeyPatch):
    variables = {
        "kb_section": "knowledge-base/concepts/governance",
        "current_score": "0.62",
        "target_score": "0.80",
        "quality_issues": "- Missing related links for key governance concepts",
        "additional_instructions": "Focus on cross-linking leadership themes.",
    }

    captured = _run_template_cli(
        monkeypatch,
        IMPROVE_TEMPLATE,
        title="Improve quality of governance concepts",
        labels=("ready-for-copilot", "kb-quality", "automated"),
        variables=variables,
    )

    assert "Missing related links" in captured["body"]


def test_cli_renders_concept_template(monkeypatch: pytest.MonkeyPatch):
    variables = {
        "concept_name": "Virtuous Council",
        "primary_topic": "governance",
        "source_material": "treatises/principles.md",
        "topic_path": "governance",
        "concept_slug": "virtuous-council",
        "source_path": "sources/principles.md",
        "source_slug": "principles",
        "additional_instructions": "Emphasize implications for leadership succession.",
    }

    captured = _run_template_cli(
        monkeypatch,
        CONCEPT_TEMPLATE,
        title="Add concept: Virtuous Council",
        labels=("ready-for-copilot", "kb-concept", "manual"),
        variables=variables,
    )

    assert "kb_id: concepts/governance/virtuous-council" in captured["body"]


def test_cli_renders_entity_template(monkeypatch: pytest.MonkeyPatch):
    variables = {
        "entity_name": "Order of the Crown",
        "entity_type": "organization",
        "source_material": "archives/order.txt",
        "entity_type_slug": "organization",
        "entity_slug": "order-of-the-crown",
        "source_path": "sources/order.txt",
        "source_slug": "order",
        "additional_instructions": "Include ties to founding charter.",
    }

    captured = _run_template_cli(
        monkeypatch,
        ENTITY_TEMPLATE,
        title="Add entity: Order of the Crown",
        labels=("ready-for-copilot", "kb-entity", "manual"),
        variables=variables,
    )

    assert "kb_id: entities/organization/order-of-the-crown" in captured["body"]
