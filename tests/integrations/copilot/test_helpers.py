from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from src.integrations.copilot.helpers import (
    generate_quality_report,
    prepare_kb_extraction_context,
    validate_kb_changes,
)
from src.integrations.github.assign_copilot import IssueDetails


@pytest.fixture()
def kb_root(tmp_path: Path) -> Path:
    kb_root = tmp_path / "knowledge-base"
    kb_root.mkdir()

    concept_dir = kb_root / "concepts" / "governance"
    concept_dir.mkdir(parents=True)
    valid_doc = concept_dir / "virtuous-council.md"
    valid_doc.write_text(
        textwrap.dedent(
            """
            ---
            title: Virtuous Council
            slug: virtuous-council
            kb_id: concepts/governance/virtuous-council
            type: concept
            primary_topic: governance
            secondary_topics:
              - leadership
            tags:
              - governance
              - council
            sources:
              - kb_id: sources/doctrine-compendium
                pages: [12]
            aliases:
              - Council of Virtue
            related_concepts:
              - concepts/governance/strategy
            dublin_core:
              title: Virtuous Council
              creator: Scholar
              subject:
                - governance
            ia:
              findability_score: 0.82
              completeness: 0.9
              audience:
                - strategists
              navigation_path:
                - governance
                - councils
            ---
            The virtuous council guides rulers toward principled governance.
            """
        ).strip(),
        encoding="utf-8",
    )

    invalid_doc = concept_dir / "incomplete-council.md"
    invalid_doc.write_text(
        textwrap.dedent(
            """
            ---
            title: Incomplete Council
            slug: incomplete-council
            kb_id: concepts/governance/incomplete-council
            type: concept
            primary_topic: governance
            tags:
              - governance
            sources: []
            dublin_core:
              title: Incomplete Council
            ia:
              findability_score: 0.2
              completeness: 0.4
            ---
            This entry is intentionally incomplete.
            """
        ).strip(),
        encoding="utf-8",
    )

    return kb_root


@pytest.fixture()
def issue_details() -> IssueDetails:
    body = (
        "## Task: Extract Knowledge from Source Material\n\n"
        "**Source Path:** `sources/doctrine-compendium.pdf`\n"
        "**Source Type:** pdf\n"
        "**Processing Date:** 2025-10-28\n\n"
        "### Extraction Requirements\n"
        "- [ ] Extract concepts (min frequency: 3)\n"
        "- [ ] Build relationship graph\n\n"
        "### Output Requirements\n"
        "**Target KB Root:** `knowledge-base/`\n\n"
        "### Notes\n"
        "Ensure validation passes before completing the task.\n"
    )
    return IssueDetails(
        number=42,
        title="Extract knowledge from Doctrine Compendium",
        body=body,
        url="https://example.com/issues/42",
        labels=("ready-for-copilot", "kb-extraction"),
    )


def test_prepare_kb_extraction_context_highlights_source_and_kb(issue_details: IssueDetails, kb_root: Path):
    context = prepare_kb_extraction_context(issue_details, kb_root=kb_root)

    assert "Issue #42" in context
    assert "Source Path: sources/doctrine-compendium.pdf" in context
    assert "Required Actions" in context
    assert "Knowledge Base Snapshot" in context
    assert "Documents tracked: 2" in context


def test_validate_kb_changes_counts_documents_and_errors(kb_root: Path):
    report = validate_kb_changes(kb_root)

    assert report.documents_checked == 2
    assert report.documents_valid == 1
    assert len(report.errors) == 1
    assert report.quality.total_documents == 1
    assert report.quality.average_completeness >= 0.9


def test_generate_quality_report_writes_markdown(kb_root: Path):
    report = validate_kb_changes(kb_root)
    output_dir = kb_root.parent / "reports"
    path = generate_quality_report(kb_root, issue_number=42, output_dir=output_dir, report=report)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Knowledge Base Quality Report" in content
    assert "Documents Checked" in content
    assert "Below-threshold documents" in content
