#!/usr/bin/env python3
"""
Speculum Principum - A Python app that runs operations via GitHub Actions
Main entry point for the application with site monitoring capabilities
"""

import os
import sys
import argparse
from collections import Counter
from typing import Optional, Any
from datetime import datetime
from dotenv import load_dotenv

from src.clients.github_issue_creator import GitHubIssueCreator
from src.core.batch_processor import BatchMetrics
from src.core.issue_processor import (
    GitHubIntegratedIssueProcessor, 
    IssueProcessingStatus, 
    ProcessingResult
)
from src.core.processing_orchestrator import ProcessingOrchestrator
from src.core.site_monitor import create_monitor_service_from_config
from src.agents.ai_workflow_assignment_agent import AIWorkflowAssignmentAgent
from src.agents.workflow_assignment_agent import WorkflowAssignmentAgent
from src.utils.cli_helpers import (
    ConfigValidator,
    IssueResultFormatter,
    safe_execute_cli_command,
    CliResult,
    prepare_cli_execution,
)
from src.utils.cli_monitors import get_monitor_service, MonitorServiceError
from src.utils.telemetry import publish_telemetry_event
from src.utils.telemetry_helpers import (
    attach_cli_static_fields,
    emit_cli_summary,
    setup_cli_publishers,
)
from src.utils.cli_runtime import ensure_runtime_ready
from src.utils.specialist_config_cli import (
    setup_specialist_config_parser,
    handle_specialist_config_command
)
from src.utils.logging_config import setup_logging
from src.workflow.workflow_schemas import WorkflowSchemaValidator


TAXONOMY_CATEGORIES = sorted(WorkflowSchemaValidator.TAXONOMY_CATEGORIES)


def setup_argument_parser() -> argparse.ArgumentParser:
    """
    Set up the command-line argument parser with all subcommands.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='Speculum Principum - GitHub Operations & Site Monitoring',
        prog='speculum-principum'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Legacy issue creation command
    setup_create_issue_parser(subparsers)
    
    # Site monitoring commands
    setup_monitor_parser(subparsers)
    setup_setup_parser(subparsers)
    setup_status_parser(subparsers)
    setup_cleanup_parser(subparsers)
    
    # Issue processing commands
    setup_process_issues_parser(subparsers)
    setup_assign_workflows_parser(subparsers)
    
    # Specialist workflow configuration commands
    setup_specialist_config_parser(subparsers)
    
    return parser


def attach_static_fields(publishers, static_fields):
    """Backward-compatible shim for tests expecting the legacy helper."""
    return attach_cli_static_fields(publishers, **static_fields)


DEFAULT_AUTO_CONFIDENCE = getattr(AIWorkflowAssignmentAgent, "HIGH_CONFIDENCE_THRESHOLD", 0.8)
DEFAULT_REVIEW_CONFIDENCE = getattr(AIWorkflowAssignmentAgent, "MEDIUM_CONFIDENCE_THRESHOLD", 0.6)


def summarize_workflow_outcomes(
    matcher,
    results: list[dict[str, Any]],
    *,
    workflow_key: str = "workflow",
    status_key: str = "status",
    filter_applied: bool = False,
    auto_threshold: float = DEFAULT_AUTO_CONFIDENCE,
    review_threshold: float = DEFAULT_REVIEW_CONFIDENCE,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Aggregate taxonomy adoption, confidence thresholds, and status counts."""

    taxonomy_assigned = 0
    legacy_assigned = 0
    unknown_workflows = 0
    total_with_workflow = 0
    thresholds: list[float] = []
    threshold_buckets: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()

    for entry in results:
        status_value = entry.get(status_key)
        if isinstance(status_value, str) and status_value:
            status_counter[status_value] += 1

        workflow_name = entry.get(workflow_key)
        if not workflow_name:
            continue

        workflow_info = matcher.get_workflow_by_name(workflow_name) if matcher else None

        if workflow_info is None:
            unknown_workflows += 1
            continue

        total_with_workflow += 1
        if workflow_info.is_taxonomy():
            taxonomy_assigned += 1
        else:
            legacy_assigned += 1

        category_value = workflow_info.category or ("legacy" if not workflow_info.is_taxonomy() else None)
        if category_value:
            category_counter[category_value] += 1

        threshold = getattr(workflow_info, "confidence_threshold", None)
        if isinstance(threshold, (int, float)):
            threshold_value = float(threshold)
        else:
            threshold_value = None

        if threshold_value is not None:
            thresholds.append(threshold_value)
            if threshold_value >= auto_threshold:
                threshold_buckets["auto_assignment"] += 1
            elif threshold_value >= review_threshold:
                threshold_buckets["review_gate"] += 1
            else:
                threshold_buckets["manual_review"] += 1
        else:
            threshold_buckets["unspecified"] += 1

    taxonomy_metrics: dict[str, Any] | None = None
    if total_with_workflow or unknown_workflows:
        taxonomy_rate = (
            taxonomy_assigned / total_with_workflow
            if total_with_workflow
            else 0.0
        )
        taxonomy_metrics = {
            "total_with_workflow": total_with_workflow,
            "taxonomy_assigned": taxonomy_assigned,
            "legacy_assigned": legacy_assigned,
            "unknown_workflows": unknown_workflows,
            "category_breakdown": dict(category_counter),
            "taxonomy_rate": taxonomy_rate,
            "filter_applied": filter_applied,
        }

    threshold_metrics: dict[str, Any] | None = None
    clean_thresholds = [value for value in thresholds if isinstance(value, float)]
    if threshold_buckets or clean_thresholds:
        average_threshold = (
            sum(clean_thresholds) / len(clean_thresholds)
            if clean_thresholds
            else None
        )
        min_threshold = min(clean_thresholds) if clean_thresholds else None
        max_threshold = max(clean_thresholds) if clean_thresholds else None
        threshold_metrics = {
            "bucket_counts": dict(threshold_buckets),
            "average_threshold": average_threshold,
            "min_threshold": min_threshold,
            "max_threshold": max_threshold,
            "auto_threshold": auto_threshold,
            "review_threshold": review_threshold,
        }

    status_metrics = dict(status_counter) if status_counter else None

    taxonomy_lines: list[str] = []
    if taxonomy_metrics:
        denominator_text = (
            str(taxonomy_metrics["total_with_workflow"])
            if taxonomy_metrics["total_with_workflow"]
            else "0"
        )
        taxonomy_lines.append(
            f"  Taxonomy workflows: {taxonomy_metrics['taxonomy_assigned']}/{denominator_text}"
            f" ({taxonomy_metrics['taxonomy_rate']:.0%})"
        )
        if taxonomy_metrics["legacy_assigned"]:
            taxonomy_lines.append(
                f"  Legacy workflows: {taxonomy_metrics['legacy_assigned']}"
            )
        if taxonomy_metrics["unknown_workflows"]:
            taxonomy_lines.append(
                f"  Unknown workflows: {taxonomy_metrics['unknown_workflows']}"
            )
        for category, count in sorted(taxonomy_metrics["category_breakdown"].items()):
            friendly = category.replace('-', ' ').title()
            taxonomy_lines.append(f"  {friendly}: {count}")

    threshold_lines: list[str] = []
    if threshold_metrics:
        bucket_counts = threshold_metrics["bucket_counts"]
        if threshold_metrics["average_threshold"] is not None:
            threshold_lines.append(
                f"  Avg confidence threshold: {threshold_metrics['average_threshold']:.0%}"
            )
        if threshold_metrics["min_threshold"] is not None and threshold_metrics["max_threshold"] is not None:
            threshold_lines.append(
                f"  Threshold range: {threshold_metrics['min_threshold']:.0%}–{threshold_metrics['max_threshold']:.0%}"
            )
        if bucket_counts:
            auto_count = bucket_counts.get("auto_assignment", 0)
            review_count = bucket_counts.get("review_gate", 0)
            manual_count = bucket_counts.get("manual_review", 0)
            unspecified_count = bucket_counts.get("unspecified", 0)
            threshold_lines.append(
                f"  ≥{auto_threshold:.0%} (auto-assign ready): {auto_count}"
            )
            threshold_lines.append(
                f"  ≥{review_threshold:.0%} review gate: {review_count}"
            )
            threshold_lines.append(
                f"  Below review gate: {manual_count}"
            )
            if unspecified_count:
                threshold_lines.append(
                    f"  Unspecified thresholds: {unspecified_count}"
                )

    status_lines: list[str] = []
    if status_metrics:
        for status_name, count in status_counter.most_common():
            friendly_status = status_name.replace('_', ' ').title()
            status_lines.append(f"  {friendly_status}: {count}")

    metrics = {
        "taxonomy_metrics": taxonomy_metrics,
        "threshold_metrics": threshold_metrics,
        "status_counts": status_metrics,
    }
    lines = {
        "taxonomy": taxonomy_lines,
        "thresholds": threshold_lines,
        "statuses": status_lines,
    }
    return metrics, lines


