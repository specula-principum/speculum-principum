"""Utility helpers for consistent CLI telemetry behavior."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from src.utils.cli_helpers import CliResult
from src.utils.telemetry import (
    attach_static_fields,
    prepare_cli_telemetry_publishers,
    publish_telemetry_event,
)


def setup_cli_publishers(
    command_name: str,
    *,
    extra_static_fields: Optional[Mapping[str, Any]] = None,
    static_fields: Optional[Mapping[str, Any]] = None,
) -> Iterable:
    """Return telemetry publishers configured for a CLI command."""

    publishers, _, _ = prepare_cli_telemetry_publishers(
        command_name,
        extra_static_fields=dict(extra_static_fields or {}),
    )

    if static_fields:
        publishers = attach_static_fields(publishers, dict(static_fields))

    return publishers


def attach_cli_static_fields(publishers: Iterable, **static_fields: Any) -> Iterable:
    """Attach static fields to publishers if provided."""
    if not static_fields:
        return publishers
    return attach_static_fields(publishers, static_fields)


def emit_cli_summary(
    publishers: Iterable,
    event_name: str,
    result: CliResult,
    *,
    phase: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> CliResult:
    """Publish a standardized CLI summary telemetry event."""
    payload: Dict[str, Any] = {
        "success": result.success,
    }

    if result.error_code:
        payload["error_code"] = result.error_code

    if result.message:
        payload["message_preview"] = result.message[:240]

    if result.data is not None:
        payload["data"] = result.data

    if phase:
        payload["phase"] = phase

    if extra:
        payload.update(extra)

    publish_telemetry_event(publishers, event_name, payload)
    return result
