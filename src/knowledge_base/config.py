"""Mission configuration loader and validation helpers."""
from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # pragma: no cover - enforced in tests when dependency missing
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_DEFAULT_MISSION_PATH = Path("config/mission.yaml")

_ORGANIZATION_SCHEMES = {
    "hierarchical",
    "sequential",
    "topical",
    "task-based",
    "audience-based",
    "hybrid",
}
_ORGANIZATION_TYPES = {
    "topical",
    "alphabetical",
    "chronological",
    "audience",
    "workflow",
}
_DEPTH_STRATEGIES = {"progressive_disclosure", "full_depth"}
_NAVIGATION_PRIORITIES = {
    "concept_based",
    "entity_based",
    "source_based",
    "relationship_based",
    "chronological",
}
_LABEL_CASE_OPTIONS = {"kebab-case", "snake_case", "title_case"}


def _dedupe(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} entries must be non-empty strings.")
        value = item.strip()
        if value in seen:
            raise ValueError(f"{label} entries must be unique: {value!r}")
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _ensure_bool(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{label} must be a boolean.")


def _require_mapping(payload: Mapping[str, Any], *, key: str) -> Mapping[str, Any]:
    section = payload.get(key)
    if not isinstance(section, MappingABC):
        raise ValueError(f"Mission config requires mapping section '{key}'.")
    return section


def _require_string(payload: Mapping[str, Any], *, key: str, label: str | None = None) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        label_name = label or key
        raise ValueError(f"{label_name} must be a non-empty string.")
    return value.strip()


def _require_float(payload: Mapping[str, Any], *, key: str, minimum: float, maximum: float) -> float:
    value = payload.get(key)
    if not isinstance(value, (float, int)):
        raise ValueError(f"{key} must be a number between {minimum} and {maximum}.")
    number = float(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum} inclusive.")
    return number


def _require_int(payload: Mapping[str, Any], *, key: str, minimum: int) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer >= {minimum}.")
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}.")
    return value


@dataclass(slots=True)
class MissionDetails:
    title: str
    description: str
    audience: tuple[str, ...]
    goals: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "MissionDetails":
        title = _require_string(payload, key="title", label="mission.title")
        if len(title) < 3:
            raise ValueError("mission.title must be at least 3 characters long.")
        description = _require_string(payload, key="description", label="mission.description")
        if len(description) < 10:
            raise ValueError("mission.description must be at least 10 characters long.")
        audience = payload.get("audience", ())
        if not isinstance(audience, SequenceABC) or isinstance(audience, str):
            raise ValueError("mission.audience must be a sequence of strings.")
        audience_values = _dedupe(audience, label="mission.audience")
        if not audience_values:
            raise ValueError("mission.audience must contain at least one entry.")
        goals = payload.get("goals", ())
        if not isinstance(goals, SequenceABC) or isinstance(goals, str):
            raise ValueError("mission.goals must be a sequence of strings.")
        goal_values = _dedupe(goals, label="mission.goals")
        if not goal_values:
            raise ValueError("mission.goals must contain at least one entry.")
        return cls(title=title, description=description, audience=audience_values, goals=goal_values)


@dataclass(slots=True)
class LabelingConventions:
    case: str
    max_length: int
    preferred_language: str
    terminology_source: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LabelingConventions":
        case = _require_string(payload, key="case", label="labeling_conventions.case")
        if case not in _LABEL_CASE_OPTIONS:
            raise ValueError(
                "labeling_conventions.case must be one of: " + ", ".join(sorted(_LABEL_CASE_OPTIONS))
            )
        max_length = _require_int(payload, key="max_length", minimum=1)
        preferred_language = _require_string(
            payload, key="preferred_language", label="labeling_conventions.preferred_language"
        )
        terminology_source = _require_string(
            payload, key="terminology_source", label="labeling_conventions.terminology_source"
        )
        return cls(
            case=case,
            max_length=max_length,
            preferred_language=preferred_language,
            terminology_source=terminology_source,
        )


@dataclass(slots=True)
class SearchOptimization:
    full_text_enabled: bool
    metadata_indexing: bool
    synonym_expansion: bool
    related_content_suggestions: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SearchOptimization":
        expected = {
            "full_text_enabled",
            "metadata_indexing",
            "synonym_expansion",
            "related_content_suggestions",
        }
        missing = expected - payload.keys()
        if missing:
            raise ValueError(
                "search_optimization missing required flags: " + ", ".join(sorted(missing))
            )
        unknown = set(payload.keys()) - expected
        if unknown:
            raise ValueError(
                "search_optimization contains unsupported flags: " + ", ".join(sorted(unknown))
            )
        return cls(
            full_text_enabled=_ensure_bool(payload["full_text_enabled"], label="search_optimization.full_text_enabled"),
            metadata_indexing=_ensure_bool(
                payload["metadata_indexing"], label="search_optimization.metadata_indexing"
            ),
            synonym_expansion=_ensure_bool(
                payload["synonym_expansion"], label="search_optimization.synonym_expansion"
            ),
            related_content_suggestions=_ensure_bool(
                payload["related_content_suggestions"],
                label="search_optimization.related_content_suggestions",
            ),
        )