def setup_create_issue_parser(subparsers) -> None:
    """Set up create-issue command parser."""
    issue_parser = subparsers.add_parser(
        'create-issue', 
        help='Create a GitHub issue'
    )
    issue_parser.add_argument('--title', required=True, help='Issue title')
    issue_parser.add_argument('--body', help='Issue body/description')
    issue_parser.add_argument('--labels', nargs='*', help='Issue labels')
    issue_parser.add_argument('--assignees', nargs='*', help='Issue assignees')


def setup_monitor_parser(subparsers) -> None:
    """Set up monitor command parser."""
    monitor_parser = subparsers.add_parser(
        'monitor', 
        help='Run site monitoring'
    )
    monitor_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )
    monitor_parser.add_argument(
        '--no-individual-issues', 
        action='store_true',
        help='Skip creating individual issues for each search result'
    )
    monitor_parser.add_argument(
        '--issue-template',
        choices=['minimal', 'full'],
        help='Override the discovery issue template layout for this run'
    )
    monitor_parser.add_argument(
        '--show-taxonomy-metrics',
        action='store_true',
        help='Include workflow taxonomy and confidence metrics when monitor triggers processing'
    )


def setup_setup_parser(subparsers) -> None:
    """Set up setup command parser."""
    setup_parser = subparsers.add_parser(
        'setup', 
        help='Set up repository for monitoring'
    )
    setup_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )


def setup_status_parser(subparsers) -> None:
    """Set up status command parser."""
    status_parser = subparsers.add_parser(
        'status', 
        help='Show monitoring status'
    )
    status_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )


def setup_cleanup_parser(subparsers) -> None:
    """Set up cleanup command parser."""
    cleanup_parser = subparsers.add_parser(
        'cleanup', 
        help='Clean up old monitoring data'
    )
    cleanup_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )
    cleanup_parser.add_argument(
        '--days-old', 
        type=int, 
        default=7, 
        help='Days old threshold'
    )
    cleanup_parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Dry run mode'
    )


def setup_process_issues_parser(subparsers) -> None:
    """Set up process-issues command parser."""
    process_parser = subparsers.add_parser(
        'process-issues', 
        help='Process issues with automated workflows'
    )
    process_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )
    process_parser.add_argument(
        '--issue', 
        type=int, 
        help='Process specific issue number'
    )
    process_parser.add_argument(
        '--batch-size', 
        type=int, 
        default=10, 
        help='Maximum issues to process in batch mode'
    )
    process_parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Show what would be processed without making changes'
    )
    process_parser.add_argument(
        '--force-clarification', 
        action='store_true', 
        help='Force clarification requests even for apparent matches'
    )
    process_parser.add_argument(
        '--assignee-filter', 
        help='Only process issues assigned to specific user'
    )
    process_parser.add_argument(
        '--label-filter', 
        nargs='*', 
        help='Additional labels to filter issues (beyond site-monitor)'
    )
    process_parser.add_argument(
        '--workflow-category',
        choices=TAXONOMY_CATEGORIES,
        nargs='+',
        help='Filter issues to workflows within these taxonomy categories'
    )
    process_parser.add_argument(
        '--show-taxonomy-metrics',
        action='store_true',
        help='Include workflow taxonomy adoption metrics in the output summary'
    )
    process_parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help='Show detailed progress information'
    )
    process_parser.add_argument(
        '--continue-on-error', 
        action='store_true', 
        help='Continue batch processing even if individual issues fail'
    )
    process_parser.add_argument(
        '--from-monitor', 
        action='store_true', 
        help='Use site monitor to find and process unprocessed issues'
    )
    process_parser.add_argument(
        '--find-issues-only', 
        action='store_true', 
        help='Find and output site-monitor issues without processing (for CI/CD)'
    )

def setup_assign_workflows_parser(subparsers) -> None:
    """Set up assign-workflows command parser."""
    assign_parser = subparsers.add_parser(
        'assign-workflows', 
        help='Assign workflows to unassigned site-monitor issues using AI analysis'
    )
    assign_parser.add_argument(
        '--config', 
        default='config.yaml', 
        help='Configuration file path'
    )
    assign_parser.add_argument(
        '--limit', 
        type=int, 
        default=20, 
        help='Maximum issues to process'
    )
    assign_parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Show what would be done without making changes'
    )
    assign_parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help='Show detailed progress information'
    )
    assign_parser.add_argument(
        '--statistics', 
        action='store_true', 
        help='Show workflow assignment statistics'
    )
    assign_parser.add_argument(
        '--disable-ai', 
        action='store_true', 
        help='Disable AI analysis and use label-based matching only (fallback mode)'
    )
    assign_parser.add_argument(
        '--workflow-category',
        choices=TAXONOMY_CATEGORIES,
        nargs='+',
        help='Restrict recommendations to workflows within these taxonomy categories'
    )
    assign_parser.add_argument(
        '--show-taxonomy-metrics',
        action='store_true',
        help='Include workflow taxonomy adoption metrics in the output summary'
    )


