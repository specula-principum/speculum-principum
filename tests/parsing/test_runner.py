from __future__ import annotations

import hashlib
from pathlib import Path

from src.parsing.base import ParseTarget, ParsedDocument
from src.parsing.registry import ParserRegistry
from src.parsing.runner import parse_single_target, scan_and_parse
from src.parsing.storage import ParseStorage


class TextParser:
    name = "text"

    def detect(self, target: ParseTarget) -> bool:
        try:
            return target.to_path().suffix.lower() == ".txt"
        except ValueError:
            return False

    def extract(self, target: ParseTarget) -> ParsedDocument:
        path = target.to_path()
        checksum = _sha256_path(path)
        document = ParsedDocument(target=target, checksum=checksum, parser_name=self.name)
        document.add_segment(path.read_text(encoding="utf-8"))
        return document

    def to_markdown(self, document: ParsedDocument) -> str:  # pragma: no cover - unused
        from src.parsing.markdown import document_to_markdown

        return document_to_markdown(document)


def make_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register_parser(TextParser(), suffixes=(".txt",), priority=5, replace=True)
    return registry


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_parse_single_target_persists_document(tmp_path) -> None:
    source = tmp_path / "example.txt"
    source.write_text("hello world", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = make_registry()

    outcome = parse_single_target(
        source,
        storage=storage,
        registry_override=registry,
        expected_parser="text",
    )

    assert outcome.status == "completed"
    assert outcome.artifact_path is not None
    artifact = storage.root / outcome.artifact_path
    assert artifact.exists()
    segment_files = sorted(artifact.parent.glob("segment-*.md"))
    assert segment_files, "expected at least one segment artifact"
    content = segment_files[0].read_text(encoding="utf-8")
    assert "hello world" in content


def test_parse_single_target_skips_known_checksum(tmp_path) -> None:
    source = tmp_path / "skipped.txt"
    source.write_text("cached", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = make_registry()

    first = parse_single_target(source, storage=storage, registry_override=registry)
    second = parse_single_target(source, storage=storage, registry_override=registry)

    assert first.status == "completed"
    assert second.status == "skipped"
    assert second.artifact_path == first.artifact_path


def test_parse_single_target_force_reprocesses(tmp_path) -> None:
    source = tmp_path / "forced.txt"
    source.write_text("force", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = make_registry()

    initial = parse_single_target(source, storage=storage, registry_override=registry)
    forced = parse_single_target(source, storage=storage, registry_override=registry, force=True)

    assert initial.status == "completed"
    assert forced.status == "completed"
    assert forced.artifact_path == initial.artifact_path


def test_parse_single_target_handles_missing_parser(tmp_path) -> None:
    source = tmp_path / "unknown.bin"
    source.write_text("data", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = ParserRegistry()

    outcome = parse_single_target(source, storage=storage, registry_override=registry)

    assert outcome.status == "error"
    assert outcome.error is not None


def test_scan_and_parse_discovers_matching_files(tmp_path) -> None:
    root = tmp_path / "docs"
    nested = root / "nested"
    nested.mkdir(parents=True)

    file_one = root / "one.txt"
    file_two = nested / "two.txt"
    ignored = root / "ignored.pdf"

    file_one.write_text("first", encoding="utf-8")
    file_two.write_text("second", encoding="utf-8")
    ignored.write_text("skip", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = make_registry()

    outcomes = scan_and_parse(
        root,
        storage=storage,
        registry_override=registry,
        suffixes=(".txt",),
    )

    assert len(outcomes) == 2
    assert all(outcome.status == "completed" for outcome in outcomes)

    top_level_only = scan_and_parse(
        root,
        storage=ParseStorage(tmp_path / "artifacts2"),
        registry_override=registry,
        suffixes=(".txt",),
        recursive=False,
    )

    assert len(top_level_only) == 1
    assert Path(top_level_only[0].source).name == "one.txt"


def test_scan_and_parse_respects_include_exclude(tmp_path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "skip.txt").write_text("skip", encoding="utf-8")

    storage = ParseStorage(tmp_path / "artifacts")
    registry = make_registry()

    outcomes = scan_and_parse(
        root,
        storage=storage,
        registry_override=registry,
        suffixes=(".txt",),
        include_patterns=("keep.txt",),
        exclude_patterns=("skip.txt",),
    )

    assert len(outcomes) == 1
    assert Path(outcomes[0].source).name == "keep.txt"
