from __future__ import annotations

import textwrap
from pathlib import Path
import json

import pytest

import main
from src.integrations.copilot.helpers import ValidationReport
from src.integrations.github.assign_copilot import IssueDetails
from src.integrations.github.automation import AutomationOutcome
from src.kb_engine.models import KBProcessingResult, ProcessingContext, StageResult
from src.knowledge_base.validation import QualityMetrics


@pytest.fixture()
def kb_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge-base"
    root.mkdir()

    concept_dir = root / "concepts" / "governance"
    concept_dir.mkdir(parents=True)
    concept_dir.joinpath("virtuous-council.md").write_text(
        textwrap.dedent(
            """
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
              findability_score: 0.8
              completeness: 0.9
            ---
            A validated concept entry.
            """
        ).strip(),
        encoding="utf-8",
    )

    concept_dir.joinpath("incomplete.md").write_text(
        textwrap.dedent(
            """
            ---
            title: Incomplete
            slug: incomplete
            kb_id: concepts/governance/incomplete
            type: concept
            primary_topic: governance
            tags:
              - governance
            sources: []
            dublin_core:
              title: Incomplete
            ia:
              findability_score: 0.3
              completeness: 0.2
            ---
            An intentionally invalid entry.
            """
        ).strip(),
        encoding="utf-8",
    )

    return root


