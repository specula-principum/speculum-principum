"""Metadata enrichment utilities."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from collections.abc import Iterable, Mapping

from . import ExtractionResult
from .normalization import normalize_keyword_sequence

__all__ = ["generate_metadata"]

_WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]?")
_HEADING_PATTERN = re.compile(r"(?m)^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_LIST_PATTERN = re.compile(r"(?m)^\s*[-*+]\s+")


def _coerce_int(value: object, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
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


def _coerce_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item).strip())
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(";") if part.strip())
    return ()


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_title(text: str) -> str | None:
    heading_match = _HEADING_PATTERN.search(text)
    if heading_match:
        return heading_match.group(2).strip()
    for line in text.splitlines():
        striped = line.strip()
        if striped:
            return striped
    return None


def _extract_summary(text: str, length: int) -> str:
    normalized = _normalize_space(text)
    if not normalized:
        return ""
    if len(normalized) <= length:
        return normalized
    truncated = normalized[: length - 1]
    # avoid chopping mid-word when possible
    last_space = truncated.rfind(" ")
    if last_space > length // 2:
        truncated = truncated[:last_space]
    return truncated.strip()


def _collect_sentences(text: str) -> list[str]:
    sentences = [match.group(0).strip() for match in _SENTENCE_PATTERN.finditer(text) if match.group(0).strip()]
    if sentences:
        return sentences
    normalized = _normalize_space(text)
    return [normalized] if normalized else []


def _collect_paragraphs(text: str) -> list[str]:
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]
    return paragraphs


def _collect_keywords(
    words: Iterable[str],
    *,
    max_keywords: int,
    min_length: int,
    stopwords: Iterable[str] | None = None,
) -> tuple[str, ...]:
    stopword_set = {word.lower() for word in stopwords or ()}
    ranked: dict[str, int] = {}
    for word in words:
        if len(word) < min_length:
            continue
        key = word.lower()
        if key in stopword_set:
            continue
        ranked[key] = ranked.get(key, 0) + 1
    ordered = sorted(ranked.items(), key=lambda item: (-item[1], item[0]))
    return tuple(word for word, _ in ordered[:max_keywords])


def _load_stopwords_from_file(path_value: str) -> tuple[str, ...]:
    path = Path(path_value).expanduser()
    if not path.exists():
        return ()

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    data: object
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - PyYAML should be present but guard in tests
            raise ValueError("yaml stopword files require PyYAML to be installed") from exc
        data = yaml.safe_load(text)
    else:
        data = [line.strip() for line in text.splitlines() if line.strip()]

    tokens: list[str] = []
    if isinstance(data, Mapping):
        for value in data.values():
            candidate = str(value).strip()
            if candidate:
                tokens.append(candidate)
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        for item in data:
            candidate = str(item).strip()
            if candidate:
                tokens.append(candidate)
    else:
        candidate = str(data).strip()
        if candidate:
            tokens.append(candidate)

    return tuple(tokens)


def _collect_keyword_stopwords(config_map: Mapping[str, object]) -> tuple[str, ...]:
    ordered: list[str] = list(_coerce_sequence(config_map.get("keyword_stopwords")))
    raw_file = config_map.get("keyword_stopwords_file")
    files: list[str] = []
    if isinstance(raw_file, str) and raw_file.strip():
        files.append(raw_file)
    elif isinstance(raw_file, (list, tuple, set)):
        files.extend(str(item) for item in raw_file if str(item).strip())

    for file_path in files:
        ordered.extend(_load_stopwords_from_file(file_path))

    deduped: list[str] = []
    seen: set[str] = set()
    for token in ordered:
        lowered = token.strip()
        if not lowered:
            continue
        if lowered in seen:
            continue
        deduped.append(lowered)
        seen.add(lowered)
    return tuple(deduped)


def generate_metadata(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Produce structured metadata and quality metrics for a parsed document."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    language = str(config_map.get("language", "en") or "en")
    summary_length = _coerce_int(config_map.get("summary_length"), 240, minimum=40)
    words_per_minute = max(_coerce_int(config_map.get("words_per_minute"), 215, minimum=60), 60)
    include_quality = _coerce_bool(config_map.get("include_quality_metrics"), True)
    include_history = _coerce_bool(config_map.get("include_history"), True)
    min_keyword_length = _coerce_int(config_map.get("min_keyword_length"), 4, minimum=1)
    max_keywords = _coerce_int(config_map.get("max_keywords"), 6, minimum=0, maximum=20)
    keyword_stopwords = _collect_keyword_stopwords(config_map)

    sentences = _collect_sentences(text)
    words = _WORD_PATTERN.findall(text)
    paragraphs = _collect_paragraphs(text)
    headings = list(_HEADING_PATTERN.finditer(text))
    list_items = _LIST_PATTERN.findall(text)

    word_count = len(words)
    sentence_count = len(sentences) if sentences else 0
    paragraph_count = len(paragraphs)
    heading_count = len(headings)
    list_item_count = len(list_items)
    unique_words = len({word.lower() for word in words}) if words else 0
    avg_sentence_length = (word_count / sentence_count) if sentence_count else 0.0
    avg_word_length = (sum(len(word) for word in words) / word_count) if word_count else 0.0
    lexical_density = (unique_words / word_count) if word_count else 0.0
    estimated_reading_time = round(word_count / words_per_minute, 2) if word_count else 0.0

    keywords = _collect_keywords(
        words,
        max_keywords=max_keywords,
        min_length=min_keyword_length,
        stopwords=keyword_stopwords,
    )
    keywords = normalize_keyword_sequence(keywords)

    title = config_map.get("title") or _extract_title(text) or source_path
    description = config_map.get("description") or _extract_summary(text, summary_length)
    subjects = _coerce_sequence(config_map.get("subjects")) or keywords
    creators = _coerce_sequence(config_map.get("creators"))
    contributors = _coerce_sequence(config_map.get("contributors"))

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    history: list[dict[str, str]] = []
    if include_history:
        raw_history = config_map.get("history")
        if isinstance(raw_history, list):
            for entry in raw_history:
                if isinstance(entry, Mapping):
                    normalized_entry = {str(key): str(value) for key, value in entry.items()}
                    history.append(normalized_entry)
        history.append(
            {
                "step": "metadata",
                "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
                "notes": "Metadata heuristics executed.",
            }
        )

    dublin_core: dict[str, object] = {
        "title": title,
        "description": description,
        "language": language,
        "subject": subjects,
        "creator": creators,
        "contributor": contributors,
        "identifier": config_map.get("identifier", source_path),
        "source": source_path,
        "coverage": config_map.get("coverage"),
        "rights": config_map.get("rights"),
        "type": config_map.get("type", "Text"),
        "format": config_map.get("format", "text/markdown"),
    }

    statistics: dict[str, object] = {
        "character_count": len(text),
        "word_count": word_count,
        "unique_word_count": unique_words,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "heading_count": heading_count,
        "list_item_count": list_item_count,
        "average_sentence_length": round(avg_sentence_length, 2),
        "average_word_length": round(avg_word_length, 2),
        "lexical_density": round(lexical_density, 3),
        "estimated_reading_time_minutes": estimated_reading_time,
    }

    quality: dict[str, object] | None = None
    if include_quality:
        long_sentence_threshold = _coerce_int(config_map.get("long_sentence_threshold"), 35, minimum=5)
        long_sentences = [sentence for sentence in sentences if len(sentence.split()) > long_sentence_threshold]
        quality = {
            "long_sentence_count": len(long_sentences),
            "long_sentence_threshold": long_sentence_threshold,
            "keyword_coverage": round(len(keywords) / max_keywords, 3) if max_keywords else 0.0,
            "has_summary": bool(description),
            "has_title": bool(title),
        }

    provenance = {
        "source_path": source_path,
        "checksum": checksum,
        "history": tuple(history),
        "keywords": keywords,
    }

    data: dict[str, object] = {
        "dublin_core": dublin_core,
        "statistics": statistics,
        "provenance": provenance,
    }
    if quality is not None:
        data["quality"] = quality

    metadata: dict[str, object] = {
        "source_path": source_path,
        "config": config_map,
        "keyword_count": len(keywords),
        "summary_length": summary_length,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="metadata",
        data=data,
        metadata=metadata,
    )
