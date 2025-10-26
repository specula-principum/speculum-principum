"""Tests for the summarization extractor."""
from __future__ import annotations

import json

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
