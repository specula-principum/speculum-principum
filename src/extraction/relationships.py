"""Relationship mapping utilities."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable, Mapping

from . import ExtractedRelationship, ExtractionResult

__all__ = ["extract_relationships"]

_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]?")
_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z']*")
_CONNECTOR_WORDS = {
    "of",
    "the",
    "de",
    "di",
    "von",
    "da",
    "la",
    "le",
    "del",
    "du",
    "van",
    "den",
}
_ARTICLE_PREFIXES = ("The ", "A ", "An ")
_RELATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "support": ("support", "bolster", "aid", "assist", "protect", "defend"),
    "opposition": ("oppose", "against", "resist", "challenge", "confront"),
    "comparison": ("between", "versus", "vs", "compared", "contrast"),
    "governance": ("rule", "govern", "command", "control", "lead"),
    "alliance": ("alliance", "ally", "together", "coalition", "treaty"),
    "causal": ("because", "therefore", "since", "thus", "hence"),
}


def _coerce_int(value: object, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        return default
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


def _collect_keywords(config_keywords: Mapping[str, Iterable[str]] | None) -> dict[str, tuple[str, ...]]:
    if not config_keywords:
        return _RELATION_KEYWORDS
    keywords: dict[str, tuple[str, ...]] = {}
    for relation_type, words in config_keywords.items():
        normalized = []
        for word in words:
            normalized.append(str(word).lower())
        if normalized:
            keywords[str(relation_type)] = tuple(dict.fromkeys(normalized))
    if not keywords:
        return _RELATION_KEYWORDS
    return keywords


def extract_relationships(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Identify relationships between entities and concepts using heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    max_relationships = _coerce_int(config_map.get("max_relationships"), 100, minimum=1)
    max_pairs_per_sentence = _coerce_int(config_map.get("max_pairs_per_sentence"), 6, minimum=1)
    window_size = _coerce_int(config_map.get("window_size"), 3, minimum=1)
    include_self_pairs = _coerce_bool(config_map.get("include_self_pairs"), False)
    keywords_raw = config_map.get("keywords")
    keywords_mapping = keywords_raw if isinstance(keywords_raw, Mapping) else None
    keywords = _collect_keywords(keywords_mapping)

    sentences = list(_SENTENCE_PATTERN.finditer(text))
    if not sentences:
        sentences = [re.match(r".*", text) or None]

    relationships: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str, int]] = set()

    for sentence_index, match in enumerate(sentences):
        if match is None:
            continue
        sentence = match.group(0)
        sentence_lower = sentence.lower()
        candidates = list(_gather_candidates(sentence))
        if not candidates:
            continue

        scored_types = _classify_sentence(sentence_lower, keywords)
        relation_type = _determine_relation_type(scored_types)
        pairs_added = 0
        for idx, (subject_text, subject_offset) in enumerate(candidates):
            for other_idx in range(idx + 1, min(len(candidates), idx + 1 + window_size)):
                other_text, object_offset = candidates[other_idx]
                if not include_self_pairs and subject_text == other_text:
                    continue
                pair_key = (subject_text, other_text, relation_type, sentence_index)
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                confidence = _calculate_confidence(scored_types)
                evidence = sentence.strip()
                relationships.append(
                    ExtractedRelationship(
                        subject=subject_text,
                        object=other_text,
                        relation_type=relation_type,
                        evidence=evidence,
                        confidence=confidence,
                        metadata={
                            "sentence_index": sentence_index,
                            "subject_offset": subject_offset + match.start(),
                            "object_offset": object_offset + match.start(),
                            "keywords": tuple(keyword for _, keyword in scored_types if keyword),
                        },
                    )
                )
                pairs_added += 1
                if pairs_added >= max_pairs_per_sentence:
                    break
            if pairs_added >= max_pairs_per_sentence:
                break

    relationships.sort(
        key=lambda item: (
            -item.confidence,
            item.relation_type,
            item.subject.lower(),
            item.object.lower(),
        )
    )

    if len(relationships) > max_relationships:
        relationships = relationships[:max_relationships]

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        "source_path": source_path,
        "total_sentences": len(sentences),
        "detected_relationships": len(relationships),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="relationships",
        data=tuple(relationships),
        metadata=metadata,
    )


def _gather_candidates(sentence: str) -> Iterable[tuple[str, int]]:
    start_index: int | None = None
    end_index: int | None = None
    contains_capital = False

    for match in _WORD_PATTERN.finditer(sentence):
        token = match.group(0)
        if token[0].isupper():
            if start_index is None:
                start_index = match.start()
            end_index = match.end()
            contains_capital = True
        elif start_index is not None and token.lower() in _CONNECTOR_WORDS:
            end_index = match.end()
        else:
            if start_index is not None and end_index is not None and contains_capital:
                candidate = sentence[start_index:end_index].strip(", ").strip()
                for prefix in _ARTICLE_PREFIXES:
                    if candidate.startswith(prefix):
                        candidate = candidate[len(prefix) :]
                        break
                if candidate:
                    yield candidate, start_index
            start_index = None
            end_index = None
            contains_capital = False

    if start_index is not None and end_index is not None and contains_capital:
        candidate = sentence[start_index:end_index].strip(", ").strip()
        for prefix in _ARTICLE_PREFIXES:
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix) :]
                break
        if candidate:
            yield candidate, start_index


def _classify_sentence(
    sentence_lower: str,
    keywords: Mapping[str, Iterable[str]],
) -> list[tuple[str, str | None]]:
    matches: list[tuple[str, str | None]] = []
    for relation_type, words in keywords.items():
        for word in words:
            if word in sentence_lower:
                matches.append((relation_type, word))
    if matches:
        return matches
    return [("association", None)]


def _determine_relation_type(scored_types: list[tuple[str, str | None]]) -> str:
    if not scored_types:
        return "association"
    counter: Counter[str] = Counter()
    for relation_type, _ in scored_types:
        counter[relation_type] += 1
    most_common = counter.most_common(1)
    return most_common[0][0] if most_common else "association"


def _calculate_confidence(scored_types: list[tuple[str, str | None]]) -> float:
    base = 0.55
    bonus_counts: Counter[str] = Counter()
    for relation_type, keyword in scored_types:
        bonus_counts[relation_type] += 1
        if keyword:
            base += 0.05
    if bonus_counts:
        base += min(max(bonus_counts.values()) * 0.05, 0.2)
    return min(base, 0.95)
