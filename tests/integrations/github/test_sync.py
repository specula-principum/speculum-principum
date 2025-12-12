"""Unit tests for GitHub sync utilities."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.github.sync import (
    CODE_DIRECTORIES,
    CODE_FILES,
    PROTECTED_DIRECTORIES,
    FileInfo,
    SyncChange,
    SyncResult,
    SyncStatus,
    SyncError,
    ValidationResult,
    compare_files,
    configure_upstream_variable,
    filter_syncable_files,
    get_default_branch,
    get_repository_tree,
    get_repository_variable,
    get_sync_status,
    get_template_repository,
    get_tree_sha,
    set_repository_variable,
    update_sync_status,
    validate_pre_sync,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_token() -> str:
    return "test-token-12345"


@pytest.fixture
def mock_repository() -> str:
    return "test-owner/test-repo"


@pytest.fixture
def sample_tree_response() -> dict[str, Any]:
    """Sample response from Git Trees API."""
    return {
        "sha": "abc123tree",
        "tree": [
            {"path": "main.py", "type": "blob", "sha": "sha1", "size": 100},
            {"path": "requirements.txt", "type": "blob", "sha": "sha2", "size": 50},
            {"path": "pytest.ini", "type": "blob", "sha": "sha3", "size": 30},
            {"path": "src", "type": "tree", "sha": "sha_dir"},
            {"path": "src/__init__.py", "type": "blob", "sha": "sha4", "size": 10},
            {"path": "src/config.py", "type": "blob", "sha": "sha5", "size": 200},
            {"path": "tests/test_main.py", "type": "blob", "sha": "sha6", "size": 500},
            {"path": ".github/workflows/ci.yml", "type": "blob", "sha": "sha7", "size": 150},
            {"path": "evidence/doc1.pdf", "type": "blob", "sha": "sha8", "size": 1000},
            {"path": "knowledge-graph/entity.yaml", "type": "blob", "sha": "sha9", "size": 100},
            {"path": "reports/analysis.md", "type": "blob", "sha": "sha10", "size": 500},
            {"path": "README.md", "type": "blob", "sha": "sha11", "size": 300},
        ],
    }


@pytest.fixture
def sample_ref_response() -> dict[str, Any]:
    """Sample response from Git Refs API."""
    return {
        "ref": "refs/heads/main",
        "object": {
            "sha": "commit123",
            "type": "commit",
        },
    }


@pytest.fixture
def sample_commit_response() -> dict[str, Any]:
    """Sample response from Git Commits API."""
    return {
        "sha": "commit123",
        "tree": {
            "sha": "tree123",
        },
    }


@pytest.fixture
def sample_repo_response() -> dict[str, Any]:
    """Sample response from Repos API."""
    return {
        "id": 12345,
        "name": "test-repo",
        "full_name": "test-owner/test-repo",
        "default_branch": "main",
    }


# =============================================================================
# FileInfo Tests
# =============================================================================


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_creation(self):
        """Test basic FileInfo creation."""
        info = FileInfo(path="src/main.py", sha="abc123", size=100)
        assert info.path == "src/main.py"
        assert info.sha == "abc123"
        assert info.size == 100
        assert info.content is None

    def test_content_hash(self):
        """Test content_hash returns SHA."""
        info = FileInfo(path="test.py", sha="deadbeef", size=50)
        assert info.content_hash() == "deadbeef"


# =============================================================================
# SyncChange Tests
# =============================================================================


class TestSyncChange:
    """Tests for SyncChange dataclass."""

    def test_add_change(self):
        """Test add change creation."""
        change = SyncChange(
            path="src/new_file.py",
            action="add",
            upstream_sha="new123",
        )
        assert change.path == "src/new_file.py"
        assert change.action == "add"
        assert change.upstream_sha == "new123"
        assert change.downstream_sha is None

    def test_update_change(self):
        """Test update change creation."""
        change = SyncChange(
            path="src/existing.py",
            action="update",
            upstream_sha="new456",
            downstream_sha="old456",
        )
        assert change.action == "update"
        assert change.upstream_sha == "new456"
        assert change.downstream_sha == "old456"

    def test_delete_change(self):
        """Test delete change creation."""
        change = SyncChange(
            path="src/removed.py",
            action="delete",
            downstream_sha="old789",
        )
        assert change.action == "delete"
        assert change.upstream_sha is None
        assert change.downstream_sha == "old789"


# =============================================================================
# SyncResult Tests
# =============================================================================


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_empty_result(self):
        """Test empty result properties."""
        result = SyncResult()
        assert not result.has_changes
        assert result.changes == []
        assert result.branch_name is None
        assert result.pr_number is None
        assert result.pr_url is None
        assert not result.dry_run
        assert result.error is None

    def test_has_changes(self):
        """Test has_changes with changes."""
        result = SyncResult(
            changes=[SyncChange(path="test.py", action="add", upstream_sha="abc")]
        )
        assert result.has_changes

    def test_summary_no_changes(self):
        """Test summary with no changes."""
        result = SyncResult()
        summary = result.summary()
        assert "up to date" in summary.lower()

    def test_summary_with_changes(self):
        """Test summary with various changes."""
        result = SyncResult(
            changes=[
                SyncChange(path="src/new.py", action="add", upstream_sha="a"),
                SyncChange(path="src/mod.py", action="update", upstream_sha="b"),
                SyncChange(path="src/old.py", action="delete", downstream_sha="c"),
            ]
        )
        summary = result.summary()
        assert "3 file(s)" in summary
        assert "Added" in summary
        assert "Updated" in summary
        assert "Removed" in summary
        assert "src/new.py" in summary
        assert "src/mod.py" in summary
        assert "src/old.py" in summary


# =============================================================================
# filter_syncable_files Tests
# =============================================================================


class TestFilterSyncableFiles:
    """Tests for filter_syncable_files function."""

    def test_includes_root_code_files(self):
        """Test that root code files are included."""
        files = [
            FileInfo(path="main.py", sha="a", size=100),
            FileInfo(path="requirements.txt", sha="b", size=50),
            FileInfo(path="pytest.ini", sha="c", size=30),
        ]
        result = filter_syncable_files(files)
        assert len(result) == 3
        paths = {f.path for f in result}
        assert "main.py" in paths
        assert "requirements.txt" in paths
        assert "pytest.ini" in paths

    def test_includes_code_directories(self):
        """Test that code directory files are included."""
        files = [
            FileInfo(path="src/__init__.py", sha="a", size=10),
            FileInfo(path="src/config.py", sha="b", size=100),
            FileInfo(path="tests/test_main.py", sha="c", size=200),
            FileInfo(path=".github/workflows/ci.yml", sha="d", size=50),
        ]
        result = filter_syncable_files(files)
        assert len(result) == 4

    def test_excludes_protected_directories(self):
        """Test that protected directories are excluded."""
        files = [
            FileInfo(path="evidence/doc.pdf", sha="a", size=1000),
            FileInfo(path="knowledge-graph/entity.yaml", sha="b", size=100),
            FileInfo(path="reports/report.md", sha="c", size=500),
            FileInfo(path="dev_data/test.json", sha="d", size=200),
        ]
        result = filter_syncable_files(files)
        assert len(result) == 0

    def test_excludes_non_code_root_files(self):
        """Test that non-code root files are excluded."""
        files = [
            FileInfo(path="README.md", sha="a", size=100),
            FileInfo(path="LICENSE", sha="b", size=50),
            FileInfo(path=".gitignore", sha="c", size=30),
        ]
        result = filter_syncable_files(files)
        assert len(result) == 0

    def test_mixed_files(self):
        """Test filtering with mixed file types."""
        files = [
            FileInfo(path="main.py", sha="a", size=100),  # include
            FileInfo(path="src/app.py", sha="b", size=200),  # include
            FileInfo(path="evidence/doc.pdf", sha="c", size=500),  # exclude
            FileInfo(path="README.md", sha="d", size=50),  # exclude
            FileInfo(path="tests/test_app.py", sha="e", size=150),  # include
        ]
        result = filter_syncable_files(files)
        assert len(result) == 3
        paths = {f.path for f in result}
        assert "main.py" in paths
        assert "src/app.py" in paths
        assert "tests/test_app.py" in paths


# =============================================================================
# compare_files Tests
# =============================================================================


class TestCompareFiles:
    """Tests for compare_files function."""

    def test_no_changes(self):
        """Test when files are identical."""
        upstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
            FileInfo(path="tests/test.py", sha="def", size=50),
        ]
        downstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
            FileInfo(path="tests/test.py", sha="def", size=50),
        ]
        changes = compare_files(upstream, downstream)
        assert len(changes) == 0

    def test_file_added(self):
        """Test when upstream has new file."""
        upstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
            FileInfo(path="src/new.py", sha="new", size=50),
        ]
        downstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
        ]
        changes = compare_files(upstream, downstream)
        assert len(changes) == 1
        assert changes[0].path == "src/new.py"
        assert changes[0].action == "add"
        assert changes[0].upstream_sha == "new"

    def test_file_updated(self):
        """Test when file content differs."""
        upstream = [
            FileInfo(path="src/main.py", sha="new_sha", size=150),
        ]
        downstream = [
            FileInfo(path="src/main.py", sha="old_sha", size=100),
        ]
        changes = compare_files(upstream, downstream)
        assert len(changes) == 1
        assert changes[0].path == "src/main.py"
        assert changes[0].action == "update"
        assert changes[0].upstream_sha == "new_sha"
        assert changes[0].downstream_sha == "old_sha"

    def test_file_deleted(self):
        """Test when upstream removed a file."""
        upstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
        ]
        downstream = [
            FileInfo(path="src/main.py", sha="abc", size=100),
            FileInfo(path="src/removed.py", sha="old", size=50),
        ]
        changes = compare_files(upstream, downstream)
        assert len(changes) == 1
        assert changes[0].path == "src/removed.py"
        assert changes[0].action == "delete"
        assert changes[0].downstream_sha == "old"

    def test_mixed_changes(self):
        """Test combination of add, update, delete."""
        upstream = [
            FileInfo(path="src/unchanged.py", sha="same", size=100),
            FileInfo(path="src/updated.py", sha="new", size=200),
            FileInfo(path="src/added.py", sha="add", size=50),
        ]
        downstream = [
            FileInfo(path="src/unchanged.py", sha="same", size=100),
            FileInfo(path="src/updated.py", sha="old", size=150),
            FileInfo(path="src/removed.py", sha="del", size=75),
        ]
        changes = compare_files(upstream, downstream)
        assert len(changes) == 3

        by_action = {c.action: c for c in changes}
        assert "add" in by_action
        assert "update" in by_action
        assert "delete" in by_action

        assert by_action["add"].path == "src/added.py"
        assert by_action["update"].path == "src/updated.py"
        assert by_action["delete"].path == "src/removed.py"


# =============================================================================
# API Function Tests (with mocking)
# =============================================================================


class TestGetDefaultBranch:
    """Tests for get_default_branch function."""

    def test_returns_default_branch(self, mock_token, mock_repository, sample_repo_response):
        """Test getting default branch from API."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.return_value = sample_repo_response
            
            result = get_default_branch(mock_repository, mock_token)
            
            assert result == "main"
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "test-owner/test-repo" in call_args[0][0]

    def test_defaults_to_main_if_missing(self, mock_token, mock_repository):
        """Test default fallback when field is missing."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.return_value = {"name": "test-repo"}
            
            result = get_default_branch(mock_repository, mock_token)
            
            assert result == "main"


class TestGetTreeSha:
    """Tests for get_tree_sha function."""

    def test_returns_tree_sha(
        self, mock_token, mock_repository, sample_ref_response, sample_commit_response
    ):
        """Test getting tree SHA from refs and commits API."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.side_effect = [sample_ref_response, sample_commit_response]
            
            result = get_tree_sha(mock_repository, "main", mock_token)
            
            assert result == "tree123"
            assert mock_request.call_count == 2


