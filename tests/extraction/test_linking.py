"""Tests for the linking extractor."""
from __future__ import annotations

import json

from src.cli.commands.extraction import build_parser, extract_cli
from src.extraction.linking import generate_links


def test_generate_links_detects_anchors_and_outbound_links() -> None:
    text = (
        "# Prologue\n"
        "Introduction with a [reference](docs/intro.md).\n\n"
        "## Counsel\n"
        "See also William Marshal for historical precedent."
    )

    result = generate_links(text, config={"source_path": "doc.md"})

    anchors = result.data["anchors"]  # type: ignore[index]
    outbound = result.data["outbound_links"]  # type: ignore[index]
    see_also = result.data["see_also"]  # type: ignore[index]

    assert result.extractor_name == "linking"
    assert result.metadata["source_path"] == "doc.md"
    assert anchors[0]["title"] == "Prologue"
    assert anchors[1]["slug"] == "counsel"
    assert outbound[0]["target"] == "docs/intro.md"
    assert see_also and "William Marshal" in see_also[0]["target"]


def test_generate_links_mentions_respect_configuration() -> None:
    text = "Prince Henry met Prince Henry and the Royal Council."
    config = {
        "source_path": "doc.md",
        "include_mentions": False,
    }

    result = generate_links(text, config=config)

    mentions = result.data["mentions"]  # type: ignore[index]
    assert mentions == ()

    result_with_mentions = generate_links(text, config={"source_path": "doc.md", "max_mentions": 1})
    assert result_with_mentions.data["mentions"]  # type: ignore[index]


def test_linking_cli_integration(tmp_path, capsys) -> None:
    input_path = tmp_path / "doc.md"
    input_path.write_text(
        "# Chapters\nConsult the [appendix](appendix.md).\nSee also Council of Ten.",
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "linking:\n  max_links: 5\n  include_mentions: true\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "linking",
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
    assert payload["extractor_name"] == "linking"
    assert payload["data"]["outbound_links"]
    assert payload["data"]["see_also"]
