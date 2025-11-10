"""High-level orchestration for document parsing workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Sequence

from . import utils
from .base import ParseTarget, ParserError
from .registry import ParserRegistry, registry
from .storage import ManifestEntry, ParseStorage

_DEFAULT_SCAN_SUFFIXES = (".pdf", ".docx", ".html", ".htm", ".xhtml")


@dataclass(slots=True)
class ParseOutcome:
    source: str
    parser: str | None
    status: str
    artifact_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    checksum: str | None = None
    error: str | None = None
    message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in {"completed", "empty", "skipped"}


def parse_single_target(
    source: str | Path,
    *,
    storage: ParseStorage,
    registry_override: ParserRegistry | None = None,
    expected_parser: str | None = None,
    force: bool = False,
    media_type: str | None = None,
    is_remote: bool | None = None,
) -> ParseOutcome:
    active_registry = registry_override or registry
    target = _build_target(source, is_remote=is_remote, media_type=media_type)

    try:
        parser = active_registry.require_parser(target)
    except ParserError as exc:
        return ParseOutcome(
            source=target.source,
            parser=None,
            status="error",
            error=str(exc),
        )

    if expected_parser and parser.name != expected_parser:
        return ParseOutcome(
            source=target.source,
            parser=parser.name,
            status="error",
            error=f"Expected parser '{expected_parser}' but '{parser.name}' matched",
        )

    precomputed_checksum = None

    if not force and not target.is_remote:
        try:
            path = target.to_path()
        except ValueError:
            path = Path(target.source)
        precomputed_checksum = utils.sha256_path(path)
        if not storage.should_process(precomputed_checksum):
            return _outcome_from_manifest(
                target.source,
                parser.name,
                storage.manifest().get(precomputed_checksum),
                checksum=precomputed_checksum,
                message="Already processed",
            )

    try:
        document = parser.extract(target)
    except ParserError as exc:
        return ParseOutcome(
            source=target.source,
            parser=parser.name,
            status="error",
            checksum=precomputed_checksum,
            error=str(exc),
        )

    checksum = document.checksum

    if not force and not storage.should_process(checksum):
        return _outcome_from_manifest(
            document.target.source,
            parser.name,
            storage.manifest().get(checksum),
            checksum=checksum,
            message="Already processed",
        )

    entry = storage.persist_document(document)

    return ParseOutcome(
        source=document.target.source,
        parser=parser.name,
        status=entry.status,
        artifact_path=entry.artifact_path,
        warnings=document.warnings,
        checksum=checksum,
    )


def scan_and_parse(
    root: str | Path,
    *,
    storage: ParseStorage,
    registry_override: ParserRegistry | None = None,
    suffixes: Sequence[str] | None = None,
    recursive: bool = True,
    force: bool = False,
    limit: int | None = None,
    include_patterns: Sequence[str] | None = None,
    exclude_patterns: Sequence[str] | None = None,
) -> list[ParseOutcome]:
    candidates = collect_parse_candidates(
        root,
        suffixes=suffixes,
        recursive=recursive,
        storage_root=storage.root,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )
    if limit is not None and limit >= 0:
        candidates = candidates[:limit]

    results: list[ParseOutcome] = []
    for candidate in candidates:
        outcome = parse_single_target(
            candidate,
            storage=storage,
            registry_override=registry_override,
            force=force,
        )
        results.append(outcome)
    return results


def collect_parse_candidates(
    root: str | Path,
    *,
    suffixes: Sequence[str] | None = None,
    recursive: bool = True,
    storage_root: Path | None = None,
    include_patterns: Sequence[str] | None = None,
    exclude_patterns: Sequence[str] | None = None,
) -> list[Path]:
    """Return candidate paths that match the parsing filters without executing parsers."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Scan root '{root_path}' does not exist")

    normalized_suffixes = utils.normalize_suffixes(
        suffixes,
        default=_DEFAULT_SCAN_SUFFIXES,
        sort=True,
        preserve_order=False,
    )

    return _collect_candidates(
        root_path,
        normalized_suffixes,
        recursive,
        storage_root,
        include_patterns,
        exclude_patterns,
    )


def _outcome_from_manifest(
    source: str,
    parser_name: str | None,
    entry: ManifestEntry | None,
    *,
    checksum: str | None,
    message: str,
) -> ParseOutcome:
    if entry is not None:
        note = f"{message} (status={entry.status})" if entry.status else message
        return ParseOutcome(
            source=source,
            parser=entry.parser or parser_name,
            status="skipped",
            artifact_path=entry.artifact_path,
            warnings=[],
            checksum=checksum,
            message=note,
        )
    return ParseOutcome(
        source=source,
        parser=parser_name,
        status="skipped",
        checksum=checksum,
        message=message,
    )


def _build_target(source: str | Path, *, is_remote: bool | None, media_type: str | None) -> ParseTarget:
    if isinstance(source, Path):
        source_str = str(source)
    else:
        source_str = str(source)

    is_remote_resolved = is_remote if is_remote is not None else utils.is_http_url(source_str)

    if is_remote_resolved:
        return ParseTarget(source=source_str, is_remote=True, media_type=media_type)

    path = Path(source_str).expanduser().resolve(strict=False)
    return ParseTarget(source=str(path), is_remote=False, media_type=media_type)


def _collect_candidates(
    root: Path,
    suffixes: Sequence[str],
    recursive: bool,
    storage_root: Path | None,
    include_patterns: Sequence[str] | None,
    exclude_patterns: Sequence[str] | None,
) -> list[Path]:
    if recursive:
        iterator: Iterable[Path] = root.rglob("*")
    else:
        iterator = root.iterdir()

    include = tuple(include_patterns or ())
    exclude = tuple(exclude_patterns or ())

    candidates: list[Path] = []
    for path in iterator:
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        resolved = path.resolve()
        if storage_root is not None and _is_within(resolved, storage_root):
            continue
        relative = resolved.relative_to(root)
        rel_posix = relative.as_posix()
        if include and not any(fnmatch(rel_posix, pattern) for pattern in include):
            continue
        if exclude and any(fnmatch(rel_posix, pattern) for pattern in exclude):
            continue
        candidates.append(resolved)

    candidates.sort()
    return candidates


def _is_within(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
    except ValueError:
        return False
    return True


__all__ = [
    "ParseOutcome",
    "parse_single_target",
    "scan_and_parse",
    "collect_parse_candidates",
]
