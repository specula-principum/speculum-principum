"""Pipeline configuration helpers for the knowledge base engine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import json

try:  # pragma: no cover - dependency guaranteed in runtime but guarded for tests
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_DEFAULT_CONFIG_PATH = Path("config/kb-processing.yaml")


def _ensure_mapping(payload: Mapping[str, Any] | None, *, section: str) -> Mapping[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"Pipeline configuration section '{section}' must be a mapping.")
    return payload


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Validated configuration payload for kb-engine pipelines."""

    extraction: Mapping[str, Any]
    transformation: Mapping[str, Any]
    organization: Mapping[str, Any]
    linking: Mapping[str, Any]
    quality: Mapping[str, Any]
    monitoring: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PipelineConfig":
        if not isinstance(payload, Mapping):
            raise ValueError("Pipeline configuration must be a mapping.")
        pipeline_payload = payload.get("pipeline")
        pipeline = _ensure_mapping(pipeline_payload, section="pipeline")

        extraction = _ensure_mapping(pipeline.get("extraction"), section="pipeline.extraction")
        transformation = _ensure_mapping(pipeline.get("transformation"), section="pipeline.transformation")
        organization = _ensure_mapping(pipeline.get("organization"), section="pipeline.organization")
        linking = _ensure_mapping(pipeline.get("linking"), section="pipeline.linking")
        quality = _ensure_mapping(pipeline.get("quality"), section="pipeline.quality")
        monitoring = _ensure_mapping(payload.get("monitoring"), section="monitoring")

        return cls(
            extraction=dict(extraction),
            transformation=dict(transformation),
            organization=dict(organization),
            linking=dict(linking),
            quality=dict(quality),
            monitoring=dict(monitoring),
        )

    @property
    def metrics_output(self) -> Path | None:
        output = self.monitoring.get("metrics_output")
        if not output:
            return None
        return Path(str(output))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline": {
                "extraction": dict(self.extraction),
                "transformation": dict(self.transformation),
                "organization": dict(self.organization),
                "linking": dict(self.linking),
                "quality": dict(self.quality),
            },
            "monitoring": dict(self.monitoring),
        }

    def dumps(self) -> str:  # pragma: no cover - convenience not used in tests
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def load_pipeline_config(path: Path | None = None) -> PipelineConfig:
    """Load pipeline configuration from YAML, defaulting to built-in path."""

    candidate = _DEFAULT_CONFIG_PATH if path is None else path.expanduser()
    if not candidate.exists():
        # Fall back to an empty configuration when not present, enabling tests to inject overrides.
        return PipelineConfig.from_mapping({})
    if yaml is None:
        raise ImportError("PyYAML is required to load pipeline configuration files.")
    raw = candidate.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Pipeline configuration root must be a mapping.")
    return PipelineConfig.from_mapping(data)


__all__ = ["PipelineConfig", "load_pipeline_config"]