class TestGetRepositoryTree:
    """Tests for get_repository_tree function."""

    def test_returns_file_infos(
        self,
        mock_token,
        mock_repository,
        sample_repo_response,
        sample_ref_response,
        sample_commit_response,
        sample_tree_response,
    ):
        """Test getting repository tree returns FileInfo objects."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.side_effect = [
                sample_repo_response,  # get_default_branch
                sample_ref_response,   # get_tree_sha (refs)
                sample_commit_response,  # get_tree_sha (commits)
                sample_tree_response,  # actual tree
            ]
            
            result = get_repository_tree(mock_repository, token=mock_token)
            
            assert len(result) == 11  # Only blobs, not trees
            assert all(isinstance(f, FileInfo) for f in result)
            paths = {f.path for f in result}
            assert "main.py" in paths
            assert "src/__init__.py" in paths
            # Directory entries should not be in result
            assert "src" not in paths

    def test_uses_provided_branch(
        self,
        mock_token,
        mock_repository,
        sample_ref_response,
        sample_commit_response,
        sample_tree_response,
    ):
        """Test that provided branch is used."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.side_effect = [
                sample_ref_response,
                sample_commit_response,
                sample_tree_response,
            ]
            
            result = get_repository_tree(
                mock_repository, branch="develop", token=mock_token
            )
            
            # Should not call get_default_branch when branch is provided
            assert mock_request.call_count == 3


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_code_directories_not_empty(self):
        """Ensure code directories list is populated."""
        assert len(CODE_DIRECTORIES) > 0
        assert "src/" in CODE_DIRECTORIES
        assert "tests/" in CODE_DIRECTORIES

    def test_code_files_not_empty(self):
        """Ensure code files list is populated."""
        assert len(CODE_FILES) > 0
        assert "main.py" in CODE_FILES

    def test_protected_directories_not_empty(self):
        """Ensure protected directories list is populated."""
        assert len(PROTECTED_DIRECTORIES) > 0
        assert "evidence/" in PROTECTED_DIRECTORIES
        assert "knowledge-graph/" in PROTECTED_DIRECTORIES

    def test_no_overlap_code_and_protected(self):
        """Ensure code and protected directories don't overlap."""
        code_set = set(CODE_DIRECTORIES)
        protected_set = set(PROTECTED_DIRECTORIES)
        assert code_set.isdisjoint(protected_set)


