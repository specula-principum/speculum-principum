"""End-to-end CLI dry-run validation for the workflow refactor pipeline."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

import pytest

import main as cli_main
from src.core.batch_processor import BatchMetrics, SiteMonitorIssueDiscovery
from src.core.issue_processor import IssueProcessingStatus, ProcessingResult


@pytest.mark.e2e
def test_cli_pipeline_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Run monitor → assign-workflows → process-issues via the CLI with dry-run stubs."""

    # Prepare configuration directory structure expected by validators
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    (workflow_dir / "example.yaml").write_text("name: Example Workflow\nversion: 1.0\n")

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "sites:",
                "  - url: https://example.com",
                "    name: Example Site",
                "github:",
                "  repository: ${GITHUB_REPOSITORY}",
                "search:",
                "  api_key: ${GOOGLE_API_KEY}",
                "  search_engine_id: ${GOOGLE_SEARCH_ENGINE_ID}",
                "  daily_query_limit: 90",
                "  results_per_query: 10",
                "  date_range_days: 30",
                "agent:",
                "  username: ${GITHUB_ACTOR}",
                f"  workflow_directory: \"{workflow_dir}\"",
                f"  template_directory: \"{template_dir}\"",
                f"  output_directory: \"{output_dir}\"",
                f"storage_path: \"{tmp_path / 'processed.json'}\"",
                "log_level: INFO",
            ]
        )
    )

    # Environment substitution required by ConfigManager
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_ACTOR", "cli-bot")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    telemetry_dir = tmp_path / "telemetry"
    monkeypatch.setenv("SPECULUM_CLI_TELEMETRY_DIR", str(telemetry_dir))

    pipeline_events: list[tuple[str, dict]] = []
    issue_finder_calls: list[dict] = []
    captured_cli_results: list = []
    recorded_static_fields: list[dict] = []

    import src.utils.telemetry as telemetry_module
    import src.utils.telemetry_helpers as telemetry_helpers_module

    original_attach_static_fields = telemetry_module.attach_static_fields

    def tracking_attach_static_fields(publishers, static_fields):
        recorded_static_fields.append(dict(static_fields))
        return original_attach_static_fields(publishers, static_fields)

    monkeypatch.setattr(telemetry_module, "attach_static_fields", tracking_attach_static_fields)
    monkeypatch.setattr(telemetry_helpers_module, "attach_static_fields", tracking_attach_static_fields)

    dummy_issue_details = {
        301: {
            "title": "Discovery item 301",
            "labels": ["site-monitor", "state::assigned"],
        },
        302: {
            "title": "Discovery item 302",
            "labels": ["site-monitor", "state::assigned"],
        },
    }

    specialist_guidance_block = (
        "### Persona: Intelligence Analyst\n"
        "- **Role**: Intelligence Analyst\n"
        "- **Objective**: Deliver actionable insight on Example Workflow\n\n"
        "### Key Insights from AI Assessment\n"
        "- Summary: Example insight\n"
        "- Primary source: https://example.com\n\n"
        "### Required Actions\n"
        "1. Review discovery context\n"
        "2. Populate deliverable draft\n\n"
        "### Deliverables\n"
        "- [ ] study/example/report.md\n\n"
        "### Collaboration Notes\n"
        "- Coordinate with workflow lead\n"
    )

    copilot_assignment_block = (
        "**Assignee**: @github-copilot[bot]\n"
        "**Due**: 2025-10-02T09:00:00Z\n\n"
        "**Summary**: Execute specialist guidance for Example Workflow.\n\n"
        "**Acceptance Criteria**:\n"
        "- [ ] Update study/example/report.md\n"
        "- [ ] Document source vetting notes\n\n"
        "**Validation Steps**:\n"
        "- [ ] Review branch example/feature\n\n"
        "**Notes**: Collaborate with the specialist if scope shifts.\n"
    )

    class DummyAssignmentAgent:
        def __init__(
            self,
            github_token: str,
            repo_name: str,
            config_path: str,
            enable_ai: bool,
            telemetry_publishers: list | None = None,
            allowed_categories: Iterable[str] | None = None,
        ) -> None:
            self.github_token = github_token
            self.repo_name = repo_name
            self.config_path = config_path
            self.enable_ai = enable_ai
            self.telemetry_publishers = telemetry_publishers or []
            self.allowed_categories = allowed_categories

        def process_issues_batch(self, *, limit: int, dry_run: bool) -> dict:
            pipeline_events.append(("assign", {"limit": limit, "dry_run": dry_run}))
            workflows = [
                "Case Law Precedent Explorer",
                "Inter-Agency Coordination Briefs",
                "Witness & Expert Reliability Assessment",
            ]

            reason_code_sets = [
                [
                    "PERSON_ENTITY_DETECTED",
                    "PLACE_ENTITY_DETECTED",
                    "THING_ENTITY_DETECTED",
                    "HIGH_ENTITY_COVERAGE",
                    "STATUTE_CITATION_DETECTED",
                    "AUTO_ASSIGN_THRESHOLD_MET",
                ],
                [
                    "PERSON_ENTITY_DETECTED",
                    "PLACE_ENTITY_DETECTED",
                    "PARTIAL_ENTITY_COVERAGE",
                    "INTERAGENCY_CONTEXT_DETECTED",
                    "LABEL_TRIGGER_MATCH",
                ],
                [
                    "PERSON_ENTITY_DETECTED",
                    "THING_ENTITY_MISSING",
                    "LOW_ENTITY_COVERAGE",
                    "LEGAL_CONTEXT_NOT_DETECTED",
                ],
            ]

            coverage_values = [0.82, 0.55, 0.21]
            missing_entities = [[], ["thing"], ["place", "thing"]]
            legal_signals_list = [
                {
                    "statutes": 1.0,
                    "statute_matches": ["18 U.S.C. § 371", "5 C.F.R. § 2635"],
                    "precedent": 1.0,
                    "precedent_matches": ["Smith v. Jones"],
                    "interagency": 0.0,
                    "interagency_terms": [],
                },
                {
                    "statutes": 0.0,
                    "statute_matches": [],
                    "precedent": 0.0,
                    "precedent_matches": [],
                    "interagency": 1.0,
                    "interagency_terms": ["GAO", "FBI"],
                },
                {
                    "statutes": 0.0,
                    "statute_matches": [],
                    "precedent": 0.0,
                    "precedent_matches": [],
                    "interagency": 0.0,
                    "interagency_terms": [],
                },
            ]

            results: list[dict] = []
            issue_count = limit if limit is not None else 0
            for idx in range(issue_count):
                reason_codes = reason_code_sets[idx % len(reason_code_sets)]
                workflow_name = workflows[idx % len(workflows)]
                coverage = coverage_values[idx % len(coverage_values)]
                missing = missing_entities[idx % len(missing_entities)]
                legal_signals = legal_signals_list[idx % len(legal_signals_list)]
                issue_number = 500 + idx

                ai_analysis = {
                    "summary": f"Analysis for issue {issue_number} focusing on {workflow_name}.",
                    "key_topics": ["statutes", "jurisdiction"],
                    "suggested_workflows": [workflow_name],
                    "confidence_scores": {workflow_name: 0.9 - (idx * 0.1)},
                    "technical_indicators": ["legal"],
                    "urgency_level": "medium",
                    "content_type": "research",
                    "combined_scores": {workflow_name: max(0.5, 0.85 - idx * 0.1)},
                    "reason_codes": reason_codes,
                    "entity_summary": {
                        "coverage": coverage,
                        "counts": {"person": 3 - idx, "place": 2 - (idx // 2), "thing": max(0, 1 - idx)},
                        "present_base_entities": ["person", "place"] if idx < 2 else ["person"],
                        "missing_base_entities": missing,
                        "source": "heuristic",
                    },
                    "legal_signals": legal_signals,
                }

                results.append(
                    {
                        "issue_number": issue_number,
                        "action_taken": "auto_assigned",
                        "assigned_workflow": workflow_name,
                        "assigned_workflows": [workflow_name],
                        "labels_added": [
                            f"workflow::{workflow_name.lower().replace(' ', '-')}",
                            "state::assigned",
                        ],
                        "labels_removed": [],
                        "message": f"AI analysis selected {workflow_name}",
                        "dry_run": dry_run,
                        "reason_codes": reason_codes,
                        "ai_analysis": ai_analysis,
                    }
                )

            statistics = {
                "auto_assigned": issue_count,
                "review_requested": 0,
                "clarification_requested": 0,
                "errors": 0,
            }

            return {
                "total_issues": issue_count,
                "processed": issue_count,
                "duration_seconds": 1.2,
                "statistics": statistics,
                "results": results,
            }

        def get_assignment_statistics(self) -> dict:
            pipeline_events.append(("assign_statistics", {}))
            return {
                "total_site_monitor_issues": 5,
                "unassigned": 2,
                "assigned": 3,
                "needs_clarification": 1,
                "needs_review": 0,
                "feature_labeled": 1,
                "workflow_breakdown": {"Example Workflow": 3},
                "label_distribution": {
                    "workflow::example": 3,
                    "state::assigned": 2,
                    "monitor::triage": 1,
                },
            }

    class DummyFallbackAgent:
        def __init__(
            self,
            github_token: str,
            repo_name: str,
            config_path: str,
            telemetry_publishers: list | None = None,
            allowed_categories: Iterable[str] | None = None,
        ) -> None:
            self.github_token = github_token
            self.repo_name = repo_name
            self.config_path = config_path
            self.telemetry_publishers = telemetry_publishers or []
            self.allowed_categories = allowed_categories

        def add_telemetry_publisher(self, publisher) -> None:
            self.telemetry_publishers.append(publisher)

        def process_issues_batch(self, *, limit: int, dry_run: bool) -> dict:
            pipeline_events.append(("assign_fallback", {"limit": limit, "dry_run": dry_run}))
            statistics = {
                "assign_workflow": 1,
                "request_clarification": 1,
                "skip_feature": 0,
                "skip_needs_clarification": 0,
                "error": 0,
            }
            return {
                "total_issues": 2,
                "processed": 1,
                "duration_seconds": 0.4,
                "statistics": statistics,
                "results": [
                    {
                        "issue_number": 401,
                        "action_taken": "assign_workflow",
                        "assigned_workflow": "Fallback Workflow",
                        "labels_added": [
                            "workflow::fallback",
                            "state::assigned",
                            "analysis",
                        ],
                        "labels_removed": [
                            "monitor::triage",
                            "state::discovery",
                        ],
                        "message": "Assigned via fallback heuristics",
                        "dry_run": dry_run,
                    },
                    {
                        "issue_number": 402,
                        "action_taken": "request_clarification",
                        "assigned_workflow": None,
                        "labels_added": ["needs clarification"],
                        "labels_removed": [],
                        "message": "Awaiting additional context",
                        "dry_run": dry_run,
                    },
                ],
            }

        def get_assignment_statistics(self) -> dict:
            pipeline_events.append(("assign_fallback_statistics", {}))
            return {
                "total_site_monitor_issues": 4,
                "unassigned": 1,
                "assigned": 3,
                "needs_clarification": 1,
                "needs_review": 0,
                "feature_labeled": 0,
                "workflow_breakdown": {"Fallback Workflow": 2},
                "label_distribution": {
                    "workflow::fallback": 2,
                    "state::assigned": 3,
                    "monitor::triage": 1,
                },
            }

    class DummyWorkflowInfo:
        def __init__(self, name: str, *, category: str, threshold: float, legacy: bool = False) -> None:
            self.name = name
            self.category = category
            self.confidence_threshold = threshold
            self.legacy_mode = legacy
            self.workflow_version = "1.0.0" if not legacy else None

        def is_taxonomy(self) -> bool:
            return bool(self.workflow_version and self.category and not self.legacy_mode)

    class DummyWorkflowMatcher:
        def __init__(self) -> None:
            self._workflows = {
                "Example Workflow": DummyWorkflowInfo(
                    "Example Workflow",
                    category="entity-foundation",
                    threshold=0.82,
                ),
                "Fallback Workflow": DummyWorkflowInfo(
                    "Fallback Workflow",
                    category="legacy",
                    threshold=0.7,
                    legacy=True,
                ),
                "Case Law Precedent Explorer": DummyWorkflowInfo(
                    "Case Law Precedent Explorer",
                    category="legal-research",
                    threshold=0.8,
                ),
                "Inter-Agency Coordination Briefs": DummyWorkflowInfo(
                    "Inter-Agency Coordination Briefs",
                    category="operational-coordination",
                    threshold=0.75,
                ),
                "Witness & Expert Reliability Assessment": DummyWorkflowInfo(
                    "Witness & Expert Reliability Assessment",
                    category="entity-foundation",
                    threshold=0.65,
                ),
            }

        def get_workflow_by_name(self, workflow_name: str):
            return self._workflows.get(workflow_name)

    class DummyMonitorService:
        def __init__(self) -> None:
            matcher = DummyWorkflowMatcher()
            self.issue_processor = SimpleNamespace(workflow_matcher=matcher)

        def run_monitoring_cycle(self, *, create_individual_issues: bool) -> dict:
            pipeline_events.append(("monitor", {"create_individual_issues": create_individual_issues}))
            return {
                "success": True,
                "new_results_found": 2,
                "individual_issues_created": 0,
                "issue_processing_results": [
                    {
                        "issue_number": 211,
                        "status": "completed",
                        "workflow": "Example Workflow",
                        "deliverables": ["study/example/report.md"],
                        "error": None,
                    },
                    {
                        "issue_number": 212,
                        "status": "needs_clarification",
                        "workflow": "Witness & Expert Reliability Assessment",
                        "deliverables": [],
                        "error": None,
                    },
                ],
            }

        def process_existing_issues(self, *, limit: int, force_reprocess: bool) -> dict:
            pipeline_events.append(
                (
                    "process_from_monitor",
                    {"limit": limit, "force_reprocess": force_reprocess},
                )
            )
            due_iso = "2025-10-02T09:00:00Z"
            return {
                "success": True,
                "total_found": 2,
                "successful_processes": 1,
                "processed_issues": [
                    {
                        "issue_number": 201,
                        "status": "completed",
                        "workflow": "Example Workflow",
                        "deliverables": ["study/example/report.md"],
                        "error": None,
                        "copilot_assignee": "github-copilot[bot]",
                        "copilot_due_at": due_iso,
                        "handoff_summary": "🚀 Unified handoff summary",
                        "specialist_guidance": specialist_guidance_block,
                        "copilot_assignment": copilot_assignment_block,
                    },
                    {
                        "issue_number": 202,
                        "status": "error",
                        "workflow": "Example Workflow",
                        "deliverables": [],
                        "error": "Failed to fetch additional context",
                        "copilot_assignee": None,
                        "copilot_due_at": None,
                        "handoff_summary": None,
                        "specialist_guidance": None,
                        "copilot_assignment": None,
                    },
                ],
                "metrics": {
                    "total_issues": 2,
                    "processed_count": 2,
                    "success_count": 1,
                    "error_count": 1,
                    "skipped_count": 0,
                    "clarification_count": 0,
                    "duration_seconds": 0.0,
                    "average_processing_time": 0.0,
                    "success_rate": 50.0,
                    "start_time": None,
                    "end_time": None,
                    "copilot_assignments": {
                        "count": 1,
                        "assignees": ["github-copilot[bot]"],
                        "due_dates": [due_iso],
                        "next_due_at": due_iso,
                    },
                },
                "next_copilot_due_at": due_iso,
            }


    class DummyGitHubClient:
        def __init__(self) -> None:
            self.call_history: list[int] = []

        def get_issue_data(self, issue_number: int) -> dict:
            self.call_history.append(issue_number)
            payload = dummy_issue_details.get(issue_number)
            if payload is None:
                return {
                    "title": f"Issue {issue_number}",
                    "labels": ["site-monitor"],
                }
            return payload

    class DummyProcessor:
        def __init__(self, github_token: str, repository: str, config_path: str) -> None:
            self.github_token = github_token
            self.repository = repository
            self.config_path = config_path
            self.config = SimpleNamespace(workflow_directory=str(workflow_dir))
            self.github = DummyGitHubClient()
            self.workflow_matcher = DummyWorkflowMatcher()

    class DummyOrchestrator:
        def __init__(self, processor: DummyProcessor, **kwargs) -> None:
            self.processor = processor
            self.telemetry_publishers = kwargs.get("telemetry_publishers", [])

        def process_all_site_monitor_issues(
            self,
            *,
            batch_size: int,
            dry_run: bool,
            assignee_filter: str | None,
                additional_labels: list[str] | None,
                workflow_category: list[str] | None = None,
        ):
            pipeline_events.append(
                (
                    "process_batch",
                    {
                        "mode": "site-monitor",
                        "batch_size": batch_size,
                        "dry_run": dry_run,
                        "assignee_filter": assignee_filter,
                            "additional_labels": additional_labels,
                            "workflow_category": workflow_category,
                    },
                )
            )
            now = datetime.utcnow()
            due_iso = (now + timedelta(hours=48)).replace(microsecond=0).isoformat() + "Z"
            metrics = BatchMetrics(
                total_issues=1,
                processed_count=1,
                success_count=1,
                error_count=0,
                start_time=now,
                end_time=now,
            )
            results = [
                ProcessingResult(
                    issue_number=101,
                    status=IssueProcessingStatus.COMPLETED,
                    workflow_name="Example Workflow",
                    created_files=["study/example/report.md"],
                    copilot_assignee="github-copilot[bot]",
                    copilot_due_at=due_iso,
                    handoff_summary="🚀 Unified handoff summary",
                    specialist_guidance=specialist_guidance_block,
                    copilot_assignment=copilot_assignment_block,
                )
            ]
            return metrics, results

        def process_batch(self, *, issue_numbers, batch_size: int, dry_run: bool):
            pipeline_events.append(
                (
                    "process_issue",
                    {
                        "issue_numbers": list(issue_numbers),
                        "batch_size": batch_size,
                        "dry_run": dry_run,
                    },
                )
            )
            now = datetime.utcnow()
            results = []
            for issue_number in issue_numbers:
                if issue_number == 202:
                    results.append(
                        ProcessingResult(
                            issue_number=issue_number,
                            status=IssueProcessingStatus.NEEDS_CLARIFICATION,
                            workflow_name="Example Workflow",
                            created_files=[],
                            clarification_needed="Need additional discovery details",
                        )
                    )
                else:
                    due_iso = (now + timedelta(hours=72)).replace(microsecond=0).isoformat() + "Z"
                    results.append(
                        ProcessingResult(
                            issue_number=issue_number,
                            status=IssueProcessingStatus.COMPLETED,
                            workflow_name="Example Workflow",
                            created_files=["study/example/report.md"],
                            copilot_assignee="github-copilot[bot]",
                            copilot_due_at=due_iso,
                            handoff_summary="🚀 Unified handoff summary",
                            specialist_guidance=specialist_guidance_block,
                            copilot_assignment=copilot_assignment_block,
                        )
                    )

            metrics = BatchMetrics(
                total_issues=len(issue_numbers),
                processed_count=len(issue_numbers),
                success_count=len([r for r in results if r.status == IssueProcessingStatus.COMPLETED]),
                error_count=len([r for r in results if r.status == IssueProcessingStatus.ERROR]),
                start_time=now,
                end_time=now,
            )
            return metrics, results

    class DummyBatchProcessor:
        def __init__(self, issue_processor, github_client, config=None, telemetry_publishers=None):
            self.issue_processor = issue_processor
            self.github_client = github_client
            self.config = config
            self.telemetry_publishers = telemetry_publishers or []

        def find_site_monitor_issues(self, filters, include_details=False):
            issue_finder_calls.append(filters)
            pipeline_events.append(("find_issues_only", {"filters": filters.copy()}))
            issues = []
            if include_details:
                issues = []
                for issue_number in [301, 302]:
                    details = dummy_issue_details.get(issue_number, {
                        "title": f"Stub Issue {issue_number}",
                        "labels": ["site-monitor"],
                    })
                    issues.append(
                        SimpleNamespace(
                            number=issue_number,
                            title=details.get("title", f"Issue {issue_number}"),
                            labels=[SimpleNamespace(name=label) for label in details.get("labels", [])],
                            assignee=None,
                        )
                    )
            return SiteMonitorIssueDiscovery(
                issue_numbers=[301, 302],
                filters=filters.copy(),
                total_found=2,
                issues=issues if include_details else None,
            )

    original_safe_execute = cli_main.safe_execute_cli_command

    def capturing_safe_execute(func):
        def wrapped_func():
            result = func()
            captured_cli_results.append(result)
            return result

        return original_safe_execute(wrapped_func)

    monkeypatch.setattr(cli_main, "safe_execute_cli_command", capturing_safe_execute)
    monkeypatch.setattr(cli_main, "create_monitor_service_from_config", lambda *args, **kwargs: DummyMonitorService())
    monkeypatch.setattr("src.utils.cli_monitors.get_monitor_service", lambda *args, **kwargs: DummyMonitorService())
    monkeypatch.setattr(cli_main, "get_monitor_service", lambda *args, **kwargs: DummyMonitorService())
    monkeypatch.setattr(cli_main, "AIWorkflowAssignmentAgent", DummyAssignmentAgent)
    monkeypatch.setattr(cli_main, "WorkflowAssignmentAgent", DummyFallbackAgent)
    monkeypatch.setattr(cli_main, "GitHubIntegratedIssueProcessor", DummyProcessor)
    monkeypatch.setattr(cli_main, "ProcessingOrchestrator", DummyOrchestrator)
    monkeypatch.setattr("src.core.batch_processor.BatchProcessor", DummyBatchProcessor)

    def invoke_cli(cli_args: list[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["speculum-principum"] + cli_args)
        cli_main.main()

    # Execute the three CLI commands in sequence
    invoke_cli(["monitor", "--config", str(config_path), "--no-individual-issues"])
    invoke_cli([
        "assign-workflows",
        "--config",
        str(config_path),
        "--limit",
        "3",
        "--dry-run",
        "--verbose",
    ])
    invoke_cli(["assign-workflows", "--config", str(config_path), "--statistics"])
    invoke_cli([
        "assign-workflows",
        "--config",
        str(config_path),
        "--limit",
        "2",
        "--dry-run",
        "--disable-ai",
    ])
    invoke_cli(["process-issues", "--config", str(config_path), "--batch-size", "5", "--dry-run"])
    invoke_cli(["process-issues", "--config", str(config_path), "--batch-size", "2", "--from-monitor", "--dry-run"])
    invoke_cli(["process-issues", "--config", str(config_path), "--issue", "202", "--dry-run", "--force-clarification"])
    invoke_cli(["process-issues", "--config", str(config_path), "--batch-size", "5", "--dry-run", "--find-issues-only"])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert "Monitoring completed successfully" in captured.out
    assert "Taxonomy Adoption" in captured.out
    assert "Confidence Thresholds" in captured.out
    assert "Processing Outcomes" in captured.out
    assert "Workflow Assignment Complete" in captured.out
    assert "Top reason codes:" in captured.out
    assert "Base entity coverage:" in captured.out
    assert "Legal signals detected:" in captured.out
    assert "Statute citations:" in captured.out
    assert "Precedent references:" in captured.out
    assert "Inter-agency terms:" in captured.out
    assert "Reason Codes:" in captured.out
    assert "Entity Coverage:" in captured.out
    assert "Label-based (fallback)" in captured.out
    assert "Assignment mode: AI-enhanced [ai]" in captured.out
    assert "Assignment mode: Label-based (fallback) [fallback]" in captured.out
    assert "Processed 1 issue" in captured.out or "Processed 1 issue(s)" in captured.out
    assert "Issue #202" in captured.out and "needs_clarification" in captured.out
    assert "Waiting for workflow clarification" in captured.out
    assert "🤖 Copilot: @github-copilot[bot]" in captured.out
    assert "Copilot assignments:" in combined_output
    assert "Next Copilot due at:" in combined_output
    assert any(event[0] == "assign_fallback" for event in pipeline_events)

    find_issues_lines = [line for line in captured.out.splitlines() if line.strip().startswith("[")]
    assert find_issues_lines, "Expected JSON output for find-issues-only command"
    issues_payload = json.loads(find_issues_lines[-1])
    assert issues_payload == [
        {"number": 301, "title": "Discovery item 301", "labels": ["site-monitor", "state::assigned"]},
        {"number": 302, "title": "Discovery item 302", "labels": ["site-monitor", "state::assigned"]},
    ]

    process_results_with_sections = [
        result
        for result in captured_cli_results
        if getattr(result, "data", None) and isinstance(result.data, dict)
        and any(
            entry.get("specialist_guidance") or entry.get("copilot_assignment")
            for entry in result.data.get("results", [])
        )
    ]

    assert process_results_with_sections, "Expected process-issues results containing Markdown sections"
    first_section_payload = process_results_with_sections[0].data["results"][0]
    assert first_section_payload["specialist_guidance"].startswith("### Persona:")
    assert "### Deliverables" in first_section_payload["specialist_guidance"]
    assert first_section_payload["copilot_assignment"].startswith("**Assignee**: @github-copilot[bot]")
    assert "**Acceptance Criteria**" in first_section_payload["copilot_assignment"]

    assert pipeline_events == [
        ("monitor", {"create_individual_issues": False}),
        ("assign", {"limit": 3, "dry_run": True}),
        ("assign_statistics", {}),
        ("assign_fallback", {"limit": 2, "dry_run": True}),
        (
            "process_batch",
            {
                "mode": "site-monitor",
                "batch_size": 5,
                "dry_run": True,
                "assignee_filter": None,
                "additional_labels": None,
                "workflow_category": None,
            },
        ),
        ("process_from_monitor", {"limit": 2, "force_reprocess": False}),
        (
            "process_issue",
            {
                "issue_numbers": [202],
                "batch_size": 1,
                "dry_run": True,
            },
        ),
        ("find_issues_only", {"filters": {}}),
    ]

    assert issue_finder_calls == [{}]

    assert telemetry_dir.exists()

    assign_telemetry_file = telemetry_dir / "assign-workflows.jsonl"
    assert assign_telemetry_file.exists()
    with assign_telemetry_file.open() as handle:
        events = [json.loads(line) for line in handle if line.strip()]

    stats_events = [event for event in events if event.get("event_type") == "workflow_assignment.statistics_view"]
    assert stats_events, "Expected telemetry event for statistics command"
    latest_stats_event = stats_events[-1]
    assert latest_stats_event.get("success") is True
    assert latest_stats_event.get("statistics_snapshot", {}).get("total_site_monitor_issues") == 5
    assert latest_stats_event.get("assignment_mode") == "ai"

    monitor_telemetry_file = telemetry_dir / "monitor.jsonl"
    assert monitor_telemetry_file.exists()
    with monitor_telemetry_file.open() as handle:
        monitor_events = [json.loads(line) for line in handle if line.strip()]

    monitor_cli_events = [event for event in monitor_events if event.get("event_type") == "site_monitor.cli_summary"]
    assert len(monitor_cli_events) == 1
    monitor_event = monitor_cli_events[0]
    assert monitor_event.get("success") is True
    assert monitor_event.get("data", {}).get("new_results_found") == 2

    process_telemetry_file = telemetry_dir / "process-issues.jsonl"
    assert process_telemetry_file.exists()
    with process_telemetry_file.open() as handle:
        process_events = [json.loads(line) for line in handle if line.strip()]

    process_cli_events = [event for event in process_events if event.get("event_type") == "process_issues.cli_summary"]
    assert len(process_cli_events) == 4
    assert sum(1 for event in process_cli_events if event.get("phase") == "batch_processing") == 2
    assert any(event.get("phase") == "single_issue_processing" for event in process_cli_events)
    assert any(event.get("phase") == "find_issues" for event in process_cli_events)

    workflow_stage_fields = [fields for fields in recorded_static_fields if "workflow_stage" in fields]
    monitor_stage_fields = [fields for fields in workflow_stage_fields if fields.get("workflow_stage") == "monitoring"]
    assert monitor_stage_fields, "Expected monitoring telemetry metadata"
    assert any(field.get("monitor_mode") == "aggregate-only" for field in monitor_stage_fields)

    process_stage_fields = [fields for fields in workflow_stage_fields if fields.get("workflow_stage") == "issue-processing"]
    assert process_stage_fields, "Expected issue-processing telemetry metadata"
    processing_modes = {field.get("processing_mode") for field in process_stage_fields}
    expected_modes = {"batch", "from-monitor", "single-issue", "find-issues-only"}
    assert expected_modes.issubset(processing_modes)
