"""Metadata utilities for IA quality metrics and front matter generation."""
from __future__ import annotations

from datetime import datetime
from typing import Final, Sequence

import yaml

from . import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)

_MIN_COMPLETENESS: Final[float] = 0.7
_MIN_FINDABILITY: Final[float] = 0.6


def completeness_score(metadata: KBMetadata) -> float:
    """Return the completeness value, falling back to a heuristic when absent."""

    if metadata.ia.completeness is not None:
        return metadata.ia.completeness

    total = 5
    filled = 0
    if metadata.doc_type:
        filled += 1
    if metadata.primary_topic:
        filled += 1
    if metadata.dc.title:
        filled += 1
    if metadata.tags:
        filled += 1
    if metadata.sources:
        filled += 1
    return round(filled / total, 2)


def assert_quality_thresholds(metadata: KBMetadata) -> None:
    """Validate metadata against baseline IA quality standards."""

    completeness = completeness_score(metadata)
    if completeness < _MIN_COMPLETENESS:
        raise ValueError(
            f"Completeness {completeness:.2f} below minimum threshold {_MIN_COMPLETENESS:.2f}."
        )
    if metadata.ia.findability_score is None:
        raise ValueError("Findability score is required for IA validation.")
    if metadata.ia.findability_score < _MIN_FINDABILITY:
        raise ValueError(
            f"Findability {metadata.ia.findability_score:.2f} below minimum {_MIN_FINDABILITY:.2f}."
        )


def _dc_to_dict(dc: DublinCoreMetadata) -> dict[str, object]:
    return {
        "title": dc.title,
        "creator": dc.creator,
        "subject": list(dc.subject),
        "description": dc.description,
        "publisher": dc.publisher,
        "contributor": list(dc.contributor),
        "date": dc.date,
        "type": dc.doc_type,
        "format": dc.format,
        "identifier": dc.identifier,
        "source": dc.source,
        "language": dc.language,
        "relation": list(dc.relation),
        "coverage": dc.coverage,
    }


def _ia_to_dict(ia: IAMetadata) -> dict[str, object]:
    payload: dict[str, object] = {
        "findability_score": ia.findability_score,
        "completeness": ia.completeness,
        "depth": ia.depth,
        "audience": list(ia.audience),
        "navigation_path": list(ia.navigation_path),
        "related_by_topic": list(ia.related_by_topic),
        "related_by_entity": list(ia.related_by_entity),
        "update_frequency": ia.update_frequency,
    }
    if ia.last_updated is not None:
        payload["last_updated"] = _datetime_to_iso(ia.last_updated)
    return payload


def _datetime_to_iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def _sources_to_list(sources: Sequence[SourceReference]) -> list[dict[str, object]]:
    return [
        {
            "kb_id": ref.kb_id,
            "pages": list(ref.pages),
        }
        for ref in sources
    ]


def metadata_payload(metadata: KBMetadata) -> dict[str, object]:
    """Serialise metadata to a dictionary suitable for front matter."""

    return {
        "type": metadata.doc_type,
        "primary_topic": metadata.primary_topic,
        "secondary_topics": list(metadata.secondary_topics),
        "tags": list(metadata.tags),
        "sources": _sources_to_list(metadata.sources),
        "dublin_core": _dc_to_dict(metadata.dc),
        "ia": _ia_to_dict(metadata.ia),
    }


def document_front_matter(document: KBDocument) -> dict[str, object]:
    """Build the IA front matter payload for a document."""

    payload = {
        "title": document.title,
        "slug": document.slug,
        "kb_id": document.kb_id,
        "aliases": list(document.aliases),
        "related_concepts": list(document.related_concepts),
    }
    payload.update(metadata_payload(document.metadata))
    return payload


def render_document(document: KBDocument) -> str:
    """Render a full markdown document with YAML front matter."""

    front_matter = document_front_matter(document)
    yaml_block = yaml.safe_dump(front_matter, sort_keys=False)
    body = document.body or ""
    if body and not body.endswith("\n"):
        body = f"{body}\n"
    return f"---\n{yaml_block}---\n\n{body}" if body else f"---\n{yaml_block}---\n"
