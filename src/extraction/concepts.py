"""Concept extraction utilities."""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Mapping

from . import ExtractedConcept, ExtractionResult

__all__ = ["extract_concepts"]

_TOKEN_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z\-']{1,})\b")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def _coerce_int(value: object, default: int, *, minimum: int = 1) -> int:
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return coerced if coerced >= minimum else default


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def extract_concepts(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Detect concepts and high-signal terms using lightweight heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))

    min_frequency = _coerce_int(config_map.get("min_frequency"), 2)
    max_concepts = _coerce_int(config_map.get("max_concepts"), 50, minimum=1)
    window_size = _coerce_int(config_map.get("window_size"), 4)
    max_related_terms = _coerce_int(config_map.get("max_related_terms"), 5, minimum=0)
    min_term_length = _coerce_int(config_map.get("min_term_length"), 3)
    exclude_stopwords = _coerce_bool(config_map.get("exclude_stopwords"), True)

    token_infos: list[tuple[str, str, int]] = []
    for match in _TOKEN_PATTERN.finditer(text):
        original = match.group(1)
        normalized = original.lower()
        if len(normalized) < min_term_length:
            continue
        if exclude_stopwords and normalized in _STOPWORDS:
            continue
        token_infos.append((normalized, original, match.start(1)))

    frequency: Counter[str] = Counter()
    positions: dict[str, list[int]] = defaultdict(list)
    forms: dict[str, Counter[str]] = defaultdict(Counter)
    co_occurrence: dict[str, Counter[str]] = defaultdict(Counter)

    for index, (term, original, start) in enumerate(token_infos):
        frequency[term] += 1
        positions[term].append(start)
        forms[term][original] += 1
        window_end = min(len(token_infos), index + 1 + window_size)
        for _, other_original, _ in token_infos[index + 1 : window_end]:
            other_term = other_original.lower()
            if other_term == term:
                continue
            co_occurrence[term][other_term] += 1
            co_occurrence[other_term][term] += 1

    candidates: list[ExtractedConcept] = []
    for term, count in frequency.items():
        if count < min_frequency:
            continue
        display_term = forms[term].most_common(1)[0][0]
        related_counter = co_occurrence.get(term, Counter())
        related_terms: list[str] = []
        if related_counter:
            for related_term, _ in related_counter.most_common():
                if related_term == term:
                    continue
                related_display = forms.get(related_term, Counter()).most_common(1)
                label = related_display[0][0] if related_display else related_term
                if label not in related_terms:
                    related_terms.append(label)
                if len(related_terms) >= max_related_terms:
                    break
        candidates.append(
            ExtractedConcept(
                term=display_term,
                frequency=count,
                positions=tuple(positions[term]),
                related_terms=tuple(related_terms),
            )
        )

    candidates.sort(
        key=lambda concept: (
            -concept.frequency,
            concept.positions[0] if concept.positions else 0,
            concept.term.lower(),
        )
    )

    if len(candidates) > max_concepts:
        candidates = candidates[:max_concepts]

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        "total_candidates": len(frequency),
        "selected_concepts": len(candidates),
        "source_path": source_path,
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="concepts",
        data=tuple(candidates),
        metadata=metadata,
    )
