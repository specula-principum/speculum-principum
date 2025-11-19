"""CLI helpers for Copilot-focused workflows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import yaml

from src.integrations.copilot.accuracy import (
    evaluate_accuracy,
    load_accuracy_scenario,
    render_accuracy_report,
)
from src.integrations.github.assign_copilot import fetch_issue_details
from src.integrations.github.issues import (
    DEFAULT_API_URL,
    GitHubIssueError,
    resolve_repository,
    resolve_token,
)
from src.mcp_server.kb_server import main as run_mcp_server
from src.orchestration.demo import run_issue_detail_demo, run_parsing_preview_demo
from src.orchestration.planner import PlanConfigError, load_deterministic_plan
from src.orchestration.types import MissionStatus
from src.parsing.runner import collect_parse_candidates


_DEFAULT_PREVIEW_PLAN_PATH = Path("devops/projects/kb-source-preview.plan.yaml")
_DEFAULT_PREVIEW_MISSION_PATH = Path("config/missions/kb_source_preview.yaml")


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

    _register_mcp_serve(copilot_sub)
    _register_agent_demo(copilot_sub)
    _register_preview_demo(copilot_sub)





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


def _register_agent_demo(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "agent-demo",
        description="Execute the deterministic issue detail mission for dry-run validation.",
        help="Run the issue detail demo mission with an optional custom plan.",
    )
    parser.add_argument("--issue", type=int, required=True, help="Issue number to fetch from GitHub.")
    parser.add_argument(
        "--repo",
        help="Repository in owner/repo form. Defaults to $GITHUB_REPOSITORY if omitted.",
    )
    parser.add_argument(
        "--token",
        help="GitHub token. Defaults to $GITHUB_TOKEN if omitted.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        help="Path to a deterministic plan definition (YAML or JSON).",
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="Optional JSON or YAML file providing additional planner context inputs.",
    )
    parser.add_argument(
        "--param",
        dest="params",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional context overrides for the plan (repeatable).",
    )
    parser.add_argument(
        "--default-finish",
        help="Override the default completion summary when supplying a custom plan.",
    )
    parser.add_argument(
        "--transcript-path",
        type=Path,
        help="Explicit path where the mission transcript JSON should be written.",
    )
    parser.add_argument(
        "--transcript-dir",
        type=Path,
        default=Path("reports/transcripts"),
        help="Directory used for transcript output when --transcript-path is not provided.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Skip writing a mission transcript to disk.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the mission outcome as JSON for scripting.",
    )
    parser.add_argument(
        "--triage",
        action="store_true",
        help="Enable triage mode, requiring a recommendation in the transcript.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive approval mode for destructive operations.",
    )
    parser.set_defaults(func=_run_agent_demo)


def _register_preview_demo(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "preview-demo",
        description="Execute the parsing preview mission to capture a Markdown excerpt without front matter.",
        help="Run the parsing preview mission.",
    )
    parser.add_argument(
        "--parse-root",
        type=Path,
        default=Path("evidence"),
        help="Directory to scan when locating candidate documents (default: evidence).",
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        help="Explicit document path to preview. When omitted, the command scans --parse-root and selects a candidate.",
    )
    parser.add_argument(
        "--suffix",
        dest="suffixes",
        action="append",
        default=[],
        help="File suffix filter applied during auto-selection (repeatable).",
    )
    parser.add_argument(
        "--include",
        dest="include",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern relative to --parse-root that candidates must match (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        dest="exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern relative to --parse-root that excludes candidates (repeatable).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidates to consider during auto-selection.",
    )
    parser.add_argument(
        "--selection",
        type=int,
        default=1,
        help="1-based index of the candidate to preview after scanning (default: 1).",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Recursively scan subdirectories when auto-selecting (default: true).",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        help="Path to a deterministic plan definition (default: devops/projects/kb-source-preview.plan.yaml).",
    )
    parser.add_argument(
        "--mission",
        type=Path,
        help="Mission specification override (default: config/missions/kb_source_preview.yaml).",
    )
    parser.add_argument(
        "--expected-parser",
        help="Optional parser name forwarded to the preview context.",
    )
    parser.add_argument(
        "--max-preview-chars",
        type=int,
        help="Override maximum characters captured in preview context (requires plan support).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the mission outcome as JSON.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Skip writing a transcript file for this run.",
    )
    parser.add_argument(
        "--transcript-path",
        type=Path,
        help="Explicit path for the transcript JSON output.",
    )
    parser.add_argument(
        "--transcript-dir",
        type=Path,
        default=Path("reports/transcripts"),
        help="Directory used when deriving the transcript filename (default: reports/transcripts).",
    )
    parser.set_defaults(func=_run_preview_demo)





def _run_mcp_serve(args: argparse.Namespace) -> int:
    argv: list[str] = []
    if args.list_tools:
        argv.append("--list-tools")
    return run_mcp_server(argv)


def _run_agent_demo(args: argparse.Namespace) -> int:
    try:
        repository = resolve_repository(args.repo)
        token = resolve_token(args.token)
    except GitHubIssueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        context_inputs = _build_demo_context(args, repository, token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    plan_steps = None
    default_finish = args.default_finish

    if args.plan is not None:
        try:
            plan = load_deterministic_plan(args.plan, variables=context_inputs)
        except PlanConfigError as exc:
            print(f"Plan error: {exc}", file=sys.stderr)
            return 1
        plan_steps = plan.steps
        if default_finish is None:
            default_finish = plan.default_finish

    issue_value = context_inputs.get("issue_number", args.issue)
    try:
        issue_number = _coerce_issue_number(issue_value)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    context_inputs["issue_number"] = issue_number

    interactive = bool(getattr(args, "interactive", False))

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=issue_number,
        repository=repository,
        token=token,
        plan_override=plan_steps,
        default_finish=default_finish,
        context_inputs=context_inputs,
        triage_mode=args.triage,
        interactive=interactive,
    )

    transcript_path: Path | None = None
    if not args.no_transcript:
        transcript_payload = _build_transcript_payload(
            outcome=outcome,
            summary=summary,
            recommendation=recommendation,
            context=context_inputs,
            issue_number=issue_number,
            repository=repository,
            plan_path=args.plan,
            default_finish=default_finish,
            plan_steps=plan_steps,
        )
        transcript_path = _write_transcript(
            payload=transcript_payload,
            explicit_path=args.transcript_path,
            directory=args.transcript_dir,
            issue_number=issue_number,
        )

    if args.json:
        payload = _build_demo_payload(outcome, summary, recommendation, transcript_path)
        print(_safe_json_dump(payload))
    else:
        _print_demo_outcome(outcome, summary, recommendation, transcript_path)

    return 0 if outcome.status is MissionStatus.SUCCEEDED else 1


def _run_preview_demo(args: argparse.Namespace) -> int:
    parse_root = args.parse_root.expanduser().resolve()

    context_inputs: dict[str, object] = {}
    if args.expected_parser:
        context_inputs["expected_parser"] = args.expected_parser
    if args.max_preview_chars is not None:
        if args.max_preview_chars <= 0:
            print("error: --max-preview-chars must be a positive integer.", file=sys.stderr)
            return 1
        context_inputs["max_preview_chars"] = int(args.max_preview_chars)

    candidate_snapshot: tuple[str, ...] = tuple()
    if args.source_path is not None:
        source_candidate = args.source_path.expanduser().resolve()
    else:
        suffixes = tuple(args.suffixes) if args.suffixes else None
        include_patterns = tuple(args.include) if args.include else None
        exclude_patterns = tuple(args.exclude) if args.exclude else None
        recursive = True if args.recursive is None else bool(args.recursive)
        try:
            candidates = collect_parse_candidates(
                parse_root,
                suffixes=suffixes,
                recursive=recursive,
                storage_root=None,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if args.limit is not None and args.limit >= 0:
            candidates = candidates[: args.limit]
        if not candidates:
            print(f"No documents found under {parse_root} matching the requested filters.", file=sys.stderr)
            return 1
        selection_index = args.selection - 1
        if selection_index < 0 or selection_index >= len(candidates):
            print(
                f"Selection index {args.selection} is out of range for {len(candidates)} candidates.",
                file=sys.stderr,
            )
            return 1
        source_candidate = candidates[selection_index].resolve()
        candidate_snapshot = tuple(str(path) for path in candidates)
        if candidate_snapshot:
            context_inputs.setdefault("preview_candidates", candidate_snapshot)

    plan_path = args.plan.expanduser().resolve() if args.plan else _DEFAULT_PREVIEW_PLAN_PATH
    mission_path = args.mission.expanduser().resolve() if args.mission else _DEFAULT_PREVIEW_MISSION_PATH

    try:
        outcome, preview_payload, candidates_result, mission, plan, context_mapping = run_parsing_preview_demo(
            parse_root=parse_root,
            source_path=source_candidate,
            plan_path=plan_path if args.plan else None,
            mission_path=mission_path if args.mission else None,
            context_inputs=context_inputs,
        )
    except PlanConfigError as exc:
        print(f"Plan error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    candidates = candidates_result if candidates_result else candidate_snapshot

    transcript_path: Path | None = None
    transcript_dir = args.transcript_dir.expanduser()
    explicit_transcript = args.transcript_path.expanduser() if args.transcript_path else None

    if not args.no_transcript:
        transcript_payload = _build_preview_transcript_payload(
            outcome=outcome,
            preview_payload=preview_payload,
            candidates=candidates,
            context=context_mapping,
            mission=mission,
            plan=plan,
            plan_path=plan_path,
            parse_root=parse_root,
            source_path=source_candidate,
        )
        try:
            transcript_path = _write_preview_transcript(
                payload=transcript_payload,
                explicit_path=explicit_transcript,
                directory=transcript_dir,
            )
        except OSError as exc:
            print(f"error: failed to write transcript: {exc}", file=sys.stderr)
            return 1

    if args.json:
        payload = _build_preview_payload(
            outcome,
            preview_payload,
            candidates,
            transcript_path,
            plan_path,
            parse_root,
            source_candidate,
        )
        print(_safe_json_dump(payload))
    else:
        _print_preview_outcome(outcome, preview_payload, candidates, transcript_path)

    return 0 if outcome.status is MissionStatus.SUCCEEDED else 1


def _build_demo_context(
    args: argparse.Namespace,
    repository: str,
    token: str,
) -> dict[str, object]:
    context: dict[str, object] = {}
    if args.context is not None:
        loaded = _load_context_file(args.context)
        context.update(loaded)

    for raw_param in args.params:
        key, value = _parse_context_override(raw_param)
        context[key] = value

    context.setdefault("issue_number", args.issue)
    context.setdefault("repository", repository)
    context.setdefault("token", token)
    context.setdefault("triage_mode", args.triage)
    return context


def _load_context_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read context file: {path}") from exc

    suffix = path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw) or {}
        else:
            data = json.loads(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Context file '{path}' contains invalid syntax.") from exc

    if not isinstance(data, Mapping):
        raise ValueError("Context file must contain a JSON/YAML object at the top level.")
    return dict(data)


def _parse_context_override(raw: str) -> tuple[str, object]:
    if "=" not in raw:
        raise ValueError(f"Invalid context override '{raw}'. Expected KEY=VALUE format.")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("Context override key cannot be empty.")
    return key, _coerce_param_value(value.strip())


def _coerce_param_value(raw: str) -> object:
    lowered = raw.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def _coerce_issue_number(value: object) -> int:
    if value is None:
        raise ValueError("Context value 'issue_number' cannot be null.")
    if isinstance(value, bool):
        raise ValueError("Context value 'issue_number' cannot be boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Context value 'issue_number' must be a whole number.")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Context value 'issue_number' cannot be empty.")
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError("Context value 'issue_number' must be an integer.") from exc
    raise ValueError(f"Unsupported type for context value 'issue_number': {type(value).__name__}.")


def _build_demo_payload(outcome, summary, recommendation, transcript_path: Path | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": outcome.status.value,
        "summary": outcome.summary,
        "steps": _serialize_steps(outcome.steps),
    }
    if summary is not None:
        payload["issue_summary"] = summary.as_text()
    if recommendation is not None:
        payload["recommendation"] = {
            "classification": recommendation.classification,
            "rationale": recommendation.rationale,
            "suggested_labels": list(recommendation.suggested_labels),
        }
    if transcript_path is not None:
        payload["transcript_path"] = str(transcript_path)
    return payload


def _print_demo_outcome(outcome, summary, recommendation, transcript_path: Path | None) -> None:
    print(f"Mission status: {outcome.status.value}")
    if outcome.summary:
        print(f"Summary: {outcome.summary}")

    validation_errors: list[dict[str, object]] = []
    for index, step in enumerate(outcome.steps, start=1):
        tool_name = step.thought.tool_call.name if step.thought.tool_call else "finish"
        result = step.result
        state = "ok" if result and result.success else "error"
        print(f"  {index}. {tool_name} -> {state}")
        if result and result.error:
            print(f"     error: {result.error}")
            if _is_validation_error(result.error):
                validation_errors.append(
                    {
                        "index": index,
                        "tool": tool_name,
                        "message": result.error,
                    }
                )

    if summary is not None:
        print(f"Issue summary: {summary.as_text()}")
    if recommendation is not None:
        print(f"Recommendation: {recommendation.classification} — {recommendation.rationale}")
        if recommendation.suggested_labels:
            labels = ", ".join(recommendation.suggested_labels)
            print(f"Suggested labels: {labels}")
    if validation_errors:
        print("Validation errors recorded in transcript; review 'validation_errors' for remediation guidance.")
    if transcript_path is not None:
        print(f"Transcript written to {transcript_path}")


def _build_transcript_payload(
    *,
    outcome,
    summary,
    recommendation,
    context: Mapping[str, object],
    issue_number: int,
    repository: str,
    plan_path: Path | None,
    default_finish: str | None,
    plan_steps: Sequence | None,
) -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    sanitized_context = _sanitize_context(context)
    serialized_steps = _serialize_steps(outcome.steps)
    step_errors = _collect_step_errors(outcome.steps)
    validation_errors = [
        error for error in step_errors if _is_validation_error(cast(str | None, error.get("message")))
    ]

    transcript: dict[str, object] = {
        "timestamp": timestamp,
        "mission": {
            "status": outcome.status.value,
            "summary": outcome.summary,
        },
        "issue": {
            "number": issue_number,
            "repository": repository,
        },
        "plan": {
            "path": str(plan_path) if plan_path else None,
            "default_finish": default_finish,
            "steps_configured": len(plan_steps) if plan_steps is not None else None,
        },
        "context": sanitized_context,
        "steps": serialized_steps,
    }
    if step_errors:
        transcript["errors"] = step_errors
    if validation_errors:
        transcript["validation_errors"] = validation_errors
    if summary is not None:
        transcript["issue_summary"] = {
            "text": summary.as_text(),
            "number": summary.number,
            "state": summary.state,
            "labels": list(summary.labels),
            "url": summary.url,
            "title": summary.title,
        }
    if recommendation is not None:
        transcript["recommendation"] = {
            "classification": recommendation.classification,
            "rationale": recommendation.rationale,
            "suggested_labels": list(recommendation.suggested_labels),
        }
    return transcript


def _build_preview_payload(
    outcome,
    preview_payload: Mapping[str, object] | None,
    candidates: tuple[str, ...],
    transcript_path: Path | None,
    plan_path: Path,
    parse_root: Path,
    source_path: Path,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": outcome.status.value,
        "summary": outcome.summary,
        "steps": _serialize_steps(outcome.steps),
        "plan_path": str(plan_path),
        "parse_root": str(parse_root),
        "source_path": str(source_path),
    }
    if preview_payload is not None:
        payload["preview"] = dict(preview_payload)
    if candidates:
        payload["candidates"] = list(candidates)
    if transcript_path is not None:
        payload["transcript_path"] = str(transcript_path)
    return payload


def _print_preview_outcome(
    outcome,
    preview_payload: Mapping[str, object] | None,
    candidates: tuple[str, ...],
    transcript_path: Path | None,
) -> None:
    print(f"Mission status: {outcome.status.value}")
    if outcome.summary:
        print(f"Summary: {outcome.summary}")

    validation_errors: list[dict[str, object]] = []
    for index, step in enumerate(outcome.steps, start=1):
        tool_name = step.thought.tool_call.name if step.thought.tool_call else "finish"
        result = step.result
        state = "ok" if result and result.success else "error"
        print(f"  {index}. {tool_name} -> {state}")
        if result and result.error:
            print(f"     error: {result.error}")
            if _is_validation_error(result.error):
                validation_errors.append(
                    {
                        "index": index,
                        "tool": tool_name,
                        "message": result.error,
                    }
                )

    if preview_payload is not None:
        preview_block = preview_payload.get("preview")
        if isinstance(preview_block, Mapping):
            rel_path = preview_block.get("relative_path") or "unknown"
            truncated = bool(preview_block.get("truncated"))
            print(f"Preview artifact: {rel_path} (truncated={truncated})")
    if candidates:
        print("Candidates:")
        display = candidates[:5]
        for item in display:
            print(f"  - {item}")
        remaining = len(candidates) - len(display)
        if remaining > 0:
            print(f"  ... ({remaining} more)")
    if validation_errors:
        print("Validation errors recorded in transcript; review 'validation_errors'.")
    if transcript_path is not None:
        print(f"Transcript written to {transcript_path}")


def _build_preview_transcript_payload(
    *,
    outcome,
    preview_payload: Mapping[str, object] | None,
    candidates: tuple[str, ...],
    context: Mapping[str, Any],
    mission,
    plan,
    plan_path: Path,
    parse_root: Path,
    source_path: Path,
) -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).isoformat()
    sanitized_context = _sanitize_context(context)
    serialized_steps = _serialize_steps(outcome.steps)
    step_errors = _collect_step_errors(outcome.steps)
    validation_errors = [
        error
        for error in step_errors
        if _is_validation_error(cast(str | None, error.get("message")))
    ]

    payload: dict[str, object] = {
        "timestamp": timestamp,
        "mission": {
            "id": mission.id,
            "status": outcome.status.value,
            "summary": outcome.summary,
            "max_steps": mission.max_steps,
        },
        "plan": {
            "path": str(plan_path),
            "default_finish": plan.default_finish,
            "steps_configured": len(plan.steps),
        },
        "inputs": {
            "parse_root": str(parse_root),
            "source_path": str(source_path),
        },
        "context": sanitized_context,
        "steps": serialized_steps,
    }
    if step_errors:
        payload["errors"] = step_errors
    if validation_errors:
        payload["validation_errors"] = validation_errors
    if preview_payload is not None:
        payload["preview"] = dict(preview_payload)
    if candidates:
        payload["candidates"] = list(candidates)
    return payload


def _write_preview_transcript(
    *,
    payload: Mapping[str, object],
    explicit_path: Path | None,
    directory: Path,
) -> Path:
    target_dir = directory.expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = explicit_path.expanduser() if explicit_path is not None else _derive_preview_transcript_path(target_dir)
    if path.is_dir():
        raise OSError(f"Transcript path '{path}' is a directory, expected a file path.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_safe_json_dump(payload), encoding="utf-8")
    return path


def _derive_preview_transcript_path(directory: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"preview-demo-{timestamp}.json"
    return directory / filename


def _sanitize_context(context: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in context.items():
        if key.lower() in {"token", "auth_token", "authorization"}:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def _serialize_steps(steps) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for index, step in enumerate(steps, start=1):
        tool_call = step.thought.tool_call
        tool_args = _sanitize_arguments(tool_call.arguments) if tool_call is not None else None
        result = step.result
        serialized.append(
            {
                "index": index,
                "thought": step.thought.content,
                "type": step.thought.type.value,
                "tool": tool_call.name if tool_call else None,
                "arguments": tool_args,
                "result": {
                    "success": result.success if result is not None else None,
                    "error": result.error if result is not None else None,
                    "output": result.output if result is not None else None,
                },
            }
        )
    return serialized


def _collect_step_errors(steps) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for index, step in enumerate(steps, start=1):
        result = step.result
        if result is None or result.success or not result.error:
            continue
        tool_call = step.thought.tool_call
        errors.append(
            {
                "index": index,
                "tool": tool_call.name if tool_call else None,
                "message": result.error,
            }
        )
    return errors


def _is_validation_error(message: str | None) -> bool:
    if not message:
        return False
    return message.startswith("Argument validation failed")


def _write_transcript(
    *,
    payload: Mapping[str, object],
    explicit_path: Path | None,
    directory: Path,
    issue_number: int,
) -> Path:
    path = explicit_path or _derive_transcript_path(directory, issue_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_safe_json_dump(payload), encoding="utf-8")
    return path


def _derive_transcript_path(directory: Path, issue_number: int) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"agent-demo-{issue_number}-{timestamp}.json"
    return directory / filename


def _safe_json_dump(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, indent=2, default=_json_fallback)


def _json_fallback(value):  # type: ignore[override]
    return repr(value)


def _sanitize_arguments(arguments: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in arguments.items():
        if key.lower() in {"token", "auth_token", "authorization"}:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


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
