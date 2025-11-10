"""Utilities for Copilot agent workflows over the knowledge base."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

import yaml

from src.knowledge_base import (
    DublinCoreMetadata,
    IAMetadata,
    KBDocument,
    KBMetadata,
    SourceReference,
)
from src.knowledge_base.metadata import assert_quality_thresholds
from src.knowledge_base.validation import QualityMetrics, calculate_quality_metrics

if TYPE_CHECKING:
    from src.integrations.github.assign_copilot import IssueDetails


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate results from validating knowledge base changes."""

    kb_root: Path
    documents_checked: int
    documents_valid: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    quality: QualityMetrics

    @property
    def is_successful(self) -> bool:
        """Return ``True`` when no blocking validation errors were found."""

        return not self.errors


def prepare_kb_extraction_context(
    issue: IssueDetails,
    *,
    kb_root: Path | None = None,
) -> str:
    """Produce a structured context block tailored to an extraction issue."""

    parsed = _parse_issue_body(issue.body)
    documents, _ = _gather_documents(kb_root) if kb_root else ((), ())

    lines: list[str] = [
        f"Issue #{issue.number}: {issue.title}",
        f"URL: {issue.url}",
        f"Labels: {', '.join(issue.labels) if issue.labels else 'none'}",
    ]

    source_fields = (
        ("Source Path", parsed.fields.get("Source Path")),
        ("Source Type", parsed.fields.get("Source Type")),
        ("Processing Date", parsed.fields.get("Processing Date")),
        ("Target KB Root", parsed.fields.get("Target KB Root")),
    )

    details = [value for _, value in source_fields if value]
    if details or parsed.tasks:
        lines.append("")

    if details:
        lines.append("Source Inputs:")
        for label, value in source_fields:
            if value:
                lines.append(f"- {label}: {value}")

    if parsed.tasks:
        lines.append("")
        lines.append("Required Actions:")
        for item in parsed.tasks:
            lines.append(f"- {item}")

    if documents:
        lines.append("")
        lines.append("Knowledge Base Snapshot:")
        lines.append(f"- Documents tracked: {len(documents)}")
        type_counts = Counter(doc.metadata.doc_type for doc in documents)
        for doc_type, count in sorted(type_counts.items()):
            lines.append(f"  - {doc_type}: {count}")
        topic_counts = Counter(doc.metadata.primary_topic for doc in documents)
        top_topics = topic_counts.most_common(5)
        if top_topics:
            joined = ", ".join(f"{topic} ({count})" for topic, count in top_topics)
            lines.append(f"- Top primary topics: {joined}")

    if parsed.notes:
        lines.append("")
        lines.append("Additional Notes:")
        lines.extend(f"- {note}" for note in parsed.notes)

    return "\n".join(lines).strip()


def validate_kb_changes(kb_root: Path) -> ValidationReport:
    """Validate the knowledge base and collect aggregate quality signals."""

    resolved_root = kb_root.expanduser().resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Knowledge base root does not exist: {resolved_root}")

    documents, load_errors = _gather_documents(resolved_root)
    errors: list[str] = list(load_errors)
    valid: list[KBDocument] = []

    for document in documents:
        try:
            document.validate()
            assert_quality_thresholds(document.metadata)
        except ValueError as exc:
            label = document.kb_id or document.title or document.slug
            errors.append(f"{label}: {exc}")
            continue
        valid.append(document)

    quality = calculate_quality_metrics(valid)
    warnings = tuple(
        f"{kb_id}: quality thresholds not met"
        for kb_id in quality.below_threshold
    )

    report = ValidationReport(
        kb_root=resolved_root,
        documents_checked=len(documents),
        documents_valid=len(valid),
        errors=tuple(errors),
        warnings=warnings,
        quality=quality,
    )
    return report