def validate_environment() -> tuple[str, str]:
    """
    Validate required environment variables.
    
    Returns:
        Tuple of (github_token, repo_name)
        
    Raises:
        SystemExit: If required environment variables are missing
    """
    github_token = os.getenv('GITHUB_TOKEN')
    repo_name = os.getenv('GITHUB_REPOSITORY')
    
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)
        
    if not repo_name:
        print("Error: GITHUB_REPOSITORY environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    return github_token, repo_name


def handle_create_issue_command(args, github_token: str, repo_name: str) -> None:
    """Handle create-issue command."""
    creator = GitHubIssueCreator(github_token, repo_name)
    issue = creator.create_issue(
        title=args.title,
        body=args.body or "",
        labels=args.labels or [],
        assignees=args.assignees or []
    )
    print(f"Successfully created issue #{issue.number}: {issue.title}")
    print(f"URL: {issue.html_url}")


def handle_monitor_command(args, github_token: str) -> None:
    """Handle monitor command."""
    monitor_mode = "aggregate-only" if args.no_individual_issues else "full"
    telemetry_publishers = setup_cli_publishers(
        "monitor",
        extra_static_fields={
            "no_individual_issues": args.no_individual_issues,
            "show_taxonomy_metrics": getattr(args, 'show_taxonomy_metrics', False),
        },
        static_fields={
            "workflow_stage": "monitoring",
            "monitor_mode": monitor_mode,
        },
    )

    try:
        service = get_monitor_service(
            args.config,
            github_token,
            telemetry=telemetry_publishers,
        )
    except MonitorServiceError as exc:
        emit_cli_summary(
            telemetry_publishers,
            "site_monitor.cli_summary",
            CliResult(
                success=False,
                message=str(exc),
                data={
                    "create_individual_issues": not args.no_individual_issues,
                },
                error_code=1,
            ),
            phase="monitor_setup",
            extra={
                "create_individual_issues": not args.no_individual_issues,
            },
        )
        print(f"❌ Monitoring setup failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'issue_template', None):
        service.set_issue_template_layout(args.issue_template)

    try:
        results = service.run_monitoring_cycle(
            create_individual_issues=not args.no_individual_issues
        )
    except Exception as exc:  # noqa: BLE001
        emit_cli_summary(
            telemetry_publishers,
            "site_monitor.cli_summary",
            CliResult(
                success=False,
                message=str(exc),
                data={
                    "create_individual_issues": not args.no_individual_issues,
                },
                error_code=1,
            ),
            phase="monitoring_cycle",
            extra={
                "create_individual_issues": not args.no_individual_issues,
            },
        )
        print(f"❌ Monitoring failed: {exc}", file=sys.stderr)
        sys.exit(1)

    processing_results = list(results.get('issue_processing_results') or [])
    matcher = getattr(getattr(service, 'issue_processor', None), 'workflow_matcher', None)
    metrics_summary: dict[str, Any] = {
        'taxonomy_metrics': None,
        'threshold_metrics': None,
        'status_counts': None,
    }
    metrics_lines: dict[str, list[str]] = {
        'taxonomy': [],
        'thresholds': [],
        'statuses': [],
    }
    if processing_results:
        metrics_summary, metrics_lines = summarize_workflow_outcomes(
            matcher,
            processing_results,
        )

    monitoring_success = bool(results.get('success'))
    summary_result = CliResult(
        success=monitoring_success,
        message=(
            "Monitoring completed successfully"
            if monitoring_success
            else f"Monitoring failed: {results.get('error')}"
        ),
        data={
            "new_results_found": results.get('new_results_found'),
            "individual_issues_created": results.get('individual_issues_created'),
            "cycle_start": results.get('cycle_start'),
            "cycle_end": results.get('cycle_end'),
            "error": results.get('error'),
            "workflow_metrics": metrics_summary.get('taxonomy_metrics'),
            "confidence_metrics": metrics_summary.get('threshold_metrics'),
            "status_counts": metrics_summary.get('status_counts'),
        },
        error_code=0 if monitoring_success else 1,
    )

    emit_cli_summary(
        telemetry_publishers,
        "site_monitor.cli_summary",
        summary_result,
        phase="monitoring_cycle",
        extra={
            "workflow_metrics": metrics_summary.get('taxonomy_metrics'),
            "confidence_metrics": metrics_summary.get('threshold_metrics'),
            "status_counts": metrics_summary.get('status_counts'),
        },
    )
    
    if results.get('success'):
        print("✅ Monitoring completed successfully")
        print(f"📊 Found {results.get('new_results_found')} new results")
        print(f"📝 Created {results.get('individual_issues_created')} individual issues")

        display_metrics = (
            getattr(args, 'show_taxonomy_metrics', False)
            or any(metrics_lines.values())
        )

        if display_metrics and any(metrics_lines.values()):
            print("\n📈 Taxonomy Adoption:")
            adoption_lines = metrics_lines.get('taxonomy') or ["  No workflow data yet"]
            for line in adoption_lines:
                print(line)

            threshold_lines = metrics_lines.get('thresholds') or []
            if threshold_lines:
                print("\n🎯 Confidence Thresholds:")
                for line in threshold_lines:
                    print(line)

            status_lines = metrics_lines.get('statuses') or []
            if status_lines:
                print("\n🛠 Processing Outcomes:")
                for line in status_lines:
                    print(line)
    else:
        print(f"❌ Monitoring failed: {results.get('error')}", file=sys.stderr)
        sys.exit(1)


def handle_setup_command(args, github_token: str) -> None:
    """Handle setup command."""
    try:
        service = get_monitor_service(args.config, github_token)
    except MonitorServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    service.setup_repository()
    print("✅ Repository setup completed")


def handle_status_command(args, github_token: str) -> None:
    """Handle status command."""
    try:
        service = get_monitor_service(args.config, github_token)
    except MonitorServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    status = service.get_monitoring_status()
    print(f"📊 Site Monitor Status")
    print(f"Repository: {status['repository']}")
    print(f"Sites configured: {status['sites_configured']}")
    rate_status = status['rate_limit_status']
    print(f"Rate limit: {rate_status['calls_remaining']}/{rate_status['daily_limit']} calls remaining")
    dedup_stats = status['deduplication_stats']
    print(f"Processed entries: {dedup_stats['total_entries']}")

    capture_counts = dedup_stats.get('capture_status_counts', {}) or {}
    capture_summary = dedup_stats.get('capture_summary', {}) or {}

    if capture_counts or capture_summary:
        total_attempts = capture_summary.get('total_attempts')
        if total_attempts is None:
            total_attempts = sum(capture_counts.values())
            total_attempts -= capture_counts.get('unknown', 0)
            total_attempts -= capture_counts.get('disabled', 0)
        total_attempts = max(total_attempts, 0)

        success_count = capture_summary.get('success', capture_counts.get('success', 0))
        failure_count = capture_summary.get(
            'failures',
            capture_counts.get('failed', 0) + capture_counts.get('error', 0),
        )
        empty_count = capture_summary.get('empty', capture_counts.get('empty', 0))
        disabled_count = capture_summary.get('disabled', capture_counts.get('disabled', 0))
        unknown_count = capture_summary.get('unknown', capture_counts.get('unknown', 0))
        persisted_count = capture_summary.get(
            'persisted_artifacts',
            dedup_stats.get('captures_with_artifacts', 0),
        )

        failed_breakdown = capture_summary.get('failed_breakdown', {}) or {}
        failed_fail = capture_counts.get('failed', failed_breakdown.get('failed', 0))
        failed_error = capture_counts.get('error', failed_breakdown.get('error', 0))

        print("Page capture results:")
        print(
            f"  ✅ Success: {success_count}" +
            (f" / {total_attempts} attempts" if total_attempts else "")
        )
        print(
            f"  ❌ Failures: {failure_count}"
            f" (failed={failed_fail}, error={failed_error})"
        )
        print(f"  ◽ Empty extracts: {empty_count}")
        print(f"  🚫 Disabled: {disabled_count}")
        if unknown_count:
            print(f"  ❔ Unknown: {unknown_count}")
        print(f"  💾 Artifacts persisted: {persisted_count}")


def handle_cleanup_command(args, github_token: str) -> None:
    """Handle cleanup command."""
    prepare_cli_execution(
        "cleanup",
        dry_run=args.dry_run,
    )
    try:
        service = get_monitor_service(args.config, github_token)
    except MonitorServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    results = service.cleanup_old_data(
        days_old=args.days_old,
        dry_run=args.dry_run
    )
    
    if results['success']:
        if args.dry_run:
            print(f"🔍 Dry run: would remove {results['removed_dedup_entries']} entries and close {results['closed_issues']} issues")
        else:
            print(f"🧹 Cleanup completed: removed {results['removed_dedup_entries']} entries and closed {results['closed_issues']} issues")
    else:
        print(f"❌ Cleanup failed: {results['error']}", file=sys.stderr)
        sys.exit(1)


def handle_process_issues_command(args, github_token: str, repo_name: str) -> None:
    """Handle process-issues command."""
    
    def process_issues_command() -> CliResult:
        context = prepare_cli_execution(
            "process-issues",
            verbose=args.verbose,
            dry_run=args.dry_run,
        )

        if args.find_issues_only:
            processing_mode = "find-issues-only"
        elif args.from_monitor:
            processing_mode = "from-monitor"
        elif args.issue:
            processing_mode = "single-issue"
        else:
            processing_mode = "batch"

        telemetry_publishers = setup_cli_publishers(
            "process-issues",
            extra_static_fields={
                "dry_run": args.dry_run,
                "from_monitor": args.from_monitor,
                "issue": args.issue,
                "batch_size": args.batch_size,
                "find_issues_only": args.find_issues_only,
                "assignee_filter": args.assignee_filter,
                "workflow_category": args.workflow_category,
                "show_taxonomy_metrics": args.show_taxonomy_metrics,
            },
            static_fields={
                "workflow_stage": "issue-processing",
                "processing_mode": processing_mode,
            },
        )

        def emit_summary(
            result: CliResult,
            *,
            phase: str,
            extra: Optional[dict] = None,
            structured: bool = False,
        ) -> CliResult:
            """Helper to emit telemetry with standardized CLI output."""

            decorated_result = context.decorate_cli_result(result, structured=structured)
            return emit_cli_summary(
                telemetry_publishers,
                "process_issues.cli_summary",
                decorated_result,
                phase=phase,
                extra=extra,
            )

        runtime_result = ensure_runtime_ready(
            args.config,
            telemetry_publishers=telemetry_publishers,
            telemetry_event="process_issues.runtime_validation",
        )

        if not runtime_result.success:
            return emit_summary(
                runtime_result,
                phase="preflight_validation",
            )

        runtime_context = runtime_result.data or {}
        runtime_config = runtime_context.get("config")

        # Initialize components
        reporter = context.reporter
        
        try:
            # Create processor
            processor = GitHubIntegratedIssueProcessor(
                github_token=github_token,
                repository=repo_name,
                config_path=args.config
            )
            
            # Create orchestrator for batch operations
            orchestrator = ProcessingOrchestrator(
                processor,
                telemetry_publishers=telemetry_publishers,
            )
            
            # Validate workflow directory from config
            config = runtime_config or processor.config
            workflow_dir = getattr(config, 'workflow_directory', 'docs/workflow/deliverables')
            
            workflow_result = ConfigValidator.validate_workflow_directory(workflow_dir)
            if not workflow_result.success:
                return context.decorate_cli_result(workflow_result)
            
            if args.verbose:
                reporter.show_info(f"Using workflow directory: {workflow_dir}")
                if workflow_result.data:
                    reporter.show_info(f"Found {workflow_result.data['workflow_count']} workflow(s)")
            
            
            # Handle find-issues-only mode (for CI/CD integration)
            if args.find_issues_only:
                reporter.start_operation("Finding site-monitor issues")
                
                try:
                    from src.core.batch_processor import BatchProcessor
                    
                    # Create a batch processor just for finding issues
                    batch_processor = BatchProcessor(
                        processor,
                        processor.github,
                        config=None,
                        telemetry_publishers=telemetry_publishers,
                    )
                    
                    # Build filters
                    filters = {}
                    if args.assignee_filter:
                        filters['assignee'] = args.assignee_filter
                    if args.label_filter:
                        filters['additional_labels'] = args.label_filter
                    if args.workflow_category:
                        filters['workflow_category'] = args.workflow_category
                    
                    # Find issues
                    discovery = batch_processor.find_site_monitor_issues(
                        filters,
                        include_details=True,
                    )
                    issue_numbers = discovery.issue_numbers
                    
                    if not issue_numbers:
                        reporter.complete_operation(True)
                        result = CliResult(
                            success=True,
                            message="[]",  # Empty JSON array for no issues
                            data={'issues': [], 'count': 0}
                        )
                        return emit_summary(
                            result,
                            phase="find_issues",
                            extra={"issues_found": 0},
                            structured=True,
                        )
                    
                    # Get detailed issue information
                    issues_data = []
                    issue_lookup = (
                        {issue.number: issue for issue in discovery.issues}
                        if discovery.issues
                        else {}
                    )

                    for issue_number in issue_numbers[:args.batch_size]:
                        issue_payload: dict[str, Any]
                        issue = issue_lookup.get(issue_number)

                        if issue is not None:
                            issue_payload = {
                                'number': issue_number,
                                'title': getattr(issue, 'title', ''),
                                'labels': [label.name for label in getattr(issue, 'labels', [])],
                            }
                        else:
                            try:
                                issue_data = processor.github.get_issue_data(issue_number)
                                issue_payload = {
                                    'number': issue_number,
                                    'title': issue_data.get('title', ''),
                                    'labels': issue_data.get('labels', []),
                                }
                            except Exception as e:
                                reporter.show_info(
                                    f"Warning: Could not get data for issue #{issue_number}: {e}"
                                )
                                issue_payload = {
                                    'number': issue_number,
                                    'title': '',
                                    'labels': [],
                                }

                        issues_data.append(issue_payload)
                    
                    reporter.complete_operation(True)
                    
                    # Output JSON for CI/CD consumption
                    import json
                    issues_json = json.dumps(issues_data)
                    
                    result = CliResult(
                        success=True,
                        message=issues_json,
                        data={'issues': issues_data, 'count': len(issues_data)}
                    )
                    return emit_summary(
                        result,
                        phase="find_issues",
                        extra={"issues_found": len(issues_data)},
                        structured=True,
                    )

                except Exception as e:
                    reporter.complete_operation(False)
                    result = CliResult(
                        success=False,
                        message=f"❌ Failed to find issues: {str(e)}",
                        error_code=1
                    )
                    return emit_summary(
                        result,
                        phase="find_issues",
                    )
            
            # Process issues (single or batch)
            if args.issue:
                # Single issue processing using batch processor for consistency
                reporter.start_operation(f"Processing issue #{args.issue}")
                
                # Check if issue has site-monitor label first
                if not args.dry_run:
                    try:
                        issue_data_dict = processor.github.get_issue_data(args.issue)
                        labels = issue_data_dict.get('labels', [])
                        
                        if 'site-monitor' not in labels:
                            reporter.complete_operation(False)
                            result = CliResult(
                                success=False,
                                message=f"❌ Issue #{args.issue} does not have the 'site-monitor' label",
                                error_code=1
                            )
                            return emit_summary(
                                result,
                                phase="single_issue_validation",
                                extra={"issue_number": args.issue},
                            )
                    except Exception as e:
                        reporter.complete_operation(False)
                        result = CliResult(
                            success=False,
                            message=f"❌ Could not retrieve issue #{args.issue}: {str(e)}",
                            error_code=1
                        )
                        return emit_summary(
                            result,
                            phase="single_issue_validation",
                            extra={"issue_number": args.issue},
                        )
                
                # Process using batch processor
                issue_numbers = [args.issue]
                batch_metrics, batch_results = orchestrator.process_batch(
                    issue_numbers=issue_numbers,
                    batch_size=1,
                    dry_run=args.dry_run
                )
                
                reporter.complete_operation(len(batch_results) > 0 and batch_results[0].status not in [IssueProcessingStatus.ERROR])
                
                # Format single result
                if batch_results:
                    result = batch_results[0]
                    result_payload = result.to_dict()
                    formatted_result = IssueResultFormatter.format_single_result({
                        'status': result_payload['status'],
                        'issue': result_payload['issue_number'],
                        'workflow': result_payload['workflow_name'],
                        'files_created': result_payload['created_files'] or [],
                        'error': result_payload['error_message'],
                        'clarification': result_payload['clarification_needed'],
                        'copilot_assignee': result_payload['copilot_assignee'],
                        'copilot_due_at': result_payload['copilot_due_at'],
                        'handoff_summary': result_payload['handoff_summary'],
                        'specialist_guidance': result_payload.get('specialist_guidance'),
                        'copilot_assignment': result_payload.get('copilot_assignment'),
                    })
                    
                    cli_result = CliResult(
                        success=result.status not in [IssueProcessingStatus.ERROR],
                        message=formatted_result,
                        data=result_payload
                    )
                    return emit_summary(
                        cli_result,
                        phase="single_issue_processing",
                        extra={"issue_number": args.issue},
                    )
                else:
                    cli_result = CliResult(
                        success=False,
                        message=f"❌ No result returned for issue #{args.issue}",
                        error_code=1
                    )
                    return emit_summary(
                        cli_result,
                        phase="single_issue_processing",
                        extra={"issue_number": args.issue},
                    )
            
            else:
                # Batch processing using the new BatchProcessor
                reporter.start_operation("Starting batch processing")
                
                try:
                    # Determine processing mode
                    if args.issue:
                        # Process specific issue using batch processor for consistency
                        issue_numbers = [args.issue]
                        batch_metrics, batch_results = orchestrator.process_batch(
                            issue_numbers=issue_numbers,
                            batch_size=1,
                            dry_run=args.dry_run
                        )
                    elif args.from_monitor:
                        # Use site monitor to find unprocessed issues
                        
                        reporter.show_info("🔍 Using site monitor to find unprocessed issues...")
                        
                        # Create site monitor service
                        monitor_service = create_monitor_service_from_config(
                            args.config,
                            github_token,
                            telemetry_publishers=telemetry_publishers,
                        )
                        
                        # Process existing issues using site monitor integration
                        monitor_result = monitor_service.process_existing_issues(
                            limit=args.batch_size,
                            force_reprocess=False
                        )
                        
                        if monitor_result['success']:
                            status_lookup = {status.value: status for status in IssueProcessingStatus}

                            def _parse_status(value: str) -> IssueProcessingStatus:
                                if not value:
                                    return IssueProcessingStatus.ERROR
                                return status_lookup.get(value.lower(), IssueProcessingStatus.ERROR)

                            batch_results = []
                            for result in monitor_result.get('processed_issues', []):
                                status_enum = _parse_status(result.get('status', ''))
                                batch_results.append(ProcessingResult(
                                    issue_number=result.get('issue_number'),
                                    status=status_enum,
                                    workflow_name=result.get('workflow'),
                                    created_files=result.get('deliverables') or [],
                                    error_message=result.get('error'),
                                    copilot_assignee=result.get('copilot_assignee'),
                                    copilot_due_at=result.get('copilot_due_at'),
                                    handoff_summary=result.get('handoff_summary'),
                                    specialist_guidance=result.get('specialist_guidance'),
                                    copilot_assignment=result.get('copilot_assignment'),
                                ))

                            metrics_data = monitor_result.get('metrics') or {}

                            def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
                                if not value:
                                    return None
                                try:
                                    normalised = value.replace('Z', '+00:00')
                                    return datetime.fromisoformat(normalised)
                                except ValueError:
                                    return None

                            if metrics_data:
                                batch_metrics = BatchMetrics(
                                    total_issues=metrics_data.get('total_issues', monitor_result.get('total_found', len(batch_results))),
                                    processed_count=metrics_data.get('processed_count', len(batch_results)),
                                    success_count=metrics_data.get('success_count', monitor_result.get('successful_processes', 0)),
                                    error_count=metrics_data.get('error_count', sum(1 for r in batch_results if r.status == IssueProcessingStatus.ERROR)),
                                    skipped_count=metrics_data.get('skipped_count', 0),
                                    clarification_count=metrics_data.get('clarification_count', sum(1 for r in batch_results if r.status == IssueProcessingStatus.NEEDS_CLARIFICATION)),
                                    start_time=_parse_timestamp(metrics_data.get('start_time')),
                                    end_time=_parse_timestamp(metrics_data.get('end_time')),
                                )

                                copilot_info = metrics_data.get('copilot_assignments') or {}
                                batch_metrics.copilot_assignment_count = copilot_info.get('count', 0)
                                batch_metrics.copilot_assignees.update(copilot_info.get('assignees', []))
                                batch_metrics.copilot_due_dates.extend(copilot_info.get('due_dates', []))
                            else:
                                total_found = monitor_result.get('total_found', len(batch_results))
                                successful = monitor_result.get('successful_processes', 0)
                                now = datetime.now()
                                batch_metrics = BatchMetrics(
                                    total_issues=total_found,
                                    processed_count=len(batch_results),
                                    success_count=successful,
                                    error_count=sum(1 for r in batch_results if r.status == IssueProcessingStatus.ERROR),
                                    skipped_count=0,
                                    clarification_count=sum(1 for r in batch_results if r.status == IssueProcessingStatus.NEEDS_CLARIFICATION),
                                    start_time=now,
                                    end_time=now,
                                )

                                for item in batch_results:
                                    if any([item.copilot_assignee, item.copilot_due_at, item.handoff_summary]):
                                        batch_metrics.register_copilot_assignment(item.copilot_assignee, item.copilot_due_at)
                        else:
                            result = CliResult(
                                success=False,
                                message=f"❌ Site monitor failed to find issues: {monitor_result['error']}",
                                error_code=1
                            )
                            return emit_summary(
                                result,
                                phase="process_monitor_bridge",
                            )
                    else:
                        # Process all site-monitor issues using standard method
                        batch_metrics, batch_results = orchestrator.process_all_site_monitor_issues(
                            batch_size=args.batch_size,
                            dry_run=args.dry_run,
                            assignee_filter=args.assignee_filter,
                            additional_labels=args.label_filter,
                            workflow_category=args.workflow_category,
                        )
                    
                    reporter.complete_operation(True, f"Batch processing complete")
                    
                    # Format batch results
                    if args.verbose:
                        reporter.show_info(
                            f"Processed {batch_metrics.processed_count}/{batch_metrics.total_issues} issues"
                        )
                        reporter.show_info(f"Success rate: {batch_metrics.success_rate:.1f}%")
                        reporter.show_info(f"Duration: {batch_metrics.duration_seconds:.1f}s")
                        if batch_metrics.copilot_assignment_count:
                            reporter.show_info(
                                f"Copilot assignments: {batch_metrics.copilot_assignment_count}"
                            )
                            next_due_verbose = batch_metrics.next_copilot_due_at
                            if next_due_verbose:
                                reporter.show_info(
                                    f"Next Copilot due at: {next_due_verbose}"
                                )
                    
                    # Convert results for formatting
                    results = []
                    raw_results = []
                    for result in batch_results:
                        result_payload = result.to_dict()
                        raw_results.append(result_payload)
                        results.append({
                            'status': result_payload['status'],
                            'issue': result_payload['issue_number'],
                            'workflow': result_payload['workflow_name'],
                            'files_created': result_payload['created_files'] or [],
                            'error': result_payload['error_message'],
                            'clarification': result_payload['clarification_needed'],
                            'copilot_assignee': result_payload['copilot_assignee'],
                            'copilot_due_at': result_payload['copilot_due_at'],
                            'handoff_summary': result_payload['handoff_summary'],
                            'specialist_guidance': result_payload.get('specialist_guidance'),
                            'copilot_assignment': result_payload.get('copilot_assignment'),
                        })
                    
                    # Format batch results
                    formatted_results = IssueResultFormatter.format_batch_results(results)

                    matcher = getattr(processor, "workflow_matcher", None)
                    metrics_input = [
                        {
                            "workflow": item.get("workflow"),
                            "status": item.get("status"),
                        }
                        for item in results
                    ]
                    metrics_summary, metrics_lines = summarize_workflow_outcomes(
                        matcher,
                        metrics_input,
                        filter_applied=bool(args.workflow_category),
                    )
                    taxonomy_metrics = metrics_summary.get("taxonomy_metrics") or {}
                    threshold_metrics = metrics_summary.get("threshold_metrics") or {}
                    status_counts = metrics_summary.get("status_counts") or {}

                    show_metrics = (
                        args.show_taxonomy_metrics
                        or args.verbose
                        or args.dry_run
                    )

                    copilot_summary_lines: list[str] = []
                    if batch_metrics.copilot_assignment_count:
                        copilot_summary_lines.append(
                            f"🤖 Copilot assignments: {batch_metrics.copilot_assignment_count}"
                        )
                        next_due = batch_metrics.next_copilot_due_at
                        if next_due:
                            copilot_summary_lines.append(
                                f"⏰ Next Copilot due at: {next_due}"
                            )

                    summary_sections = [formatted_results]
                    if show_metrics and metrics_lines.get("taxonomy"):
                        summary_sections.append(
                            "\n".join(["**Taxonomy Adoption:**", *metrics_lines["taxonomy"]])
                        )
                    if show_metrics and metrics_lines.get("thresholds"):
                        summary_sections.append(
                            "\n".join(["**Confidence Thresholds:**", *metrics_lines["thresholds"]])
                        )
                    if show_metrics and metrics_lines.get("statuses"):
                        summary_sections.append(
                            "\n".join(["**Processing Outcomes:**", *metrics_lines["statuses"]])
                        )
                    if copilot_summary_lines:
                        summary_sections.append("\n".join(copilot_summary_lines))

                    formatted_results = "\n\n".join(summary_sections)
                    
                    # Check for errors
                    error_count = batch_metrics.error_count
                    success = error_count == 0 or args.continue_on_error
                    
                    cli_result = CliResult(
                        success=success,
                        message=formatted_results,
                        data={
                            'results': raw_results,
                            'error_count': error_count,
                            'metrics': batch_metrics.to_dict(),
                            'copilot_assignment_count': batch_metrics.copilot_assignment_count,
                            'next_copilot_due_at': batch_metrics.next_copilot_due_at,
                            'taxonomy_metrics': taxonomy_metrics or None,
                            'confidence_metrics': threshold_metrics or None,
                            'status_counts': status_counts or None,
                        }
                    )
                    return emit_summary(
                        cli_result,
                        phase="batch_processing",
                        extra={
                            "processed_count": batch_metrics.processed_count,
                            "total_issues": batch_metrics.total_issues,
                            "error_count": error_count,
                            "taxonomy_metrics": taxonomy_metrics or None,
                            "confidence_metrics": threshold_metrics or None,
                            "status_counts": status_counts or None,
                        },
                    )
                    
                except Exception as e:
                    cli_result = CliResult(
                        success=False,
                        message=f"Failed to retrieve issues: {str(e)}",
                        error_code=1
                    )
                    return emit_summary(
                        cli_result,
                        phase="batch_processing_error",
                    )
        
        except Exception as e:
            cli_result = CliResult(
                success=False,
                message=f"Issue processing failed: {str(e)}",
                error_code=1
            )
            return emit_summary(
                cli_result,
                phase="command_error",
            )
    
    # Execute the command safely
    exit_code = safe_execute_cli_command(process_issues_command)
    if exit_code != 0:
        sys.exit(exit_code)
def handle_assign_workflows_command(args, github_token: str, repo_name: str) -> None:
    """Handle assign-workflows command."""
    
    def assign_workflows_command() -> CliResult:
        context = prepare_cli_execution(
            "assign-workflows",
            verbose=args.verbose,
            dry_run=args.dry_run,
        )

        telemetry_publishers = setup_cli_publishers(
            "assign-workflows",
            extra_static_fields={
                "dry_run": args.dry_run,
                "limit": args.limit,
                "statistics": args.statistics,
                "disable_ai": args.disable_ai,
                "workflow_category": args.workflow_category,
                "show_taxonomy_metrics": args.show_taxonomy_metrics,
            },
            static_fields={
                "workflow_stage": "workflow-assignment",
            },
        )

        def finalize(result: CliResult, *, structured: bool = False) -> CliResult:
            """Apply standardized CLI decorations before returning."""

            return context.decorate_cli_result(result, structured=structured)

        runtime_result = ensure_runtime_ready(
            args.config,
            telemetry_publishers=telemetry_publishers,
            telemetry_event="assign_workflows.runtime_validation",
        )

        if not runtime_result.success:
            return finalize(runtime_result)

        runtime_context = runtime_result.data or {}
        runtime_config = runtime_context.get("config")
        
        try:
            # Determine whether to disable AI based on arguments and configuration
            disable_ai_flag = args.disable_ai

            # Load AI configuration from file
            ai_config_enabled = True  # Default to enabled
            ai_config = getattr(runtime_config, 'ai', None)
            if ai_config is not None and not getattr(ai_config, 'enabled', True):
                ai_config_enabled = False

            ai_enabled = ai_config_enabled and not disable_ai_flag

            if ai_enabled:
                assignment_mode = "ai"
                telemetry_publishers = attach_static_fields(
                    telemetry_publishers,
                    {
                        "assignment_mode": assignment_mode,
                        "assignment_agent": "AIWorkflowAssignmentAgent",
                    },
                )
                agent = AIWorkflowAssignmentAgent(
                    github_token=github_token,
                    repo_name=repo_name,
                    config_path=args.config,
                    enable_ai=True,
                    telemetry_publishers=telemetry_publishers,
                    allowed_categories=args.workflow_category,
                )
                agent_type = "AI-enhanced"
            else:
                assignment_mode = "fallback"
                telemetry_publishers = attach_static_fields(
                    telemetry_publishers,
                    {
                        "assignment_mode": assignment_mode,
                        "assignment_agent": "WorkflowAssignmentAgent",
                    },
                )
                agent = WorkflowAssignmentAgent(
                    github_token=github_token,
                    repo_name=repo_name,
                    config_path=args.config,
                    telemetry_publishers=telemetry_publishers,
                    allowed_categories=args.workflow_category,
                )
                agent_type = "Label-based (fallback)"
            
            reporter = context.reporter
            reporter.show_info(f"Assignment mode: {agent_type} [{assignment_mode}]")
            
            if args.statistics:
                # Show statistics instead of processing
                reporter.start_operation("Fetching assignment statistics")
                stats = agent.get_assignment_statistics()
                
                if 'error' in stats:
                    publish_telemetry_event(
                        telemetry_publishers,
                        "workflow_assignment.statistics_view",
                        {
                            "success": False,
                            "agent_type": agent_type,
                            "error": stats.get('error'),
                            "dry_run": args.dry_run,
                            "limit": args.limit,
                            "statistics_snapshot": stats,
                        },
                    )
                    return finalize(CliResult(
                        success=False,
                        message=f"❌ Failed to get statistics: {stats['error']}",
                        error_code=1
                    ))
                
                # Format statistics output
                stats_lines = [
                    f"📊 **Workflow Assignment Statistics**",
                    f"🤖 **Agent Type:** {agent_type}",
                    f"",
                    f"**Issues Overview:**",
                    f"  Total site-monitor issues: {stats['total_site_monitor_issues']}",
                    f"  Unassigned issues: {stats['unassigned']}",
                    f"  Assigned issues: {stats['assigned']}",
                    f"  Need clarification: {stats['needs_clarification']}",
                ]
                
                if stats.get('needs_review', 0) > 0:
                    stats_lines.append(f"  Need review: {stats['needs_review']}")
                
                stats_lines.extend([
                    f"  Feature labeled: {stats['feature_labeled']}",
                    f""
                ])
                
                if stats['workflow_breakdown']:
                    stats_lines.extend([
                        f"**Workflow Breakdown:**"
                    ])
                    for workflow, count in sorted(stats['workflow_breakdown'].items()):
                        stats_lines.append(f"  {workflow}: {count}")
                    stats_lines.append("")
                
                if stats['label_distribution']:
                    stats_lines.extend([
                        f"**Label Distribution (Top 10):**"
                    ])
                    sorted_labels = sorted(stats['label_distribution'].items(), key=lambda x: x[1], reverse=True)
                    for label, count in sorted_labels[:10]:
                        stats_lines.append(f"  {label}: {count}")
                
                publish_telemetry_event(
                    telemetry_publishers,
                    "workflow_assignment.statistics_view",
                    {
                        "success": True,
                        "agent_type": agent_type,
                        "statistics_snapshot": stats,
                        "dry_run": args.dry_run,
                        "limit": args.limit,
                    },
                )

                return finalize(CliResult(
                    success=True,
                    message="\n".join(stats_lines),
                    data=stats
                ))
            
            else:
                # Process issues for workflow assignment
                reporter.start_operation(f"Processing workflow assignments (limit: {args.limit}, dry_run: {args.dry_run})")
                
                result = agent.process_issues_batch(
                    limit=args.limit,
                    dry_run=args.dry_run
                )
                
                if 'error' in result:
                    return finalize(CliResult(
                        success=False,
                        message=f"❌ Processing failed: {result['error']}",
                        error_code=1
                    ))
                
                # Format results
                total = result['total_issues']
                processed = result['processed']
                duration = result['duration_seconds']
                stats = result['statistics']
                
                result_lines = [
                    f"✅ **Workflow Assignment Complete**",
                    f"🤖 **Agent Type:** {agent_type}",
                    f"",
                    f"**Summary:**",
                    f"  Processed: {processed}/{total} issues in {duration:.1f}s",
                    f""
                ]
                
                # Add statistics breakdown
                if stats:
                    result_lines.extend([
                        f"**Actions Taken:**"
                    ])
                    for action, count in stats.items():
                        if count > 0:
                            action_name = action.replace('_', ' ').title()
                            result_lines.append(f"  {action_name}: {count}")

                results_list = result.get('results') or []

                adoption_lines: list[str] = []
                taxonomy_metrics: dict[str, Any] = {}
                matcher = getattr(agent, "workflow_matcher", None)
                if matcher and results_list:
                    category_counter: Counter[str] = Counter()
                    taxonomy_assigned = 0
                    legacy_assigned = 0
                    unknown_workflows = 0
                    total_assigned = 0

                    for issue_result in results_list:
                        assigned_name = issue_result.get('assigned_workflow')
                        if not assigned_name:
                            continue
                        info = matcher.get_workflow_by_name(assigned_name)
                        if info is None:
                            unknown_workflows += 1
                            continue

                        total_assigned += 1
                        if info.is_taxonomy():
                            taxonomy_assigned += 1
                        else:
                            legacy_assigned += 1

                        if info.category:
                            category_counter[info.category] += 1
                        else:
                            category_counter['legacy'] += 1

                    if total_assigned or category_counter or unknown_workflows:
                        taxonomy_rate = (
                            taxonomy_assigned / total_assigned
                            if total_assigned
                            else 0.0
                        )
                        taxonomy_metrics = {
                            "total_assigned": total_assigned,
                            "taxonomy_assigned": taxonomy_assigned,
                            "legacy_assigned": legacy_assigned,
                            "unknown_workflows": unknown_workflows,
                            "category_breakdown": dict(category_counter),
                            "taxonomy_rate": taxonomy_rate,
                            "filter_applied": bool(args.workflow_category),
                        }

                        if args.show_taxonomy_metrics or args.verbose:
                            denominator_text = str(total_assigned) if total_assigned else "0"
                            adoption_lines.append(
                                f"  Taxonomy workflows: {taxonomy_assigned}/{denominator_text}"
                                f" ({taxonomy_rate:.0%})"
                            )
                            if legacy_assigned:
                                adoption_lines.append(
                                    f"  Legacy workflows: {legacy_assigned}"
                                )
                            if unknown_workflows:
                                adoption_lines.append(
                                    f"  Unknown workflows: {unknown_workflows}"
                                )
                            for category, count in sorted(category_counter.items()):
                                friendly = category.replace('-', ' ').title()
                                adoption_lines.append(f"  {friendly}: {count}")

                explainability_lines: list[str] = []
                if ai_enabled and results_list:
                    reason_counter: Counter[str] = Counter()
                    coverage_values: list[float] = []
                    high_coverage = 0
                    partial_coverage = 0
                    missing_entity_issues = 0
                    legal_counts: Counter[str] = Counter()
                    statute_citations: Counter[str] = Counter()
                    precedent_citations: Counter[str] = Counter()
                    interagency_terms: Counter[str] = Counter()

                    for issue_result in results_list:
                        reason_counter.update(issue_result.get('reason_codes') or [])

                        ai_analysis = issue_result.get('ai_analysis') or {}
                        if isinstance(ai_analysis, dict) and ai_analysis:
                            entity_summary = ai_analysis.get('entity_summary') or {}
                            if isinstance(entity_summary, dict):
                                coverage = entity_summary.get('coverage')
                                if isinstance(coverage, (int, float)):
                                    coverage_values.append(float(coverage))
                                    if coverage >= 0.67:
                                        high_coverage += 1
                                    elif coverage >= 0.34:
                                        partial_coverage += 1
                                if entity_summary.get('missing_base_entities'):
                                    missing_entity_issues += 1

                            legal_signals = ai_analysis.get('legal_signals') or {}
                            if isinstance(legal_signals, dict):
                                for signal_name, value in legal_signals.items():
                                    try:
                                        numeric_value = float(value)
                                    except (TypeError, ValueError):
                                        continue
                                    if numeric_value > 0:
                                        legal_counts[signal_name] += 1

                                for citation in legal_signals.get('statute_matches') or []:
                                    if isinstance(citation, str) and citation.strip():
                                        statute_citations[citation.strip()] += 1
                                for precedent in legal_signals.get('precedent_matches') or []:
                                    if isinstance(precedent, str) and precedent.strip():
                                        precedent_citations[precedent.strip()] += 1
                                for agency in legal_signals.get('interagency_terms') or []:
                                    if isinstance(agency, str) and agency.strip():
                                        interagency_terms[agency.strip().lower()] += 1

                    if reason_counter:
                        top_codes = reason_counter.most_common(5)
                        explainability_lines.append(
                            "  Top reason codes: "
                            + ", ".join(f"{code} ({count})" for code, count in top_codes)
                        )

                    if coverage_values:
                        avg_coverage = sum(coverage_values) / len(coverage_values)
                        coverage_fragments: list[str] = []
                        if high_coverage:
                            coverage_fragments.append(f"{high_coverage} high")
                        if partial_coverage:
                            coverage_fragments.append(f"{partial_coverage} partial")
                        low_count = len(coverage_values) - high_coverage - partial_coverage
                        if low_count:
                            coverage_fragments.append(f"{low_count} low")

                        coverage_line = f"  Base entity coverage: {avg_coverage:.0%} avg"
                        if coverage_fragments:
                            coverage_line += f" ({', '.join(coverage_fragments)})"
                        explainability_lines.append(coverage_line)

                        if missing_entity_issues:
                            explainability_lines.append(
                                f"  Missing base entities flagged in {missing_entity_issues} issue(s)"
                            )

                    if legal_counts:
                        friendly_names = {
                            'statutes': 'Statutes',
                            'precedent': 'Precedent',
                            'interagency': 'Inter-Agency',
                        }
                        explainability_lines.append(
                            "  Legal signals detected: "
                            + ", ".join(
                                f"{friendly_names.get(signal, signal.replace('_', ' ').title())} ({count})"
                                for signal, count in sorted(legal_counts.items())
                            )
                        )

                    if statute_citations:
                        top_statutes = [citation for citation, _ in statute_citations.most_common(5)]
                        explainability_lines.append(
                            "  Statute citations: " + ", ".join(top_statutes)
                        )
                    if precedent_citations:
                        top_precedents = [case for case, _ in precedent_citations.most_common(5)]
                        explainability_lines.append(
                            "  Precedent references: " + ", ".join(top_precedents)
                        )
                    if interagency_terms:
                        top_agencies = [agency.upper() for agency, _ in interagency_terms.most_common(5)]
                        explainability_lines.append(
                            "  Inter-agency terms: " + ", ".join(top_agencies)
                        )

                if explainability_lines:
                    result_lines.extend([
                        f"",
                        f"**Explainability Signals:**",
                        *explainability_lines,
                    ])

                if adoption_lines:
                    result_lines.extend([
                        f"",
                        f"**Taxonomy Adoption:**",
                        *adoption_lines,
                    ])
                
                # Add details if verbose
                if args.verbose and results_list:
                    result_lines.extend([
                        f"",
                        f"**Issue Details:**"
                    ])
                    for issue_result in results_list:
                        # All results are now from AI agent (dictionary format)
                        action = issue_result.get('action_taken', 'unknown').replace('_', ' ').title()
                        result_lines.append(f"  Issue #{issue_result['issue_number']}: {action}")
                        if issue_result.get('assigned_workflow'):
                            result_lines.append(f"    Workflow: {issue_result['assigned_workflow']}")
                        if issue_result.get('labels_added'):
                            result_lines.append(f"    Labels added: {', '.join(issue_result['labels_added'])}")
                        if issue_result.get('message'):
                            result_lines.append(f"    Note: {issue_result['message']}")
                        reason_codes = issue_result.get('reason_codes') or []
                        if reason_codes:
                            result_lines.append(f"    Reason Codes: {', '.join(reason_codes)}")
                        # Add AI-specific information
                        if ai_enabled and 'ai_analysis' in issue_result:
                            ai_analysis = issue_result['ai_analysis']
                            if ai_analysis.get('summary'):
                                result_lines.append(f"    AI Summary: {ai_analysis['summary']}")
                            if ai_analysis.get('content_type'):
                                result_lines.append(f"    Content Type: {ai_analysis['content_type']}")
                            if ai_analysis.get('urgency_level'):
                                result_lines.append(f"    Urgency: {ai_analysis['urgency_level']}")
                            combined_scores = ai_analysis.get('combined_scores') or {}
                            if isinstance(combined_scores, dict) and combined_scores:
                                top_scores = sorted(
                                    combined_scores.items(),
                                    key=lambda item: item[1],
                                    reverse=True,
                                )[:3]
                                scores_text = ", ".join(
                                    f"{name} {score:.0%}" for name, score in top_scores
                                )
                                result_lines.append(f"    Combined Scores: {scores_text}")
                            entity_summary = ai_analysis.get('entity_summary') or {}
                            if isinstance(entity_summary, dict) and entity_summary:
                                coverage = entity_summary.get('coverage')
                                counts = entity_summary.get('counts') or {}
                                if isinstance(coverage, (int, float)):
                                    counts_text = ", ".join(
                                        f"{key}={counts.get(key, 0)}"
                                        for key in sorted(counts)
                                    ) or "no counts"
                                    result_lines.append(
                                        f"    Entity Coverage: {coverage:.0%} ({counts_text})"
                                    )
                                missing_entities = entity_summary.get('missing_base_entities') or []
                                if missing_entities:
                                    result_lines.append(
                                        f"    Missing Entities: {', '.join(missing_entities)}"
                                    )
                            legal_signals = ai_analysis.get('legal_signals') or {}
                            if isinstance(legal_signals, dict) and legal_signals:
                                signal_parts = []
                                for signal_name, value in legal_signals.items():
                                    try:
                                        numeric_value = float(value)
                                    except (TypeError, ValueError):
                                        continue
                                    icon = "✔" if numeric_value > 0 else "✖"
                                    friendly = {
                                        'statutes': 'Statutes',
                                        'precedent': 'Precedent',
                                        'interagency': 'Inter-Agency',
                                    }.get(signal_name, signal_name.replace('_', ' ').title())
                                    signal_parts.append(f"{friendly} {icon}")
                                if signal_parts:
                                    result_lines.append(
                                        f"    Legal Signals: {', '.join(signal_parts)}"
                                    )

                                statute_matches = [
                                    citation.strip()
                                    for citation in (legal_signals.get('statute_matches') or [])
                                    if isinstance(citation, str) and citation.strip()
                                ]
                                if statute_matches:
                                    result_lines.append(
                                        "    Statute Citations: "
                                        + ", ".join(statute_matches[:5])
                                    )

                                precedent_matches = [
                                    case.strip()
                                    for case in (legal_signals.get('precedent_matches') or [])
                                    if isinstance(case, str) and case.strip()
                                ]
                                if precedent_matches:
                                    result_lines.append(
                                        "    Precedent References: "
                                        + ", ".join(precedent_matches[:5])
                                    )

                                interagency_matches = [
                                    agency.strip().upper()
                                    for agency in (legal_signals.get('interagency_terms') or [])
                                    if isinstance(agency, str) and agency.strip()
                                ]
                                if interagency_matches:
                                    result_lines.append(
                                        "    Inter-Agency Terms: "
                                        + ", ".join(interagency_matches[:5])
                                    )
                
                success = processed > 0 or total == 0
                error_code = 0
                if not success:
                    has_errors = False
                    if isinstance(stats, dict):
                        error_values = [
                            stats.get('errors', 0),
                            stats.get('error', 0),
                        ]
                        has_errors = any(value and value > 0 for value in error_values)
                    has_error_results = any(
                        isinstance(issue_result, dict)
                        and issue_result.get('action_taken') == 'error'
                        for issue_result in results_list
                    )
                    if processed == 0 and (has_errors or has_error_results):
                        error_code = 1
                if taxonomy_metrics:
                    result.setdefault('taxonomy_metrics', taxonomy_metrics)
                return finalize(CliResult(
                    success=success,
                    message="\n".join(result_lines),
                    data=result,
                    error_code=error_code,
                ))
                
        except Exception as e:
            return finalize(CliResult(
                success=False,
                message=f"Workflow assignment failed: {str(e)}",
                error_code=1
            ))
    
    # Execute the command safely
    exit_code = safe_execute_cli_command(assign_workflows_command)
    if exit_code != 0:
        sys.exit(exit_code)


def main():
    """Main entry point for the application."""
    load_dotenv()
    
    # Set up argument parser
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Set up logging configuration
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', None)
    enable_console = not os.getenv('GITHUB_ACTIONS', '').lower() == 'true'  # Disable console in GitHub Actions
    
    try:
        setup_logging(
            log_level=log_level,
            log_file=log_file,
            enable_console=enable_console
        )
    except Exception as e:
        print(f"Warning: Failed to set up logging: {e}", file=sys.stderr)
        # Continue without proper logging rather than failing
    
    # Validate environment
    github_token, repo_name = validate_environment()
    
    try:
        # Route to appropriate command handler
        if args.command == 'create-issue':
            handle_create_issue_command(args, github_token, repo_name)
        elif args.command == 'monitor':
            handle_monitor_command(args, github_token)
        elif args.command == 'setup':
            handle_setup_command(args, github_token)
        elif args.command == 'status':
            handle_status_command(args, github_token)
        elif args.command == 'cleanup':
            handle_cleanup_command(args, github_token)
        elif args.command == 'process-issues':
            handle_process_issues_command(args, github_token, repo_name)
        elif args.command == 'assign-workflows':
            handle_assign_workflows_command(args, github_token, repo_name)
        elif args.command == 'specialist-config':
            exit_code = handle_specialist_config_command(args)
            sys.exit(exit_code)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            parser.print_help()
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()