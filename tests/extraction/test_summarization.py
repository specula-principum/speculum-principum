"""Tests for the summarization extractor."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.cli.commands.extraction import build_parser, extract_cli
from src.extraction.summarization import summarize


def test_summarize_selects_high_value_sentences() -> None:
    text = (
        "Virtue guides rulers toward prudence. "
        "A wise prince studies history to master governance. "
        "Idle courtiers whisper distractions that erode prudence. "
        "Therefore, the prince must favor virtuous counsel above flattery."
    )

    result = summarize(text, config={"source_path": "doc.md", "max_sentences": 2})

    summary = result.data["summary"]  # type: ignore[index]
    sentences = result.data["sentences"]  # type: ignore[index]
    highlights = result.data["highlights"]  # type: ignore[index]

    assert result.extractor_name == "summarization"
    assert result.metadata["source_path"] == "doc.md"
    assert len(sentences) <= 2
    assert "virtuous" in summary.lower()
    assert "prudence" in highlights


def test_summarize_respects_config_overrides() -> None:
    text = (
        "Discipline wins campaigns. "
        "Preparation positions supply lines. "
        "Courage without planning invites defeat."
    )

    config = {
        "source_path": "scroll.md",
        "max_sentences": 1,
        "max_length": 120,
        "style": "bullet",
        "include_highlights": False,
        "preserve_order": False,
    }

    result = summarize(text, config=config)

    summary = result.data["summary"]  # type: ignore[index]
    assert summary.startswith("-")
    assert result.data["highlights"] == ()  # type: ignore[index]
    assert result.metadata["max_length"] == 120


def test_summarization_cli_integration(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text(
        "Leadership demands prudence. Prudence ensures justice.",
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "summarization:\n  max_sentences: 1\n  include_highlights: true\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "summarization",
            "--input",
            str(input_path),
            "--config",
            str(config_path),
            "--output-format",
            "json",
        ]
    )

    exit_code = extract_cli(args)
    assert exit_code == 0

    out, _ = capsys.readouterr()
    payload = json.loads(out)
    assert payload["extractor_name"] == "summarization"
    assert payload["data"]["summary"]


def test_summarize_handles_numeric_sentences_when_reordering() -> None:
    text = "1234567890. 9876543210."
    result = summarize(
        text,
        config={
            "source_path": "doc.md",
            "min_sentence_length": 2,
            "preserve_order": False,
            "max_sentences": 2,
        },
    )

    summary = result.data["summary"]  # type: ignore[index]
    assert "1234567890" in summary


def test_default_config_generates_auto_templates() -> None:
    text_path = Path("tests/extraction/fixtures/prince01mach_1/sample_combined.md")
    text = text_path.read_text(encoding="utf-8")

    full_config = yaml.safe_load(Path("config/extraction.yaml").read_text(encoding="utf-8"))
    summarization_config = dict(full_config["summarization"])  # type: ignore[index]
    summarization_config["source_path"] = str(text_path)
    summarization_config["taxonomy_path"] = "evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/taxonomy.json"
    summarization_config["structure_path"] = "evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/structure.json"

    result = summarize(text, config=summarization_config)

    sentences = result.data["sentences"]  # type: ignore[index]
    assert summarization_config.get("auto_template") is True
    assert len(sentences) == summarization_config.get("auto_template_max_sentences", 4)
    assert sentences[0].startswith("Examines governance")
    assert "Highlights virtue" in sentences[-1]
    assert result.data["summary"].startswith("-")  # type: ignore[index]
    highlights = result.data["highlights"]  # type: ignore[index]
    assert "highlights" not in highlights
    assert "themes" not in highlights