def generate_quality_report(
    kb_root: Path,
    issue_number: int,
    *,
    output_dir: Path | None = None,
    report: ValidationReport | None = None,
) -> Path:
    """Write a markdown quality report for the supplied issue."""

    resolved_root = kb_root.expanduser()
    computed = report or validate_kb_changes(resolved_root)
    target_dir = (output_dir or Path("reports")).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"quality-{issue_number}.md"

    lines = [
        "# Knowledge Base Quality Report",
        f"*KB Root:* `{computed.kb_root}`",
        f"*Documents Checked:* {computed.documents_checked}",
        f"*Documents Valid:* {computed.documents_valid}",
        f"*Average Completeness:* {computed.quality.average_completeness:.2f}",
        f"*Average Findability:* {computed.quality.average_findability:.2f}",
    ]

    if computed.errors:
        lines.append("\n## Errors")
        lines.extend(f"- {msg}" for msg in computed.errors)

    if computed.warnings:
        lines.append("\n## Warnings")
        lines.extend(f"- {msg}" for msg in computed.warnings)

    lines.append("\n## Notes")
    lines.append(
        "- Below-threshold documents: "
        + (", ".join(computed.quality.below_threshold) if computed.quality.below_threshold else "none")
    )

    target_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target_path


def gather_kb_documents(kb_root: Path | None) -> tuple[KBDocument, ...]:
    """Return all knowledge base documents located beneath ``kb_root``."""

    documents, _ = _gather_documents(kb_root)
    return documents


# Internal helpers -----------------------------------------------------


@dataclass(frozen=True)
class _ParsedIssue:
    fields: Mapping[str, str]
    tasks: tuple[str, ...]
    notes: tuple[str, ...]


def _parse_issue_body(body: str) -> _ParsedIssue:
    fields: dict[str, str] = {}
    tasks: list[str] = []
    notes: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("- ["):
            task = line.split("]", 1)[-1].strip()
            if task:
                tasks.append(_clean_markdown(task))
            continue
        if line.startswith("**") and "**" in line[2:]:
            label, _, remainder = line[2:].partition("**")
            value = remainder.lstrip(": ")
            label_text = label.strip().rstrip(":")
            if label_text and value:
                fields[label_text] = _clean_markdown(value.strip())
            continue
        notes.append(_clean_markdown(line))

    return _ParsedIssue(fields=fields, tasks=tuple(tasks), notes=tuple(notes))


def _gather_documents(kb_root: Path | None) -> tuple[tuple[KBDocument, ...], tuple[str, ...]]:
    if kb_root is None:
        return (), ()
    resolved = kb_root.expanduser().resolve()
    if not resolved.exists():
        return (), ()

    documents: list[KBDocument] = []
    errors: list[str] = []
    for path in sorted(resolved.rglob("*.md")):
        try:
            relative_path = path.relative_to(resolved)
        except ValueError:
            continue

        if relative_path.parts and relative_path.parts[0] == "meta":
            continue

        try:
            front_matter, body = _read_markdown(path)
            document = _document_from_front_matter(front_matter, body, path, kb_root=resolved)
        except ValueError as exc:
            errors.append(f"{relative_path}: {exc}")
            continue
        documents.append(document)
    return tuple(documents), tuple(errors)