# =============================================================================
# Repository Variable Tests
# =============================================================================


class TestGetTemplateRepository:
    """Tests for get_template_repository function."""

    def test_returns_template_name(self, mock_token, mock_repository):
        """Test getting template repository name."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.return_value = {
                "name": "test-repo",
                "template_repository": {
                    "full_name": "template-owner/template-repo",
                },
            }
            
            result = get_template_repository(mock_repository, mock_token)
            
            assert result == "template-owner/template-repo"

    def test_returns_none_if_not_from_template(self, mock_token, mock_repository):
        """Test returns None when repo is not from template."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.return_value = {"name": "test-repo"}
            
            result = get_template_repository(mock_repository, mock_token)
            
            assert result is None


class TestGetRepositoryVariable:
    """Tests for get_repository_variable function."""

    def test_returns_variable_value(self, mock_token, mock_repository):
        """Test getting a variable value."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.return_value = {
                "name": "UPSTREAM_REPO",
                "value": "owner/upstream",
            }
            
            result = get_repository_variable(mock_repository, "UPSTREAM_REPO", mock_token)
            
            assert result == "owner/upstream"

    def test_returns_none_if_not_found(self, mock_token, mock_repository):
        """Test returns None when variable doesn't exist."""
        with patch("src.integrations.github.sync._make_request") as mock_request:
            mock_request.side_effect = SyncError("GitHub API error (404): Not Found")
            
            result = get_repository_variable(mock_repository, "MISSING_VAR", mock_token)
            
            assert result is None


