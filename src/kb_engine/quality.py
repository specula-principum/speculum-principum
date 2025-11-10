"""Quality analysis utilities for the knowledge base engine."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence, cast

import yaml

from src.knowledge_base import KBDocument
from src.knowledge_base.metadata import completeness_score

from .models import QualityGap


@dataclass(frozen=True)
class _LoadedFrontMatter:
    kb_id: str
    doc_type: str
    payload: Mapping[str, object]
    ia: Mapping[str, object]
    tags: tuple[str, ...]
    related: tuple[str, ...]
    backlinks: tuple[str, ...]
    sources: tuple[Mapping[str, object], ...]
    aliases: tuple[str, ...]
    body: str


class QualityAnalyzer:
    """Calculates and tracks knowledge base quality metrics."""

    def __init__(
        self,
        *,
        min_body_length: int = 80,
        completeness_floor: float = 0.7,
        findability_floor: float = 0.6,
    ) -> None:
        self._min_body_length = max(0, int(min_body_length))
        self._completeness_floor = float(completeness_floor)
        self._findability_floor = float(findability_floor)
        self._cache: MutableMapping[str, _LoadedFrontMatter] = {}
        self._kb_root: Path | None = None

    # Public API -----------------------------------------------------

    def calculate_completeness(self, document: KBDocument) -> float:
        """Return a completeness score between 0.0 and 1.0."""

        if not isinstance(document, KBDocument):
            raise TypeError("calculate_completeness expects a KBDocument instance")

        baseline = completeness_score(document.metadata)
        body_length = len(document.body.strip()) if document.body else 0
        body_bonus = min(0.1, body_length / 1000.0)
        alias_bonus = 0.04 if document.aliases else 0.0
        citations = sum(len(ref.pages) or 1 for ref in document.metadata.sources)
        citation_bonus = min(0.06, 0.01 * citations)
        score = min(1.0, baseline + body_bonus + alias_bonus + citation_bonus)
        return round(score, 3)

    def calculate_findability(self, kb_id: str, kb_root: Path) -> float:
        """Return a findability score for the specified knowledge base entry."""

        front_matter = self._load_front_matter(kb_root, kb_id)
        base = _as_float(front_matter.ia.get("findability_score"), default=0.0)

        tags = front_matter.tags
        backlinks = front_matter.backlinks
        related = front_matter.related
        aliases = front_matter.aliases
        navigation = tuple(self._iter_strings(front_matter.ia.get("navigation_path", ())))

        score: float = base or 0.0
        if tags:
            score += min(0.1, 0.015 * len(tags))
        if related:
            score += min(0.08, 0.02 * len(related))
        if backlinks:
            score += min(0.15, 0.03 * len(backlinks))
        if aliases:
            score += 0.03
        if navigation:
            score += min(0.07, max(0, 4 - len(navigation)) * 0.02)

        return round(min(1.0, score), 3)

    def identify_gaps(self, kb_root: Path) -> Sequence[QualityGap]:
        """Identify quality gaps across the knowledge base."""

        kb_root = kb_root.expanduser().resolve()
        if not kb_root.exists():
            raise FileNotFoundError(f"kb_root '{kb_root}' does not exist")

        gaps: list[QualityGap] = []
        for path in sorted(kb_root.rglob("*.md")):
            try:
                front_matter = self._load_front_matter_from_path(kb_root, path)
            except ValueError as exc:
                kb_id = path.relative_to(kb_root).with_suffix("").as_posix()
                gaps.append(
                    QualityGap(
                        kb_id=kb_id,
                        issue="invalid-front-matter",
                        severity="error",
                        details={"path": str(path), "error": str(exc)},
                    )
                )
                continue

            kb_id = front_matter.kb_id
            issue_details = {"path": str(path)}

            if not front_matter.sources:
                gaps.append(QualityGap(kb_id, "missing-sources", "error", issue_details))

            if not front_matter.tags:
                gaps.append(QualityGap(kb_id, "missing-tags", "warning", issue_details))

            if front_matter.doc_type == "concept" and not front_matter.related:
                gaps.append(QualityGap(kb_id, "missing-related-concepts", "warning", issue_details))

            if front_matter.doc_type == "concept" and not front_matter.backlinks:
                gaps.append(QualityGap(kb_id, "missing-backlinks", "info", issue_details))

            body_length = len(front_matter.body.strip())
            if body_length < self._min_body_length:
                gaps.append(
                    QualityGap(
                        kb_id,
                        "body-too-short",
                        "warning",
                        {**issue_details, "length": body_length, "minimum": self._min_body_length},
                    )
                )

            findability = _as_float(front_matter.ia.get("findability_score"))
            if findability is not None and findability < self._findability_floor:
                gaps.append(
                    QualityGap(
                        kb_id,
                        "findability-below-threshold",
                        "warning",
                        {**issue_details, "score": findability, "threshold": self._findability_floor},
                    )
                )

            completeness = _as_float(front_matter.ia.get("completeness"))
            if completeness is not None and completeness < self._completeness_floor:
                gaps.append(
                    QualityGap(
                        kb_id,
                        "completeness-below-threshold",
                        "warning",
                        {**issue_details, "score": completeness, "threshold": self._completeness_floor},
                    )
                )

        return tuple(gaps)

    # Internal helpers ------------------------------------------------

    def _load_front_matter(self, kb_root: Path, kb_id: str) -> _LoadedFrontMatter:
        kb_root = kb_root.expanduser().resolve()
        if self._kb_root is not None and kb_root != self._kb_root:
            self._cache.clear()
        self._kb_root = kb_root

        cached = self._cache.get(kb_id)
        if cached is not None:
            return cached

        path = (kb_root / kb_id).with_suffix(".md")
        if not path.exists():
            raise FileNotFoundError(f"Document '{kb_id}' not found under '{kb_root}'")

        document = self._load_front_matter_from_path(kb_root, path)
        self._cache[kb_id] = document
        return document

    def _load_front_matter_from_path(self, kb_root: Path, path: Path) -> _LoadedFrontMatter:
        front, body = self._parse_markdown(path)
        kb_id = str(front.get("kb_id") or path.relative_to(kb_root).with_suffix("").as_posix())
        doc_type = str(front.get("type", "")).strip()
        ia_raw = front.get("ia")
        ia: Mapping[str, object]
        if isinstance(ia_raw, Mapping):
            ia = dict(cast(Mapping[str, object], ia_raw))
        else:
            ia = {}

        tags = tuple(self._iter_strings(front.get("tags", ())))
        related = tuple(self._iter_strings(front.get("related_concepts", ())))
        backlinks = tuple(self._iter_strings(ia.get("related_by_topic", ())))
        aliases = tuple(self._iter_strings(front.get("aliases", ())))
        sources_raw = front.get("sources")
        if isinstance(sources_raw, Sequence):
            sources = tuple(
                item
                for item in sources_raw
                if isinstance(item, Mapping) and item.get("kb_id")
            )
        else:
            sources = ()

        return _LoadedFrontMatter(
            kb_id=kb_id,
            doc_type=doc_type,
            payload=front,
            ia=ia,
            tags=tags,
            related=related,
            backlinks=backlinks,
            sources=sources,
            aliases=aliases,
            body=body,
        )

    @staticmethod
    def _parse_markdown(path: Path) -> tuple[dict[str, object], str]:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("Missing YAML front matter header")

        terminator = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                terminator = index
                break
        if terminator is None:
            raise ValueError("Unterminated YAML front matter")

        yaml_payload = "\n".join(lines[1:terminator])
        body = "\n".join(lines[terminator + 1 :])
        front = yaml.safe_load(yaml_payload) or {}
        if not isinstance(front, dict):
            raise ValueError("Front matter must be a mapping")
        if body:
            body = body + "\n"
        return front, body

    @staticmethod
    def _iter_strings(values: object) -> Iterable[str]:
        if values is None:
            return ()
        if isinstance(values, str):
            return (values.strip(),) if values.strip() else ()
        try:
            tokens: list[str] = []
            for item in values:  # type: ignore[typeddict-item]
                if isinstance(item, str):
                    value = item.strip()
                else:
                    value = str(item).strip()
                if value:
                    tokens.append(value)
            return tuple(tokens)
        except TypeError:
            value = str(values).strip()
            return (value,) if value else ()


def _as_float(value: object, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return default
        try:
            return float(token)
        except ValueError:
            return default
    return default
