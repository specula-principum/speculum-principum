"""Named entity extraction utilities."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Mapping

from . import ExtractedEntity, ExtractionResult
from .normalization import normalize_ocr_token

__all__ = ["extract_entities"]

_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_UPPERCASE_ORG_PATTERN = re.compile(r"\b([A-Z]{3,})\b")
_DATE_PATTERN = re.compile(r"\b(\d{4})\b")
_ORG_SUFFIXES = {
    "Company",
    "Corporation",
    "Council",
    "Institute",
    "University",
    "Republic",
    "Agency",
    "Archive",
    "Archives",
    "Library",
    "Libraries",
    "Press",
    "Society",
    "Kingdom",
    "Empire",
}
_LEADING_STOPWORDS = {
    "Of",
    "The",
    "Chapter",
    "Book",
    "Contents",
}
_NON_PERSON_SUFFIXES = {
    "Anthology",
    "Autobiography",
    "Catalogue",
    "Collected",
    "Collection",
    "Commentary",
    "Comedies",
    "Criticism",
    "Edition",
    "Essays",
    "History",
    "Introduction",
    "Letters",
    "Narrative",
    "Preface",
    "Plays",
    "Poems",
    "Series",
    "Stories",
    "Testament",
    "Tales",
    "Tragedies",
    "Verse",
}

_KNOWN_GPE_TOKENS = {
    "Africa",
    "Bologna",
    "England",
    "Ferrara",
    "Florence",
    "France",
    "Genoa",
    "Germany",
    "Greece",
    "Italy",
    "Lombardy",
    "Mantua",
    "Milan",
    "Naples",
    "Parma",
    "Perugia",
    "Piedmont",
    "Pisa",
    "Pistoia",
    "Siena",
    "Rome",
    "Romagna",
    "Sardinia",
    "Savoy",
    "Scotland",
    "Sicily",
    "Spain",
    "Switzerland",
    "Tuscany",
    "Umbria",
    "Lucca",
    "Venice",
}

_DEMONYM_MAP = {
    "English": "England",
    "Englishmen": "England",
    "Florentine": "Florence",
    "Florentines": "Florence",
    "French": "France",
    "Frenchmen": "France",
    "German": "Germany",
    "Germans": "Germany",
    "Italian": "Italy",
    "Italians": "Italy",
    "Scots": "Scotland",
    "Scottish": "Scotland",
    "Roman": "Rome",
    "Romans": "Rome",
    "Spaniards": "Spain",
    "Spanish": "Spain",
    "Swiss": "Switzerland",
    "Venetian": "Venice",
    "Venetians": "Venice",
}


def _load_serialized_mapping(path_value: str) -> object:
    path = Path(path_value).expanduser()
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return json.loads(text)

    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - PyYAML is an expected dependency
        raise ValueError("Loading YAML location maps requires PyYAML to be installed") from exc

    return yaml.safe_load(text)


def _coerce_string_iterable(value: object) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        for token in value.split(","):
            stripped = token.strip()
            if stripped:
                yield stripped
        return
    if isinstance(value, Mapping):
        for token in value.values():
            yield from _coerce_string_iterable(token)
        return
    if isinstance(value, (list, tuple, set)):
        for token in value:
            yield from _coerce_string_iterable(token)
        return
    stripped = str(value).strip()
    if stripped:
        yield stripped


def _coerce_mapping(value: object) -> Mapping[str, str]:
    if isinstance(value, Mapping):
        return {str(key).strip(): str(val).strip() for key, val in value.items() if str(key).strip() and str(val).strip()}
    return {}


def _load_known_locations(config_map: Mapping[str, object]) -> set[str]:
    tokens = set(_KNOWN_GPE_TOKENS)
    tokens.update(_coerce_string_iterable(config_map.get("known_locations")))

    file_value = config_map.get("known_locations_file")
    if isinstance(file_value, str) and file_value.strip():
        data = _load_serialized_mapping(file_value)
        tokens.update(_coerce_string_iterable(data if data is not None else ()))

    files_value = config_map.get("known_locations_files")
    if isinstance(files_value, (list, tuple, set)):
        for file_path in files_value:
            file_path_str = str(file_path).strip()
            if not file_path_str:
                continue
            data = _load_serialized_mapping(file_path_str)
            tokens.update(_coerce_string_iterable(data if data is not None else ()))

    return {token for token in tokens if token}


def _load_known_organizations(config_map: Mapping[str, object]) -> set[str]:
    tokens: set[str] = set()
    tokens.update(_coerce_string_iterable(config_map.get("known_organizations")))

    file_value = config_map.get("known_organizations_file")
    if isinstance(file_value, str) and file_value.strip():
        data = _load_serialized_mapping(file_value)
        tokens.update(_coerce_string_iterable(data if data is not None else ()))

    files_value = config_map.get("known_organizations_files")
    if isinstance(files_value, (list, tuple, set)):
        for file_path in files_value:
            file_path_str = str(file_path).strip()
            if not file_path_str:
                continue
            data = _load_serialized_mapping(file_path_str)
            tokens.update(_coerce_string_iterable(data if data is not None else ()))

    return {token for token in tokens if token}


def _load_demonym_map(config_map: Mapping[str, object]) -> Mapping[str, str]:
    mapping = dict(_DEMONYM_MAP)

    raw_map = config_map.get("demonym_map")
    mapping.update(_coerce_mapping(raw_map))

    file_value = config_map.get("demonym_map_file")
    if isinstance(file_value, str) and file_value.strip():
        data = _load_serialized_mapping(file_value)
        mapping.update(_coerce_mapping(data))

    files_value = config_map.get("demonym_map_files")
    if isinstance(files_value, (list, tuple, set)):
        for file_path in files_value:
            file_path_str = str(file_path).strip()
            if not file_path_str:
                continue
            data = _load_serialized_mapping(file_path_str)
            mapping.update(_coerce_mapping(data))

    return {key: value for key, value in mapping.items() if key and value}


def extract_entities(
    text: str,
    *,
    entity_types: Iterable[str] | None = None,
    config: Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Identify entities present in the supplied text using lightweight heuristics."""

    config_map = dict(config or {})
    source_path = str(config_map.get("source_path", "<memory>"))
    if entity_types is not None:
        requested_types = {str(item) for item in entity_types}
    else:
        configured_types = config_map.get("entity_types")
        if configured_types is None:
            requested_types = {"PERSON", "ORG", "DATE"}
        elif isinstance(configured_types, str):
            requested_types = {configured_types}
        else:
            try:
                requested_types = {str(item) for item in configured_types}  # type: ignore[arg-type]
            except TypeError:
                requested_types = {"PERSON", "ORG", "DATE"}
    if not requested_types:
        requested_types = {"PERSON", "ORG", "DATE"}

    threshold_value = config_map.get("confidence_threshold", 0.7)
    if isinstance(threshold_value, (int, float, str)):
        try:
            threshold = float(threshold_value)
        except ValueError:
            threshold = 0.7
    else:
        threshold = 0.7

    uppercase_enabled_value = config_map.get("enable_uppercase_orgs", True)
    if isinstance(uppercase_enabled_value, str):
        uppercase_enabled = uppercase_enabled_value.strip().lower() not in {"0", "false", "no", "off"}
    else:
        uppercase_enabled = bool(uppercase_enabled_value)

    uppercase_min_length = 3
    uppercase_min_length_value = config_map.get("uppercase_min_length", 3)
    if isinstance(uppercase_min_length_value, (int, float, str)):
        try:
            uppercase_min_length = int(uppercase_min_length_value)
        except (TypeError, ValueError):  # pragma: no cover - guard against malformed config
            uppercase_min_length = 3

    configured_stopwords = set()
    stopword_values = config_map.get("uppercase_stopwords")
    if isinstance(stopword_values, (set, list, tuple)):
        configured_stopwords.update(str(value).strip().upper() for value in stopword_values)
    elif isinstance(stopword_values, str):
        configured_stopwords.update(token.strip().upper() for token in stopword_values.split(",") if token.strip())

    uppercase_stopwords = {
        "THE",
        "AND",
        "FOR",
        "WITH",
        "FROM",
        "IN",
        "OF",
        "ON",
        "BY",
    }
    uppercase_stopwords.update(configured_stopwords)

    allow_multiline_sequences_value = config_map.get("allow_multiline_sequences", False)
    if isinstance(allow_multiline_sequences_value, str):
        allow_multiline_sequences = allow_multiline_sequences_value.strip().lower() in {"1", "true", "yes", "on"}
    else:
        allow_multiline_sequences = bool(allow_multiline_sequences_value)

    configured_leading_stopwords = config_map.get("leading_stopwords")
    leading_stopwords = set(_LEADING_STOPWORDS)
    if isinstance(configured_leading_stopwords, (list, tuple, set)):
        leading_stopwords.update(str(value).strip() for value in configured_leading_stopwords if str(value).strip())
    elif isinstance(configured_leading_stopwords, str):
        leading_stopwords.update(
            token.strip() for token in configured_leading_stopwords.split(",") if token.strip()
        )

    entities: list[ExtractedEntity] = []
    seen_positions: set[tuple[int, int, str]] = set()
    known_locations = _load_known_locations(config_map)
    known_organizations = _load_known_organizations(config_map)
    demonym_map = _load_demonym_map(config_map)

    def add_entity(
        *,
        text_value: str,
        entity_type: str,
        start: int,
        end: int,
        confidence: float,
        metadata: Mapping[str, object],
    ) -> None:
        if entity_type not in requested_types:
            return
        if confidence < threshold:
            return
        key = (start, end, entity_type)
        if key in seen_positions:
            return
        seen_positions.add(key)
        normalized_text = normalize_ocr_token(text_value)
        entity_metadata = dict(metadata)
        if normalized_text != text_value:
            entity_metadata.setdefault("raw_text", text_value)
        entities.append(
            ExtractedEntity(
                text=normalized_text,
                entity_type=entity_type,
                start_offset=start,
                end_offset=end,
                confidence=confidence,
                metadata=entity_metadata,
            )
        )

    for match in _PERSON_PATTERN.finditer(text):
        candidate = match.group(1).strip()
        if "\n" in candidate and not allow_multiline_sequences:
            continue
        tokens = candidate.split()
        last_token = tokens[-1]
        first_token = tokens[0]
        entity_type = "PERSON"
        if last_token in _ORG_SUFFIXES or last_token.isupper():
            entity_type = "ORG"
        if last_token in _NON_PERSON_SUFFIXES:
            continue
        if first_token in leading_stopwords:
            continue
        if entity_type == "PERSON" and len(tokens) < 2:
            continue
        add_entity(
            text_value=candidate,
            entity_type=entity_type,
            start=match.start(1),
            end=match.end(1),
            confidence=0.92 if entity_type == "PERSON" else 0.88,
            metadata={"pattern": "capitalized_sequence", "token_count": len(tokens)},
        )

    if uppercase_enabled:
        for match in _UPPERCASE_ORG_PATTERN.finditer(text):
            token = match.group(1)
            if len(token) < uppercase_min_length:
                continue
            if "\n" in token:
                continue
            if token in uppercase_stopwords:
                continue
            add_entity(
                text_value=token,
                entity_type="ORG",
                start=match.start(1),
                end=match.end(1),
                confidence=0.87,
                metadata={"pattern": "uppercase_token"},
            )

    for match in _DATE_PATTERN.finditer(text):
        token = match.group(1)
        add_entity(
            text_value=token,
            entity_type="DATE",
            start=match.start(1),
            end=match.end(1),
            confidence=0.9,
            metadata={"pattern": "year"},
        )

    if known_locations:
        ordered_locations = sorted(known_locations, key=lambda item: (-len(item), item.lower()))
        pattern_tokens = "|".join(re.escape(location) for location in ordered_locations)
        location_regex = re.compile(rf"(?<!\w)({pattern_tokens})(?!\w)")
        for match in location_regex.finditer(text):
            location = match.group(1)
            add_entity(
                text_value=location,
                entity_type="GPE",
                start=match.start(1),
                end=match.end(1),
                confidence=0.89,
                metadata={"pattern": "known_location"},
            )

    if known_organizations:
        ordered_orgs = sorted(known_organizations, key=lambda item: (-len(item), item.lower()))
        org_pattern = "|".join(re.escape(org) for org in ordered_orgs)
        org_regex = re.compile(rf"(?<!\w)({org_pattern})(?!\w)")
        for match in org_regex.finditer(text):
            org_name = match.group(1)
            add_entity(
                text_value=org_name,
                entity_type="ORG",
                start=match.start(1),
                end=match.end(1),
                confidence=0.9,
                metadata={"pattern": "known_organization"},
            )

    if demonym_map:
        ordered_demonyms = sorted(demonym_map, key=lambda item: (-len(item), item.lower()))
        demonym_pattern = "|".join(re.escape(token) for token in ordered_demonyms)
        demonym_regex = re.compile(rf"\b({demonym_pattern})\b")
        for match in demonym_regex.finditer(text):
            demonym = match.group(1)
            canonical = demonym_map.get(demonym)
            if not canonical:
                continue
            add_entity(
                text_value=demonym,
                entity_type="GPE",
                start=match.start(1),
                end=match.end(1),
                confidence=0.9,
                metadata={
                    "pattern": "known_demonym",
                    "canonical": canonical,
                },
            )

    entities.sort(key=lambda entity: (entity.start_offset, entity.end_offset, entity.entity_type))

    checksum = hashlib.md5(text.encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        "detected_count": len(entities),
        "source_path": source_path,
        "entity_types": tuple(sorted(requested_types)),
        "config": config_map,
    }

    return ExtractionResult(
        source_path=source_path,
        checksum=checksum,
        extractor_name="entities",
        data=tuple(entities),
        metadata=metadata,
    )
