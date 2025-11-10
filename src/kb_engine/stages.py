"""Pipeline stage implementations for the knowledge base engine."""
from __future__ import annotations

from typing import Iterable, TypeVar

from .links import LinkBuilder
from .models import ProcessingContext, QualityGap, StageResult
from .quality import QualityAnalyzer


class LinkingStage:
    """Pipeline stage that builds concept graphs and backlinks."""

    name = "linking"

    def __init__(self, builder: LinkBuilder | None = None) -> None:
        self._builder = builder or LinkBuilder()

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:  # noqa: D401
        del previous
        graph = self._builder.build_concept_graph(context.kb_root)
        updated_backlinks = self._builder.generate_backlinks(context.kb_root)

        metrics = {
            "concepts": float(len(graph.concepts)),
            "edges": float(len(graph.edges)),
            "backlinks_updated": float(len(updated_backlinks)),
        }

        notes: list[str] = []
        for edge in graph.edges[:3]:
            notes.append(f"edge:{edge.source}->{edge.target}")
        for kb_id in updated_backlinks[:3]:
            notes.append(f"backlink-updated:{kb_id}")

        return StageResult(stage=self.name, metrics=metrics, notes=tuple(notes))


class QualityStage:
    """Pipeline stage that evaluates knowledge base quality."""

    name = "quality"

    def __init__(self, analyzer: QualityAnalyzer | None = None) -> None:
        self._analyzer = analyzer or QualityAnalyzer()

    def run(self, context: ProcessingContext, previous: tuple[StageResult, ...]) -> StageResult:  # noqa: D401
        del previous
        gaps: tuple[QualityGap, ...] = tuple(self._analyzer.identify_gaps(context.kb_root))
        error_count = sum(1 for gap in gaps if gap.severity == "error")
        warning_count = sum(1 for gap in gaps if gap.severity == "warning")

        metrics = {
            "gaps_total": float(len(gaps)),
            "gaps_errors": float(error_count),
            "gaps_warnings": float(warning_count),
        }

        notes: list[str] = []
        for gap in _take(gaps, 3):
            notes.append(f"gap:{gap.severity}:{gap.issue}:{gap.kb_id}")

        return StageResult(stage=self.name, metrics=metrics, notes=tuple(notes))


_T = TypeVar("_T")


def _take(items: Iterable[_T], limit: int) -> list[_T]:
    collected: list[_T] = []
    for item in items:
        collected.append(item)
        if len(collected) >= limit:
            break
    return collected


__all__ = ["LinkingStage", "QualityStage"]