class TestSetRepositoryVariable:
    """Tests for set_repository_variable function."""

    def test_creates_new_variable(self, mock_token, mock_repository):
        """Test creating a new variable."""
        with patch("src.integrations.github.sync.get_repository_variable") as mock_get:
            mock_get.return_value = None
            
            with patch("src.integrations.github.sync._make_request") as mock_request:
                mock_request.return_value = {}
                
                result = set_repository_variable(
                    mock_repository, "NEW_VAR", "new_value", mock_token
                )
            
            assert result is True
            # Verify POST was used for create
            call_args = mock_request.call_args
            assert call_args[1]["method"] == "POST"

    def test_updates_existing_variable(self, mock_token, mock_repository):
        """Test updating an existing variable."""
        with patch("src.integrations.github.sync.get_repository_variable") as mock_get:
            mock_get.return_value = "old_value"
            
            with patch("src.integrations.github.sync._make_request") as mock_request:
                mock_request.return_value = {}
                
                result = set_repository_variable(
                    mock_repository, "EXISTING_VAR", "new_value", mock_token
                )
            
            assert result is True
            # Verify PATCH was used for update
            call_args = mock_request.call_args
            assert call_args[1]["method"] == "PATCH"


class TestConfigureUpstreamVariable:
    """Tests for configure_upstream_variable function."""

    def test_uses_explicit_upstream(self, mock_token, mock_repository):
        """Test using explicitly provided upstream repo."""
        with patch("src.integrations.github.sync.set_repository_variable") as mock_set:
            mock_set.return_value = True
            
            result = configure_upstream_variable(
                mock_repository, mock_token, upstream_repo="explicit/upstream"
            )
            
            assert result["success"] is True
            assert result["upstream_repo"] == "explicit/upstream"
            mock_set.assert_called_once_with(
                mock_repository, "UPSTREAM_REPO", "explicit/upstream", mock_token, "https://api.github.com"
            )

    def test_auto_detects_from_template(self, mock_token, mock_repository):
        """Test auto-detecting upstream from template."""
        with patch("src.integrations.github.sync.get_template_repository") as mock_template:
            mock_template.return_value = "template/repo"
            
            with patch("src.integrations.github.sync.set_repository_variable") as mock_set:
                mock_set.return_value = True
                
                result = configure_upstream_variable(mock_repository, mock_token)
                
                assert result["success"] is True
                assert result["upstream_repo"] == "template/repo"

    def test_fails_if_no_template_and_no_explicit(self, mock_token, mock_repository):
        """Test failure when no template and no explicit upstream."""
        with patch("src.integrations.github.sync.get_template_repository") as mock_template:
            mock_template.return_value = None
            
            result = configure_upstream_variable(mock_repository, mock_token)
            
            assert result["success"] is False
            assert "not created from a template" in result["error"]


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_default_valid(self):
        """Test default state is valid."""
        result = ValidationResult()
        assert result.valid is True
        assert result.local_modifications == []
        assert result.warnings == []

    def test_summary_when_valid(self):
        """Test summary for valid result."""
        result = ValidationResult()
        assert "passed" in result.summary().lower()

    def test_summary_with_modifications(self):
        """Test summary includes modification details."""
        result = ValidationResult(
            valid=False,
            local_modifications=["src/config.py", "tests/test_main.py"],
        )
        summary = result.summary()
        assert "2 locally modified" in summary
        assert "src/config.py" in summary


