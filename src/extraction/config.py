"""Configuration helpers for extraction workflows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import cli

try:  # pragma: no cover - module always available during runtime, but guard import
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_DEFAULT_CONFIG_PATH = Path("config/extraction.yaml")


@dataclass(slots=True)
class ExtractionConfig:
    """Represents the full extraction configuration mapping."""

    raw: Mapping[str, Any]

    @classmethod
    def empty(cls) -> "ExtractionConfig":
        return cls(raw={})

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "ExtractionConfig":
        normalized = _normalize_mapping(mapping)
        return cls(raw=normalized)


def load_extraction_config(path: Path | None) -> ExtractionConfig:
    """Load extraction configuration from YAML, defaulting to empty mapping."""

    if path is None:
        return _load_default_config()

    resolved = path.expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Extraction config '{resolved}' does not exist")

    if yaml is None:
        raise ImportError("PyYAML is required to parse extraction configuration files.")

    data = _load_yaml(resolved)
    return ExtractionConfig.from_mapping(data)


def load_default_or_empty() -> ExtractionConfig:
    try:
        return _load_default_config()
    except (FileNotFoundError, ImportError, ValueError):
        return ExtractionConfig.empty()


def _load_default_config() -> ExtractionConfig:
    if not _DEFAULT_CONFIG_PATH.exists():
        return ExtractionConfig.empty()
    if yaml is None:
        raise ImportError("PyYAML is required to parse extraction configuration files.")
    data = _load_yaml(_DEFAULT_CONFIG_PATH)
    return ExtractionConfig.from_mapping(data)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    if yaml is None:  # pragma: no cover - enforced before calling
        raise ImportError("PyYAML is required to parse extraction configuration files.")
    raw = path.read_text(encoding="utf-8")
    assert yaml is not None  # narrow for type-checkers
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Extraction config must be a mapping at the top level.")
    return data


def _normalize_mapping(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in mapping.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        if not isinstance(value, Mapping):
            raise ValueError(f"Configuration for extractor '{key_str}' must be a mapping.")
        normalized[key_str] = dict(value)
    return normalized


def validate_requested_extractors(extractors: list[str]) -> None:
    available = set(cli.available_extractors())
    unknown = sorted(set(extractors) - available)
    if unknown:
        raise ValueError(f"Unknown extractors requested: {', '.join(unknown)}")


__all__ = [
    "ExtractionConfig",
    "load_extraction_config",
    "load_default_or_empty",
    "validate_requested_extractors",
]
