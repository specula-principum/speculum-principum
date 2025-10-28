"""Unit tests for the KBPipeline orchestrator."""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest

from src.kb_engine.models import (
    DocumentArtifact,
    KBUpdateResult,
    PipelineStage,
    PipelineStageError,
    ProcessingContext,
    StageResult,
)
from src.kb_engine.pipeline import KBPipeline


class DummyStage:
    """Simple pipeline stage used for orchestration tests."""

    def __init__(self, name: str, *, warnings: Tuple[str, ...] = (), add_artifact: bool = False) -> None:
        self.name = name
        self.warnings = warnings
        self.add_artifact = add_artifact

    def run(self, context: ProcessingContext, previous: Tuple[StageResult, ...]) -> StageResult:
        notes = (f"received {len(previous)} previous results",)
        artifacts: tuple[DocumentArtifact, ...] = ()
        if self.add_artifact:
            artifacts = (
                DocumentArtifact(
                    kb_id=f"{self.name}/doc",
                    path=context.kb_root / f"{self.name}.md",
                    doc_type="concept",
                    metadata={"stage": self.name},
                ),
            )
        return StageResult(stage=self.name, artifacts=artifacts, notes=notes, warnings=self.warnings)


class FailingStage:
    name = "failing"

    def run(self, context: ProcessingContext, previous: Tuple[StageResult, ...]) -> StageResult:
        raise PipelineStageError("boom")


@pytest.fixture()
def pipeline_context(tmp_path: Path) -> ProcessingContext:
    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    source.mkdir()
    kb_root.mkdir()
    return ProcessingContext(source_path=source, kb_root=kb_root)


def test_pipeline_runs_stages_in_order(pipeline_context: ProcessingContext) -> None:
    stages: tuple[PipelineStage, ...] = (
        DummyStage("analysis"),
        DummyStage("extraction", add_artifact=True),
    )
    pipeline = KBPipeline(stages)

    result = pipeline.run_with_context(pipeline_context)

    assert [stage.stage for stage in result.stages] == ["analysis", "extraction"]
    assert result.success is True
    assert len(result.stages[1].artifacts) == 1
    assert "duration_seconds" in result.stages[0].metrics
    assert not result.error_details


def test_pipeline_stops_on_stage_error(pipeline_context: ProcessingContext) -> None:
    stages: tuple[PipelineStage, ...] = (
        DummyStage("analysis"),
        FailingStage(),
        DummyStage("transformation"),
    )
    pipeline = KBPipeline(stages)

    result = pipeline.run_with_context(pipeline_context)

    assert result.success is False
    assert result.errors == ("failing (PipelineStageError): boom",)
    assert [stage.stage for stage in result.stages] == ["analysis"]
    assert result.error_details
    detail = result.error_details[0]
    assert detail.stage == "failing"
    assert detail.error_type == "PipelineStageError"
    assert "boom" in detail.message


def test_process_source_builds_context(tmp_path: Path) -> None:
    stages: tuple[PipelineStage, ...] = (DummyStage("analysis"),)
    pipeline = KBPipeline(stages)

    source = tmp_path / "source"
    kb_root = tmp_path / "kb"
    source.mkdir()
    kb_root.mkdir()

    result = pipeline.process_source(source, kb_root=kb_root, extractors=["concepts"], validate=True, extra={"run": "1"})

    assert result.context.extractors == ("concepts",)
    assert result.context.validate is True
    assert result.context.extra["run"] == "1"


def test_pipeline_requires_stages() -> None:
    with pytest.raises(ValueError):
        KBPipeline(())


def test_update_existing_wraps_pipeline_result(pipeline_context: ProcessingContext) -> None:
    pipeline = KBPipeline((DummyStage("analysis"),))

    result = pipeline.update_existing("concepts/test", context=pipeline_context)

    assert isinstance(result, KBUpdateResult)
    assert result.kb_id == "concepts/test"
    assert result.success is True
    assert result.context.extra["update"]["target_kb_id"] == "concepts/test"
    assert not result.error_details


def test_rebuild_indexes_placeholder(pipeline_context: ProcessingContext) -> None:
    pipeline = KBPipeline((DummyStage("analysis"),))

    with pytest.raises(NotImplementedError):
        pipeline.rebuild_indexes(pipeline_context.kb_root)