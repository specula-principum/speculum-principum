"""Integration tests for knowledge base CLI commands via main entry point."""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib
import json
import sys
import types
from pathlib import Path

import pytest
import yaml
from src.extraction import ExtractedConcept, ExtractedEntity, ExtractionResult
from src.kb_engine.extraction import ExtractionBundle, ExtractionCoordinator, ExtractionRunSummary
from src.kb_engine.config import PipelineConfig


def _write_source_markdown(path: Path, *, body: str) -> None:
    payload = (
        "---\n"
        "metadata:\n"
        "  page_number: 1\n"
        "---\n\n"
        f"{body}\n"
    )
    path.write_text(payload, encoding="utf-8")


def _write_kb_document(root: Path, kb_id: str, front_matter: dict[str, object], body: str) -> Path:
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False)
    if body and not body.endswith("\n"):
        body = f"{body}\n"
    payload = f"---\n{yaml_block}---\n"
    if body:
        payload = f"{payload}\n{body}"
    path = (root / kb_id).with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _make_bundle(source_path: Path, *, concept_frequency: int) -> ExtractionBundle:
    concept = ExtractedConcept(
        term="Virtue",
        frequency=concept_frequency,
        positions=(1, 5),
        related_terms=("Fortune",),
        definition="Guiding principle for rulers.",
    )
    entity = ExtractedEntity(
        text="Niccolo Machiavelli",
        entity_type="PERSON",
        start_offset=0,
        end_offset=20,
        confidence=0.95,
        metadata={
            "related_concepts": ("concepts/statecraft/virtue",),
            "aliases": ("Machiavelli",),
        },
    )

    concept_result = ExtractionResult(
        source_path=str(source_path),
        checksum="deadbeef",
        extractor_name="concepts",
        data=(concept,),
        metadata={},
    )
    entity_result = ExtractionResult(
        source_path=str(source_path),
        checksum="cafebabe",
        extractor_name="entities",
        data=(entity,),
        metadata={},
    )

    started_at = datetime.utcnow()
    completed_at = started_at + timedelta(milliseconds=5)
    summaries = (
        ExtractionRunSummary(extractor="concepts", duration=0.001, from_cache=False),
        ExtractionRunSummary(extractor="entities", duration=0.001, from_cache=False),
    )
    return ExtractionBundle(
        results={"concepts": concept_result, "entities": entity_result},
        failures={},
        summaries=summaries,
        started_at=started_at,
        completed_at=completed_at,
    )


def run_main(args: list[str]) -> int:
    module = importlib.import_module("main")
    return module.main(args)


@pytest.fixture(autouse=True)
def _stub_pipeline_config(monkeypatch: pytest.MonkeyPatch) -> PipelineConfig:
    pdf_module = types.ModuleType("pypdf")
    errors_module = types.ModuleType("pypdf.errors")

    class _PdfReader:  # pragma: no cover - stub for dependency injection
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

    class _PdfReadError(Exception):
        pass

    setattr(pdf_module, "PdfReader", _PdfReader)
    setattr(errors_module, "PdfReadError", _PdfReadError)

    monkeypatch.setitem(sys.modules, "pypdf", pdf_module)
    monkeypatch.setitem(sys.modules, "pypdf.errors", errors_module)

    trafilatura_module = types.ModuleType("trafilatura")

    def _extract(_html: str, *, url: str | None = None) -> str:  # pragma: no cover - stub behaviour
        del _html, url
        return "stubbed extraction"

    setattr(trafilatura_module, "extract", _extract)
    monkeypatch.setitem(sys.modules, "trafilatura", trafilatura_module)
    sys.modules.pop("main", None)
    config = PipelineConfig.from_mapping(
        {
            "pipeline": {
                "extraction": {"enabled_tools": ("concepts", "entities")},
                "transformation": {
                    "primary_topic": "statecraft",
                    "findability_baseline": 0.75,
                    "completeness_baseline": 0.85,
                },
                "organization": {"collision_strategy": "replace", "index_generation": "manual"},
                "linking": {"build_concept_graph": False, "generate_backlinks": False},
                "quality": {"validate_on_creation": False},
            },
            "monitoring": {},
        }
    )
    monkeypatch.setattr("src.kb_engine.workflows.load_pipeline_config", lambda path=None: config)
    return config


