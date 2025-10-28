"""Knowledge base CLI command registration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.kb_engine.workflows import (
    BenchmarkOptions,
    ExportGraphOptions,
    KBBenchmarkResult,
    ImproveOptions,
    ProcessOptions,
    UpdateOptions,
    QualityReportOptions,
    run_benchmark_workflow,
    run_process_workflow,
    run_export_graph_workflow,
    run_improve_workflow,
    run_quality_report_workflow,
    run_update_workflow,
)
from src.knowledge_base.cli import initialize_knowledge_base
from src.knowledge_base.config import load_mission_config
from src.knowledge_base.taxonomy import load_taxonomy


def _handle_init(args: argparse.Namespace) -> int:
    """Preview the files that would be created for knowledge base initialization."""

    root = Path(args.root).expanduser()
    mission_config = None
    mission_path = Path(args.mission).expanduser() if args.mission else Path("config/mission.yaml")
    if mission_path.exists():
        try:
            mission_config = load_mission_config(mission_path)
        except (FileNotFoundError, ImportError, ValueError) as exc:
            print(f"mission config validation failed: {exc}", file=sys.stderr)
            return 1
    elif args.mission:
        print(f"mission config '{mission_path}' does not exist", file=sys.stderr)
        return 1

    context: dict[str, str] = {}
    if args.title is not None:
        context["title"] = args.title
    if args.description is not None:
        context["description"] = args.description
    context_payload = context or None

    paths = initialize_knowledge_base(
        root,
        apply=args.apply,
        context=context_payload,
        mission=mission_config,
    )
    for path in paths:
        print(path)
    return 0


def _handle_validate_taxonomy(args: argparse.Namespace) -> int:
    """Validate a taxonomy definition file and report issues."""

    taxonomy_path = Path(args.taxonomy).expanduser()
    try:
        load_taxonomy(taxonomy_path)
    except ValueError as exc:  # Defensive: surface schema errors via exit code.
        print(f"taxonomy validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _emit_pipeline_summary(result, *, label: str | None = None) -> None:
    header = "SUCCESS" if result.success else "FAILED"
    print(f"{label + ': ' if label else ''}{header}")
    for stage in result.stages:
        metrics = ", ".join(f"{key}={value}" for key, value in sorted(stage.metrics.items())) or "no-metrics"
        print(f"- {stage.stage}: {metrics}")
        for warning in stage.warnings:
            print(f"  warning: {warning}")
    for error in result.errors:
        print(f"error: {error}")
    error_details = getattr(result, "error_details", ())
    if error_details:
        print("error details:")
        for detail in error_details:
            print(f"  stage={detail.stage} type={detail.error_type} message={detail.message}")
            if detail.traceback:
                print("    traceback:")
                for line in detail.traceback.rstrip().splitlines():
                    print(f"      {line}")


def _emit_improvement_summary(result) -> None:
    status = "SUCCESS" if result.success else "ATTENTION"
    print(f"IMPROVEMENT {status}: gaps={len(result.gaps)}")
    if result.metrics:
        for key, value in sorted(result.metrics.items()):
            print(f"- {key}={value}")
    if result.fixes_applied:
        print("Fixes applied:")
        for fix in result.fixes_applied:
            print(f"  - {fix}")
    if result.report_path is not None:
        print(f"Report written to: {result.report_path}")
    if result.suggestions:
        print("Suggestions:")
        for kb_id, actions in sorted(result.suggestions.items()):
            print(f"  {kb_id}:")
            for action in actions[:5]:
                print(f"    - {action}")


def _emit_export_summary(result) -> None:
    print("GRAPH EXPORT SUCCESS")
    print(f"- format={result.format}")
    print(f"- nodes={result.nodes}")
    print(f"- edges={result.edges}")
    print(f"- output={result.output_path}")


def _emit_quality_report_summary(result) -> None:
    print("QUALITY REPORT")
    print(f"- documents={result.documents_total}")
    if result.document_types:
        doc_types = ", ".join(f"{name}={count}" for name, count in sorted(result.document_types.items()))
        print(f"- by_type={doc_types}")

    completeness = result.metrics.get("completeness", {})
    if completeness:
        print(
            "- completeness.mean={mean:.3f} missing={missing}".format(
                mean=completeness.get("mean", 0.0),
                missing=int(completeness.get("missing", 0.0)),
            )
        )

    findability = result.metrics.get("findability", {})
    if findability:
        print(
            "- findability.mean={mean:.3f} missing={missing}".format(
                mean=findability.get("mean", 0.0),
                missing=int(findability.get("missing", 0.0)),
            )
        )

    error_count = result.gap_counts.get("error", 0)
    warning_count = result.gap_counts.get("warning", 0)
    info_count = result.gap_counts.get("info", 0)
    total_gaps = result.gap_counts.get("total", len(result.gaps))
    print(
        f"- gaps.total={total_gaps} errors={error_count} warnings={warning_count} info={info_count}"
    )

    if result.invalid_documents:
        print(f"- invalid_documents={len(result.invalid_documents)}")

    print(f"- report={result.output_path}")


def _benchmark_payload(result: KBBenchmarkResult) -> dict[str, Any]:
    iterations = [
        {
            "iteration": item.iteration,
            "duration_seconds": item.duration_seconds,
            "stage_durations": dict(item.stage_durations),
            "documents": item.documents,
            "warnings": list(item.warnings),
            "errors": list(item.errors),
        }
        for item in result.iterations
    ]
    payload = {
        "source": str(result.source_path),
        "iterations": result.iteration_count,
        "success": result.success,
        "artifacts_root": str(result.artifacts_root),
        "pipeline_stages": list(result.stage_names),
        "iterations_detail": iterations,
        "metrics": {
            "total": dict(result.total_summary),
            "stages": {name: dict(metrics) for name, metrics in result.stage_summaries.items()},
        },
    }
    return payload


def _emit_benchmark_summary(result: KBBenchmarkResult, payload: dict[str, Any]) -> None:
    print("KB BENCHMARK SUMMARY")
    print(f"- iterations={payload['iterations']}")
    print(f"- success={payload['success']}")
    total = payload["metrics"]["total"]
    print(f"- total.mean_seconds={total['mean_seconds']}")
    print(f"- total.max_seconds={total['max_seconds']}")
    for stage in sorted(payload["metrics"]["stages"].keys()):
        summary = payload["metrics"]["stages"][stage]
        print(
            f"  {stage}: mean={summary['mean_seconds']}s min={summary['min_seconds']}s max={summary['max_seconds']}s"
        )
    if payload["artifacts_root"] and Path(payload["artifacts_root"]).exists():
        print(f"- artifacts_root={payload['artifacts_root']}")


def _handle_benchmark(args: argparse.Namespace) -> int:
    options = BenchmarkOptions(
        source_path=Path(args.source).expanduser(),
        iterations=args.iterations,
        mission_path=Path(args.mission).expanduser() if args.mission else None,
        extractors=tuple(args.extractors) if args.extractors else None,
        validate=args.validate,
        scratch_root=Path(args.scratch_root).expanduser() if args.scratch_root else None,
        retain_artifacts=args.retain_artifacts,
    )

    try:
        result = run_benchmark_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb benchmark error: {exc}", file=sys.stderr)
        return 1

    payload = _benchmark_payload(result)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Benchmark results written to {output_path}")
    else:
        _emit_benchmark_summary(result, payload)

    return 0 if result.success else 1


def _handle_process(args: argparse.Namespace) -> int:
    options = ProcessOptions(
        source_path=Path(args.source).expanduser(),
        kb_root=Path(args.kb_root).expanduser(),
        mission_path=Path(args.mission).expanduser() if args.mission else None,
        extractors=tuple(args.extractors) if args.extractors else None,
        validate=args.validate,
        metrics_path=Path(args.metrics_output).expanduser() if args.metrics_output else None,
    )

    try:
        result = run_process_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb process error: {exc}", file=sys.stderr)
        return 1

    _emit_pipeline_summary(result)
    return 0 if result.success else 1


def _handle_update(args: argparse.Namespace) -> int:
    options = UpdateOptions(
        kb_id=args.kb_id,
        source_path=Path(args.source).expanduser(),
        kb_root=Path(args.kb_root).expanduser(),
        mission_path=Path(args.mission).expanduser() if args.mission else None,
        extractors=tuple(args.extractors) if args.extractors else None,
        validate=args.validate,
        reextract=args.reextract,
        rebuild_links=args.rebuild_links,
        metrics_path=Path(args.metrics_output).expanduser() if args.metrics_output else None,
    )

    try:
        result = run_update_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb update error: {exc}", file=sys.stderr)
        return 1

    _emit_pipeline_summary(result, label=args.kb_id)
    return 0 if result.success else 1


def _handle_improve(args: argparse.Namespace) -> int:
    options = ImproveOptions(
        kb_root=Path(args.kb_root).expanduser(),
        min_completeness=args.min_completeness,
        min_findability=args.min_findability,
        fix_links=args.fix_links,
        suggest_tags=args.suggest_tags,
        report_path=Path(args.report).expanduser() if args.report else None,
    )

    try:
        result = run_improve_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb improve error: {exc}", file=sys.stderr)
        return 1

    _emit_improvement_summary(result)
    return 0


def _handle_export_graph(args: argparse.Namespace) -> int:
    options = ExportGraphOptions(
        kb_root=Path(args.kb_root).expanduser(),
        output_path=Path(args.output).expanduser(),
        format=args.format,
    )

    try:
        result = run_export_graph_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb export-graph error: {exc}", file=sys.stderr)
        return 1

    _emit_export_summary(result)
    return 0


def _handle_quality_report(args: argparse.Namespace) -> int:
    options = QualityReportOptions(
        kb_root=Path(args.kb_root).expanduser(),
        output_path=Path(args.output).expanduser() if args.output else None,
        min_completeness=args.min_completeness,
        min_findability=args.min_findability,
        min_body_length=args.min_body_length,
        include_meta=args.include_meta,
    )

    try:
        result = run_quality_report_workflow(options)
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"kb quality-report error: {exc}", file=sys.stderr)
        return 1

    _emit_quality_report_summary(result)
    return 0 if result.success else 1


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register knowledge base commands with the global CLI."""

    parser = subparsers.add_parser(
        "kb",
        help="Experimental knowledge base tooling (Phase 2).",
        description=(
            "Knowledge base workflows are under active development."
        ),
    )
    kb_subparsers = parser.add_subparsers(dest="kb_command", metavar="KB_COMMAND")
    kb_subparsers.required = True

    init_parser = kb_subparsers.add_parser(
        "init",
        help="Display the IA structure blueprint for a knowledge base root.",
    )
    init_parser.add_argument(
        "--root",
        default="knowledge-base",
        help="Path to the knowledge base root (default: knowledge-base).",
    )
    init_parser.add_argument(
        "--mission",
        help="Path to mission configuration. Defaults to config/mission.yaml when present.",
    )
    init_parser.add_argument(
        "--title",
        help="Override the mission title for this run.",
    )
    init_parser.add_argument(
        "--description",
        help="Override the mission description for this run.",
    )
    init_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the planned structure to disk instead of previewing paths.",
    )
    init_parser.set_defaults(func=_handle_init)

    validate_parser = kb_subparsers.add_parser(
        "validate-taxonomy",
        help="Validate a taxonomy YAML file against IA rules.",
    )
    validate_parser.add_argument(
        "--taxonomy",
        default="config/taxonomy.yaml",
        help="Path to the taxonomy definition (default: config/taxonomy.yaml).",
    )
    validate_parser.set_defaults(func=_handle_validate_taxonomy)

    process_parser = kb_subparsers.add_parser(
        "process",
        help="Process parsed evidence into the knowledge base.",
    )
    process_parser.add_argument(
        "--source",
        required=True,
        help="Path to the parsed evidence directory.",
    )
    process_parser.add_argument(
        "--kb-root",
        default="knowledge-base",
        help="Knowledge base root directory (default: knowledge-base).",
    )
    process_parser.add_argument(
        "--mission",
        help="Optional mission configuration path.",
    )
    process_parser.add_argument(
        "--extract",
        dest="extractors",
        nargs="+",
        help="Override extractor list (default: pipeline configuration).",
    )
    process_parser.add_argument(
        "--validate",
        action="store_true",
        help="Run quality validation after processing.",
    )
    process_parser.add_argument(
        "--metrics-output",
        dest="metrics_output",
        help="Write metrics to a custom file path.",
    )
    process_parser.set_defaults(func=_handle_process)

    update_parser = kb_subparsers.add_parser(
        "update",
        help="Update an existing knowledge base entry from parsed evidence.",
    )
    update_parser.add_argument(
        "--kb-id",
        required=True,
        help="Knowledge base identifier to refresh (e.g., concepts/statecraft/virtue).",
    )
    update_parser.add_argument(
        "--source",
        required=True,
        help="Path to the parsed evidence directory.",
    )
    update_parser.add_argument(
        "--kb-root",
        default="knowledge-base",
        help="Knowledge base root directory (default: knowledge-base).",
    )
    update_parser.add_argument(
        "--mission",
        help="Optional mission configuration path.",
    )
    update_parser.add_argument(
        "--extract",
        dest="extractors",
        nargs="+",
        help="Override extractor list (default: pipeline configuration).",
    )
    update_parser.add_argument(
        "--reextract",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Re-run extraction stages (default: enabled).",
    )
    update_parser.add_argument(
        "--rebuild-links",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Rebuild graphs and backlinks during update.",
    )
    update_parser.add_argument(
        "--validate",
        action="store_true",
        help="Run quality validation after update.",
    )
    update_parser.add_argument(
        "--metrics-output",
        dest="metrics_output",
        help="Write metrics to a custom file path.",
    )
    update_parser.set_defaults(func=_handle_update)

    benchmark_parser = kb_subparsers.add_parser(
        "benchmark",
        help="Benchmark the knowledge base pipeline over repeated runs.",
    )
    benchmark_parser.add_argument(
        "--source",
        required=True,
        help="Path to the parsed evidence directory used for benchmarking.",
    )
    benchmark_parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of benchmark iterations to execute (default: 3).",
    )
    benchmark_parser.add_argument(
        "--mission",
        help="Optional mission configuration path.",
    )
    benchmark_parser.add_argument(
        "--extract",
        dest="extractors",
        nargs="+",
        help="Override extractor list (default: pipeline configuration).",
    )
    benchmark_parser.add_argument(
        "--validate",
        action="store_true",
        help="Run quality validation during each iteration.",
    )
    benchmark_parser.add_argument(
        "--scratch-root",
        help="Directory to store benchmark artifacts (default: temporary directory).",
    )
    benchmark_parser.add_argument(
        "--retain-artifacts",
        action="store_true",
        help="Keep generated benchmark artifacts instead of cleaning them up.",
    )
    benchmark_parser.add_argument(
        "--output",
        help="Optional path to write benchmark metrics as JSON.",
    )
    benchmark_parser.set_defaults(func=_handle_benchmark)

    improve_parser = kb_subparsers.add_parser(
        "improve",
        help="Review and improve knowledge base quality gaps.",
    )
    improve_parser.add_argument(
        "--kb-root",
        default="knowledge-base",
        help="Knowledge base root directory (default: knowledge-base).",
    )
    improve_parser.add_argument(
        "--min-completeness",
        type=float,
        help="Override minimum completeness threshold.",
    )
    improve_parser.add_argument(
        "--min-findability",
        type=float,
        help="Override minimum findability threshold.",
    )
    improve_parser.add_argument(
        "--fix-links",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Automatically regenerate backlinks during improvement.",
    )
    improve_parser.add_argument(
        "--suggest-tags",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Provide tag suggestions for documents missing tags.",
    )
    improve_parser.add_argument(
        "--report",
        help="Optional path to write an improvement report (JSON).",
    )
    improve_parser.set_defaults(func=_handle_improve)

    export_parser = kb_subparsers.add_parser(
        "export-graph",
        help="Export the knowledge graph to standard formats.",
    )
    export_parser.add_argument(
        "--kb-root",
        default="knowledge-base",
        help="Knowledge base root directory (default: knowledge-base).",
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "graphml", "dot", "csv"],
        default="json",
        help="Graph export format (default: json).",
    )
    export_parser.add_argument(
        "--output",
        required=True,
        help="Destination file for the exported graph.",
    )
    export_parser.set_defaults(func=_handle_export_graph)

    quality_parser = kb_subparsers.add_parser(
        "quality-report",
        help="Generate a quality metrics report for the knowledge base.",
    )
    quality_parser.add_argument(
        "--kb-root",
        default="knowledge-base",
        help="Knowledge base root directory (default: knowledge-base).",
    )
    quality_parser.add_argument(
        "--output",
        help="Write the quality report JSON to a file (default: reports/kb-quality-report-<timestamp>.json).",
    )
    quality_parser.add_argument(
        "--min-completeness",
        type=float,
        help="Override the completeness threshold used for gap detection.",
    )
    quality_parser.add_argument(
        "--min-findability",
        type=float,
        help="Override the findability threshold used for gap detection.",
    )
    quality_parser.add_argument(
        "--min-body-length",
        type=int,
        help="Override the minimum body length used when flagging short documents.",
    )
    quality_parser.add_argument(
        "--include-meta",
        action="store_true",
        help="Include documents under the 'meta' directory when generating the report.",
    )
    quality_parser.set_defaults(func=_handle_quality_report)
