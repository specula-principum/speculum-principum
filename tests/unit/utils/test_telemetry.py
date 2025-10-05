"""Unit tests for telemetry utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.telemetry import (
    create_jsonl_publisher,
    prepare_cli_telemetry_publishers,
    publish_telemetry_event,
)


def test_create_jsonl_publisher_writes_event(tmp_path: Path) -> None:
    """JSONL publisher should append serialized telemetry events."""

    output_path = tmp_path / "telemetry" / "events.jsonl"
    publisher = create_jsonl_publisher(output_path)

    publish_telemetry_event([publisher], "unit.test", {"value": 42})

    contents = output_path.read_text(encoding="utf-8").strip()
    assert contents, "Telemetry file should contain at least one event"
    event = json.loads(contents)
    assert event["event_type"] == "unit.test"
    assert event["value"] == 42
    assert "timestamp" in event


def test_prepare_cli_telemetry_publishers_honors_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """prepare_cli_telemetry_publishers respects explicit environment overrides."""

    explicit_path = tmp_path / "artifacts" / "custom.jsonl"
    monkeypatch.setenv("SPECULUM_CLI_TELEMETRY_PATH", str(explicit_path))

    publishers, path, session_id = prepare_cli_telemetry_publishers(
        "process-issues",
        extra_static_fields={"dry_run": True},
    )

    assert path == explicit_path
    assert session_id

    publish_telemetry_event(publishers, "unit.test", {"status": "ok"})

    payloads = [json.loads(line) for line in explicit_path.read_text(encoding="utf-8").splitlines()]
    assert payloads, "Expected telemetry event to be written"

    event = payloads[-1]
    assert event["cli_command"] == "process-issues"
    assert event["cli_session_id"] == session_id
    assert event["dry_run"] is True
    assert event["status"] == "ok"

    monkeypatch.delenv("SPECULUM_CLI_TELEMETRY_PATH")
