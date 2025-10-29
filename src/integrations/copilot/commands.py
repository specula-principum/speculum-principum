"""CLI helpers for Copilot-focused workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.integrations.copilot.accuracy import (
    evaluate_accuracy,
    load_accuracy_scenario,
    render_accuracy_report,
)
from src.integrations.copilot.helpers import (
    ValidationReport,
    generate_quality_report,
    prepare_kb_extraction_context,
    validate_kb_changes,
)
from src.integrations.github.automation import run_end_to_end_automation
from src.integrations.github.assign_copilot import fetch_issue_details
from src.integrations.github.issues import DEFAULT_API_URL, resolve_repository, resolve_token
from src.mcp_server.kb_server import main as run_mcp_server


def register_copilot_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register Copilot-oriented subcommands with the main CLI."""

    parser = subparsers.add_parser(
        "copilot",
        description="Convenience commands that streamline Copilot agent workflows.",
        help="Copilot agent automation helpers.",
    )
    parser.set_defaults(command="copilot")
    copilot_sub = parser.add_subparsers(dest="copilot_command", metavar="SUBCOMMAND")
    copilot_sub.required = True

    _register_kb_extract(copilot_sub)
    _register_kb_validate(copilot_sub)
    _register_kb_report(copilot_sub)
    _register_kb_accuracy(copilot_sub)
    _register_kb_automation(copilot_sub)
    _register_mcp_serve(copilot_sub)


def _register_kb_extract(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "kb-extract",
        description="Render focused context for a knowledge extraction issue.",
        help="Prepare context for KB extraction tasks.",
    )
    parser.add_argument("--issue", type=int, required=True, help="Issue number to parse.")
    parser.add_argument(
        "--repo",
        help="Target repository in owner/repo form. Defaults to $GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Base URL for the GitHub API (set for GitHub Enterprise).",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=Path("knowledge-base"),
        help="Knowledge base root directory.",
    )
    parser.set_defaults(func=_run_kb_extract)


def _register_kb_validate(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "kb-validate",
        description="Run validation on knowledge base changes.",
        help="Validate knowledge base structure and quality thresholds.",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=Path("knowledge-base"),
        help="Knowledge base root directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit validation output as JSON.",
    )
    parser.set_defaults(func=_run_kb_validate)


def _register_kb_report(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "kb-report",
        description="Generate a quality report for a knowledge base issue.",
        help="Produce a markdown quality report for the specified issue.",
    )
    parser.add_argument("--issue", type=int, required=True, help="Issue number for naming the report.")
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=Path("knowledge-base"),
        help="Knowledge base root directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory where the report markdown file will be written.",
    )
    parser.set_defaults(func=_run_kb_report)


def _register_kb_accuracy(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "verify-accuracy",
        description="Evaluate knowledge base accuracy against curated scenarios.",
        help="Compare KB contents to gold-standard expectations.",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        required=True,
        help="Path to the accuracy scenario definition (YAML or JSON).",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=Path("knowledge-base"),
        help="Knowledge base root directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit accuracy metrics as JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path where JSON accuracy results should be written.",
    )
    parser.set_defaults(func=_run_kb_accuracy)


def _register_kb_automation(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "kb-automation",
        description="Run the end-to-end automation workflow for knowledge extraction.",
        help="Execute processing, validation, and report generation in one command.",
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Path to the parsed evidence directory used as pipeline input.",
    )
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=Path("knowledge-base"),
        help="Knowledge base root directory (default: knowledge-base).",
    )
    parser.add_argument(
        "--mission",
        type=Path,
        help="Optional mission configuration path passed to the pipeline.",
    )
    parser.add_argument(
        "--extract",
        dest="extractors",
        nargs="+",
        help="Override extractor list (defaults to pipeline configuration).",
    )
    parser.add_argument(
        "--issue",
        type=int,
        help="Issue number used when naming the generated quality report.",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        help="Optional path where pipeline metrics should be written.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Directory where the quality report markdown file will be stored.",
    )
    parser.add_argument(
        "--skip-pipeline-validation",
        action="store_true",
        help="Skip internal validation inside the pipeline and rely on post-checks only.",
    )
    parser.set_defaults(func=_run_kb_automation)