def _install_extraction_stub(monkeypatch: pytest.MonkeyPatch, bundle: ExtractionBundle) -> None:
    def fake_extract_all(self, text, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, config, source_path, progress_callback
        return bundle

    def fake_extract_selective(self, text, extractors, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, extractors, config, source_path, progress_callback
        return bundle

    monkeypatch.setattr(ExtractionCoordinator, "extract_all", fake_extract_all)
    monkeypatch.setattr(ExtractionCoordinator, "extract_selective", fake_extract_selective)


def test_kb_process_cli_creates_kb_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"
    metrics_path = tmp_path / "metrics.json"

    source_dir.mkdir()
    _write_source_markdown(source_dir / "segment-001.md", body="Virtue guides stable rule through prudence.")

    bundle = _make_bundle(source_dir, concept_frequency=3)
    _install_extraction_stub(monkeypatch, bundle)

    exit_code = run_main(
        [
            "kb",
            "process",
            "--source",
            str(source_dir),
            "--kb-root",
            str(kb_root),
            "--metrics-output",
            str(metrics_path),
        ]
    )

    assert exit_code == 0
    concept_path = kb_root / "concepts" / "statecraft" / "virtue.md"
    entity_path = kb_root / "entities" / "people" / "niccolo-machiavelli.md"
    assert concept_path.exists()
    assert entity_path.exists()

    payload = concept_path.read_text(encoding="utf-8")
    assert "Virtue" in payload
    assert "**Frequency:** 3" in payload

    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["success"] is True

    assert metrics["metrics"]["organization.documents"] >= 1


def test_kb_update_cli_refreshes_existing_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"
    metrics_path = tmp_path / "update-metrics.json"

    source_dir.mkdir()
    _write_source_markdown(source_dir / "segment-001.md", body="Virtue ensures the prince wins loyalty.")

    initial_bundle = _make_bundle(source_dir, concept_frequency=2)
    _install_extraction_stub(monkeypatch, initial_bundle)

    process_exit_code = run_main(
        [
            "kb",
            "process",
            "--source",
            str(source_dir),
            "--kb-root",
            str(kb_root),
        ]
    )
    assert process_exit_code == 0

    concept_path = kb_root / "concepts" / "statecraft" / "virtue.md"
    assert concept_path.exists()
    original_contents = concept_path.read_text(encoding="utf-8")
    assert "**Frequency:** 2" in original_contents

    updated_bundle = _make_bundle(source_dir, concept_frequency=7)
    _install_extraction_stub(monkeypatch, updated_bundle)

    update_exit_code = run_main(
        [
            "kb",
            "update",
            "--kb-id",
            "concepts/statecraft/virtue",
            "--source",
            str(source_dir),
            "--kb-root",
            str(kb_root),
            "--metrics-output",
            str(metrics_path),
        ]
    )
    assert update_exit_code == 0

    updated_contents = concept_path.read_text(encoding="utf-8")
    assert "**Frequency:** 7" in updated_contents
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["success"] is True


def test_kb_benchmark_cli_records_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    source_dir.mkdir()
    _write_source_markdown(source_dir / "segment.md", body="Virtue balances fortune and prudence.")

    bundle = _make_bundle(source_dir, concept_frequency=4)
    _install_extraction_stub(monkeypatch, bundle)

    output_path = tmp_path / "benchmark.json"

    exit_code = run_main(
        [
            "kb",
            "benchmark",
            "--source",
            str(source_dir),
            "--iterations",
            "2",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["iterations"] == 2
    assert payload["success"] is True
    assert payload["metrics"]["total"]["iterations"] == 2
    assert "analysis" in payload["metrics"]["stages"]
    assert payload["iterations_detail"][0]["stage_durations"]


def test_kb_benchmark_cli_retains_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "evidence"
    source_dir.mkdir()
    _write_source_markdown(source_dir / "segment.md", body="Fortune yields to prepared rulers.")

    bundle = _make_bundle(source_dir, concept_frequency=5)
    _install_extraction_stub(monkeypatch, bundle)

    scratch_root = tmp_path / "scratch"

    exit_code = run_main(
        [
            "kb",
            "benchmark",
            "--source",
            str(source_dir),
            "--iterations",
            "1",
            "--scratch-root",
            str(scratch_root),
            "--retain-artifacts",
        ]
    )

    assert exit_code == 0
    retained = sorted(scratch_root.glob("iteration-*/concepts/statecraft/virtue.md"))
    assert retained, "expected benchmark artifacts to be retained"


def test_kb_benchmark_cli_rejects_invalid_iterations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = tmp_path / "evidence"
    source_dir.mkdir()
    _write_source_markdown(source_dir / "segment.md", body="Virtue requires iterative practice.")

    bundle = _make_bundle(source_dir, concept_frequency=3)
    _install_extraction_stub(monkeypatch, bundle)

    exit_code = run_main(
        [
            "kb",
            "benchmark",
            "--source",
            str(source_dir),
            "--iterations",
            "0",
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "iterations" in captured.err


def test_kb_quality_report_cli_generates_report(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    virtue_front = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": "concepts/statecraft/virtue",
        "type": "concept",
        "tags": ["statecraft", "virtue"],
        "related_concepts": ["concepts/statecraft/fortune"],
        "sources": [{"kb_id": "sources/the-prince/chapter-1", "pages": [1]}],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": ["concepts/statecraft/fortune"],
            "findability_score": 0.8,
            "completeness": 0.85,
        },
    }

    _write_kb_document(
        kb_root,
        "concepts/statecraft/virtue",
        virtue_front,
        ("Virtue balances fortune and prudence. " * 10).strip(),
    )

    output_path = tmp_path / "quality-report.json"

    exit_code = run_main(
        [
            "kb",
            "quality-report",
            "--kb-root",
            str(kb_root),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["documents"]["total"] == 1
    assert payload["metrics"]["completeness"]["mean"] >= 0.8