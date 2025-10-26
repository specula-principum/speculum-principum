"""Summarization utilities."""
from __future__ import annotations

import hashlib
import heapq
import re
from typing import Mapping

from . import ExtractionResult

__all__ = ["summarize"]

_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]")
_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
_STOPWORDS = {
    "a",
    "an",
    "and",
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
    "or",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}


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


def summarize(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Summarize a document using frequency-based heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))

    default_max_length = _coerce_int(config_map.get("default_max_length", config_map.get("max_length")), 250, minimum=60)
    max_length = _coerce_int(config_map.get("max_length"), default_max_length, minimum=60)
    max_sentences = _coerce_int(config_map.get("max_sentences"), 5, minimum=1)
    min_sentence_length = _coerce_int(config_map.get("min_sentence_length"), 25, minimum=5)
    preserve_order = _coerce_bool(config_map.get("preserve_order"), True)
    include_highlights = _coerce_bool(config_map.get("include_highlights"), True)
    style = str(config_map.get("style", "abstract") or "abstract")

    raw_sentences = [match.group(0).strip() for match in _SENTENCE_PATTERN.finditer(text)]
    if not raw_sentences:
        normalized = " ".join(text.split())
        raw_sentences = [normalized] if normalized else []

    candidate_sentences: list[tuple[int, str]] = []
    for index, sentence in enumerate(raw_sentences):
        if len(sentence) < min_sentence_length:
            continue
        candidate_sentences.append((index, sentence))

    if not candidate_sentences and raw_sentences:
        candidate_sentences = list(enumerate(raw_sentences))

    frequencies: dict[str, int] = {}
    for _, sentence in candidate_sentences:
        for word in _WORD_PATTERN.findall(sentence.lower()):
            if word in _STOPWORDS or len(word) <= 2:
                continue
            frequencies[word] = frequencies.get(word, 0) + 1

    sentence_scores: list[tuple[float, int, str]] = []
    for index, sentence in candidate_sentences:
        score = 0.0
        for word in _WORD_PATTERN.findall(sentence.lower()):
            if word in _STOPWORDS or len(word) <= 2:
                continue
            score += frequencies.get(word, 0)
        sentence_scores.append((score, index, sentence))

    top_sentences: list[tuple[int, str]]
    if len(sentence_scores) <= max_sentences:
        top_sentences = [(index, sentence) for _, index, sentence in sentence_scores]
    else:
        best = heapq.nlargest(max_sentences, sentence_scores)
        top_sentences = [(index, sentence) for _, index, sentence in best]

    if preserve_order:
        top_sentences.sort(key=lambda item: item[0])
    else:
        def ranking(item: tuple[int, str]) -> tuple[int, int]:
            index, sentence_text = item
            words = _WORD_PATTERN.findall(sentence_text.lower())
            if not words:
                return (0, index)
            score = max(frequencies.get(word, 0) for word in words)
            return (-score, index)

        top_sentences.sort(key=ranking)

    summary_sentences: list[str] = []
    current_length = 0
    for _, sentence in top_sentences:
        if current_length + len(sentence) > max_length and summary_sentences:
            break
        summary_sentences.append(sentence)
        current_length += len(sentence)

    summary_text: str
    if style == "bullet":
        summary_text = "\n".join(f"- {sentence}" for sentence in summary_sentences)
    else:
        summary_text = " ".join(summary_sentences)

    highlights: tuple[str, ...] = ()
    if include_highlights and frequencies:
        sorted_keywords = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[:5]
        highlights = tuple(word for word, _ in sorted_keywords)

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()

    data: dict[str, object] = {
        "summary": summary_text,
        "summary_style": style,
        "sentences": tuple(sentence for _, sentence in top_sentences),
        "highlights": highlights,
    }

    metadata: dict[str, object] = {
        "source_path": source_path,
        "max_length": max_length,
        "selected_sentences": len(summary_sentences),
        "total_sentences": len(raw_sentences),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="summarization",
        data=data,
        metadata=metadata,
    )
