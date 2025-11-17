"""Extraction CLI commands for running structured extractors."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from src.extraction.cli import available_extractors, run_extractor
from src.extraction.config import (
    load_default_or_empty,
    load_extraction_config,
    validate_requested_extractors,
)

__all__ = ["register_commands", "build_parser"]


# Named collections of extractors that mirror common benchmarking workflows.
_BENCHMARK_PROFILES: dict[str, tuple[str, ...]] = {
    "governance-default": ("entities", "relationships", "metadata", "summarization"),
    "governance-full": (
        "entities",
        "relationships",
        "metadata",
        "summarization",
        "taxonomy",
        "linking",
    ),
}


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add extraction-related commands to the main CLI parser."""

    register_extract_command(subparsers)
    register_benchmark_command(subparsers)


def register_extract_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "extract",
        description="Execute text extraction modules on parsed documents.",
        help="Run extraction modules.",
    )
    _configure_parser(parser)
    return parser


def register_benchmark_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "extract-benchmark",
        description="Benchmark extraction modules over one input document.",
        help="Benchmark extraction performance.",
    )
    _configure_benchmark_parser(parser)
    return parser


def build_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute text extraction modules on parsed documents.",
        prog=prog,
    )
    _configure_parser(parser)
    return parser


def _configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "extractor",
        choices=available_extractors(),
        help="Name of the extraction module to invoke.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the parsed document or directory to process.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/extraction.yaml"),
        help="Path to an extraction YAML config (default: config/extraction.yaml).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for extracted data (default: stdout).",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "yaml", "text"),
        default="json",
        help="Output serialization format.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing the extractor.",
    )
    parser.set_defaults(func=extract_cli)


def _configure_benchmark_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "extractors",
        nargs="*",
        help="Optional list of extraction modules to benchmark (default: all).",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(sorted(_BENCHMARK_PROFILES)),
        help="Predefined extractor set to benchmark (e.g., governance-full).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the parsed document used for benchmarking.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of times to run each extractor (default: 3).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/extraction.yaml"),
        help="Path to an extraction YAML config (default: config/extraction.yaml).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for benchmark results (default: stdout).",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "yaml"),
        default="json",
        help="Output serialization format.",
    )
    parser.set_defaults(func=extract_benchmark_cli)


