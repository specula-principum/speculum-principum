"""Relationship management utilities for the knowledge base engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence

import yaml

from src.knowledge_base import KBRelationship

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ConceptGraph:
    """In-memory representation of concept relationships."""

    concepts: tuple[str, ...]
    edges: tuple[KBRelationship, ...]
    metrics: Mapping[str, float] = field(default_factory=dict)

    def adjacency(self) -> Mapping[str, tuple[str, ...]]:
        """Return adjacency map (outgoing edges) for quick inspection."""

        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
        return {node: tuple(sorted(neighbors)) for node, neighbors in sorted(adjacency.items())}

    def manifest(self) -> dict[str, object]:
        """Return a serialisable manifest describing the graph."""

        return {
            "concepts": list(self.concepts),
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.relationship_type,
                    **({"weight": edge.weight} if edge.weight is not None else {}),
                }
                for edge in self.edges
            ],
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class _LoadedDocument:
    kb_id: str
    doc_type: str
    path: Path
    front_matter: Mapping[str, object]
    body: str
    outgoing_topics: tuple[str, ...]
    tags: frozenset[str]
    tokens: frozenset[str]


class LinkBuilder:
    """Generates and maintains relationships between knowledge base documents."""

    def __init__(self, *, min_similarity: float = 0.05, relationship_type: str = "related-to") -> None:
        if min_similarity < 0 or min_similarity > 1:
            raise ValueError("min_similarity must be within [0.0, 1.0].")
        self._min_similarity = float(min_similarity)
        self._relationship_type = relationship_type
        self._documents: MutableMapping[str, _LoadedDocument] = {}
        self._kb_root: Path | None = None
        self._graph: ConceptGraph | None = None

    # Public API -----------------------------------------------------

    def build_concept_graph(self, kb_root: Path) -> ConceptGraph:
        """Create a graph that represents relationships between concepts."""

        documents = self._load_documents(kb_root)
        concepts = {kb_id: doc for kb_id, doc in documents.items() if doc.doc_type == "concept"}

        edges: dict[tuple[str, str], KBRelationship] = {}
        for kb_id, document in concepts.items():
            for target in document.outgoing_topics:
                if target not in concepts or target == kb_id:
                    continue
                weight = self._relationship_weight(document, concepts[target])
                relationship = KBRelationship(
                    source=kb_id,
                    target=target,
                    relationship_type=self._relationship_type,
                    weight=weight,
                )
                relationship.validate()
                edges[(kb_id, target)] = relationship

        metrics = {
            "concept_count": float(len(concepts)),
            "edge_count": float(len(edges)),
        }
        graph = ConceptGraph(
            concepts=tuple(sorted(concepts)),
            edges=tuple(sorted(edges.values(), key=lambda edge: (edge.source, edge.target))),
            metrics=metrics,
        )
        self._graph = graph
        return graph

    def generate_backlinks(self, kb_root: Path) -> tuple[str, ...]:
        """Create bidirectional links to improve navigation across documents."""

        documents = self._load_documents(kb_root)
        reverse_index: dict[str, set[str]] = {}
        updated: list[str] = []

        for kb_id, document in documents.items():
            for target in document.outgoing_topics:
                if target == kb_id:
                    continue
                reverse_index.setdefault(target, set()).add(kb_id)

        for kb_id, document in documents.items():
            backlinks = tuple(sorted(reverse_index.get(kb_id, ())))
            current = tuple(self._current_backlinks(document.front_matter))
            if backlinks == current:
                continue

            updated_front_matter = dict(document.front_matter)
            ia_raw = updated_front_matter.get("ia")
            if isinstance(ia_raw, Mapping):
                ia_section = dict(ia_raw)
            else:
                ia_section = {}
            ia_section["related_by_topic"] = list(backlinks)
            updated_front_matter["ia"] = ia_section
            self._write_document(document.path, updated_front_matter, document.body)
            updated.append(kb_id)

        # Reload to keep in-memory index consistent with file contents
        self._load_documents(kb_root, force=True)
        return tuple(sorted(updated))

    def suggest_related(self, kb_id: str, *, limit: int = 10) -> Sequence[str]:
        """Suggest related knowledge base entries for the requested identifier."""

        if limit <= 0:
            return ()
        if kb_id not in self._documents:
            if self._kb_root is None:
                raise RuntimeError("Link index not initialised; call build_concept_graph first.")
            # If we have a kb_root, reload to capture potential new files before giving up.
            self._load_documents(self._kb_root, force=True)
            if kb_id not in self._documents:
                return ()

        target_doc = self._documents[kb_id]
        suggestions: list[tuple[float, str]] = []
        for other_id, other_doc in self._documents.items():
            if other_id == kb_id:
                continue
            score = self._score_documents(target_doc, other_doc)
            if score < self._min_similarity:
                continue
            suggestions.append((score, other_id))

        suggestions.sort(key=lambda item: (-item[0], item[1]))
        return tuple(kb_id for _, kb_id in suggestions[:limit])

    # Internal helpers ------------------------------------------------

    def _load_documents(self, kb_root: Path, *, force: bool = False) -> Dict[str, _LoadedDocument]:
        kb_root = kb_root.expanduser().resolve()
        if not kb_root.exists():
            raise FileNotFoundError(f"kb_root '{kb_root}' does not exist")
        if self._kb_root is not None and kb_root != self._kb_root:
            # If the root changes we must rebuild the cache regardless of force flag.
            force = True

        if self._documents and not force:
            return dict(self._documents)

        loaded: dict[str, _LoadedDocument] = {}
        for path in sorted(kb_root.rglob("*.md")):
            try:
                front_matter, body = self._parse_markdown(path)
            except ValueError:
                continue
            kb_id = str(front_matter.get("kb_id")) if front_matter.get("kb_id") else ""
            doc_type = str(front_matter.get("type", "")).strip()
            if not kb_id or not doc_type:
                continue
            outgoing = self._extract_related(front_matter.get("related_concepts"))
            tags = frozenset(self._iter_strings(front_matter.get("tags", ())))
            tokens = frozenset(self._tokenise(front_matter, body))
            loaded[kb_id] = _LoadedDocument(
                kb_id=kb_id,
                doc_type=doc_type,
                path=path,
                front_matter=front_matter,
                body=body,
                outgoing_topics=outgoing,
                tags=tags,
                tokens=tokens,
            )

        self._documents = loaded
        self._kb_root = kb_root
        return dict(self._documents)

    def _relationship_weight(self, source: _LoadedDocument, target: _LoadedDocument) -> float:
        similarity = self._jaccard(source.tokens, target.tokens)
        shared_tags = len(source.tags & target.tags)
        tag_bonus = 0.05 * shared_tags
        weight = max(0.1, min(1.0, round(similarity + tag_bonus, 3)))
        return weight

    def _current_backlinks(self, front_matter: Mapping[str, object]) -> Iterable[str]:
        ia_section = front_matter.get("ia")
        if not isinstance(ia_section, Mapping):
            return ()
        return tuple(self._iter_strings(ia_section.get("related_by_topic", ())))

    def _write_document(self, path: Path, front_matter: Mapping[str, object], body: str) -> None:
        yaml_block = yaml.safe_dump(dict(front_matter), sort_keys=False)
        if body and not body.endswith("\n"):
            body = f"{body}\n"
        payload = f"---\n{yaml_block}---\n"
        if body:
            payload = f"{payload}\n{body}"
        path.write_text(payload, encoding="utf-8")

    def _score_documents(self, source: _LoadedDocument, target: _LoadedDocument) -> float:
        similarity = self._jaccard(source.tokens, target.tokens)
        if similarity == 0:
            similarity = 0.0
        tag_similarity = 0.0
        if source.tags or target.tags:
            tag_similarity = len(source.tags & target.tags) / len(source.tags | target.tags)

        link_bonus = 0.0
        if target.kb_id in source.outgoing_topics:
            link_bonus += 0.35
        if source.kb_id in target.outgoing_topics:
            link_bonus += 0.35

        score = min(1.0, round(link_bonus + (0.5 * similarity) + (0.15 * tag_similarity), 4))
        return score

    @staticmethod
    def _parse_markdown(path: Path) -> tuple[dict[str, object], str]:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("Missing YAML front matter header")

        end_index = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
        if end_index is None:
            raise ValueError("Unterminated YAML front matter")

        front_matter_text = "\n".join(lines[1:end_index])
        body_lines = lines[end_index + 1 :]
        front_matter = yaml.safe_load(front_matter_text) or {}
        if not isinstance(front_matter, dict):
            raise ValueError("Front matter must be a mapping")
        body = "\n".join(body_lines)
        if body:
            body = body + "\n"
        return front_matter, body

    @staticmethod
    def _tokenise(front_matter: Mapping[str, object], body: str) -> Iterable[str]:
        tokens: set[str] = set()
        for key in ("title", "kb_id"):
            value = front_matter.get(key)
            if isinstance(value, str):
                tokens.update(_TOKEN_PATTERN.findall(value.lower()))
        for field in ("tags", "aliases", "related_concepts"):
            value = front_matter.get(field)
            for item in LinkBuilder._iter_strings(value):
                tokens.update(_TOKEN_PATTERN.findall(item.lower()))
        if body:
            snippet = body[:10_000]
            tokens.update(_TOKEN_PATTERN.findall(snippet.lower()))
        return tokens

    @staticmethod
    def _jaccard(lhs: Iterable[str], rhs: Iterable[str]) -> float:
        left = set(lhs)
        right = set(rhs)
        if not left and not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return round(len(left & right) / len(union), 4)

    @staticmethod
    def _extract_related(raw: object) -> tuple[str, ...]:
        values = [value for value in LinkBuilder._iter_strings(raw) if value]
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return tuple(ordered)

    @staticmethod
    def _iter_strings(values: object) -> Iterable[str]:
        if values is None:
            return ()
        if isinstance(values, str):
            return (values.strip(),)
        try:
            result = []
            for value in values:  # type: ignore[typeddict-item]
                if isinstance(value, str):
                    result.append(value.strip())
                else:
                    result.append(str(value).strip())
            return tuple(result)
        except TypeError:
            return (str(values).strip(),)