def test_copilot_kb_extract_command_renders_context(monkeypatch: pytest.MonkeyPatch, capsys, kb_root: Path):
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/knowledge")

    issue = IssueDetails(
        number=99,
        title="Extract sample knowledge",
        body=(
            "## Task: Extract Knowledge from Source Material\n\n"
            "**Source Path:** `sources/sample.pdf`\n"
            "**Source Type:** pdf\n"
            "**Processing Date:** 2025-10-28\n"
            "- [ ] Extract concepts\n"
        ),
        url="https://example.com/issues/99",
        labels=("ready-for-copilot",),
    )

    def _fake_fetch_issue_details(**_: object) -> IssueDetails:
        return issue

    monkeypatch.setattr("src.integrations.copilot.commands.fetch_issue_details", _fake_fetch_issue_details)

    exit_code = main.main([
        "copilot",
        "kb-extract",
        "--issue",
        "99",
        "--kb-root",
        str(kb_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Issue #99" in captured.out
    assert "Source Path: sources/sample.pdf" in captured.out


def test_copilot_kb_validate_reports_errors(capsys, kb_root: Path):
    exit_code = main.main([
        "copilot",
        "kb-validate",
        "--kb-root",
        str(kb_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Documents Checked" in captured.out
    assert "Errors:" in captured.out


def test_copilot_kb_validate_missing_root(tmp_path: Path, capsys) -> None:
    missing_root = tmp_path / "kb"

    exit_code = main.main([
        "copilot",
        "kb-validate",
        "--kb-root",
        str(missing_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Knowledge base root does not exist" in captured.err


def test_copilot_kb_report_writes_file(tmp_path: Path, kb_root: Path):
    output_dir = tmp_path / "reports"

    exit_code = main.main([
        "copilot",
        "kb-report",
        "--issue",
        "77",
        "--kb-root",
        str(kb_root),
        "--output-dir",
        str(output_dir),
    ])

    report_path = output_dir / "quality-77.md"
    assert report_path.exists()
    assert exit_code == 1
    content = report_path.read_text(encoding="utf-8")
    assert "Knowledge Base Quality Report" in content
    assert "Errors" in content


def test_copilot_verify_accuracy_command(tmp_path: Path, kb_root: Path, capsys) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        textwrap.dedent(
            """
            expectations:
              concepts:
                                - concepts/governance/virtuous-council
                                - concepts/governance/incomplete
            """
        ).strip(),
        encoding="utf-8",
    )

    exit_code = main.main([
        "copilot",
        "verify-accuracy",
        "--scenario",
        str(scenario_path),
        "--kb-root",
        str(kb_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Scenario:" in captured.out
    assert "Success: yes" in captured.out


def test_copilot_verify_accuracy_json_failure(tmp_path: Path, kb_root: Path, capsys) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        textwrap.dedent(
            """
            expectations:
              concepts:
                - concepts/governance/missing
            """
        ).strip(),
        encoding="utf-8",
    )

    exit_code = main.main([
        "copilot",
        "verify-accuracy",
        "--scenario",
        str(scenario_path),
        "--kb-root",
        str(kb_root),
        "--json",
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "\"success\": false" in captured.out.lower()
    assert "missing" in captured.out


def test_copilot_verify_accuracy_detects_unexpected(tmp_path: Path, kb_root: Path, capsys) -> None:
    # No expectations, so any KB content should count as unexpected noise.
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text("expectations: {}\n", encoding="utf-8")

    exit_code = main.main([
        "copilot",
        "verify-accuracy",
        "--scenario",
        str(scenario_path),
        "--kb-root",
        str(kb_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Unexpected" in captured.out
    assert "Success: no" in captured.out


def test_copilot_verify_accuracy_writes_output(tmp_path: Path, kb_root: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    output_path = tmp_path / "reports" / "accuracy.json"
    scenario_path.write_text(
        textwrap.dedent(
            """
            expectations:
              concepts:
                                - concepts/governance/virtuous-council
                                - concepts/governance/incomplete
            """
        ).strip(),
        encoding="utf-8",
    )

    exit_code = main.main([
        "copilot",
        "verify-accuracy",
        "--scenario",
        str(scenario_path),
        "--kb-root",
        str(kb_root),
        "--output",
        str(output_path),
    ])

    assert exit_code == 0
    assert output_path.exists()
    content = json.loads(output_path.read_text(encoding="utf-8"))
    assert content["overall"]["success"] is True


def test_copilot_mcp_serve_lists_tools(capsys):
    exit_code = main.main([
        "copilot",
        "mcp-serve",
        "--list-tools",
    ])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "kb_extract_concepts" in captured.out


def test_copilot_kb_automation_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "knowledge-base"
    report_dir = tmp_path / "reports"
    metrics_path = tmp_path / "metrics.json"
    report_path = report_dir / "quality-5.md"

    source_dir.mkdir()
    kb_root.mkdir()
    report_dir.mkdir()
    report_path.write_text("report", encoding="utf-8")
    metrics_path.write_text("{}", encoding="utf-8")

    context = ProcessingContext(source_dir, kb_root)
    stage = StageResult(stage="analysis", metrics={"documents": 1.0})
    processing = KBProcessingResult(context=context, stages=(stage,), warnings=(), errors=())
    metrics = QualityMetrics(
        total_documents=1,
        average_completeness=0.9,
        average_findability=0.95,
        below_threshold=(),
    )
    validation = ValidationReport(
        kb_root=kb_root,
        documents_checked=1,
        documents_valid=1,
        errors=(),
        warnings=(),
        quality=metrics,
    )
    outcome = AutomationOutcome(
        processing=processing,
        validation=validation,
        report_path=report_path,
        metrics_path=metrics_path,
    )

    captured_args: dict[str, object] = {}

    def fake_run_end_to_end_automation(**kwargs):
        captured_args.update(kwargs)
        return outcome

    monkeypatch.setattr(
        "src.integrations.copilot.commands.run_end_to_end_automation",
        fake_run_end_to_end_automation,
    )

    exit_code = main.main([
        "copilot",
        "kb-automation",
        "--source",
        str(source_dir),
        "--kb-root",
        str(kb_root),
        "--issue",
        "5",
        "--metrics-output",
        str(metrics_path),
        "--report-dir",
        str(report_dir),
    ])

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "KB PROCESSING: SUCCESS" in stdout
    assert f"Quality report: {report_path}" in stdout
    assert captured_args["source_path"] == source_dir
    assert captured_args["kb_root"] == kb_root
    assert captured_args["issue_number"] == 5
    assert captured_args["metrics_output"] == metrics_path


def test_copilot_kb_automation_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "knowledge-base"
    report_path = tmp_path / "reports" / "quality-9.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("report", encoding="utf-8")

    context = ProcessingContext(source_dir, kb_root)
    stage = StageResult(stage="analysis", metrics={})
    processing = KBProcessingResult(context=context, stages=(stage,), warnings=(), errors=("stage failure",))
    metrics = QualityMetrics(
        total_documents=1,
        average_completeness=0.6,
        average_findability=0.4,
        below_threshold=("concepts/statecraft/virtue",),
    )
    validation = ValidationReport(
        kb_root=kb_root,
        documents_checked=1,
        documents_valid=0,
        errors=("concepts/statecraft/virtue: missing metadata",),
        warnings=(),
        quality=metrics,
    )
    outcome = AutomationOutcome(
        processing=processing,
        validation=validation,
        report_path=report_path,
        metrics_path=None,
    )

    def fake_run_end_to_end_automation(**_: object) -> AutomationOutcome:
        return outcome

    monkeypatch.setattr(
        "src.integrations.copilot.commands.run_end_to_end_automation",
        fake_run_end_to_end_automation,
    )

    exit_code = main.main([
        "copilot",
        "kb-automation",
        "--source",
        str(source_dir),
        "--kb-root",
        str(kb_root),
    ])

    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "KB PROCESSING: FAILED" in stdout
    assert "concepts/statecraft/virtue" in stdout
