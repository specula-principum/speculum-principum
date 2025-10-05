"""Utility helpers for emitting workflow telemetry events.

This module provides lightweight helpers for publishing structured
telemetry events to arbitrary sinks (logging, JSONL files, metrics
bridges, etc.). Callers supply callables that accept a dictionary
payload; the helper normalizes the event shape and guards against
publisher failures so telemetry never blocks the primary workflow.

The module also includes convenience utilities for CLI instrumentation,
including JSONL publishers and helpers that attach consistent metadata
for automation and observability pipelines.
"""

from __future__ import annotations

import logging
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, Any, Optional, Union
from uuid import uuid4

TelemetryPublisher = Callable[[Dict[str, Any]], None]

CLI_TELEMETRY_PATH_ENV = "SPECULUM_CLI_TELEMETRY_PATH"
CLI_TELEMETRY_DIR_ENV = "SPECULUM_CLI_TELEMETRY_DIR"
CLI_ARTIFACTS_DIR_ENV = "SPECULUM_ARTIFACTS_DIR"
DEFAULT_CLI_TELEMETRY_DIR = Path("artifacts/telemetry")


def publish_telemetry_event(
    publishers: Iterable[TelemetryPublisher],
    event_type: str,
    payload: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
) -> None:
    """Publish a telemetry event to all configured publishers.

    Args:
        publishers: Iterable of callables that accept a telemetry payload.
        event_type: Logical identifier describing the event.
        payload: Event-specific data to include in the emission.
        logger: Optional logger for warning when a publisher fails.
    """
    if not publishers:
        return

    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }

    for publisher in publishers:
        try:
            publisher(event)
        except Exception as exc:  # pylint: disable=broad-except  # pragma: no cover - defensive guard
            if logger:
                logger.warning("Telemetry publisher failed for %s: %s", event_type, exc)


def normalize_publishers(
    publishers: Optional[Iterable[TelemetryPublisher]]
) -> list[TelemetryPublisher]:
    """Return publishers as a concrete list for repeated dispatch."""
    if not publishers:
        return []
    return list(publishers)


def create_jsonl_publisher(
    output_path: Union[str, Path],
    *,
    ensure_directory: bool = True,
) -> TelemetryPublisher:
    """Create a telemetry publisher that appends JSON lines to ``output_path``.

    Args:
        output_path: Destination file for telemetry events.
        ensure_directory: When True, create the parent directory automatically.

    Returns:
        A callable that writes telemetry dictionaries as JSON lines.
    """

    path = Path(output_path)
    if ensure_directory:
        path.parent.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()

    def _publisher(event: Dict[str, Any]) -> None:
        serialized = json.dumps(event, separators=(",", ":"), sort_keys=True)
        with lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.write("\n")

    return _publisher


def _with_static_fields(
    publisher: TelemetryPublisher,
    static_fields: Dict[str, Any],
) -> TelemetryPublisher:
    """Wrap ``publisher`` to include ``static_fields`` with every event."""

    def _wrapped(event: Dict[str, Any]) -> None:
        enriched = {**event, **static_fields}
        publisher(enriched)

    return _wrapped


def attach_static_fields(
    publishers: Iterable[TelemetryPublisher],
    static_fields: Dict[str, Any],
) -> list[TelemetryPublisher]:
    """Return publishers that automatically include ``static_fields``.

    Args:
        publishers: Existing telemetry publishers to wrap.
        static_fields: Additional metadata to merge into each event.

    Returns:
        A new list of publishers that enrich every emitted event with
        the provided static fields.
    """

    if not publishers:
        return []

    return [_with_static_fields(publisher, static_fields) for publisher in publishers]


def _resolve_cli_telemetry_path(command_name: str) -> Path:
    """Determine the JSONL path for CLI telemetry events."""

    explicit_path = os.getenv(CLI_TELEMETRY_PATH_ENV)
    if explicit_path:
        return Path(explicit_path)

    base_dir_value = (
        os.getenv(CLI_TELEMETRY_DIR_ENV)
        or os.getenv(CLI_ARTIFACTS_DIR_ENV)
    )
    base_dir = Path(base_dir_value) if base_dir_value else DEFAULT_CLI_TELEMETRY_DIR

    filename = f"{command_name}.jsonl"
    return base_dir / filename


def prepare_cli_telemetry_publishers(
    command_name: str,
    *,
    output_path: Optional[Union[str, Path]] = None,
    extra_static_fields: Optional[Dict[str, Any]] = None,
) -> tuple[list[TelemetryPublisher], Path, str]:
    """Configure telemetry publishers for a CLI invocation.

    Args:
        command_name: The CLI command being executed (e.g., ``process-issues``).
        output_path: Optional override for the JSONL file location.
        extra_static_fields: Additional metadata to append to every event.

    Returns:
        A tuple of (publishers, path, cli_session_id).
    """

    command_slug = command_name.replace("/", "-")
    path = Path(output_path) if output_path else _resolve_cli_telemetry_path(command_slug)
    session_id = uuid4().hex

    static_fields: Dict[str, Any] = {
        "cli_command": command_name,
        "cli_session_id": session_id,
    }
    if extra_static_fields:
        static_fields.update(extra_static_fields)

    publisher = create_jsonl_publisher(path)
    wrapped_publisher = _with_static_fields(publisher, static_fields)
    return [wrapped_publisher], path, session_id
