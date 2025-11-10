"""Tests for parsing preview missions and mission loading utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.orchestration.demo import run_parsing_preview_demo
from src.orchestration.missions import load_mission
from src.orchestration.types import MissionStatus
from src.parsing import utils as parsing_utils
from src.parsing.base import ParsedDocument
from src.parsing.registry import ParserRegistry


def test_load_mission_parses_preview_spec() -> None:
    mission_path = Path("config/missions/kb_source_preview.yaml")
    mission = load_mission(mission_path)

    assert mission.id == "kb_source_preview"
    assert mission.max_steps == 6
    assert mission.allowed_tools == ("list_parse_candidates", "preview_parse_document")
    assert mission.requires_approval is False


def test_load_mission_requires_mandatory_fields(tmp_path: Path) -> None:
    mission_path = tmp_path / "broken.yaml"
    mission_path.write_text("id: missing\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_mission(mission_path)


def test_run_parsing_preview_demo_generates_preview(monkeypatch, tmp_path: Path) -> None:

    class DummyPdfParser:
        name = "dummy-pdf"

        def detect(self, target):  # type: ignore[override]
            try:
                return target.to_path().suffix.lower() == ".pdf"
            except ValueError:
                return False

        def extract(self, target):  # type: ignore[override]
            path = target.to_path()
            checksum = parsing_utils.sha256_path(path)
            document = ParsedDocument(target=target, checksum=checksum, parser_name=self.name)
            document.add_segment(path.read_text(encoding="utf-8"))
            return document

        def to_markdown(self, document):  # type: ignore[override]
            return "\n\n".join(document.segments)

    custom_registry = ParserRegistry()
    custom_registry.register_parser(DummyPdfParser(), suffixes=(".pdf",), priority=50, replace=True)
    monkeypatch.setattr("src.parsing.runner.registry", custom_registry)

    evidence_root = tmp_path / "docs"
    evidence_root.mkdir()
    source_path = evidence_root / "sample.pdf"
    source_path.write_text("Sample preview content", encoding="utf-8")

    outcome, preview_payload, candidates, mission, plan, context_inputs = run_parsing_preview_demo(
        parse_root=evidence_root,
        source_path=source_path,
        context_inputs={"max_preview_chars": 50},
    )

    assert mission.id == "kb_source_preview"
    assert plan.default_finish
    assert outcome.status is MissionStatus.SUCCEEDED
    assert preview_payload is not None

    preview_block = preview_payload.get("preview") if isinstance(preview_payload, dict) else None
    assert preview_block is not None
    assert "Sample preview content" in preview_block.get("content", "")
    assert candidates and str(source_path) in candidates

    latest_payload = context_inputs.get("latest_preview_payload")
    assert isinstance(latest_payload, dict)
    assert latest_payload == preview_payload