def _register_mcp_serve(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "mcp-serve",
        description="Start the MCP server for Copilot integration.",
        help="Run the MCP server over stdio for agent use.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available MCP tools and exit.",
    )
    parser.set_defaults(func=_run_mcp_serve)


def _run_kb_extract(args: argparse.Namespace) -> int:
    repository = resolve_repository(args.repo)
    token = resolve_token(args.token)
    issue = fetch_issue_details(
        token=token,
        repository=repository,
        issue_number=args.issue,
        api_url=args.api_url,
    )
    context = prepare_kb_extraction_context(issue, kb_root=args.kb_root)
    print(context)
    return 0


def _run_kb_validate(args: argparse.Namespace) -> int:
    try:
        report = validate_kb_changes(args.kb_root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        payload = _report_to_dict(report)
        print(json.dumps(payload, indent=2))
    else:
        print(_format_report(report))
    return 0 if report.is_successful else 1


def _run_kb_report(args: argparse.Namespace) -> int:
    try:
        report = validate_kb_changes(args.kb_root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    generate_quality_report(
        args.kb_root,
        args.issue,
        output_dir=args.output_dir,
        report=report,
    )
    print(f"Report written to {(args.output_dir / f'quality-{args.issue}.md').resolve()}")
    return 0 if report.is_successful else 1


def _run_kb_accuracy(args: argparse.Namespace) -> int:
    scenario = load_accuracy_scenario(args.scenario)
    report = evaluate_accuracy(scenario, args.kb_root)
    if args.output is not None:
        payload_path = args.output.expanduser()
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_accuracy_report(report))
    return 0 if report.is_successful else 1


def _run_kb_automation(args: argparse.Namespace) -> int:
    outcome = run_end_to_end_automation(
        source_path=args.source,
        kb_root=args.kb_root,
        mission_path=args.mission,
        extractors=tuple(args.extractors) if args.extractors else None,
        issue_number=args.issue,
        metrics_output=args.metrics_output,
        report_dir=args.report_dir,
        validate_pipeline=not args.skip_pipeline_validation,
    )

    print("KB PROCESSING:", "SUCCESS" if outcome.processing.success else "FAILED")
    for stage in outcome.processing.stages:
        metrics = ", ".join(f"{key}={value}" for key, value in sorted(stage.metrics.items())) or "no-metrics"
        print(f"- {stage.stage}: {metrics}")
    if outcome.processing.errors:
        for message in outcome.processing.errors:
            print(f"error: {message}")

    print("\nVALIDATION SUMMARY:")
    print(_format_report(outcome.validation))
    print("")
    print(f"Quality report: {outcome.report_path}")
    if outcome.metrics_path is not None:
        print(f"Metrics path: {outcome.metrics_path}")

    return 0 if outcome.success else 1


def _run_mcp_serve(args: argparse.Namespace) -> int:
    argv: list[str] = []
    if args.list_tools:
        argv.append("--list-tools")
    return run_mcp_server(argv)


def _format_report(report: ValidationReport) -> str:
    lines = [
        f"KB Root: {report.kb_root}",
        f"Documents Checked: {report.documents_checked}",
        f"Documents Valid: {report.documents_valid}",
        f"Average Completeness: {report.quality.average_completeness:.2f}",
        f"Average Findability: {report.quality.average_findability:.2f}",
    ]
    if report.errors:
        lines.append("Errors:")
        lines.extend(f"  - {message}" for message in report.errors)
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {message}" for message in report.warnings)
    return "\n".join(lines)


def _report_to_dict(report: ValidationReport) -> dict[str, object]:
    return {
        "kb_root": str(report.kb_root),
        "documents_checked": report.documents_checked,
        "documents_valid": report.documents_valid,
        "errors": list(report.errors),
        "warnings": list(report.warnings),
        "quality": {
            "total_documents": report.quality.total_documents,
            "average_completeness": report.quality.average_completeness,
            "average_findability": report.quality.average_findability,
            "below_threshold": list(report.quality.below_threshold),
        },
    }
