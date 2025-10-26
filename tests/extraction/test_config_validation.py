"""Tests for extraction configuration helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.extraction.config import load_extraction_config, validate_requested_extractors


def test_load_extraction_config_accepts_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "extraction.yaml"
    config_path.write_text(
        "concepts:\n  min_frequency: 2\nmetadata:\n  language: la\n",
        encoding="utf-8",
    )

    config = load_extraction_config(config_path)

    assert config.raw["concepts"]["min_frequency"] == 2
    assert config.raw["metadata"]["language"] == "la"


def test_load_extraction_config_rejects_non_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("- not a mapping\n- another entry\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a mapping"):
        load_extraction_config(config_path)


def test_validate_requested_extractors_flags_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown extractors"):
        validate_requested_extractors(["unknown-extractor"])