def extract_cli(args: argparse.Namespace) -> int:
    if args.dry_run:
        print(
            f"Dry run: extractor '{args.extractor}' configured with input {args.input}.",
        )
        return 0

    try:
        text = _read_input_text(Path(args.input))
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        config = _load_config(args.config)
    except (ValueError, ImportError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    extractor_config = dict(config.get(args.extractor, {})) if isinstance(config, dict) else {}
    extractor_config.setdefault("source_path", str(args.input))

    try:
        result = run_extractor(args.extractor, text=text, config=extractor_config)
    except NotImplementedError:
        print(
            f"Extractor '{args.extractor}' is not implemented yet."
            " Please track progress in devops/projects/phase-1-extraction-tooling/PROGRESS.md.",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        payload = _serialize_result(result)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_data = _format_payload(payload, args.output_format)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_data, encoding="utf-8")
        print(f"Extraction result written to {output_path}")
    else:
        end = "" if output_data.endswith("\n") else "\n"
        sys.stdout.write(output_data + end)
    return 0


def extract_benchmark_cli(args: argparse.Namespace) -> int:
    try:
        text = _read_input_text(Path(args.input))
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.iterations <= 0:
        print("error: iterations must be a positive integer", file=sys.stderr)
        return 1

    try:
        config = _load_config(args.config)
    except (ValueError, ImportError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        selected_extractors = _resolve_benchmark_extractors(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        validate_requested_extractors(selected_extractors)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary: dict[str, Any] = {}
    for extractor in selected_extractors:
        extractor_config = dict(config.get(extractor, {})) if isinstance(config, dict) else {}
        extractor_config.setdefault("source_path", str(args.input))

        durations: list[float] = []
        for _ in range(args.iterations):
            start = time.perf_counter()
            run_extractor(extractor, text=text, config=extractor_config)
            durations.append(time.perf_counter() - start)

        summary[extractor] = _summarize_durations(durations)

    payload = {
        "input": str(args.input),
        "iterations": args.iterations,
        "extractors": tuple(selected_extractors),
        "metrics": summary,
    }

    try:
        output_data = _dump_output(payload, args.output_format)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_data, encoding="utf-8")
        print(f"Benchmark results written to {output_path}")
    else:
        end = "" if output_data.endswith("\n") else "\n"
        sys.stdout.write(output_data + end)
    return 0


def _resolve_benchmark_extractors(args: argparse.Namespace) -> list[str]:
    explicit = list(args.extractors) if getattr(args, "extractors", None) else None
    profile = getattr(args, "profile", None)

    if profile and explicit:
        raise ValueError("--profile cannot be combined with explicit extractor names.")

    if profile:
        return list(_BENCHMARK_PROFILES[profile])

    if explicit is not None and explicit:
        return explicit

    return list(available_extractors())


def _summarize_durations(durations: list[float]) -> dict[str, float | int]:
    if not durations:
        return {
            "iterations": 0,
            "total_seconds": 0.0,
            "mean_seconds": 0.0,
            "median_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
        }

    total = sum(durations)
    mean = total / len(durations)
    median = statistics.median(durations)
    best = min(durations)
    worst = max(durations)

    return {
        "iterations": len(durations),
        "total_seconds": round(total, 6),
        "mean_seconds": round(mean, 6),
        "median_seconds": round(median, 6),
        "min_seconds": round(best, 6),
        "max_seconds": round(worst, 6),
    }


def _dump_output(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "yaml":
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - dependency should exist, guard anyway
            raise ValueError("yaml output requires PyYAML to be installed") from exc
        return yaml.safe_dump(payload, sort_keys=False)
    raise ValueError(f"Unsupported output format: {output_format}")


def _load_config(path: Path) -> dict[str, Any]:
    if path == Path("config/extraction.yaml"):
        config = load_default_or_empty()
        return dict(config.raw)

    resolved = Path(path).expanduser()
    if not resolved.exists():
        return {}

    config = load_extraction_config(resolved)
    return dict(config.raw)


def _read_input_text(path: Path) -> str:
    resolved = path.expanduser()
    if resolved.is_file():
        return resolved.read_text(encoding="utf-8")
    if resolved.is_dir():
        files = _iter_text_files(resolved)
        contents: list[str] = []
        for file_path in files:
            try:
                contents.append(file_path.read_text(encoding="utf-8"))
            except UnicodeDecodeError as exc:  # pragma: no cover - dependent on workspace encoding
                raise UnicodeDecodeError(
                    exc.encoding,
                    exc.object,
                    exc.start,
                    exc.end,
                    f"{exc.reason} while reading '{file_path}'",
                ) from exc
        if not contents:
            raise FileNotFoundError(f"No readable text files found under '{resolved}'")
        return "\n\n".join(contents)
    raise FileNotFoundError(f"Input path '{resolved}' does not exist")


def _iter_text_files(root: Path) -> list[Path]:
    candidates = sorted(p for p in root.rglob("*") if p.is_file())
    text_like: list[Path] = []
    for candidate in candidates:
        if candidate.suffix.lower() in {".txt", ".md", ".markdown", ".rst"}:
            text_like.append(candidate)
        elif candidate.suffix == "":
            text_like.append(candidate)
    return text_like


def _serialize_result(result: Any) -> dict[str, Any]:
    if not hasattr(result, "extractor_name"):
        raise ValueError("Extractor did not return an ExtractionResult instance.")

    def convert(value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        if isinstance(value, tuple):
            return [convert(item) for item in value]
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {key: convert(val) for key, val in value.items()}
        return value

    created_at = getattr(result, "created_at", None)
    if hasattr(created_at, "isoformat"):
        created_at_value: Any = created_at.isoformat()  # type: ignore[union-attr]
    elif created_at is not None:
        created_at_value = str(created_at)
    else:
        created_at_value = None

    payload = {
        "source_path": getattr(result, "source_path", ""),
        "checksum": getattr(result, "checksum", ""),
        "extractor_name": getattr(result, "extractor_name", ""),
        "data": convert(getattr(result, "data", {})),
        "metadata": convert(getattr(result, "metadata", {})),
        "created_at": created_at_value,
    }
    return payload


def _format_payload(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "yaml":
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - dependency should exist, but guard anyway
            raise ValueError("yaml output requires PyYAML to be installed") from exc
        return yaml.safe_dump(payload, sort_keys=False)
    if output_format == "text":
        from pprint import pformat

        return pformat(payload)
    raise ValueError(f"Unsupported output format: {output_format}")
