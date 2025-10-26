"""Tests for the metadata extractor."""
from __future__ import annotations

import json

from src.cli.commands.extraction import build_parser, extract_cli
from src.extraction.metadata import generate_metadata


def test_generate_metadata_produces_expected_statistics() -> None:
    text = (
        "# The Prince\n"
        "Prince Henry guides the realm.\n\n"
        "- Counsel the nobles.\n"
        "- Strengthen the treasury.\n\n"
        "Virtue and prudence guide governance. Virtue guides statecraft."
    )

    result = generate_metadata(text, config={"source_path": "doc.md"})

    stats = result.data["statistics"]  # type: ignore[index]
    dublin_core = result.data["dublin_core"]  # type: ignore[index]
    provenance = result.data["provenance"]  # type: ignore[index]

    assert result.extractor_name == "metadata"
    assert result.metadata["source_path"] == "doc.md"

    assert stats["word_count"] == 21
    assert stats["heading_count"] == 1
    assert stats["list_item_count"] == 2
    assert dublin_core["title"] == "The Prince"
    assert "Virtue" in dublin_core["description"]
    assert provenance["keywords"][:3] == ("guides", "prince", "virtue")
    history = provenance["history"]
    assert isinstance(history, tuple)
    assert any(entry.get("step") == "metadata" for entry in history)


def test_generate_metadata_respects_configuration_overrides() -> None:
    text = "Governance demands prudence and steady counsel."
    config = {
        "source_path": "scroll.md",
        "language": "la",
        "summary_length": 50,
        "include_quality_metrics": False,
        "include_history": False,
        "title": "Consilium",
        "description": "Custom summary",
        "subjects": ["leadership"],
        "creators": "advisor",
    }

    result = generate_metadata(text, config=config)

    data = result.data  # type: ignore[assignment]
    dublin_core = data["dublin_core"]

    assert dublin_core["language"] == "la"
    assert dublin_core["title"] == "Consilium"
    assert dublin_core["description"] == "Custom summary"
    assert dublin_core["subject"] == ("leadership",)
    assert dublin_core["creator"] == ("advisor",)
    assert "quality" not in data
    assert data["provenance"]["history"] == ()


def test_metadata_cli_integration(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text("# De Regno\nGovernance relies on virtue and prudence.", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_path.write_text("metadata:\n  summary_length: 80\n", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "metadata",
            "--input",
            str(input_path),
            "--output-format",
            "json",
            "--config",
            str(config_path),
        ]
    )

    exit_code = extract_cli(args)
    assert exit_code == 0

    out, err = capsys.readouterr()
    payload = json.loads(out)
    assert payload["extractor_name"] == "metadata"
    assert payload["data"]["dublin_core"]["title"] == "De Regno"
    assert payload["data"]["statistics"]["word_count"] > 0