def _read_markdown(path: Path) -> tuple[Mapping[str, object], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML front matter")

    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break
    if closing is None:
        raise ValueError("unterminated YAML front matter")

    yaml_block = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    payload = yaml.safe_load(yaml_block) or {}
    if not isinstance(payload, Mapping):
        raise ValueError("front matter must be a mapping")
    return payload, body


def _document_from_front_matter(
    front: Mapping[str, object],
    body: str,
    path: Path,
    *,
    kb_root: Path,
) -> KBDocument:
    try:
        relative_path = path.relative_to(kb_root)
    except ValueError as exc:
        raise ValueError("document must reside within the knowledge base root") from exc

    kb_id = _require_string(front.get("kb_id"), "kb_id")
    slug = _string_or_default(front.get("slug"), relative_path.stem)
    title = _string_or_default(front.get("title"), slug.replace("-", " ").title())

    doc_type = _require_string(front.get("type"), "type")
    primary_topic = _require_string(front.get("primary_topic"), "primary_topic")
    secondary_topics = _iter_strings(front.get("secondary_topics"))
    tags = _iter_strings(front.get("tags"))

    sources_payload = front.get("sources") or ()
    if not isinstance(sources_payload, Sequence):
        raise ValueError("sources must be a sequence")
    sources: list[SourceReference] = []
    for entry in sources_payload:
        if not isinstance(entry, Mapping):
            raise ValueError("source entries must be mappings")
        kb_target = _require_string(entry.get("kb_id"), "sources[kb_id]")
        pages = _iter_ints(entry.get("pages"))
        sources.append(SourceReference(kb_id=kb_target, pages=pages))

    dc_mapping = front.get("dublin_core") or front.get("dc") or {}
    if not isinstance(dc_mapping, Mapping):
        raise ValueError("dublin_core section must be a mapping")
    dc_title = _string_or_default(dc_mapping.get("title"), title)
    dc = DublinCoreMetadata(
        title=dc_title,
        creator=_string_or_none(dc_mapping.get("creator")),
        subject=_iter_strings(dc_mapping.get("subject")),
        description=_string_or_none(dc_mapping.get("description")),
        publisher=_string_or_none(dc_mapping.get("publisher")),
        contributor=_iter_strings(dc_mapping.get("contributor")),
        date=_string_or_none(dc_mapping.get("date")),
        doc_type=_string_or_none(dc_mapping.get("type")),
        format=_string_or_none(dc_mapping.get("format")),
        identifier=_string_or_none(dc_mapping.get("identifier")),
        source=_string_or_none(dc_mapping.get("source")),
        language=_string_or_none(dc_mapping.get("language")),
        relation=_iter_strings(dc_mapping.get("relation")),
        coverage=_string_or_none(dc_mapping.get("coverage")),
    )

    ia_mapping = front.get("ia") or {}
    if not isinstance(ia_mapping, Mapping):
        raise ValueError("ia section must be a mapping")
    ia = IAMetadata(
        findability_score=_optional_float(ia_mapping.get("findability_score")),
        completeness=_optional_float(ia_mapping.get("completeness")),
        depth=_optional_int(ia_mapping.get("depth")),
        audience=_iter_strings(ia_mapping.get("audience")),
        navigation_path=_iter_strings(ia_mapping.get("navigation_path")),
        related_by_topic=_iter_strings(ia_mapping.get("related_by_topic")),
        related_by_entity=_iter_strings(ia_mapping.get("related_by_entity")),
        last_updated=_optional_datetime(ia_mapping.get("last_updated")),
        update_frequency=_string_or_none(ia_mapping.get("update_frequency")),
    )

    metadata = KBMetadata(
        doc_type=doc_type,
        primary_topic=primary_topic,
        secondary_topics=secondary_topics,
        tags=tags,
        sources=tuple(sources),
        dc=dc,
        ia=ia,
    )

    aliases = _iter_strings(front.get("aliases"))
    related = _iter_strings(front.get("related_concepts"))

    document = KBDocument(
        kb_id=kb_id,
        slug=slug,
        title=title,
        metadata=metadata,
        aliases=aliases,
        related_concepts=related,
        body=body.strip() if body else None,
    )

    return document


def _iter_strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        token = value.strip()
        return (token,) if token else ()
    if isinstance(value, Sequence):
        items: list[str] = []
        for entry in value:
            if entry is None:
                continue
            token = str(entry).strip()
            if token:
                items.append(token)
        return tuple(items)
    return (str(value).strip(),) if str(value).strip() else ()


def _iter_ints(value: object) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items: list[int] = []
        for entry in value:
            number = _coerce_int(entry)
            if number <= 0:
                raise ValueError("pages entries must be positive integers")
            items.append(number)
        return tuple(items)
    number = _coerce_int(value)
    if number <= 0:
        raise ValueError("pages entries must be positive integers")
    return (number,)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return _coerce_float(value)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return _coerce_int(value)


def _optional_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("expected ISO-8601 datetime") from exc
    raise ValueError("expected ISO-8601 datetime")


def _require_string(value: object, label: str) -> str:
    token = _string_or_default(value, "")
    if not token:
        raise ValueError(f"{label} is required")
    return token


def _string_or_default(value: object, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_markdown(value: str) -> str:
    cleaned = value.replace("**", "").replace("`", "").strip()
    return cleaned


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid integers")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError("non-integer floats are not allowed")
    if isinstance(value, str):
        token = value.strip()
        if not token:
            raise ValueError("integer value cannot be blank")
        try:
            return int(token)
        except ValueError as exc:
            raise ValueError("expected an integer") from exc
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("expected an integer") from exc


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid floats")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip()
        if not token:
            raise ValueError("float value cannot be blank")
        try:
            return float(token)
        except ValueError as exc:
            raise ValueError("expected a float") from exc
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("expected a float") from exc
