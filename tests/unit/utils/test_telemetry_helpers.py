"""Tests for telemetry helper utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.utils.cli_helpers import CliResult
from src.utils.telemetry_helpers import (
    attach_cli_static_fields,
    emit_cli_summary,
    setup_cli_publishers,
)


def test_setup_cli_publishers_attaches_static_fields() -> None:
    base_publishers = [MagicMock()]

    with patch(
        "src.utils.telemetry_helpers.prepare_cli_telemetry_publishers",
        return_value=(base_publishers, "path", "session"),
    ) as mock_prepare, patch(
        "src.utils.telemetry_helpers.attach_static_fields",
        return_value=["decorated"],
    ) as mock_attach:
        publishers = setup_cli_publishers(
            "monitor",
            extra_static_fields={"dry_run": True},
            static_fields={"workflow_stage": "monitoring"},
        )

    assert publishers == ["decorated"]
    mock_prepare.assert_called_once_with("monitor", extra_static_fields={"dry_run": True})
    mock_attach.assert_called_once()
    assert mock_attach.call_args[0][0] is base_publishers
    assert mock_attach.call_args[0][1] == {"workflow_stage": "monitoring"}


def test_attach_cli_static_fields_passthrough() -> None:
    publishers = [MagicMock()]
    assert attach_cli_static_fields(publishers) is publishers


def test_emit_cli_summary_builds_payload() -> None:
    publishers = [MagicMock()]
    result = CliResult(
        success=False,
        message="Failure occurred while processing items",
        data={"count": 3},
        error_code=2,
    )

    with patch("src.utils.telemetry_helpers.publish_telemetry_event") as mock_publish:
        returned = emit_cli_summary(
            publishers,
            "test.event",
            result,
            phase="testing",
            extra={"extra_field": "value"},
        )

    assert returned is result
    mock_publish.assert_called_once()
    args = mock_publish.call_args[0]
    assert args[0] is publishers
    assert args[1] == "test.event"
    payload = args[2]
    assert payload["success"] is False
    assert payload["error_code"] == 2
    assert payload["data"] == {"count": 3}
    assert payload["phase"] == "testing"
    assert payload["extra_field"] == "value"
    assert payload["message_preview"].startswith("Failure occurred")
    assert len(payload["message_preview"]) <= 240
