from __future__ import annotations

from pathlib import Path
import textwrap

import main
import pytest

from src.integrations.copilot.helpers import prepare_kb_extraction_context
from src.integrations.github.assign_copilot import (
    IssueDetails,
    compose_agent_prompt,
    generate_branch_name,
)
from src.integrations.github.automation import run_end_to_end_automation
from src.kb_engine.models import KBProcessingResult, ProcessingContext, StageResult
from src.kb_engine.workflows import ProcessOptions


def _write_kb_document(path: Path, *, findability: float, completeness: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""
            ---
            title: Virtuous Council
            slug: virtuous-council
            kb_id: concepts/governance/virtuous-council
            type: concept
            primary_topic: governance
            tags:
              - governance
            sources:
              - kb_id: sources/doctrine
                pages: [1]
            dublin_core:
              title: Virtuous Council
            ia:
              findability_score: {findability}
              completeness: {completeness}
            ---
            Principled governance guidance.
            """
        ).strip(),
        encoding="utf-8",
    )


def _stub_processing_result(options: ProcessOptions) -> KBProcessingResult:
    context = ProcessingContext(
        source_path=options.source_path,
        kb_root=options.kb_root,
        mission_config=options.mission_path,
        extractors=tuple(options.extractors or ()),
        validate=options.validate,
    )
    stage = StageResult(stage="analysis", metrics={"documents": 1.0})
    return KBProcessingResult(context=context, stages=(stage,), warnings=(), errors=())


def _build_issue() -> IssueDetails:
    body = (
        "## Task: Extract Knowledge from Source Material\n\n"
        "**Source Path:** `evidence/doctrine.md`\n"
        "**Source Type:** markdown\n"
        "**Processing Date:** 2025-10-28\n\n"
        "### Extraction Requirements\n"
        "- [ ] Extract concepts\n"
        "- [ ] Build relationship graph\n\n"
        "### Output Requirements\n"
        "**Target KB Root:** `knowledge-base/`\n\n"
        "### Notes\n"
        "Ensure validation passes before completing the task.\n"
    )
    return IssueDetails(
        number=314,
        title="Extract knowledge from doctrine",
        body=body,
        url="https://example.test/issues/314",
        labels=("ready-for-copilot", "kb-extraction"),
    )


def test_mock_agent_workflow_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "knowledge-base"
    report_dir = tmp_path / "reports"
    metrics_path = tmp_path / "metrics.json"
    mission_path = tmp_path / "config" / "mission.yaml"

    source_dir.mkdir()
    kb_root.mkdir()
    report_dir.mkdir()
    mission_path.parent.mkdir(parents=True, exist_ok=True)
    mission_path.write_text("mission: doctrine-analysis\n", encoding="utf-8")

    _write_kb_document(
        kb_root / "concepts" / "governance" / "virtuous-council.md",
        findability=0.9,
        completeness=0.92,
    )

    issue = _build_issue()
    branch_name = generate_branch_name(issue.number, issue.title)
    context = prepare_kb_extraction_context(issue, kb_root=kb_root)
    prompt = compose_agent_prompt(issue, branch_name, extra_instructions=context)

    assert f"Issue #{issue.number}" in prompt
    assert branch_name in prompt
    assert "Knowledge Base Snapshot" in prompt

    captured: dict[str, ProcessOptions] = {}

    def fake_run_process_workflow(options: ProcessOptions) -> KBProcessingResult:
        captured["options"] = options
        return _stub_processing_result(options)

    monkeypatch.setattr(
        "src.integrations.github.automation.run_process_workflow",
        fake_run_process_workflow,
    )

    outcome = run_end_to_end_automation(
        source_path=source_dir,
        kb_root=kb_root,
        mission_path=mission_path,
        extractors=("concepts", "entities"),
        issue_number=issue.number,
        metrics_output=metrics_path,
        report_dir=report_dir,
    )

    options = captured["options"]
    assert options.source_path == source_dir
    assert options.kb_root == kb_root
    assert options.mission_path == mission_path
    assert options.extractors == ("concepts", "entities")
    assert options.metrics_path == metrics_path
    assert options.validate is True

    assert outcome.success is True
    report_text = outcome.report_path.read_text(encoding="utf-8")
    assert "Knowledge Base Quality Report" in report_text
    assert f"*Documents Valid:* {outcome.validation.documents_valid}" in report_text


def test_mock_agent_workflow_surfaces_validation_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "knowledge-base"
    report_dir = tmp_path / "reports"

    source_dir.mkdir()
    kb_root.mkdir()
    report_dir.mkdir()

    _write_kb_document(
        kb_root / "concepts" / "governance" / "virtue.md",
        findability=0.35,
        completeness=0.4,
    )

    issue = _build_issue()
    branch_name = generate_branch_name(issue.number, issue.title)
    context = prepare_kb_extraction_context(issue, kb_root=kb_root)
    prompt = compose_agent_prompt(issue, branch_name, extra_instructions=context)

    assert "Focus exclusively on editing" in prompt
    assert "Required Actions" in context

    def fake_run_process_workflow(options: ProcessOptions) -> KBProcessingResult:
        return _stub_processing_result(options)

    monkeypatch.setattr(
        "src.integrations.github.automation.run_process_workflow",
        fake_run_process_workflow,
    )

    outcome = run_end_to_end_automation(
        source_path=source_dir,
        kb_root=kb_root,
        issue_number=issue.number,
        report_dir=report_dir,
    )

    assert outcome.processing.success is True
    assert outcome.validation.is_successful is False
    assert outcome.success is False
    assert outcome.validation.errors

    report_text = outcome.report_path.read_text(encoding="utf-8")
    assert "Errors" in report_text
    assert "Below-threshold documents" in report_text
