"""Tests for extraction queue CLI commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.commands.extraction_queue import (
    _parse_checksum_from_issue_body,
    get_documents_needing_issues,
    queue_documents_for_extraction,
)
from src.integrations.github.issues import IssueOutcome
from src.integrations.github.search_issues import IssueSearchResult
from src.parsing.storage import Manifest, ManifestEntry


class TestParseChecksumFromIssueBody:
    """Test checksum parsing from Issue body."""

    def test_parse_checksum_from_marker(self):
        """Should extract checksum from HTML comment marker."""
        body = "Some text\n<!-- checksum:abc123def456 -->\nMore text"
        assert _parse_checksum_from_issue_body(body) == "abc123def456"

    def test_parse_checksum_no_marker(self):
        """Should return None when no marker present."""
        body = "Some text without marker"
        assert _parse_checksum_from_issue_body(body) is None

    def test_parse_checksum_none_body(self):
        """Should return None when body is None."""
        assert _parse_checksum_from_issue_body(None) is None


class TestGetDocumentsNeedingIssues:
    """Test logic for finding documents that need Issues."""

    def test_no_existing_issues(self):
        """Should return all completed documents when no issues exist."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        result = get_documents_needing_issues(manifest, [])
        assert len(result) == 2
        assert result[0].checksum == "checksum1"
        assert result[1].checksum == "checksum2"

    def test_skip_non_completed(self):
        """Should skip documents that aren't completed."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="failed",
                ),
            }
        )
        
        result = get_documents_needing_issues(manifest, [])
        assert len(result) == 1
        assert result[0].checksum == "checksum1"

    def test_skip_with_existing_issue(self):
        """Should skip documents that already have Issues."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        existing_issues = [
            IssueSearchResult(
                number=1,
                title="Extract: <!-- checksum:checksum1 -->",
                state="open",
                url="https://github.com/owner/repo/issues/1",
                assignee=None,
            )
        ]
        
        result = get_documents_needing_issues(manifest, existing_issues)
        assert len(result) == 1
        assert result[0].checksum == "checksum2"

    def test_force_mode_returns_all(self):
        """Should return all documents when force=True."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        existing_issues = [
            IssueSearchResult(
                number=1,
                title="Extract: checksum1",
                state="open",
                url="https://github.com/owner/repo/issues/1",
                assignee=None,
            )
        ]
        
        result = get_documents_needing_issues(manifest, existing_issues, force=True)
        assert len(result) == 1
        assert result[0].checksum == "checksum1"

    def test_specific_checksum_filter(self):
        """Should only return specified checksum."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        result = get_documents_needing_issues(
            manifest, [], specific_checksum="checksum1"
        )
        assert len(result) == 1
        assert result[0].checksum == "checksum1"

    def test_skip_extraction_skipped_documents(self):
        """Should skip documents marked as extraction_skipped in metadata."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                    metadata={"extraction_skipped": True, "skip_reason": "Navigation page"},
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        result = get_documents_needing_issues(manifest, [])
        assert len(result) == 1
        assert result[0].checksum == "checksum2"


    def test_skip_extraction_complete_documents(self):
        """Should skip documents marked as extraction_complete in metadata."""
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                    metadata={"extraction_complete": True},
                ),
                "checksum2": ManifestEntry(
                    source="doc2",
                    checksum="checksum2",
                    parser="web",
                    artifact_path="path/to/doc2",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        result = get_documents_needing_issues(manifest, [])
        assert len(result) == 1
        assert result[0].checksum == "checksum2"


class TestQueueDocumentsForExtraction:
    """Test queue_documents_for_extraction function."""

    @patch("src.cli.commands.extraction_queue.ParseStorage")
    @patch("src.cli.commands.extraction_queue.GitHubIssueSearcher")
    @patch("src.cli.commands.extraction_queue._create_extraction_issue")
    def test_queue_creates_issues(self, mock_create, mock_searcher_class, mock_storage_class):
        """Should create issues for pending documents."""
        # Setup manifest with one document
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1.pdf",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="evidence/parsed/2025/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                    metadata={"source_name": "Test Document"},
                ),
            }
        )
        
        # Mock storage
        mock_storage = MagicMock()
        mock_storage.manifest.return_value = manifest
        mock_storage_class.return_value = mock_storage
        
        # Mock searcher (no existing issues)
        mock_searcher = MagicMock()
        mock_searcher.search_by_label.return_value = []
        mock_searcher_class.return_value = mock_searcher
        
        # Mock issue creation
        mock_create.return_value = IssueOutcome(
            number=42,
            url="https://api.github.com/repos/owner/repo/issues/42",
            html_url="https://github.com/owner/repo/issues/42",
        )
        
        # Execute
        result = queue_documents_for_extraction(
            repository="owner/repo",
            token="fake-token",
            evidence_root=Path("/fake/evidence"),
            force=False,
        )
        
        # Verify
        assert len(result) == 1
        assert result[0].number == 42
        mock_create.assert_called_once()

    @patch("src.cli.commands.extraction_queue.ParseStorage")
    @patch("src.cli.commands.extraction_queue.GitHubIssueSearcher")
    def test_queue_empty_manifest(self, mock_searcher_class, mock_storage_class):
        """Should handle empty manifest gracefully."""
        # Setup empty manifest
        manifest = Manifest(entries={})
        
        # Mock storage
        mock_storage = MagicMock()
        mock_storage.manifest.return_value = manifest
        mock_storage_class.return_value = mock_storage
        
        # Execute
        result = queue_documents_for_extraction(
            repository="owner/repo",
            token="fake-token",
            evidence_root=Path("/fake/evidence"),
            force=False,
        )
        
        # Verify
        assert len(result) == 0

    @patch("src.cli.commands.extraction_queue.ParseStorage")
    @patch("src.cli.commands.extraction_queue.GitHubIssueSearcher")
    @patch("src.cli.commands.extraction_queue._create_extraction_issue")
    def test_queue_skips_existing_issues(
        self, mock_create, mock_searcher_class, mock_storage_class
    ):
        """Should not create issues for documents that already have them."""
        # Setup manifest
        manifest = Manifest(
            entries={
                "checksum1": ManifestEntry(
                    source="doc1",
                    checksum="checksum1",
                    parser="pdf",
                    artifact_path="path/to/doc1",
                    processed_at=datetime.now(timezone.utc),
                    status="completed",
                ),
            }
        )
        
        # Mock storage
        mock_storage = MagicMock()
        mock_storage.manifest.return_value = manifest
        mock_storage_class.return_value = mock_storage
        
        # Mock searcher with existing issue
        mock_searcher = MagicMock()
        mock_searcher.search_by_label.return_value = [
            IssueSearchResult(
                number=1,
                title="Extract: <!-- checksum:checksum1 -->",
                state="open",
                url="https://github.com/owner/repo/issues/1",
                assignee=None,
            )
        ]
        mock_searcher_class.return_value = mock_searcher
        
        # Execute
        result = queue_documents_for_extraction(
            repository="owner/repo",
            token="fake-token",
            evidence_root=Path("/fake/evidence"),
            force=False,
        )
        
        # Verify - no issues created
        assert len(result) == 0
        mock_create.assert_not_called()


class TestSkipCommand:
    """Test the skip CLI command."""

    def test_skip_marks_document_as_skipped(self, tmp_path):
        """Should update manifest metadata when skipping a document."""
        from src.cli.commands.extraction_queue import skip_cli
        from src.parsing.storage import ParseStorage
        from datetime import datetime, timezone
        import argparse
        
        # Create a test manifest
        manifest_dir = tmp_path / "parsed"
        manifest_dir.mkdir(parents=True)
        
        storage = ParseStorage(manifest_dir)
        entry = ManifestEntry(
            source="https://example.com/page",
            checksum="abc123def456",
            parser="web",
            artifact_path="parsed/example/index.md",
            processed_at=datetime.now(timezone.utc),
            status="completed",
        )
        storage.record_entry(entry)
        
        # Create args for skip command
        args = argparse.Namespace(
            checksum="abc123def456",
            reason="Homepage with only navigation links",
            evidence_root=tmp_path,
        )
        
        # Execute skip command
        result = skip_cli(args)
        
        # Should succeed
        assert result == 0
        
        # Reload manifest and verify metadata was updated
        storage2 = ParseStorage(manifest_dir)
        updated_entry = storage2.manifest().get("abc123def456")
        assert updated_entry is not None
        assert updated_entry.metadata.get("extraction_skipped") is True
        assert updated_entry.metadata.get("skip_reason") == "Homepage with only navigation links"

    def test_skip_nonexistent_document(self, tmp_path):
        """Should return error for nonexistent checksum."""
        from src.cli.commands.extraction_queue import skip_cli
        from src.parsing.storage import ParseStorage
        import argparse
        
        # Create empty manifest
        manifest_dir = tmp_path / "parsed"
        manifest_dir.mkdir(parents=True)
        ParseStorage(manifest_dir)
        
        # Create args for skip command
        args = argparse.Namespace(
            checksum="nonexistent",
            reason="Test reason",
            evidence_root=tmp_path,
        )
        
        # Execute skip command
        result = skip_cli(args)
        
        # Should fail
        assert result == 1


class TestCompleteCommand:
    """Test the complete CLI command."""

    def test_complete_marks_document_as_complete(self, tmp_path):
        """Should update manifest metadata when marking document as complete."""
        from src.cli.commands.extraction_queue import complete_cli
        from src.parsing.storage import ParseStorage
        from datetime import datetime, timezone
        import argparse
        
        # Create a test manifest
        manifest_dir = tmp_path / "parsed"
        manifest_dir.mkdir(parents=True)
        
        storage = ParseStorage(manifest_dir)
        entry = ManifestEntry(
            source="https://example.com/page",
            checksum="abc123def456",
            parser="web",
            artifact_path="parsed/example/index.md",
            processed_at=datetime.now(timezone.utc),
            status="completed",
        )
        storage.record_entry(entry)
        
        # Create args for complete command
        args = argparse.Namespace(
            checksum="abc123def456",
            evidence_root=tmp_path,
        )
        
        # Execute complete command
        result = complete_cli(args)
        
        # Should succeed
        assert result == 0
        
        # Reload manifest and verify metadata was updated
        storage2 = ParseStorage(manifest_dir)
        updated_entry = storage2.manifest().get("abc123def456")
        assert updated_entry is not None
        assert updated_entry.metadata.get("extraction_complete") is True

    def test_complete_nonexistent_document(self, tmp_path):
        """Should return error for nonexistent checksum."""
        from src.cli.commands.extraction_queue import complete_cli
        from src.parsing.storage import ParseStorage
        import argparse
        
        # Create empty manifest
        manifest_dir = tmp_path / "parsed"
        manifest_dir.mkdir(parents=True)
        ParseStorage(manifest_dir)
        
        # Create args for complete command
        args = argparse.Namespace(
            checksum="nonexistent",
            evidence_root=tmp_path,
        )
        
        # Execute complete command
        result = complete_cli(args)
        
        # Should fail
        assert result == 1
