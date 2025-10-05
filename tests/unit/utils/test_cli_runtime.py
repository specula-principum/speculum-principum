"""Tests for runtime validation helper utilities."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from src.utils.cli_helpers import CliResult
from src.utils.cli_runtime import ensure_runtime_ready


def _success_result() -> CliResult:
    return CliResult(success=True, message="ok")


def test_ensure_runtime_ready_success_emits_telemetry() -> None:
    config_obj = object()
    telemetry_stub = MagicMock()

    with patch("src.utils.cli_runtime.ConfigValidator.validate_config_file", return_value=_success_result()) as mock_config, \
        patch("src.utils.cli_runtime.ConfigValidator.validate_environment", return_value=_success_result()) as mock_env, \
        patch("src.utils.cli_runtime.ConfigManager.load_config_with_env_substitution", return_value=config_obj) as mock_loader, \
        patch("src.utils.cli_runtime.publish_telemetry_event") as mock_publish, \
        patch.dict(os.environ, {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "owner/repo"}, clear=True):

        result = ensure_runtime_ready(
            "config.yaml",
            telemetry_publishers=[telemetry_stub],
            telemetry_event="test.event",
        )

    assert result.success
    assert result.data is not None
    assert result.data["config"] is config_obj
    assert result.data["environment"] == {"github_token": "tok", "repo_name": "owner/repo"}

    mock_config.assert_called_once_with("config.yaml")
    mock_env.assert_called_once_with()
    mock_loader.assert_called_once_with("config.yaml")

    mock_publish.assert_called_once()
    last_call = mock_publish.call_args_list[-1]
    assert last_call[0][1] == "test.event"
    assert last_call[0][2]["stage"] == "ready"


def test_ensure_runtime_ready_returns_config_validation_error() -> None:
    failure = CliResult(success=False, message="bad config", error_code=1)

    with patch("src.utils.cli_runtime.ConfigValidator.validate_config_file", return_value=failure) as mock_config, \
        patch("src.utils.cli_runtime.ConfigValidator.validate_environment") as mock_env, \
        patch("src.utils.cli_runtime.publish_telemetry_event") as mock_publish:

        result = ensure_runtime_ready("config.yaml", telemetry_publishers=[MagicMock()])

    assert result is failure
    mock_config.assert_called_once_with("config.yaml")
    mock_env.assert_not_called()
    mock_publish.assert_called_once()
    assert mock_publish.call_args[0][2]["stage"] == "config_validation"
    assert not mock_publish.call_args[0][2]["success"]


def test_ensure_runtime_ready_returns_environment_error() -> None:
    success = CliResult(success=True, message="ok")
    failure = CliResult(success=False, message="missing env", error_code=1)

    with patch("src.utils.cli_runtime.ConfigValidator.validate_config_file", return_value=success) as mock_config, \
        patch("src.utils.cli_runtime.ConfigValidator.validate_environment", return_value=failure) as mock_env, \
        patch("src.utils.cli_runtime.publish_telemetry_event") as mock_publish:

        result = ensure_runtime_ready("config.yaml", telemetry_publishers=[MagicMock()])

    assert result is failure
    mock_config.assert_called_once_with("config.yaml")
    mock_env.assert_called_once_with()
    mock_publish.assert_called()
    assert mock_publish.call_args_list[-1][0][2]["stage"] == "environment_validation"


def test_ensure_runtime_ready_wraps_config_loader_errors() -> None:
    success = CliResult(success=True, message="ok")

    with patch("src.utils.cli_runtime.ConfigValidator.validate_config_file", return_value=success), \
        patch("src.utils.cli_runtime.ConfigValidator.validate_environment", return_value=success), \
        patch("src.utils.cli_runtime.ConfigManager.load_config_with_env_substitution", side_effect=ValueError("boom")), \
        patch("src.utils.cli_runtime.publish_telemetry_event") as mock_publish:

        result = ensure_runtime_ready("config.yaml", telemetry_publishers=[MagicMock()])

    assert not result.success
    assert "Failed to load configuration" in result.message
    assert result.error_code == 1
    assert mock_publish.call_args_list[-1][0][2]["stage"] == "config_loading"


def test_ensure_runtime_ready_handles_missing_env_without_telemetry() -> None:
    success = CliResult(success=True, message="ok")
    config_obj = object()

    with patch("src.utils.cli_runtime.ConfigValidator.validate_config_file", return_value=success), \
        patch("src.utils.cli_runtime.ConfigValidator.validate_environment", return_value=success), \
        patch("src.utils.cli_runtime.ConfigManager.load_config_with_env_substitution", return_value=config_obj), \
        patch.dict(os.environ, {}, clear=True):

        result = ensure_runtime_ready("config.yaml")

    assert result.success
    assert result.data is not None
    assert result.data["environment"] == {"github_token": None, "repo_name": None}