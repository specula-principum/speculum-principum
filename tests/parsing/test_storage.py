from __future__ import annotations

from datetime import datetime, timezone

from src.parsing.base import ParseTarget, ParsedDocument
from src.parsing.storage import ManifestEntry, ParseStorage


def test_manifest_roundtrip(tmp_path) -> None:
    storage = ParseStorage(tmp_path / "artifacts")
    processed_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    checksum = "a" * 64

    artifact_path = storage.make_artifact_path(
        "evidence/example.pdf",
        checksum,
        processed_at=processed_at,
    )

    entry = ManifestEntry(
        source="evidence/example.pdf",
        checksum=checksum,
        parser="pdf",
        artifact_path=storage.relative_artifact_path(artifact_path),
        processed_at=processed_at,
    )

    storage.record_entry(entry)

    reloaded = ParseStorage(tmp_path / "artifacts")
    restored = reloaded.manifest().get(checksum)

    assert restored == entry
    assert not reloaded.should_process(checksum)


def test_make_artifact_path_is_deterministic(tmp_path) -> None:
    storage = ParseStorage(tmp_path / "artifacts")
    checksum = "b" * 64
    processed_at = datetime(2025, 5, 6, tzinfo=timezone.utc)

    first = storage.make_artifact_path(
        "folder/my contract.docx",
        checksum,
        processed_at=processed_at,
    )
    second = storage.make_artifact_path(
        "folder/my contract.docx",
        checksum,
        processed_at=processed_at,
    )

    assert first == second
    assert first.parent.parent.name == "2025"
    assert first.parent.name.startswith("my-contract-docx-")
    assert first.stem.startswith("my-contract-docx-")
    assert first.name.endswith(".md")


def test_should_process_returns_true_for_unknown_checksum(tmp_path) -> None:
    storage = ParseStorage(tmp_path / "artifacts")
    assert storage.should_process("c" * 64)


def test_persist_document_writes_markdown_and_updates_manifest(tmp_path) -> None:
    storage = ParseStorage(tmp_path / "artifacts")
    target = ParseTarget(source="evidence/contract.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    document = ParsedDocument(
        target=target,
        checksum="d" * 64,
        parser_name="docx",
    )
    document.created_at = datetime(2025, 10, 22, 12, 0, tzinfo=timezone.utc)
    document.metadata = {"title": "Contract"}
    document.warnings.append("No tables detected")
    document.add_segment("First paragraph of the contract.")

    entry = storage.persist_document(document)

    index_path = storage.root / entry.artifact_path
    assert index_path.exists()
    assert index_path.name == "index.md"

    assert "page_files" not in entry.metadata

    segment_files = sorted(
        path for path in index_path.parent.glob("*.md") if path.name != "index.md"
    )
    assert segment_files, "expected at least one segment artifact"

    first_page_path = segment_files[0]
    page_content = first_page_path.read_text(encoding="utf-8")

    assert "source: evidence/contract.docx" in page_content
    assert "First paragraph of the contract." in page_content
    assert "warnings:" not in page_content
    assert "page_unit: segment" in page_content
    assert entry.metadata["artifact_type"] == "page-directory"
    assert entry.metadata["segments_total"] == 1
    assert entry.status == "completed"
    assert storage.manifest().get(document.checksum) == entry
