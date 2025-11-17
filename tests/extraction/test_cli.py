"""Tests for the extraction CLI registry and commands."""
from __future__ import annotations

import argparse
import json

import pytest

from src.cli.commands.extraction import (
    build_parser,
    extract_benchmark_cli,
    extract_cli,
    register_benchmark_command,
)
from src.extraction import cli


def test_available_extractors_contains_expected_entries() -> None:
    extractors = cli.available_extractors()
    expected = {
        "concepts",
        "entities",
        "linking",
        "metadata",
        "relationships",
        "segments",
        "structure",
        "summarization",
        "taxonomy",
    }
    assert expected.issubset(set(extractors))


def test_run_segments_extractor_returns_result() -> None:
    result = cli.run_extractor("segments", text="# Heading\n\nBody text.")
    assert result.extractor_name == "segments"
    assert len(result.data) >= 2


def test_run_concepts_extractor_returns_result() -> None:
    result = cli.run_extractor(
        "concepts",
        text="Power and power align with virtue.",
        config={"source_path": "doc.md"},
    )
    assert result.extractor_name == "concepts"
    assert result.data


def test_run_relationships_extractor_returns_result() -> None:
    result = cli.run_extractor(
        "relationships",
        text="Prince Henry supports the Council of Elders.",
        config={"source_path": "doc.md"},
    )
    assert result.extractor_name == "relationships"
    assert result.data


def test_load_unknown_extractor_raises() -> None:
    with pytest.raises(ValueError):
        cli.load_extractor("unknown")


def test_extract_cli_outputs_json(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("# Title\n\nParagraph text.", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["segments", "--input", str(input_path), "--output-format", "json"])

    exit_code = extract_cli(args)
    assert exit_code == 0

    out, err = capsys.readouterr()
    payload = json.loads(out)
    assert payload["extractor_name"] == "segments"
    assert payload["metadata"]["source_path"] == str(input_path)
    assert payload["data"]


def test_extract_cli_dry_run(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("# Title", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(["segments", "--input", str(input_path), "--dry-run"])

    exit_code = extract_cli(args)
    assert exit_code == 0

    out, err = capsys.readouterr()
    assert "Dry run" in out


def test_extract_benchmark_profile_selection(tmp_path) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("# Title\n\nYet another paragraph.", encoding="utf-8")
    output_path = tmp_path / "benchmark.json"

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_benchmark_command(subparsers)

    args = parser.parse_args(
        [
            "extract-benchmark",
            "--input",
            str(input_path),
            "--profile",
            "governance-default",
            "--iterations",
            "1",
            "--output",
            str(output_path),
            "--output-format",
            "json",
        ]
    )

    exit_code = args.func(args)
    assert exit_code == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert tuple(payload["extractors"]) == (
        "entities",
        "relationships",
        "metadata",
        "summarization",
    )


def test_extract_benchmark_profile_conflict(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("# Heading", encoding="utf-8")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_benchmark_command(subparsers)

    args = parser.parse_args(
        [
            "extract-benchmark",
            "entities",
            "--input",
            str(input_path),
            "--profile",
            "governance-default",
            "--iterations",
            "1",
        ]
    )

    exit_code = args.func(args)
    assert exit_code == 1

    out, err = capsys.readouterr()
    assert "profile" in err
