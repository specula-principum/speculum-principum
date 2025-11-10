"""Automation helpers that mirror the GitHub workflows for Copilot agents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from src.integrations.copilot.helpers import (
    ValidationReport,
    generate_quality_report,
    validate_kb_changes,
)
from src.kb_engine.models import KBProcessingResult
from src.kb_engine.workflows import ProcessOptions, run_process_workflow


@dataclass(frozen=True)
class AutomationOutcome:
    """Aggregate result produced by an end-to-end automation run."""

    processing: KBProcessingResult
    validation: ValidationReport
    report_path: Path
    metrics_path: Path | None

    @property
    def success(self) -> bool:
        """Return ``True`` when processing and validation stages both succeed."""

        return self.processing.success and self.validation.is_successful


def run_end_to_end_automation(
    *,
    source_path: Path,
    kb_root: Path,
    mission_path: Path | None = None,
    extractors: Sequence[str] | None = None,
    issue_number: int | None = None,
    metrics_output: Path | None = None,
    report_dir: Path | None = None,
    validate_pipeline: bool = True,
) -> AutomationOutcome:
    """Execute the full automation workflow for a parsed evidence source.

    The workflow performs three high-level steps:

    1. Run the knowledge-base processing pipeline with the provided options.
    2. Validate the knowledge base contents and collect aggregate metrics.
    3. Generate a markdown quality report aligned with GitHub workflow expectations.
    """

    resolved_source = source_path.expanduser()
    resolved_kb_root = kb_root.expanduser()
    resolved_mission = mission_path.expanduser() if mission_path else None
    resolved_metrics = metrics_output.expanduser() if metrics_output else None
    resolved_report_dir = report_dir.expanduser() if report_dir else None

    options = ProcessOptions(
        source_path=resolved_source,
        kb_root=resolved_kb_root,
        mission_path=resolved_mission,
        extractors=tuple(extractors) if extractors else None,
        validate=validate_pipeline,
        metrics_path=resolved_metrics,
    )

    processing_result = run_process_workflow(options)
    validation_report = validate_kb_changes(resolved_kb_root)
    report_issue = issue_number if issue_number is not None else 0
    report_path = generate_quality_report(
        resolved_kb_root,
        report_issue,
        output_dir=resolved_report_dir,
        report=validation_report,
    )

    return AutomationOutcome(
        processing=processing_result,
        validation=validation_report,
        report_path=report_path,
        metrics_path=resolved_metrics,
    )
