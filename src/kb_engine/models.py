"""Core models for the knowledge base engine pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, Tuple, runtime_checkable


@dataclass(frozen=True, slots=True)
class ProcessingContext:
    """Execution context shared across pipeline stages."""

    source_path: Path
    kb_root: Path
    mission_config: Path | None = None
    validate: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra", dict(self.extra))

    def ensure_paths(self) -> None:
        """Ensure required paths exist on disk."""

        missing: list[str] = []
        if not self.source_path.exists():
            missing.append(f"source_path '{self.source_path}'")
        if not self.kb_root.exists():
            missing.append(f"kb_root '{self.kb_root}'")
        if self.mission_config is not None and not self.mission_config.exists():
            missing.append(f"mission_config '{self.mission_config}'")
        if missing:
            raise FileNotFoundError(", ".join(missing))

    def with_extra(self, **kwargs: Any) -> "ProcessingContext":
        """Return a copy of the context with merged extra metadata."""

        merged = {**self.extra, **kwargs}
        return ProcessingContext(
            source_path=self.source_path,
            kb_root=self.kb_root,
            mission_config=self.mission_config,
            validate=self.validate,
            extra=merged,
        )


@dataclass(frozen=True, slots=True)
class DocumentArtifact:
    """Representation of a knowledge base document produced by the pipeline."""

    kb_id: str
    path: Path
    doc_type: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class StageResult:
    """Outcome produced by a single pipeline stage."""

    stage: str
    artifacts: Sequence[DocumentArtifact] = field(default_factory=tuple)
    metrics: Mapping[str, float] = field(default_factory=dict)
    notes: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class KBProcessingResult:
    """Aggregate result produced after running the pipeline."""

    context: ProcessingContext
    stages: Sequence[StageResult] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    errors: Sequence[str] = field(default_factory=tuple)
    error_details: Sequence["PipelineErrorDetail"] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "error_details", tuple(self.error_details))

    @property
    def success(self) -> bool:
        """True when no errors were recorded."""

        return not self.errors

    def collect_metrics(self) -> dict[str, float]:
        """Return a flattened mapping of stage metrics."""

        aggregated: dict[str, float] = {}
        for stage in self.stages:
            for key, value in stage.metrics.items():
                aggregated[f"{stage.stage}.{key}"] = value
        return aggregated


@dataclass(frozen=True, slots=True)
class KBUpdateResult:
    """Result for an incremental update operation."""

    kb_id: str
    context: ProcessingContext
    stages: Sequence[StageResult] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    errors: Sequence[str] = field(default_factory=tuple)
    error_details: Sequence["PipelineErrorDetail"] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "error_details", tuple(self.error_details))

    @property
    def success(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class KBIndexRebuildResult:
    """Result information for index rebuild operations."""

    kb_root: Path
    indexes: Sequence[Path] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "indexes", tuple(self.indexes))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class QualityGap:
    """Represents a quality issue discovered during analysis."""

    kb_id: str
    issue: str
    severity: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kb_id:
            raise ValueError("kb_id is required for QualityGap")
        if not self.issue:
            raise ValueError("issue is required for QualityGap")
        if not self.severity:
            raise ValueError("severity is required for QualityGap")
        object.__setattr__(self, "details", dict(self.details))


class PipelineStageError(RuntimeError):
    """Error raised when a pipeline stage fails in an unexpected way."""


@runtime_checkable
class PipelineStage(Protocol):
    """Protocol for pipeline stages that operate on a processing context."""

    name: str

    def run(
        self,
        context: ProcessingContext,
        previous: Tuple[StageResult, ...],
    ) -> StageResult:
        """Execute the stage and return its result."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class KBImprovementResult:
    """Aggregated outcome for quality improvement passes."""

    kb_root: Path
    gaps: Sequence[QualityGap] = field(default_factory=tuple)
    fixes_applied: Sequence[str] = field(default_factory=tuple)
    suggestions: Mapping[str, Sequence[str]] = field(default_factory=dict)
    metrics: Mapping[str, float] = field(default_factory=dict)
    report_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "gaps", tuple(self.gaps))
        object.__setattr__(self, "fixes_applied", tuple(self.fixes_applied))
        object.__setattr__(self, "suggestions", {key: tuple(value) for key, value in self.suggestions.items()})
        object.__setattr__(self, "metrics", dict(self.metrics))

    @property
    def success(self) -> bool:
        return not any(gap.severity == "error" for gap in self.gaps)


@dataclass(frozen=True, slots=True)
class KBGraphExportResult:
    """Summary of exported knowledge graph artifacts."""

    kb_root: Path
    output_path: Path
    format: str
    nodes: int
    edges: int

    @property
    def success(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class PipelineErrorDetail:
    """Structured metadata describing an error raised during pipeline execution."""

    stage: str
    error_type: str
    message: str
    traceback: str | None = None

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("stage is required for PipelineErrorDetail")
        if not self.error_type:
            raise ValueError("error_type is required for PipelineErrorDetail")


@dataclass(frozen=True, slots=True)
class KBQualityReportResult:
    """Aggregated metrics produced by the quality report workflow."""

    kb_root: Path
    output_path: Path
    generated_at: datetime
    documents_total: int
    document_types: Mapping[str, int]
    metrics: Mapping[str, Mapping[str, float]]
    gap_counts: Mapping[str, int]
    gaps: Sequence[QualityGap]
    invalid_documents: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_types", dict(self.document_types))
        object.__setattr__(self, "metrics", {key: dict(value) for key, value in self.metrics.items()})
        object.__setattr__(self, "gap_counts", dict(self.gap_counts))
        object.__setattr__(self, "gaps", tuple(self.gaps))
        object.__setattr__(self, "invalid_documents", tuple(dict(item) for item in self.invalid_documents))

    @property
    def success(self) -> bool:
        return not self.gap_counts.get("error") and not self.invalid_documents