"""Helper utilities for CLI commands that need site monitor services.

This module centralizes the logic for validating monitor configuration files
and constructing ``SiteMonitorService`` instances so that individual CLI
commands do not need to duplicate safety checks or wiring code.
"""

from __future__ import annotations

from typing import Iterable, Optional

from src.core.site_monitor import (
    SiteMonitorService,
    create_monitor_service_from_config,
)
from src.utils.cli_helpers import CliResult, ConfigValidator


class MonitorServiceError(RuntimeError):
    """Raised when the CLI monitor service helper cannot create a service."""


def _ensure_config_valid(config_path: str) -> None:
    """Validate the configuration file and raise an error on failure."""
    validation_result: CliResult = ConfigValidator.validate_config_file(config_path)
    if not validation_result.success:
        raise MonitorServiceError(validation_result.message)


def get_monitor_service(
    config_path: str,
    github_token: str,
    *,
    telemetry: Optional[Iterable] = None,
) -> SiteMonitorService:
    """Return a configured :class:`SiteMonitorService` for CLI commands.

    Args:
        config_path: Path to the monitoring configuration file.
        github_token: GitHub token used by the monitor service.
        telemetry: Optional iterable of telemetry publishers.

    Raises:
        MonitorServiceError: If validation fails or the service cannot be created.

    Returns:
        A ready-to-use ``SiteMonitorService`` instance.
    """

    _ensure_config_valid(config_path)

    try:
        return create_monitor_service_from_config(
            config_path,
            github_token,
            telemetry_publishers=telemetry,
        )
    except FileNotFoundError as exc:
        # Surface a consistent error message for missing configuration files.
        raise MonitorServiceError(f"Configuration file not found: {config_path}") from exc
    except Exception as exc:  # noqa: BLE001
        raise MonitorServiceError(
            f"Failed to create site monitor service: {exc}"
        ) from exc