class TestValidatePreSync:
    """Tests for validate_pre_sync function."""

    def test_valid_when_no_local_changes(self, mock_token, mock_repository):
        """Test validation passes when files match upstream."""
        upstream_files = [
            FileInfo(path="src/main.py", sha="abc", size=100),
        ]
        downstream_files = [
            FileInfo(path="src/main.py", sha="abc", size=100),
        ]
        
        with patch("src.integrations.github.sync.get_default_branch") as mock_branch:
            mock_branch.return_value = "main"
            with patch("src.integrations.github.sync.get_repository_tree") as mock_tree:
                mock_tree.side_effect = [upstream_files, downstream_files]
                
                result = validate_pre_sync(
                    mock_repository, "upstream/repo", mock_token
                )
                
                assert result.valid is True
                assert result.local_modifications == []

    def test_invalid_when_local_modifications(self, mock_token, mock_repository):
        """Test validation fails when downstream has local changes."""
        upstream_files = [
            FileInfo(path="src/main.py", sha="upstream_sha", size=100),
        ]
        downstream_files = [
            FileInfo(path="src/main.py", sha="local_sha", size=150),
        ]
        
        with patch("src.integrations.github.sync.get_default_branch") as mock_branch:
            mock_branch.return_value = "main"
            with patch("src.integrations.github.sync.get_repository_tree") as mock_tree:
                mock_tree.side_effect = [upstream_files, downstream_files]
                
                result = validate_pre_sync(
                    mock_repository, "upstream/repo", mock_token
                )
                
                assert result.valid is False
                assert "src/main.py" in result.local_modifications


