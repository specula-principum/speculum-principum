"""Tests for the `copilot agent-demo` CLI helpers."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import json
import pytest

from src.integrations.copilot import commands


@pytest.fixture(autouse=True)
def _stub_issue_fetch(monkeypatch):
    sample_issue: dict[str, Any] = {
        "number": 7,
        "title": "Demo",
        "state": "open",
        "html_url": "https://github.com/octo/repo/issues/7",
        "labels": [{"name": "triage"}],
    }

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert token == "token"
        assert repository == "octo/repo"
        assert issue_number == 7
        return sample_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)


def _make_args(**overrides) -> Namespace:
    defaults = dict(
        issue=7,
        repo="octo/repo",
        token="token",
        plan=None,
        context=None,
        params=[],
        default_finish=None,
        json=False,
        transcript_path=None,
        transcript_dir=Path("reports/transcripts"),
        no_transcript=False,
        triage=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_agent_demo_writes_transcript(tmp_path, monkeypatch, capsys):
    args = _make_args(
        transcript_path=tmp_path / "transcript.json",
        transcript_dir=tmp_path / "unused",
    )

    exit_code = commands._run_agent_demo(args)  # noqa: SLF001 - exercising CLI helper

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Transcript written to" in captured.out

    transcript_path = args.transcript_path
    assert transcript_path is not None and transcript_path.exists()

    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert payload["issue"]["number"] == 7
    assert payload["context"]["token"] == "***"
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["result"]["success"] is True
    assert payload["steps"][0]["arguments"]["token"] == "***"
    assert "recommendation" not in payload
 
 
def test_agent_demo_json_output_includes_transcript_path(tmp_path, capsys):
    args = _make_args(
        json=True,
        transcript_path=tmp_path / "transcript.json",
        transcript_dir=tmp_path / "unused",
    )

    exit_code = commands._run_agent_demo(args)  # noqa: SLF001 - exercising CLI helper

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["transcript_path"] == str(args.transcript_path)
    assert "recommendation" not in payload

    transcript_path = args.transcript_path
    assert transcript_path is not None and transcript_path.exists()


def test_agent_demo_triage_mode_records_recommendation(tmp_path, capsys):
    args = _make_args(
        json=True,
        transcript_path=tmp_path / "transcript.json",
        transcript_dir=tmp_path / "unused",
        triage=True,
    )

    exit_code = commands._run_agent_demo(args)  # noqa: SLF001 - exercising CLI helper

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert "recommendation" in payload
    assert payload["recommendation"]["classification"] == "needs-review"

    transcript_path = args.transcript_path
    assert transcript_path is not None and transcript_path.exists()
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert "recommendation" in transcript


def test_agent_demo_transcript_includes_validation_errors(tmp_path, capsys):
    plan_path = tmp_path / "invalid-plan.yaml"
    plan_path.write_text(
        """
steps:
  - description: Invalid call
    tool: get_issue_details
    arguments:
      issue_number: oops
""".strip(),
        encoding="utf-8",
    )

    args = _make_args(
        plan=plan_path,
        transcript_path=tmp_path / "transcript.json",
        transcript_dir=tmp_path / "unused",
    )

    exit_code = commands._run_agent_demo(args)  # noqa: SLF001 - exercising CLI helper

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Validation errors recorded in transcript" in captured.out

    transcript_path = args.transcript_path
    assert transcript_path is not None and transcript_path.exists()
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert payload["mission"]["status"] == "failed"
    assert payload["steps"][0]["result"]["success"] is False
    assert payload["validation_errors"][0]["tool"] == "get_issue_details"
    assert payload["validation_errors"][0]["index"] == 1
    assert payload["validation_errors"][0]["message"].startswith("Argument validation failed")