"""Coverage-oriented tests for kb_engine scaffolding modules."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src.kb_engine.cli import register_commands
from src.kb_engine.links import LinkBuilder
from src.kb_engine.quality import QualityAnalyzer


def test_link_builder_requires_existing_root(tmp_path: Path) -> None:
    builder = LinkBuilder()
    with pytest.raises(FileNotFoundError):
        builder.build_concept_graph(tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        builder.generate_backlinks(tmp_path / "missing")
    with pytest.raises(RuntimeError):
        builder.suggest_related("concepts/statecraft/virtue")


def test_quality_analyzer_validates_inputs(tmp_path: Path) -> None:
    analyzer = QualityAnalyzer()
    with pytest.raises(TypeError):
        analyzer.calculate_completeness(object())  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        analyzer.calculate_findability("kb-id", tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        analyzer.identify_gaps(tmp_path / "missing")


def test_cli_registers_placeholder_commands() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    register_commands(subparsers)

    for command in ("process", "update", "improve", "export-graph"):
        with pytest.raises(NotImplementedError):
            args = parser.parse_args(["kb-engine", command])
            assert callable(args.func)
            args.func(args)