@dataclass(slots=True)
class QualityStandards:
    min_completeness: float
    min_findability: float
    required_metadata: tuple[str, ...]
    link_depth: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "QualityStandards":
        min_completeness = _require_float(payload, key="min_completeness", minimum=0.0, maximum=1.0)
        min_findability = _require_float(payload, key="min_findability", minimum=0.0, maximum=1.0)
        metadata = payload.get("required_metadata", ())
        if not isinstance(metadata, SequenceABC) or isinstance(metadata, str):
            raise ValueError("quality_standards.required_metadata must be a sequence of strings.")
        metadata_values = _dedupe(metadata, label="quality_standards.required_metadata")
        if not metadata_values:
            raise ValueError("quality_standards.required_metadata cannot be empty.")
        link_depth = _require_int(payload, key="link_depth", minimum=1)
        return cls(
            min_completeness=min_completeness,
            min_findability=min_findability,
            required_metadata=metadata_values,
            link_depth=link_depth,
        )


@dataclass(slots=True)
class InformationArchitecturePlan:
    methodology: str
    version: str
    organization_scheme: str
    organization_types: tuple[str, ...]
    depth_strategy: str
    labeling_conventions: LabelingConventions
    navigation_priority: tuple[str, ...]
    search_optimization: SearchOptimization
    quality_standards: QualityStandards

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "InformationArchitecturePlan":
        methodology = _require_string(payload, key="methodology", label="information_architecture.methodology")
        version = _require_string(payload, key="version", label="information_architecture.version")
        organization_scheme = _require_string(
            payload, key="organization_scheme", label="information_architecture.organization_scheme"
        )
        if organization_scheme not in _ORGANIZATION_SCHEMES:
            raise ValueError(
                "information_architecture.organization_scheme must be one of: "
                + ", ".join(sorted(_ORGANIZATION_SCHEMES))
            )
        org_types = payload.get("organization_types", ())
        if not isinstance(org_types, SequenceABC) or isinstance(org_types, str):
            raise ValueError("information_architecture.organization_types must be a sequence of strings.")
        org_type_values = _dedupe(org_types, label="information_architecture.organization_types")
        if not org_type_values:
            raise ValueError("information_architecture.organization_types must contain at least one entry.")
        unknown_types = set(org_type_values) - _ORGANIZATION_TYPES
        if unknown_types:
            raise ValueError(
                "information_architecture.organization_types contains unsupported values: "
                + ", ".join(sorted(unknown_types))
            )
        depth_strategy = _require_string(
            payload, key="depth_strategy", label="information_architecture.depth_strategy"
        )
        if depth_strategy not in _DEPTH_STRATEGIES:
            raise ValueError(
                "information_architecture.depth_strategy must be one of: "
                + ", ".join(sorted(_DEPTH_STRATEGIES))
            )
        labeling_payload = _require_mapping(payload, key="labeling_conventions")
        labeling = LabelingConventions.from_mapping(labeling_payload)
        navigation = payload.get("navigation_priority", ())
        if not isinstance(navigation, SequenceABC) or isinstance(navigation, str):
            raise ValueError("information_architecture.navigation_priority must be a sequence of strings.")
        navigation_values = _dedupe(navigation, label="information_architecture.navigation_priority")
        if not navigation_values:
            raise ValueError("information_architecture.navigation_priority must contain at least one entry.")
        unknown_navigation = set(navigation_values) - _NAVIGATION_PRIORITIES
        if unknown_navigation:
            raise ValueError(
                "information_architecture.navigation_priority contains unsupported values: "
                + ", ".join(sorted(unknown_navigation))
            )
        search_payload = _require_mapping(payload, key="search_optimization")
        search = SearchOptimization.from_mapping(search_payload)
        quality_payload = _require_mapping(payload, key="quality_standards")
        quality = QualityStandards.from_mapping(quality_payload)
        return cls(
            methodology=methodology,
            version=version,
            organization_scheme=organization_scheme,
            organization_types=org_type_values,
            depth_strategy=depth_strategy,
            labeling_conventions=labeling,
            navigation_priority=navigation_values,
            search_optimization=search,
            quality_standards=quality,
        )


@dataclass(slots=True)
class MissionConfig:
    mission: MissionDetails
    information_architecture: InformationArchitecturePlan

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "MissionConfig":
        if not isinstance(payload, MappingABC):
            raise ValueError("Mission config payload must be a mapping.")
        mission_payload = _require_mapping(payload, key="mission")
        ia_payload = _require_mapping(payload, key="information_architecture")
        mission = MissionDetails.from_mapping(mission_payload)
        ia_plan = InformationArchitecturePlan.from_mapping(ia_payload)
        return cls(mission=mission, information_architecture=ia_plan)

    def structure_context(self) -> dict[str, str]:
        return {
            "title": self.mission.title,
            "description": self.mission.description,
        }


def load_mission_config(path: Path | None = None) -> MissionConfig:
    """Load mission configuration from YAML and validate contents."""

    if path is None:
        candidate = _DEFAULT_MISSION_PATH
    else:
        candidate = path.expanduser()
    if not candidate.exists():
        raise FileNotFoundError(f"Mission config '{candidate}' does not exist")
    if yaml is None:
        raise ImportError("PyYAML is required to parse mission configuration files.")
    raw = candidate.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, MappingABC):
        raise ValueError("Mission config must contain a top-level mapping.")
    return MissionConfig.from_mapping(data)


__all__ = [
    "MissionConfig",
    "MissionDetails",
    "InformationArchitecturePlan",
    "LabelingConventions",
    "SearchOptimization",
    "QualityStandards",
    "load_mission_config",
]
