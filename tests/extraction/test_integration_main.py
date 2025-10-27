"""Integration tests for the extraction CLI via the main entry point."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import main as run_main

try:  # pragma: no cover - PyYAML should be installed, but keep guard for safety
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@pytest.mark.parametrize(
    "extractor,text,expected_keys",
    [
        (
            "segments",
            """# Title\n\nParagraph one.\n\n## Section\n\nAnother paragraph.""",
            ("data", "metadata"),
        ),
        (
            "entities",
            "Prince Henry met with the Council in London on 12 March 1521.",
            ("data", "metadata"),
        ),
        (
            "concepts",
            "Virtue guides virtue and governance; virtue shapes lasting governance.",
            ("data", "metadata"),
        ),
        (
            "summarization",
            "The prince studies statecraft diligently. He balances mercy with justice. "
            "His counsel praises his foresight in every decree.",
            ("data", "metadata"),
        ),
    ],
    ids=["segments", "entities", "concepts", "summarization"],
)
def test_main_extractors_emit_valid_json(
    extractor: str,
    text: str,
    expected_keys: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "input.md"
    input_path.write_text(text, encoding="utf-8")

    exit_code = run_main(
        [
            "extract",
            extractor,
            "--input",
            str(input_path),
            "--config",
            str(tmp_path / "missing.yaml"),
            "--output-format",
            "json",
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["extractor_name"] == extractor
    for key in expected_keys:
        assert key in payload
    assert payload["metadata"].get("source_path") == str(input_path)
    assert payload["data"]


def test_main_extract_yaml_output_to_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    if yaml is None:  # pragma: no cover - ensures test skipped if dependency missing
        pytest.skip("PyYAML is required for YAML output tests.")

    input_path = tmp_path / "chapters.md"
    input_path.write_text(
        "# Chapter\n\nThe prince balances mercy with justice across realms.",
        encoding="utf-8",
    )

    output_path = tmp_path / "result.yaml"

    exit_code = run_main(
        [
            "extract",
            "metadata",
            "--input",
            str(input_path),
            "--config",
            str(tmp_path / "missing.yaml"),
            "--output",
            str(output_path),
            "--output-format",
            "yaml",
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    assert f"Extraction result written to {output_path}" in captured.out
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    assert payload["extractor_name"] == "metadata"
    assert payload["metadata"]["source_path"] == str(input_path)
    assert isinstance(payload["data"], dict)


def test_main_extract_missing_input_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing_path = tmp_path / "missing.md"

    exit_code = run_main(
        [
            "extract",
            "segments",
            "--input",
            str(missing_path),
            "--config",
            str(tmp_path / "missing.yaml"),
        ]
    )

    assert exit_code == 1

    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_main_extract_invalid_config_reports_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("Text.", encoding="utf-8")
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("- not a mapping", encoding="utf-8")

    exit_code = run_main(
        [
            "extract",
            "segments",
            "--input",
            str(input_path),
            "--config",
            str(config_path),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "must be a mapping" in captured.err


def test_main_benchmark_unknown_extractor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("Benchmark text.", encoding="utf-8")

    exit_code = run_main(
        [
            "extract-benchmark",
            "unknown",
            "--input",
            str(input_path),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Unknown extractors" in captured.err


def test_main_extract_directory_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = tmp_path / "pages"
    directory.mkdir()
    (directory / "page-001.md").write_text("# Title\n\nFirst page.", encoding="utf-8")
    (directory / "page-002.md").write_text("Second page follows.", encoding="utf-8")

    exit_code = run_main(
        [
            "extract",
            "segments",
            "--input",
            str(directory),
            "--config",
            str(tmp_path / "missing.yaml"),
            "--output-format",
            "json",
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["extractor_name"] == "segments"
    assert payload["metadata"]["source_path"] == str(directory)
    combined_texts = " ".join(
        str(segment["text"]) if isinstance(segment, dict) else str(segment.text)
        for segment in payload["data"]
    )
    assert "First page" in combined_texts
    assert "Second page" in combined_texts