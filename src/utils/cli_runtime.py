"""Runtime validation helpers for CLI commands.

This module centralizes configuration validation, environment checking, and
common telemetry emissions required before executing complex CLI workflows.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional

from src.utils.cli_helpers import CliResult, ConfigValidator
from src.utils.config_manager import ConfigManager
from src.utils.telemetry import publish_telemetry_event


class RuntimeSetupError(RuntimeError):
    """Raised when the CLI runtime environment cannot be prepared."""


def ensure_runtime_ready(
    config_path: str,
    *,
    telemetry_publishers: Optional[Iterable] = None,
    telemetry_event: str = "cli.runtime_validation",
) -> CliResult:
    """Validate configuration and environment before running a CLI command.

    Args:
        config_path: Path to the CLI configuration file.
        telemetry_publishers: Optional iterable of telemetry publishers.
        telemetry_event: Event name used when emitting telemetry validation
            payloads. Defaults to ``"cli.runtime_validation"``.

    Returns:
        ``CliResult`` containing either the prepared runtime context under
        ``data`` or an error message describing why validation failed.
    """

    publishers = list(telemetry_publishers or [])

    def _emit(payload: dict) -> None:
        if not publishers:
            return
        publish_telemetry_event(publishers, telemetry_event, payload)

    config_result = ConfigValidator.validate_config_file(config_path)
    if not config_result.success:
        _emit({
            "success": False,
            "stage": "config_validation",
            "error": config_result.message,
        })
        return config_result

    env_result = ConfigValidator.validate_environment()
    if not env_result.success:
        _emit({
            "success": False,
            "stage": "environment_validation",
            "error": env_result.message,
        })
        return env_result

    try:
        config = ConfigManager.load_config_with_env_substitution(config_path)
    except (OSError, ValueError) as exc:
        message = f"Failed to load configuration: {exc}"
        _emit({
            "success": False,
            "stage": "config_loading",
            "error": message,
        })
        return CliResult(success=False, message=message, error_code=1)

    environment = {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "repo_name": os.getenv("GITHUB_REPOSITORY"),
    }

    _emit({
        "success": True,
        "stage": "ready",
        "environment_has_token": bool(environment["github_token"]),
        "environment_has_repo": bool(environment["repo_name"]),
    })

    return CliResult(
        success=True,
        message="Runtime environment ready",
        data={
            "config": config,
            "environment": environment,
        },
    )
