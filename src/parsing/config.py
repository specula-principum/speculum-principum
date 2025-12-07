"""Configuration helpers for parsing workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src import paths
from . import utils

_DEFAULT_OUTPUT_ROOT = paths.get_evidence_root() / "parsed"
_DEFAULT_SCAN_SUFFIXES = (".pdf", ".docx", ".html", ".htm", ".xhtml")
_DEFAULT_CONFIG_PATH = Path("config/parsing.yaml")


@dataclass(slots=True)
class ScanConfig:
    suffixes: tuple[str, ...] = _DEFAULT_SCAN_SUFFIXES
    recursive: bool = True
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(slots=True)
class ParsingConfig:
    output_root: Path
    scan: ScanConfig

    @classmethod
    def default(cls) -> "ParsingConfig":
        return cls(
            output_root=_resolve_path(_DEFAULT_OUTPUT_ROOT, base=None),
            scan=ScanConfig(),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, base_path: Path | None) -> "ParsingConfig":
        output_value = payload.get("output_root")
        if output_value is None:
            output_root = _resolve_path(_DEFAULT_OUTPUT_ROOT, base=base_path)
        else:
            output_root = _resolve_path(Path(str(output_value)), base=base_path)

        scan_payload = payload.get("scan") or {}
        scan = _build_scan_config(scan_payload)
        return cls(output_root=output_root, scan=scan)


def load_parsing_config(config_path: Path | None) -> ParsingConfig:
    """Load parsing configuration from YAML or fallback to defaults."""

    if config_path is not None:
        resolved = Path(config_path).expanduser()
        if not resolved.exists():
            raise FileNotFoundError(f"Parsing config '{resolved}' does not exist")
        raw = resolved.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, Mapping):
            raise ValueError("Parsing config must be a mapping")
        return ParsingConfig.from_dict(data, base_path=resolved.parent)

    default_path = _DEFAULT_CONFIG_PATH
    if default_path.exists():
        raw = default_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, Mapping):
            raise ValueError("Parsing config must be a mapping")
        return ParsingConfig.from_dict(data, base_path=default_path.parent)

    return ParsingConfig.default()


def _build_scan_config(payload: Mapping[str, Any]) -> ScanConfig:
    suffixes = utils.normalize_suffixes(
        payload.get("suffixes"),
        default=_DEFAULT_SCAN_SUFFIXES,
        preserve_order=True,
    )
    recursive = bool(payload.get("recursive", True))
    include = tuple(_normalize_patterns(payload.get("include")))
    exclude = tuple(_normalize_patterns(payload.get("exclude")))
    return ScanConfig(
        suffixes=suffixes,
        recursive=recursive,
        include=include,
        exclude=exclude,
    )


def _normalize_patterns(values: Any) -> Sequence[str]:
    if not values:
        return ()
    if isinstance(values, str):
        values = [values]
    patterns: list[str] = []
    for raw in values:
        token = str(raw).strip()
        if token:
            patterns.append(token)
    return tuple(dict.fromkeys(patterns))


def _resolve_path(path: Path, *, base: Path | None) -> Path:
    candidate = path.expanduser()
    if candidate.is_absolute() or base is None:
        return candidate.resolve()
    return (base / candidate).resolve()


__all__ = [
    "ParsingConfig",
    "ScanConfig",
    "load_parsing_config",
]
