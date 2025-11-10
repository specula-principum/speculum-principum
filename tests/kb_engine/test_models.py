"""Unit tests for kb_engine models."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.kb_engine.models import (
    DocumentArtifact,
    KBProcessingResult,
    KBQualityReportResult,
    PipelineErrorDetail,
    ProcessingContext,
    QualityGap,
    StageResult,
)


def test_processing_context_ensure_paths_valid(tmp_path: Path) -> None:
    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    mission = tmp_path / "mission.yaml"
    source.mkdir()
    kb_root.mkdir()
    mission.touch()

    context = ProcessingContext(
        source_path=source,
        kb_root=kb_root,
        mission_config=mission,
        extractors=("concepts", "entities"),
        validate=True,
        extra={"run_id": "123"},
    )

    context.ensure_paths()


def test_processing_context_ensure_paths_missing(tmp_path: Path) -> None:
    source = tmp_path / "missing-source"
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    context = ProcessingContext(source_path=source, kb_root=kb_root)

    with pytest.raises(FileNotFoundError) as exc:
        context.ensure_paths()
    assert "source_path" in str(exc.value)


def test_processing_context_with_extra_merges(tmp_path: Path) -> None:
    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    source.mkdir()
    kb_root.mkdir()

    context = ProcessingContext(source_path=source, kb_root=kb_root, extra={"seed": "alpha"})
    extended = context.with_extra(run_id="123", seed="beta")

    assert extended.extra == {"seed": "beta", "run_id": "123"}
    assert context.extra == {"seed": "alpha"}


def test_kb_processing_result_collect_metrics(tmp_path: Path) -> None:
    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    source.mkdir()
    kb_root.mkdir()

    context = ProcessingContext(source_path=source, kb_root=kb_root)
    stage_a = StageResult(stage="analysis", metrics={"duration": 1.5})
    stage_b = StageResult(stage="extraction", metrics={"items": 20})
    result = KBProcessingResult(context=context, stages=(stage_a, stage_b))

    metrics = result.collect_metrics()
    assert metrics == {"analysis.duration": 1.5, "extraction.items": 20}


def test_document_artifact_metadata_is_copied(tmp_path: Path) -> None:
    document_path = tmp_path / "concept.md"
    metadata = {"quality": 0.9}

    artifact = DocumentArtifact(kb_id="concepts/statecraft", path=document_path, doc_type="concept", metadata=metadata)

    metadata["quality"] = 0.5
    assert artifact.metadata["quality"] == 0.9


def test_pipeline_error_detail_requires_identifiers() -> None:
    detail = PipelineErrorDetail(stage="analysis", error_type="ValueError", message="invalid data")
    assert detail.stage == "analysis"
    assert detail.error_type == "ValueError"
    assert detail.message == "invalid data"

    with pytest.raises(ValueError):
        PipelineErrorDetail(stage="", error_type="ValueError", message="missing stage")

    with pytest.raises(ValueError):
        PipelineErrorDetail(stage="analysis", error_type="", message="missing type")


def test_kb_quality_report_result_normalises_sequences(tmp_path: Path) -> None:
    gap = QualityGap(kb_id="concepts/statecraft/virtue", issue="missing-tags", severity="warning", details={})
    report_path = tmp_path / "quality.json"
    generated_at = datetime.utcnow()

    result = KBQualityReportResult(
        kb_root=tmp_path,
        output_path=report_path,
        generated_at=generated_at,
        documents_total=2,
        document_types={"concept": 2},
        metrics={"completeness": {"mean": 0.8, "missing": 0.0}},
        gap_counts={"total": 1, "warning": 1},
        gaps=(gap,),
        invalid_documents=[{"path": "broken.md", "reason": "missing front matter"}],
    )

    assert result.document_types == {"concept": 2}
    assert isinstance(result.gaps, tuple)
    assert isinstance(result.invalid_documents, tuple)
    assert not result.success
