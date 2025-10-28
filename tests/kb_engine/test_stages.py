"""Tests for kb_engine pipeline stages."""
from __future__ import annotations

from pathlib import Path

import yaml

from src.kb_engine.stages import LinkingStage, QualityStage
from src.kb_engine.models import ProcessingContext


def _write_document(root: Path, kb_id: str, payload: dict[str, object], body: str) -> Path:
    yaml_block = yaml.safe_dump(payload, sort_keys=False)
    if body and not body.endswith("\n"):
        body = f"{body}\n"
    contents = f"---\n{yaml_block}---\n"
    if body:
        contents = f"{contents}\n{body}"
    path = (root / kb_id).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def _read_front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            block = "\n".join(lines[1:index])
            break
    else:  # pragma: no cover - defensive guard
        raise AssertionError("Missing terminator")
    return yaml.safe_load(block) or {}


def _context(tmp_path: Path) -> ProcessingContext:
    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    source.mkdir()
    kb_root.mkdir()
    return ProcessingContext(source_path=source, kb_root=kb_root)


def test_linking_stage_builds_graph_and_backlinks(tmp_path: Path) -> None:
    context = _context(tmp_path)
    kb_root = context.kb_root

    virtue_payload = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": "concepts/statecraft/virtue",
        "type": "concept",
        "tags": ["statecraft", "virtue"],
        "related_concepts": ["concepts/statecraft/fortune"],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [1]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": [],
            "findability_score": 0.7,
            "completeness": 0.8,
        },
    }
    fortune_payload = {
        "title": "Fortune",
        "slug": "fortune",
        "kb_id": "concepts/statecraft/fortune",
        "type": "concept",
        "tags": ["statecraft", "fortune"],
        "related_concepts": [],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [2]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "fortune"],
            "related_by_topic": [],
            "findability_score": 0.65,
            "completeness": 0.78,
        },
    }

    virtue_path = _write_document(kb_root, "concepts/statecraft/virtue", virtue_payload, "Virtue body.\n")
    fortune_path = _write_document(kb_root, "concepts/statecraft/fortune", fortune_payload, "Fortune body.\n")

    stage = LinkingStage()
    result = stage.run(context, ())

    assert result.stage == "linking"
    assert result.metrics["concepts"] >= 2.0
    assert result.metrics["edges"] >= 1.0
    assert result.metrics["backlinks_updated"] >= 1.0
    fortune_front = _read_front_matter(fortune_path)
    fortune_ia = fortune_front.get("ia", {})
    if not isinstance(fortune_ia, dict):
        fortune_ia = {}
    assert "concepts/statecraft/virtue" in tuple(fortune_ia.get("related_by_topic", ()))
    virtue_front = _read_front_matter(virtue_path)
    virtue_ia = virtue_front.get("ia", {})
    if not isinstance(virtue_ia, dict):
        virtue_ia = {}
    assert tuple(virtue_ia.get("related_by_topic", ())) == ()


def test_quality_stage_reports_gaps(tmp_path: Path) -> None:
    context = _context(tmp_path)
    kb_root = context.kb_root

    payload = {
        "title": "Power",
        "slug": "power",
        "kb_id": "concepts/statecraft/power",
        "type": "concept",
        "related_concepts": [],
        "sources": [],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "power"],
            "related_by_topic": [],
            "findability_score": 0.4,
            "completeness": 0.5,
        },
    }
    _write_document(kb_root, "concepts/statecraft/power", payload, "Short body.\n")

    stage = QualityStage()
    result = stage.run(context, ())

    assert result.stage == "quality"
    assert result.metrics["gaps_total"] >= 1.0
    assert result.metrics["gaps_errors"] >= 1.0
    assert any(note.startswith("gap:") for note in result.notes)