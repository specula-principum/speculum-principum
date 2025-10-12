"""Regression tests for the assign-workflows CLI command."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import main as cli_main


class _FailingAssignmentAgent:
    """Stub AI agent that reports an error for every issue."""

    def __init__(
        self,
        github_token: str,
        repo_name: str,
        config_path: str,
        enable_ai: bool,
        telemetry_publishers: list | None = None,
        allowed_categories: list[str] | None = None,
    ) -> None:
        self.github_token = github_token
        self.repo_name = repo_name
        self.config_path = config_path
        self.enable_ai = enable_ai
        self.telemetry_publishers = telemetry_publishers or []
        self.allowed_categories = allowed_categories

    def process_issues_batch(self, *, limit: int, dry_run: bool) -> dict:
        return {
            "total_issues": 1,
            "processed": 0,
            "statistics": {"errors": 1},
            "duration_seconds": 0.1,
            "results": [
                {
                    "issue_number": 123,
                    "action_taken": "error",
                    "message": "simulated failure",
                    "dry_run": dry_run,
                }
            ],
        }


class _UnexpectedFallbackAgent:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - defensive guard
        raise AssertionError("Fallback agent should not be instantiated in this test")


def test_assign_workflows_returns_error_when_ai_cannot_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CLI should exit with a non-zero code when AI workflow assignment fails."""

    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    (workflow_dir / "example.yaml").write_text("name: Example Workflow\nversion: 1.0\n")

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "sites:",
                "  - url: https://example.com",
                "    name: Example Site",
                "github:",
                "  repository: ${GITHUB_REPOSITORY}",
                "search:",
                "  api_key: ${GOOGLE_API_KEY}",
                "  search_engine_id: ${GOOGLE_SEARCH_ENGINE_ID}",
                "agent:",
                "  username: ${GITHUB_ACTOR}",
                f"  workflow_directory: \"{workflow_dir}\"",
                f"  template_directory: \"{template_dir}\"",
                f"  output_directory: \"{output_dir}\"",
                f"storage_path: \"{tmp_path / 'processed.json'}\"",
            ]
        )
    )

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_ACTOR", "cli-bot")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    telemetry_dir = tmp_path / "telemetry"
    monkeypatch.setenv("SPECULUM_CLI_TELEMETRY_DIR", str(telemetry_dir))

    monkeypatch.setattr(cli_main, "AIWorkflowAssignmentAgent", _FailingAssignmentAgent)
    monkeypatch.setattr(cli_main, "WorkflowAssignmentAgent", _UnexpectedFallbackAgent)

    monkeypatch.setattr(sys, "argv", [
        "speculum-principum",
        "assign-workflows",
        "--config",
        str(config_path),
        "--limit",
        "1",
        "--dry-run",
    ])

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    assert exc.value.code == 1
