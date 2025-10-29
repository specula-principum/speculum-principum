from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from src.integrations.github.automation import run_end_to_end_automation
from src.kb_engine.models import KBProcessingResult, ProcessingContext, StageResult
from src.kb_engine.workflows import ProcessOptions


def _write_document(path: Path, *, findability: float, completeness: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""
            ---
            title: Virtue
            slug: virtue
            kb_id: concepts/statecraft/virtue
            type: concept
            primary_topic: statecraft
            tags:
              - governance
            sources:
              - kb_id: sources/prince
                pages: [1]
            dublin_core:
              title: Virtue
            ia:
              findability_score: {findability}
              completeness: {completeness}
            ---
            Prudence sustains lasting rule.
            """
        ).strip(),
        encoding="utf-8",
    )


def _stub_process_result(options) -> KBProcessingResult:
    context = ProcessingContext(
        options.source_path,
        options.kb_root,
        options.mission_path,
        tuple(options.extractors or ()),
        options.validate,
    )
    stage = StageResult(stage="analysis", metrics={"documents": 1.0})
    return KBProcessingResult(context=context, stages=(stage,), warnings=(), errors=())


def test_run_end_to_end_automation_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"
    report_dir = tmp_path / "reports"
    metrics_path = tmp_path / "metrics.json"

    source_dir.mkdir()
    kb_root.mkdir()
    metrics_path.touch()

    _write_document(kb_root / "concepts" / "statecraft" / "virtue.md", findability=0.85, completeness=0.9)

    captured: dict[str, ProcessOptions] = {}

    def fake_run_process_workflow(options):
        captured["options"] = options
        return _stub_process_result(options)

    monkeypatch.setattr(
        "src.integrations.github.automation.run_process_workflow",
        fake_run_process_workflow,
    )

    outcome = run_end_to_end_automation(
        source_path=source_dir,
        kb_root=kb_root,
        issue_number=42,
        metrics_output=metrics_path,
        report_dir=report_dir,
    )

    options = captured["options"]
    assert options.source_path == source_dir
    assert options.kb_root == kb_root
    assert options.metrics_path == metrics_path
    assert options.validate is True

    assert outcome.success is True
    assert outcome.report_path.exists()
    assert outcome.report_path.parent == report_dir
    report_text = outcome.report_path.read_text(encoding="utf-8")
    assert "Knowledge Base Quality Report" in report_text
    assert outcome.metrics_path == metrics_path


def test_run_end_to_end_automation_reports_validation_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"

    source_dir.mkdir()
    kb_root.mkdir()

    _write_document(kb_root / "concepts" / "statecraft" / "virtue.md", findability=0.4, completeness=0.5)

    def fake_run_process_workflow(options: ProcessOptions) -> KBProcessingResult:
        return _stub_process_result(options)

    monkeypatch.setattr(
        "src.integrations.github.automation.run_process_workflow",
        fake_run_process_workflow,
    )

    outcome = run_end_to_end_automation(
        source_path=source_dir,
        kb_root=kb_root,
        issue_number=7,
    )

    assert outcome.processing.success is True
    assert outcome.validation.is_successful is False
    assert outcome.success is False
    assert outcome.validation.errors  # validation should report issues
    report_text = outcome.report_path.read_text(encoding="utf-8")
    assert "Errors" in report_text
