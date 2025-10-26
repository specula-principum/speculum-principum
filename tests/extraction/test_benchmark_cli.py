"""Tests for the extraction benchmark CLI command."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import main as run_main


def test_extract_benchmark_outputs_metrics(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("Governance favors prudent counsel.", encoding="utf-8")

    exit_code = run_main(
        [
            "extract-benchmark",
            "concepts",
            "--input",
            str(input_path),
            "--config",
            str(tmp_path / "missing.yaml"),
            "--iterations",
            "2",
            "--output-format",
            "json",
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["iterations"] == 2
    assert payload["extractors"] == ["concepts"] or tuple(payload["extractors"]) == ("concepts",)
    metrics = payload["metrics"]["concepts"]
    assert metrics["iterations"] == 2
    assert metrics["total_seconds"] >= 0.0


def test_extract_benchmark_rejects_invalid_iterations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("Prudence demands preparation.", encoding="utf-8")

    exit_code = run_main(
        [
            "extract-benchmark",
            "segments",
            "--input",
            str(input_path),
            "--config",
            str(tmp_path / "missing.yaml"),
            "--iterations",
            "0",
        ]
    )

    assert exit_code == 1

    captured = capsys.readouterr()
    assert "iterations must be a positive integer" in captured.err
