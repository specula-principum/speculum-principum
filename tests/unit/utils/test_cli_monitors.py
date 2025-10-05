"""Tests for CLI monitor helper utilities."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.utils.cli_helpers import CliResult
from src.utils.cli_monitors import MonitorServiceError, get_monitor_service


def test_get_monitor_service_missing_config() -> None:
    """Helper raises when the configuration file is invalid or missing."""
    with patch(
        "src.utils.cli_monitors.ConfigValidator.validate_config_file",
        return_value=CliResult(success=False, message="Configuration file not found: missing.yaml", error_code=1),
    ):
        with pytest.raises(MonitorServiceError) as excinfo:
            get_monitor_service("missing.yaml", "token")

    assert "Configuration file not found" in str(excinfo.value)


@patch("src.utils.cli_monitors.create_monitor_service_from_config")
@patch(
    "src.utils.cli_monitors.ConfigValidator.validate_config_file",
    return_value=CliResult(success=True, message="Configuration file is valid"),
)
def test_get_monitor_service_passes_through_telemetry(
    mock_validate: MagicMock,
    mock_create: MagicMock,
) -> None:
    """Helper returns the service from factory and passes telemetry publishers."""
    telemetry_publishers = [MagicMock()]
    expected_service = MagicMock()
    mock_create.return_value = expected_service

    service = get_monitor_service("config.yaml", "token", telemetry=telemetry_publishers)

    assert service is expected_service
    mock_validate.assert_called_once_with("config.yaml")
    mock_create.assert_called_once_with(
        "config.yaml",
        "token",
        telemetry_publishers=telemetry_publishers,
    )


@patch(
    "src.utils.cli_monitors.ConfigValidator.validate_config_file",
    return_value=CliResult(success=True, message="Configuration file is valid"),
)
@patch(
    "src.utils.cli_monitors.create_monitor_service_from_config",
    side_effect=RuntimeError("broken wiring"),
)
def test_get_monitor_service_wraps_creation_errors(
    _mock_validate: MagicMock,
    _mock_create: MagicMock,
) -> None:
    """Factory errors are wrapped in a MonitorServiceError."""
    with pytest.raises(MonitorServiceError) as excinfo:
        get_monitor_service("config.yaml", "token")

    assert "Failed to create site monitor service" in str(excinfo.value)
    assert "broken wiring" in str(excinfo.value)
