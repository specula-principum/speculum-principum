"""Taxonomy classification utilities."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Mapping

from . import ExtractionResult

__all__ = ["assign_taxonomy"]

_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")

_DEFAULT_TAXONOMY: dict[str, tuple[str, ...]] = {
    "governance": (
        "govern",
        "rule",
        "council",
        "prince",
        "sovereign",
        "laws",
        "state",
        "policy",
    ),
    "military": (
        "army",
        "fort",
        "battle",
        "defend",
        "troop",
        "strategy",
        "campaign",
        "garrison",
    ),
    "diplomacy": (
        "treaty",
        "envoy",
        "alliance",
        "embassy",
        "negotiation",
        "accord",
        "pact",
    ),
    "economy": (
        "treasury",
        "tax",
        "trade",
        "coin",
        "finance",
        "commerce",
        "revenue",
    ),
    "virtue": (
        "virtue",
        "prudence",
        "honor",
        "justice",
        "wisdom",
        "mercy",
        "temperance",
    ),
}


def _normalize_categories(categories: Mapping[str, Iterable[str]] | None) -> dict[str, tuple[str, ...]]:
    if not categories:
        return _DEFAULT_TAXONOMY
    normalized: dict[str, tuple[str, ...]] = {}
    for label, keywords in categories.items():
        terms: list[str] = []
        for keyword in keywords:
            term = str(keyword).strip().lower()
            if term:
                terms.append(term)
        if terms:
            normalized[str(label)] = tuple(dict.fromkeys(terms))
    return normalized or _DEFAULT_TAXONOMY


def _coerce_int(value: object, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        return minimum
    if maximum is not None and coerced > maximum:
        return maximum
    return coerced


def _coerce_float(value: object, default: float, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    try:
        coerced = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        return minimum
    if maximum is not None and coerced > maximum:
        return maximum
    return coerced


def assign_taxonomy(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Assign taxonomy labels based on keyword heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    categories_config = config_map.get("categories")
    categories_mapping = categories_config if isinstance(categories_config, Mapping) else None
    categories = _normalize_categories(categories_mapping)

    max_labels = _coerce_int(config_map.get("max_labels"), 5, minimum=1, maximum=len(categories))
    min_score = _coerce_float(config_map.get("min_score"), 0.05, minimum=0.0, maximum=1.0)
    bonus_weight = _coerce_float(config_map.get("bonus_weight"), 0.05, minimum=0.0, maximum=1.0)

    text_lower = text.lower()
    words = _WORD_PATTERN.findall(text_lower)
    total_words = len(words) or 1

    category_scores: list[tuple[str, float, tuple[str, ...]]] = []
    for label, keywords in categories.items():
        matched: dict[str, int] = {}
        score = 0.0
        for keyword in keywords:
            occurrences = len(re.findall(rf"\b{re.escape(keyword)}\b", text_lower))
            if occurrences:
                matched[keyword] = occurrences
                score += occurrences / total_words
        if matched:
            # reward diversity of keywords to disambiguate dense passages
            score += min(len(matched), 5) * bonus_weight
        category_scores.append((label, score, tuple(sorted(matched))))
    category_scores.sort(key=lambda item: (-item[1], item[0]))

    selected = []
    for label, score, matched_keywords in category_scores[:max_labels]:
        if score < min_score:
            continue
        selected.append(
            {
                "label": label,
                "score": round(score, 3),
                "matched_keywords": matched_keywords,
                "keyword_count": len(matched_keywords),
            }
        )

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        "source_path": source_path,
        "evaluated_categories": len(categories),
        "detected_categories": len(selected),
        "config": config_map,
    }

    data: dict[str, object] = {
        "labels": tuple(selected),
        "total_words": total_words,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="taxonomy",
        data=data,
        metadata=metadata,
    )
