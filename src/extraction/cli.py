"""Extractor registry utilities used by the CLI."""
from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from . import ExtractionResult

__all__ = [
    "EXTRACTOR_REGISTRY",
    "available_extractors",
    "load_extractor",
    "run_extractor",
]

EXTRACTOR_REGISTRY: dict[str, tuple[str, str]] = {
    "segments": ("src.extraction.segments", "segment_text"),
    "entities": ("src.extraction.entities", "extract_entities"),
    "structure": ("src.extraction.structure", "analyze_structure"),
    "concepts": ("src.extraction.concepts", "extract_concepts"),
    "relationships": ("src.extraction.relationships", "extract_relationships"),
    "metadata": ("src.extraction.metadata", "generate_metadata"),
    "taxonomy": ("src.extraction.taxonomy", "assign_taxonomy"),
    "linking": ("src.extraction.linking", "generate_links"),
    "summarization": ("src.extraction.summarization", "summarize"),
}


def available_extractors() -> tuple[str, ...]:
    """Return the supported extractor keys in alphabetical order."""

    return tuple(sorted(EXTRACTOR_REGISTRY))


def load_extractor(name: str) -> Callable[..., ExtractionResult]:
    """Load the configured extractor callable for the provided name."""

    try:
        module_name, attr = EXTRACTOR_REGISTRY[name]
    except KeyError as exc:  # pragma: no cover - defensive guard until implemented
        raise ValueError(f"Unknown extractor: {name}") from exc
    module = importlib.import_module(module_name)
    try:
        extractor: Callable[..., ExtractionResult] = getattr(module, attr)
    except AttributeError as exc:  # pragma: no cover - defensive guard until implemented
        raise ValueError(f"Extractor '{name}' is misconfigured: missing attribute {attr}") from exc
    return extractor


def run_extractor(name: str, *args: Any, **kwargs: Any) -> ExtractionResult:
    """Execute an extractor by name."""

    extractor = load_extractor(name)
    return extractor(*args, **kwargs)
