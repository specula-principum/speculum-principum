"""Pipeline orchestration for the knowledge base engine."""
from __future__ import annotations

import logging
import traceback
from pathlib import Path
from time import perf_counter
from typing import Iterable, Mapping, Sequence

from .models import (
    KBIndexRebuildResult,
    KBProcessingResult,
    KBUpdateResult,
    PipelineStage,
    PipelineStageError,
    ProcessingContext,
    PipelineErrorDetail,
    StageResult,
)

logger = logging.getLogger(__name__)


class KBPipeline:
    """Orchestrates the extraction-to-knowledge-base workflow."""

    def __init__(self, stages: Sequence[PipelineStage], *, name: str = "kb-pipeline") -> None:
        if not stages:
            raise ValueError("KBPipeline requires at least one stage")
        self._stages: tuple[PipelineStage, ...] = tuple(stages)
        self.name = name

    @property
    def stages(self) -> tuple[PipelineStage, ...]:
        """Registered pipeline stages in execution order."""

        return self._stages

    def process_source(
        self,
        source_path: Path,
        *,
        kb_root: Path,
        mission_config: Path | None = None,
        extractors: Iterable[str] | None = None,
        validate: bool = False,
        extra: Mapping[str, object] | None = None,
    ) -> KBProcessingResult:
        """Run the pipeline for a new source document."""

        context = ProcessingContext(
            source_path,
            kb_root,
            mission_config,
            tuple(extractors or ()),
            validate,
            dict(extra or {}),
        )
        context.ensure_paths()
        return self._execute(context)

    def run_with_context(self, context: ProcessingContext) -> KBProcessingResult:
        """Execute the pipeline with an existing context object."""

        context.ensure_paths()
        return self._execute(context)

    def update_existing(
        self,
        kb_id: str,
        *,
        context: ProcessingContext | None = None,
        source_path: Path | None = None,
    ) -> KBUpdateResult:
        """Refresh an existing KB entry with new analysis."""

        if context is None:
            raise ValueError("update_existing requires a ProcessingContext instance")

        effective_source = source_path or context.source_path
        extra = dict(context.extra)
        update_section = dict(extra.get("update", {}))
        update_section["target_kb_id"] = kb_id
        extra["update"] = update_section

        update_context = ProcessingContext(
            effective_source,
            context.kb_root,
            context.mission_config,
            context.extractors,
            context.validate,
            extra,
        )

        update_context.ensure_paths()
        processing_result = self._execute(update_context)

        return KBUpdateResult(
            kb_id=kb_id,
            context=processing_result.context,
            stages=processing_result.stages,
            warnings=processing_result.warnings,
            errors=processing_result.errors,
            error_details=processing_result.error_details,
        )

    def rebuild_indexes(self, kb_root: Path) -> KBIndexRebuildResult:
        """Rebuild navigation indexes for a knowledge base root."""

        raise NotImplementedError("Index rebuild operations are not implemented yet")

    def _execute(self, context: ProcessingContext) -> KBProcessingResult:
        """Internal helper that executes all stages and aggregates results."""

        results: list[StageResult] = []
        warnings: list[str] = []
        errors: list[str] = []
        error_details: list[PipelineErrorDetail] = []

        for stage in self._stages:
            started = perf_counter()
            try:
                stage_result = stage.run(context, tuple(results))
            except PipelineStageError as exc:
                logger.warning("Pipeline stage '%s' terminated: %s", stage.name, exc)
                detail = self._build_error_detail(stage.name, exc)
                errors.append(f"{stage.name} ({detail.error_type}): {detail.message}")
                error_details.append(detail)
                break
            except Exception as exc:  # pragma: no cover - safety net  # noqa: BLE001  # pylint: disable=broad-except
                logger.exception("Unhandled error in stage '%s'", stage.name)
                detail = self._build_error_detail(stage.name, exc)
                errors.append(f"{stage.name} ({detail.error_type}): {detail.message}")
                error_details.append(detail)
                break

            duration = perf_counter() - started
            stage_result = self._attach_duration(stage_result, duration)

            results.append(stage_result)
            warnings.extend(stage_result.warnings)

        return KBProcessingResult(
            context=context,
            stages=tuple(results),
            warnings=tuple(warnings),
            errors=tuple(errors),
            error_details=tuple(error_details),
        )

    @staticmethod
    def _attach_duration(result: StageResult, duration: float) -> StageResult:
        metrics = dict(result.metrics)
        metrics.setdefault("duration_seconds", round(duration, 6))
        return StageResult(result.stage, result.artifacts, metrics, result.notes, result.warnings)

    @staticmethod
    def _build_error_detail(stage_name: str, exc: Exception) -> PipelineErrorDetail:
        error_type = exc.__class__.__name__
        message = str(exc) or error_type
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc.__traceback__ else None
        return PipelineErrorDetail(stage=stage_name, error_type=error_type, message=message, traceback=tb)