# =============================================================================
# Sync Status Tests
# =============================================================================


class TestSyncStatus:
    """Tests for SyncStatus dataclass."""

    def test_default_values(self):
        """Test default status values."""
        status = SyncStatus()
        assert status.last_sync_sha is None
        assert status.sync_count == 0
        assert status.upstream_repo is None


class TestGetSyncStatus:
    """Tests for get_sync_status function."""

    def test_returns_status_from_variables(self, mock_token, mock_repository):
        """Test reading sync status from repo variables."""
        with patch("src.integrations.github.sync.get_repository_variable") as mock_get:
            mock_get.side_effect = [
                "abc123",  # SYNC_LAST_SHA
                "2025-12-12T10:00:00Z",  # SYNC_LAST_TIME
                "upstream/repo",  # UPSTREAM_REPO
                "5",  # SYNC_COUNT
                "42",  # SYNC_LAST_PR
            ]
            
            status = get_sync_status(mock_repository, mock_token)
            
            assert status.last_sync_sha == "abc123"
            assert status.sync_count == 5
            assert status.last_pr_number == 42

    def test_handles_missing_variables(self, mock_token, mock_repository):
        """Test handling when variables don't exist."""
        with patch("src.integrations.github.sync.get_repository_variable") as mock_get:
            mock_get.return_value = None
            
            status = get_sync_status(mock_repository, mock_token)
            
            assert status.last_sync_sha is None
            assert status.sync_count == 0


class TestUpdateSyncStatus:
    """Tests for update_sync_status function."""

    def test_updates_all_variables(self, mock_token, mock_repository):
        """Test updating sync status variables."""
        with patch("src.integrations.github.sync.get_sync_status") as mock_status:
            mock_status.return_value = SyncStatus(sync_count=5)
            
            with patch("src.integrations.github.sync.set_repository_variable") as mock_set:
                mock_set.return_value = True
                
                update_sync_status(
                    mock_repository, mock_token, "commit123", pr_number=10
                )
                
                # Should have set SYNC_LAST_SHA, SYNC_LAST_TIME, SYNC_COUNT, SYNC_LAST_PR
                assert mock_set.call_count == 4
                
                # Check count was incremented
                calls = [call[0] for call in mock_set.call_args_list]
                count_call = [c for c in calls if c[1] == "SYNC_COUNT"][0]
                assert count_call[2] == "6"  # 5 + 1
