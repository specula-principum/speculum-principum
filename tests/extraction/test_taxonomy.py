"""Tests for the taxonomy extractor."""
from __future__ import annotations

import json

from src.cli.commands.extraction import build_parser, extract_cli
from src.extraction.taxonomy import assign_taxonomy


def test_assign_taxonomy_detects_default_categories() -> None:
    text = "Prince Henry governs the council, reforms laws, and fills the treasury with prudent trade."

    result = assign_taxonomy(text, config={"source_path": "doc.md"})

    labels = {entry["label"]: entry for entry in result.data["labels"]}  # type: ignore[index]

    assert result.extractor_name == "taxonomy"
    assert result.metadata["source_path"] == "doc.md"
    assert "governance" in labels
    assert labels["governance"]["score"] >= 0.05
    assert "economy" in labels
    assert "treasury" in labels["economy"]["matched_keywords"]


def test_assign_taxonomy_respects_custom_categories() -> None:
    text = "The scholar debates ethics and philosophy within the academy."
    config = {
        "source_path": "scroll.md",
        "min_score": 0.0,
        "categories": {"scholarship": ["scholar", "ethics", "philosophy"]},
        "max_labels": 1,
        "bonus_weight": 0.0,
    }

    result = assign_taxonomy(text, config=config)

    labels = result.data["labels"]  # type: ignore[index]
    assert len(labels) == 1
    entry = labels[0]
    assert entry["label"] == "scholarship"
    assert set(entry["matched_keywords"]) == {"ethics", "philosophy", "scholar"}


def test_taxonomy_cli_integration(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("A treaty forged alliance and strengthened trade.", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "taxonomy:\n  min_score: 0.0\n  bonus_weight: 0.0\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "taxonomy",
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
    labels = {entry["label"]: entry for entry in payload["data"]["labels"]}
    assert "diplomacy" in labels
    assert labels["diplomacy"]["matched_keywords"]
