"""Tests for kb_engine workflow orchestration."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import yaml

from src.extraction import ExtractedConcept, ExtractedEntity, ExtractionResult
from src.kb_engine.extraction import ExtractionBundle, ExtractionCoordinator, ExtractionRunSummary
from src.kb_engine.models import ProcessingContext
from src.kb_engine.workflows import (
    ExportGraphOptions,
    ImproveOptions,
    ProcessOptions,
    QualityReportOptions,
    SourceAnalysisStage,
    UpdateOptions,
    build_process_pipeline,
    run_export_graph_workflow,
    run_improve_workflow,
    run_process_workflow,
    run_quality_report_workflow,
    run_update_workflow,
)
from src.kb_engine.config import PipelineConfig
from src.knowledge_base import SourceReference
from src.kb_engine.utils import slugify


def _write_markdown(path: Path, *, page: int, body: str) -> None:
    payload = (
        "---\n"
        "metadata:\n"
        f"  page_number: {page}\n"
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


def test_source_analysis_stage_collects_segments(tmp_path: Path) -> None:
    source_dir = tmp_path / "prince-notes"
    source_dir.mkdir()
    _write_markdown(source_dir / "chapter-1.md", page=3, body="The prince must balance fear and love.")
    _write_markdown(source_dir / "chapter-2.md", page=7, body="Fortune favors the bold strategist.")

    context = ProcessingContext(
        source_path=source_dir,
        kb_root=tmp_path / "kb",
        extractors=(),
        extra={},
    )

    stage = SourceAnalysisStage()
    result = stage.run(context, tuple())

    analysis = context.extra["analysis"]
    assert "Fortune" in analysis["text"]
    assert len(analysis["segments"]) == 2
    assert isinstance(analysis["source_reference"], SourceReference)
    assert result.metrics["segments"] == 2.0
    assert result.metrics["characters"] == float(len(analysis["text"]))
    assert not result.warnings


def _bundle_with_concept_and_entity(
    source_path: str,
    *,
    concept_term: str = "Virtue",
    concept_frequency: int = 3,
    entity_confidence: float = 0.92,
) -> ExtractionBundle:
    concept_slug = slugify(concept_term)
    concept = ExtractedConcept(
        term=concept_term,
        frequency=concept_frequency,
        positions=(5, 42),
        related_terms=("Fortune",),
        definition="Guiding principle for rulers.",
    )
    entity = ExtractedEntity(
        text="Machiavelli",
        entity_type="PERSON",
        start_offset=0,
        end_offset=12,
        confidence=entity_confidence,
        metadata={"related_concepts": (f"concepts/statecraft/{concept_slug}",)},
    )

    concept_result = ExtractionResult(
        source_path=source_path,
        checksum="deadbeef",
        extractor_name="concepts",
        data=(concept,),
        metadata={},
    )
    entity_result = ExtractionResult(
        source_path=source_path,
        checksum="cafebabe",
        extractor_name="entities",
        data=(entity,),
        metadata={},
    )

    now = datetime.utcnow()
    summary = ExtractionRunSummary(extractor="concepts", duration=0.1, from_cache=False)
    return ExtractionBundle(
        results={"concepts": concept_result, "entities": entity_result},
        failures={},
        summaries=(summary,),
        started_at=now,
        completed_at=now + timedelta(milliseconds=5),
    )


def _pipeline_config_with_defaults() -> PipelineConfig:
    return PipelineConfig.from_mapping(
        {
            "pipeline": {
                "extraction": {},
                "transformation": {},
                "organization": {},
                "linking": {"build_concept_graph": True, "generate_backlinks": True},
                "quality": {
                    "required_completeness": 0.8,
                    "required_findability": 0.6,
                    "min_body_length": 10,
                },
            },
            "monitoring": {},
        }
    )


def test_build_process_pipeline_assigns_conditional_stages() -> None:
    config = PipelineConfig.from_mapping(
        {
            "pipeline": {
                "extraction": {"enabled_tools": ("concepts", "entities")},
                "transformation": {"primary_topic": "statecraft"},
                "organization": {"collision_strategy": "replace"},
                "linking": {"build_concept_graph": True, "generate_backlinks": True},
                "quality": {"validate_on_creation": False},
            },
            "monitoring": {},
        }
    )

    pipeline = build_process_pipeline(config, mission=None, validate=True)

    stage_names = tuple(stage.name for stage in pipeline.stages)
    assert stage_names[:4] == ("analysis", "extraction", "transformation", "organization")
    assert "linking" in stage_names
    assert stage_names[-1] == "quality"


def test_run_process_workflow_generates_documents_and_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "prince"
    source_dir.mkdir()
    kb_root = tmp_path / "kb"
    metrics_path = tmp_path / "metrics.json"

    _write_markdown(source_dir / "segment.md", page=1, body="Virtue guides the prince toward stable rule.")

    bundle = _bundle_with_concept_and_entity(str(source_dir))

    def fake_extract_all(self, text, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, config, source_path, progress_callback
        return bundle

    def fake_extract_selective(self, text, extractors, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, extractors, config, source_path, progress_callback
        return bundle

    monkeypatch.setattr(ExtractionCoordinator, "extract_all", fake_extract_all)
    monkeypatch.setattr(ExtractionCoordinator, "extract_selective", fake_extract_selective)

    config = PipelineConfig.from_mapping(
        {
            "pipeline": {
                "extraction": {"enabled_tools": ("concepts", "entities")},
                "transformation": {"primary_topic": "statecraft"},
                "organization": {
                    "collision_strategy": "replace",
                    "index_generation": "manual",
                },
                "linking": {"build_concept_graph": False, "generate_backlinks": False},
                "quality": {"validate_on_creation": False},
            },
            "monitoring": {"metrics_output": str(metrics_path)},
        }
    )

    options = ProcessOptions(
        source_path=source_dir,
        kb_root=kb_root,
        mission_path=None,
        extractors=None,
        validate=False,
        metrics_path=None,
    )

    result = run_process_workflow(options, config=config, mission=None)

    assert result.success
    assert result.warnings == ()
    assert not result.errors
    assert metrics_path.exists()

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert "analysis.segments" in payload["metrics"]
    assert payload["metrics"]["organization.documents"] >= 1

    created_files = sorted(str(path.relative_to(kb_root)) for path in kb_root.rglob("*.md"))
    assert any(path.startswith("concepts/statecraft/") for path in created_files)


def test_run_update_workflow_refreshes_target_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "prince"
    source_dir.mkdir()
    kb_root = tmp_path / "kb"
    metrics_path = tmp_path / "update-metrics.json"

    _write_markdown(source_dir / "segment.md", page=1, body="Virtue guides the prince toward stable rule.")

    initial_bundle = _bundle_with_concept_and_entity(str(source_dir), concept_frequency=3)
    updated_bundle = _bundle_with_concept_and_entity(str(source_dir), concept_frequency=7)

    def fake_extract_all_initial(self, text, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, config, source_path, progress_callback
        return initial_bundle

    def fake_extract_selective_initial(self, text, extractors, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, extractors, config, source_path, progress_callback
        return initial_bundle

    monkeypatch.setattr(ExtractionCoordinator, "extract_all", fake_extract_all_initial)
    monkeypatch.setattr(ExtractionCoordinator, "extract_selective", fake_extract_selective_initial)

    config = PipelineConfig.from_mapping(
        {
            "pipeline": {
                "extraction": {"enabled_tools": ("concepts", "entities")},
                "transformation": {"primary_topic": "statecraft"},
                "organization": {"collision_strategy": "replace", "index_generation": "manual"},
                "linking": {"build_concept_graph": False, "generate_backlinks": False},
                "quality": {"validate_on_creation": False},
            },
            "monitoring": {},
        }
    )

    process_options = ProcessOptions(
        source_path=source_dir,
        kb_root=kb_root,
        mission_path=None,
        extractors=None,
        validate=False,
        metrics_path=None,
    )

    process_result = run_process_workflow(process_options, config=config, mission=None)
    assert process_result.success

    concept_path = (kb_root / "concepts" / "statecraft" / "virtue.md").resolve()
    assert concept_path.exists()
    initial_contents = concept_path.read_text(encoding="utf-8")
    assert "**Frequency:** 3" in initial_contents

    def fake_extract_all_updated(self, text, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, config, source_path, progress_callback
        return updated_bundle

    def fake_extract_selective_updated(self, text, extractors, config, *, source_path=None, progress_callback=None):  # type: ignore[override]
        del self, text, extractors, config, source_path, progress_callback
        return updated_bundle

    monkeypatch.setattr(ExtractionCoordinator, "extract_all", fake_extract_all_updated)
    monkeypatch.setattr(ExtractionCoordinator, "extract_selective", fake_extract_selective_updated)

    update_options = UpdateOptions(
        kb_id="concepts/statecraft/virtue",
        source_path=source_dir,
        kb_root=kb_root,
        mission_path=None,
        extractors=None,
        validate=False,
        reextract=True,
        rebuild_links=False,
        metrics_path=metrics_path,
    )

    update_result = run_update_workflow(update_options, config=config, mission=None)

    assert update_result.success
    assert update_result.warnings == ()
    assert update_result.errors == ()
    assert update_result.context.extra["update"]["existing_document"]["path"] == concept_path
    assert metrics_path.exists()

    updated_contents = concept_path.read_text(encoding="utf-8")
    assert "**Frequency:** 7" in updated_contents


def test_run_improve_workflow_generates_report_and_updates_backlinks(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    virtue_front = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": "concepts/statecraft/virtue",
        "type": "concept",
        "related_concepts": ["concepts/statecraft/fortune"],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": [],
            "findability_score": 0.4,
            "completeness": 0.5,
        },
        "sources": [],
    }
    fortune_front = {
        "title": "Fortune",
        "slug": "fortune",
        "kb_id": "concepts/statecraft/fortune",
        "type": "concept",
        "tags": ["statecraft"],
        "related_concepts": [],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "fortune"],
            "related_by_topic": [],
            "findability_score": 0.55,
            "completeness": 0.6,
        },
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [1]},
        ],
    }

    _write_kb_document(kb_root, "concepts/statecraft/virtue", virtue_front, "Virtue body.")
    fortune_path = _write_kb_document(kb_root, "concepts/statecraft/fortune", fortune_front, "Fortune body.")

    report_path = tmp_path / "improvement-report.json"

    result = run_improve_workflow(
        ImproveOptions(
            kb_root=kb_root,
            fix_links=True,
            suggest_tags=True,
            report_path=report_path,
        ),
        config=_pipeline_config_with_defaults(),
    )

    assert result.metrics["gaps_total"] >= 1.0
    assert any("backlinks" in fix for fix in result.fixes_applied)
    assert report_path.exists()

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "gaps" in report_payload
    assert report_payload["metrics"]["gaps_total"] == result.metrics["gaps_total"]

    text = fortune_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    end_index = lines.index("---", 1)
    fortune_front_after = yaml.safe_load("\n".join(lines[1:end_index]))
    ia_section = fortune_front_after.get("ia", {}) if isinstance(fortune_front_after, dict) else {}
    backlinks = tuple(ia_section.get("related_by_topic", ())) if isinstance(ia_section, dict) else ()
    assert "concepts/statecraft/virtue" in backlinks


def test_run_quality_report_workflow_generates_metrics(tmp_path: Path) -> None:
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
            "findability_score": 0.75,
            "completeness": 0.82,
        },
    }
    _write_kb_document(
        kb_root,
        "concepts/statecraft/virtue",
        virtue_front,
        ("Virtue balances fortune and prudence. " * 10).strip(),
    )

    broken_path = kb_root / "concepts" / "statecraft" / "broken.md"
    broken_path.parent.mkdir(parents=True, exist_ok=True)
    broken_path.write_text("Broken document with no front matter\n", encoding="utf-8")

    output_path = tmp_path / "quality-report.json"

    result = run_quality_report_workflow(
        QualityReportOptions(kb_root=kb_root, output_path=output_path),
        config=_pipeline_config_with_defaults(),
    )

    assert result.documents_total == 1
    assert result.document_types == {"concept": 1}
    assert result.metrics["completeness"]["mean"] >= 0.8
    assert result.metrics["findability"]["mean"] >= 0.75
    assert isinstance(result.gaps, tuple)
    assert result.invalid_documents, "expected invalid documents to be reported"
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["documents"]["total"] == result.documents_total
    assert payload["gaps"]["counts"]["total"] == result.gap_counts["total"]


def test_run_export_graph_workflow_creates_files(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    virtue_front = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": "concepts/statecraft/virtue",
        "type": "concept",
        "tags": ["statecraft"],
        "related_concepts": ["concepts/statecraft/fortune"],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [1]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": [],
            "findability_score": 0.8,
            "completeness": 0.85,
        },
    }
    fortune_front = {
        "title": "Fortune",
        "slug": "fortune",
        "kb_id": "concepts/statecraft/fortune",
        "type": "concept",
        "tags": ["statecraft"],
        "related_concepts": ["concepts/statecraft/virtue"],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-2", "pages": [2]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "fortune"],
            "related_by_topic": ["concepts/statecraft/virtue"],
            "findability_score": 0.78,
            "completeness": 0.82,
        },
    }

    _write_kb_document(kb_root, "concepts/statecraft/virtue", virtue_front, "Virtue body.")
    _write_kb_document(kb_root, "concepts/statecraft/fortune", fortune_front, "Fortune body.")

    json_output = tmp_path / "graph.json"
    graphml_output = tmp_path / "graph.graphml"

    result_json = run_export_graph_workflow(
        ExportGraphOptions(
            kb_root=kb_root,
            output_path=json_output,
            format="json",
        ),
        config=_pipeline_config_with_defaults(),
    )

    assert json_output.exists()
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["concepts"]
    assert payload["edges"]

    result_graphml = run_export_graph_workflow(
        ExportGraphOptions(
            kb_root=kb_root,
            output_path=graphml_output,
            format="graphml",
        ),
        config=_pipeline_config_with_defaults(),
    )

    assert graphml_output.exists()
    graphml_text = graphml_output.read_text(encoding="utf-8")
    assert "<graphml" in graphml_text

    assert result_json.nodes == result_graphml.nodes
    assert result_json.edges == result_graphml.edges


def test_run_process_workflow_requires_existing_source(tmp_path: Path) -> None:
    options = ProcessOptions(
        source_path=tmp_path / "missing-source",
        kb_root=tmp_path / "kb",
        mission_path=None,
    )

    with pytest.raises(FileNotFoundError):
        run_process_workflow(options, config=_pipeline_config_with_defaults())


def test_run_update_workflow_requires_existing_source(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    virtue_front = {
        "title": "Virtue",
        "slug": "virtue",
        "kb_id": "concepts/statecraft/virtue",
        "type": "concept",
        "tags": ["statecraft"],
        "related_concepts": [],
        "sources": [
            {"kb_id": "sources/the-prince/chapter-1", "pages": [1]},
        ],
        "ia": {
            "navigation_path": ["concepts", "statecraft", "virtue"],
            "related_by_topic": [],
            "findability_score": 0.75,
            "completeness": 0.8,
        },
    }
    _write_kb_document(kb_root, "concepts/statecraft/virtue", virtue_front, "Virtue body.")

    options = UpdateOptions(
        kb_id="concepts/statecraft/virtue",
        source_path=tmp_path / "missing-source",
        kb_root=kb_root,
        mission_path=None,
    )

    with pytest.raises(FileNotFoundError):
        run_update_workflow(options, config=_pipeline_config_with_defaults())