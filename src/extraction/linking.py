"""Link generation utilities."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from . import ExtractionResult

__all__ = ["generate_links"]

_HEADING_PATTERN = re.compile(r"(?m)^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<target>[^)]+)\)")
_SEE_ALSO_PATTERN = re.compile(r"see also\s+(?P<target>[A-Z][A-Za-z0-9\s,]+?)(?:[.;]|\n|$)", re.IGNORECASE)
_CAPITALIZED_PHRASE_PATTERN = re.compile(r"\b([A-Z][A-Za-z']+(?:\s+[A-Z][A-Za-z']+){0,3})\b")
_MENTION_STOPWORDS = {
    "and",
    "the",
    "but",
    "for",
    "his",
    "her",
    "their",
    "its",
    "our",
    "your",
    "my",
    "they",
    "this",
    "that",
    "these",
    "those",
    "there",
    "here",
    "thus",
    "hence",
    "where",
    "when",
    "what",
    "why",
    "how",
    "shall",
    "will",
    "may",
    "can",
    "must",
    "introduction",
    "translated",
    "poems",
    "selected",
        "intro",
    }


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9\s-]", "", value).strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    return normalized or "section"


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


def _coerce_float(value: object, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        coerced = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if coerced < minimum:
        return minimum
    if coerced > maximum:
        return maximum
    return coerced


def _load_reference_data_from_file(path_value: str) -> object:
    path = Path(path_value).expanduser()
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - PyYAML expected but guard for minimal installs
            raise ValueError("yaml reference maps require PyYAML to be installed") from exc
        return yaml.safe_load(text)
    return {}


def _normalize_terms(raw_terms: Iterable[object]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for term in raw_terms:
        token = str(term).strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(token)
    return tuple(ordered)


def _coerce_reference_entries(data: object) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    if isinstance(data, Mapping):
        # Mapping keyed by canonical term.
        for key, value in data.items():
            base_term = str(key).strip()
            if not base_term:
                continue
            if isinstance(value, Mapping):
                target = str(value.get("target", "")).strip()
                if not target:
                    continue
                label = str(value.get("label", base_term)).strip() or base_term
                aliases: list[str] = []
                raw_aliases = value.get("aliases") or value.get("terms")
                if isinstance(raw_aliases, (list, tuple, set)):
                    aliases.extend(str(item).strip() for item in raw_aliases if str(item).strip())
                elif isinstance(raw_aliases, str):
                    aliases.extend(token.strip() for token in raw_aliases.split(",") if token.strip())
                confidence = _coerce_float(value.get("confidence", 0.68), 0.68)
                terms = _normalize_terms([base_term, *aliases])
            else:
                target = str(value).strip()
                if not target:
                    continue
                label = base_term
                confidence = 0.68
                terms = _normalize_terms([base_term])
            if not terms:
                continue
            entries.append(
                {
                    "terms": terms,
                    "target": target,
                    "label": label,
                    "confidence": confidence,
                }
            )
        return entries

    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        for item in data:
            if isinstance(item, Mapping):
                terms_field = item.get("terms") or item.get("aliases") or ()
                if isinstance(terms_field, str):
                    raw_terms = [token.strip() for token in terms_field.split(",") if token.strip()]
                elif isinstance(terms_field, (list, tuple, set)):
                    raw_terms = [str(token).strip() for token in terms_field if str(token).strip()]
                else:
                    raw_terms = []
                label_value = item.get("label") or item.get("title") or item.get("term")
                target_value = item.get("target")
                if target_value is None and isinstance(item.get("url"), str):
                    target_value = item.get("url")
                if target_value is None:
                    continue
                target = str(target_value).strip()
                if not target:
                    continue
                if not raw_terms:
                    default_term = str(label_value or "").strip()
                    if default_term:
                        raw_terms = [default_term]
                terms = _normalize_terms(raw_terms)
                if not terms:
                    continue
                label = str(label_value).strip() if label_value else terms[0]
                confidence = _coerce_float(item.get("confidence", 0.68), 0.68)
                entries.append(
                    {
                        "terms": terms,
                        "target": target,
                        "label": label,
                        "confidence": confidence,
                    }
                )
        return entries

    return entries


def _load_reference_entries(config_map: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    sources: list[object] = []

    raw_file = config_map.get("reference_map_file")
    if isinstance(raw_file, str) and raw_file.strip():
        sources.append(_load_reference_data_from_file(raw_file))
    elif isinstance(raw_file, (list, tuple, set)):
        for item in raw_file:
            candidate = str(item).strip()
            if candidate:
                sources.append(_load_reference_data_from_file(candidate))

    raw_map = config_map.get("reference_map")
    if raw_map:
        sources.append(raw_map)

    entries: list[dict[str, object]] = []
    for source in sources:
        entries.extend(_coerce_reference_entries(source))

    if not entries:
        return ()

    unique: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for entry in entries:
        target = entry.get("target")
        label = entry.get("label")
        if not isinstance(target, str):
            continue
        if not isinstance(label, str) or not label:
            label = entry.get("terms", ("reference",))[0]
            entry = dict(entry)
            entry["label"] = label
        key = (label.lower(), target)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique.append(entry)
    return tuple(unique)


def _build_context_slice(text: str, start: int, end: int, span: int) -> str:
    lower = max(start - span, 0)
    upper = min(end + span, len(text))
    return text[lower:upper].strip()


def _generate_reference_links(
    text: str,
    entries: tuple[dict[str, object], ...],
    *,
    limit: int,
    include_offsets: bool,
    context_window: int,
    existing_targets: set[str],
) -> list[dict[str, object]]:
    if limit <= 0:
        return []

    context_window = max(20, context_window)
    generated: list[dict[str, object]] = []

    for entry in entries:
        target = entry.get("target")
        if not isinstance(target, str) or not target:
            continue
        if target in existing_targets:
            continue
        terms = entry.get("terms")
        if not isinstance(terms, Iterable):
            continue
        found_match = False
        for term in terms:
            token = str(term).strip()
            if len(token) < 3:
                continue
            pattern = re.compile(rf"(?<![\\w-]){re.escape(token)}(?![\\w-])", re.IGNORECASE)
            match = pattern.search(text)
            if not match:
                continue
            label = entry.get("label") or match.group(0)
            confidence_value = _coerce_float(entry.get("confidence", 0.68), 0.68)
            context = _build_context_slice(text, match.start(), match.end(), context_window)
            generated.append(
                {
                    "label": label,
                    "target": target,
                    "context": context,
                    "confidence": confidence_value,
                    "start_offset": match.start() if include_offsets else None,
                }
            )
            existing_targets.add(target)
            found_match = True
            break
        if found_match and len(generated) >= limit:
            break

    return generated


def generate_links(
    text: str,
    *,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Build outbound link suggestions, anchors, and related mentions."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    max_links = _coerce_int(config_map.get("max_links"), 25, minimum=0)
    max_mentions = _coerce_int(config_map.get("max_mentions"), 10, minimum=0)
    include_mentions = _coerce_bool(config_map.get("include_mentions"), True)
    include_anchor_offsets = _coerce_bool(config_map.get("include_anchor_offsets"), True)
    mention_min_length = _coerce_int(config_map.get("mention_min_length"), 3, minimum=1)
    enable_reference_links = _coerce_bool(config_map.get("enable_reference_links"), True)
    reference_entries = _load_reference_entries(config_map) if enable_reference_links else ()
    reference_context_window = _coerce_int(
        config_map.get("reference_context_window"),
        80,
        minimum=20,
        maximum=400,
    )
    max_reference_links = _coerce_int(config_map.get("max_reference_links"), 8, minimum=0)

    mention_stopwords = set(_MENTION_STOPWORDS)
    raw_mention_stopwords = config_map.get("mention_stopwords")
    if isinstance(raw_mention_stopwords, str):
        tokens = [token.strip().lower() for token in raw_mention_stopwords.split(",") if token.strip()]
        mention_stopwords.update(tokens)
    elif isinstance(raw_mention_stopwords, (list, tuple, set)):
        mention_stopwords.update(
            str(token).strip().lower()
            for token in raw_mention_stopwords
            if str(token).strip()
        )

    anchors: list[dict[str, object]] = []
    seen_slugs: set[str] = set()
    for match in _HEADING_PATTERN.finditer(text):
        title = match.group("title").strip()
        if not title:
            continue
        level = len(match.group("hashes"))
        slug = _slugify(title)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        anchors.append(
            {
                "title": title,
                "slug": slug,
                "level": level,
                "start_offset": match.start() if include_anchor_offsets else None,
                "end_offset": match.end() if include_anchor_offsets else None,
            }
        )

    if not anchors:
        structure_path = config_map.get("structure_path")
        resolved_structure: Path | None = None
        if isinstance(structure_path, str) and structure_path.strip():
            candidate = Path(structure_path).expanduser()
            if candidate.exists():
                resolved_structure = candidate
        if resolved_structure is None:
            source_candidate = Path(source_path)
            if source_candidate.exists():
                outputs_dir = source_candidate.parent / "outputs"
                default_candidate = outputs_dir / "structure.json"
                if default_candidate.exists():
                    resolved_structure = default_candidate
        if resolved_structure is not None:
            try:
                structure_payload = json.loads(resolved_structure.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                structure_payload = None
            if isinstance(structure_payload, Mapping):
                data = structure_payload.get("data")
                if isinstance(data, Mapping):
                    headings = data.get("headings")
                else:
                    headings = None
                if isinstance(headings, list):
                    for heading in headings:
                        if not isinstance(heading, Mapping):
                            continue
                        title = str(heading.get("text", "")).strip()
                        if not title:
                            continue
                        slug = _slugify(title)
                        if slug in seen_slugs:
                            continue
                        seen_slugs.add(slug)
                        level_value = heading.get("level")
                        level = int(level_value) if isinstance(level_value, (int, float)) else 2
                        start_offset = heading.get("start_offset") if include_anchor_offsets else None
                        end_offset = heading.get("end_offset") if include_anchor_offsets else None
                        anchors.append(
                            {
                                "title": title,
                                "slug": slug,
                                "level": level,
                                "start_offset": start_offset,
                                "end_offset": end_offset,
                            }
                        )

    outbound_links: list[dict[str, object]] = []
    for match in _MARKDOWN_LINK_PATTERN.finditer(text):
        label = match.group("label").strip()
        target = match.group("target").strip()
        if not target:
            continue
        outbound_links.append(
            {
                "label": label or target,
                "target": target,
                "context": text[max(match.start() - 40, 0) : match.end() + 40].strip(),
                "confidence": 0.9 if target.startswith("http") else 0.8,
                "start_offset": match.start() if include_anchor_offsets else None,
            }
        )

    see_also_links: list[dict[str, object]] = []
    for match in _SEE_ALSO_PATTERN.finditer(text):
        raw_target = match.group("target").strip().rstrip(",")
        see_also_links.append(
            {
                "target": raw_target,
                "context": text[max(match.start() - 40, 0) : match.end() + 40].strip(),
                "confidence": 0.7,
            }
        )

    if (
        enable_reference_links
        and reference_entries
        and max_links
        and max_reference_links
    ):
        existing_targets: set[str] = {
            str(link.get("target"))
            for link in outbound_links
            if isinstance(link.get("target"), str)
        }
        existing_targets.update(
            str(link.get("target"))
            for link in see_also_links
            if isinstance(link.get("target"), str)
        )
        available_slots = min(max(max_links - len(outbound_links), 0), max_reference_links)
        if available_slots > 0:
            outbound_links.extend(
                _generate_reference_links(
                    text,
                    reference_entries,
                    limit=available_slots,
                    include_offsets=include_anchor_offsets,
                    context_window=reference_context_window,
                    existing_targets=existing_targets,
                )
            )

    if max_links:
        outbound_links = outbound_links[:max_links]
        see_also_links = see_also_links[:max_links]

    mentions: list[dict[str, object]] = []
    if include_mentions and max_mentions:
        counts: dict[str, int] = {}
        for match in _CAPITALIZED_PHRASE_PATTERN.finditer(text):
            phrase = match.group(1).strip()
            if len(phrase.split()) == 1 and phrase.isupper():
                continue
            if len(phrase) < mention_min_length:
                continue
            lowered = phrase.lower()
            if lowered in mention_stopwords:
                continue
            if phrase.replace(" ", "").isupper():
                continue
            counts[phrase] = counts.get(phrase, 0) + 1
        sorted_mentions = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:max_mentions]
        for phrase, count in sorted_mentions:
            mentions.append(
                {
                    "phrase": phrase,
                    "occurrences": count,
                }
            )

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()

    data: dict[str, object] = {
        "anchors": tuple(anchors),
        "outbound_links": tuple(outbound_links),
        "see_also": tuple(see_also_links),
        "mentions": tuple(mentions),
    }

    metadata: dict[str, object] = {
        "source_path": source_path,
        "anchor_count": len(anchors),
        "outbound_count": len(outbound_links),
        "see_also_count": len(see_also_links),
        "mention_count": len(mentions),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="linking",
        data=data,
        metadata=metadata,
    )
