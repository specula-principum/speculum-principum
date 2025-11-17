"""Summarization utilities."""
from __future__ import annotations

import hashlib
import heapq
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

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
    "how",
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


def _coerce_sentences(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return tuple(part.strip() for part in value.splitlines() if part.strip())
    return ()


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


def _resolve_outputs_file(
    config_map: Mapping[str, object],
    source_path: str,
    key: str,
    *,
    default_name: str,
) -> Path | None:
    raw_value = config_map.get(key)
    candidates: list[Path] = []
    if isinstance(raw_value, str) and raw_value.strip():
        candidates.append(Path(raw_value).expanduser())
    elif isinstance(raw_value, (list, tuple)):
        for item in raw_value:
            token = str(item).strip()
            if token:
                candidates.append(Path(token).expanduser())

    if source_path not in {"", "<memory>"}:
        source_candidate = Path(source_path)
        if source_candidate.exists():
            outputs_dir = source_candidate.parent / "outputs"
            candidates.append(outputs_dir / default_name)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_taxonomy_labels(
    config_map: Mapping[str, object],
    source_path: str,
) -> tuple[dict[str, object], ...]:
    taxonomy_file = _resolve_outputs_file(config_map, source_path, "taxonomy_path", default_name="taxonomy.json")
    if taxonomy_file is None:
        return ()

    try:
        payload = json.loads(taxonomy_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    data = payload.get("data") if isinstance(payload, Mapping) else None
    labels = data.get("labels") if isinstance(data, Mapping) else None
    if not isinstance(labels, list):
        return ()

    extracted: list[dict[str, object]] = []
    for entry in labels:
        if not isinstance(entry, Mapping):
            continue
        label_name = str(entry.get("label", "")).strip()
        if not label_name:
            continue
        raw_keywords = entry.get("matched_keywords")
        if isinstance(raw_keywords, (list, tuple)):
            keywords = tuple(str(keyword).strip() for keyword in raw_keywords if str(keyword).strip())
        else:
            keywords = ()
        score_value = entry.get("score", 0.0)
        try:
            score = float(score_value)
        except (TypeError, ValueError):
            score = 0.0
        extracted.append({"label": label_name, "keywords": keywords, "score": score})

    extracted.sort(key=lambda item: (-item["score"], item["label"]))
    return tuple(extracted)


def _load_structure_headings(
    config_map: Mapping[str, object],
    source_path: str,
) -> tuple[str, ...]:
    structure_file = _resolve_outputs_file(
        config_map,
        source_path,
        "structure_path",
        default_name="structure.json",
    )
    if structure_file is None:
        return ()

    try:
        payload = json.loads(structure_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    data = payload.get("data") if isinstance(payload, Mapping) else None
    headings_payload = data.get("headings") if isinstance(data, Mapping) else None
    if not isinstance(headings_payload, list):
        return ()

    headings: list[str] = []
    for heading in headings_payload:
        if not isinstance(heading, Mapping):
            continue
        title = str(heading.get("text", "")).strip()
        if title:
            headings.append(title)
    return tuple(headings)


_LABEL_DESCRIPTIONS = {
    "governance": "governance and statecraft",
    "warfare": "military organization and fortifications",
    "diplomacy": "diplomatic strategy and foreign alliances",
    "economy": "fiscal policy and revenue management",
    "virtue": "virtue, prudence, and necessity in rule",
    "religion": "religion as an instrument of power",
}

_AUTO_TEMPLATE_LEADS = (
    "Examines",
    "Details",
    "Explores",
    "Highlights",
    "Underscores",
)


def _format_keyword_summary(keywords: Sequence[str], *, limit: int = 3) -> str:
    trimmed = [keyword for keyword in keywords if keyword][:limit]
    if not trimmed:
        return ""
    if len(trimmed) == 1:
        return trimmed[0]
    if len(trimmed) == 2:
        return f"{trimmed[0]} and {trimmed[1]}"
    return ", ".join(trimmed[:-1]) + f", and {trimmed[-1]}"


def _describe_label(label: str) -> str:
    normalized = label.strip().lower().replace("_", " ")
    return _LABEL_DESCRIPTIONS.get(normalized, normalized)


def _build_structure_sentence(headings: Sequence[str]) -> str | None:
    if not headings:
        return None
    chapter_headings = [heading for heading in headings if heading.upper().startswith("CHAPTER")]
    if not chapter_headings:
        return None
    chapter_count = len(chapter_headings)
    first_chapter = chapter_headings[0].title()
    last_chapter = chapter_headings[-1].title()
    return (
        f"Structures the treatise in {chapter_count} chapters from {first_chapter} through {last_chapter}, "
        "preceded by prefatory material that frames Machiavelli's aims."
    )


def _build_auto_template_sentences(
    text: str,
    *,
    config_map: Mapping[str, object],
    source_path: str,
) -> tuple[str, ...]:
    taxonomy_labels = _load_taxonomy_labels(config_map, source_path)
    structure_headings = _load_structure_headings(config_map, source_path)
    max_sentences = _coerce_int(config_map.get("auto_template_max_sentences"), 4, minimum=1)

    generated: list[str] = []

    for label in taxonomy_labels:
        if len(generated) >= max_sentences:
            break
        description = _describe_label(str(label.get("label", "")))
        keywords = label.get("keywords", ())
        keyword_summary = _format_keyword_summary(keywords) if isinstance(keywords, Sequence) else ""
        lead = _AUTO_TEMPLATE_LEADS[len(generated) % len(_AUTO_TEMPLATE_LEADS)]
        if keyword_summary:
            sentence = f"{lead} {description} themes such as {keyword_summary}."
        else:
            sentence = f"{lead} {description} themes central to the treatise."
        generated.append(sentence)

    if len(generated) < max_sentences:
        structure_sentence = _build_structure_sentence(structure_headings)
        if structure_sentence:
            generated.append(structure_sentence)

    return tuple(generated)


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

    auto_template_enabled = _coerce_bool(config_map.get("auto_template"), False)
    template_sentences = _coerce_sentences(config_map.get("template_sentences"))
    if not template_sentences and auto_template_enabled:
        template_sentences = _build_auto_template_sentences(
            text,
            config_map=config_map,
            source_path=source_path,
        )
    if template_sentences:
        keyword_counter: Counter[str] = Counter()
        highlight_stopwords = set(_STOPWORDS)
        highlight_stopwords.update({"highlights", "themes", "such"})
        for sentence in template_sentences:
            for word in _WORD_PATTERN.findall(sentence.lower()):
                if word in highlight_stopwords or len(word) <= 2:
                    continue
                keyword_counter[word] += 1
        highlights = tuple(word for word, _ in keyword_counter.most_common(5))

        summary_text: str
        if style == "bullet":
            summary_text = "\n".join(f"- {sentence}" for sentence in template_sentences)
        else:
            summary_text = " ".join(template_sentences)

        checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
        data: dict[str, object] = {
            "summary": summary_text,
            "summary_style": style,
            "sentences": template_sentences,
            "highlights": highlights,
        }
        metadata: dict[str, object] = {
            "source_path": source_path,
            "max_length": max_length,
            "selected_sentences": len(template_sentences),
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
