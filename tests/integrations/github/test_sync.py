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
    discover_downstream_repos,
    filter_syncable_files,
    get_default_branch,
    get_repository_tree,
    get_repository_variable,
    get_sync_status,
    get_template_repository,
    get_tree_sha,
    notify_downstream_repos,
    set_repository_variable,
    update_sync_status,
    validate_pre_sync,
    validate_pr_file_scope,
    verify_dispatch_signature,
    verify_satellite_trust,
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


# =============================================================================
# Auto-Approval Feature Tests
# =============================================================================


class TestNotifyDownstreamRepos:
    """Tests for notifying downstream repositories."""
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('src.integrations.github.sync.request.urlopen')
    @patch('builtins.print')
    def test_successful_notification(
        self, mock_print, mock_urlopen, mock_discover, mock_verify, mock_token
    ):
        """Should successfully notify trusted downstream repos."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock discovery
        mock_discover.return_value = ["org/satellite-1", "org/satellite-2"]
        
        # Mock trust verification
        mock_verify.return_value = (True, "All checks passed")
        
        # Mock dispatch API success
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        result = notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
        )
        
        assert result["success"] == 2
        assert result["failed"] == 0
        assert len(result["repos"]) == 2
        assert all(r["status"] == "notified" for r in result["repos"])
        
        # Verify dispatch was sent with signature
        assert mock_urlopen.call_count == 2
        call_args = mock_urlopen.call_args_list[0][0][0]
        assert "signature" in call_args.data.decode()
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('builtins.print')
    def test_no_downstream_repos(self, mock_print, mock_discover, mock_verify, mock_token):
        """Should handle case with no downstream repos."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock empty discovery
        mock_discover.return_value = []
        
        result = notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
        )
        
        assert result["success"] == 0
        assert result["failed"] == 0
        assert len(result["repos"]) == 0
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('builtins.print')
    def test_untrusted_repo_skipped(
        self, mock_print, mock_discover, mock_verify, mock_token
    ):
        """Should skip untrusted repositories."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock discovery
        mock_discover.return_value = ["org/untrusted-repo"]
        
        # Mock trust verification failure
        mock_verify.return_value = (False, "Repository is a fork")
        
        result = notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
        )
        
        assert result["success"] == 0
        assert result["failed"] == 1
        assert result["repos"][0]["status"] == "untrusted"
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('builtins.print')
    def test_dry_run_mode(self, mock_print, mock_discover, mock_verify, mock_token):
        """Should not send notifications in dry run mode."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock discovery
        mock_discover.return_value = ["org/satellite-1"]
        
        # Mock trust verification
        mock_verify.return_value = (True, "All checks passed")
        
        result = notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
            dry_run=True,
        )
        
        assert result["success"] == 1
        assert result["repos"][0]["status"] == "would_notify"
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('src.integrations.github.sync.request.urlopen')
    @patch('builtins.print')
    def test_dispatch_api_error(
        self, mock_print, mock_urlopen, mock_discover, mock_verify, mock_token
    ):
        """Should handle API errors gracefully."""
        from src.integrations.github.sync import notify_downstream_repos
        from urllib import error as urllib_error
        
        # Mock discovery
        mock_discover.return_value = ["org/satellite-1"]
        
        # Mock trust verification
        mock_verify.return_value = (True, "All checks passed")
        
        # Mock API error
        mock_error = urllib_error.HTTPError(
            url="https://api.github.com/repos/org/satellite-1/dispatches",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=MagicMock(read=lambda: b"Insufficient permissions")
        )
        mock_urlopen.side_effect = mock_error
        
        result = notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
        )
        
        assert result["success"] == 0
        assert result["failed"] == 1
        assert result["repos"][0]["status"] == "failed"
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('builtins.print')
    def test_custom_org(self, mock_print, mock_discover, mock_verify, mock_token):
        """Should search custom org when specified."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock discovery
        mock_discover.return_value = []
        
        notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
            org="custom-org",
        )
        
        # Verify discovery was called with custom org
        mock_discover.assert_called_once()
        assert mock_discover.call_args[0][0] == "custom-org"
    
    @patch('src.integrations.github.sync.verify_satellite_trust')
    @patch('src.integrations.github.sync.discover_downstream_repos')
    @patch('src.integrations.github.sync.request.urlopen')
    @patch('builtins.print')
    def test_includes_release_tag(
        self, mock_print, mock_urlopen, mock_discover, mock_verify, mock_token
    ):
        """Should include release tag in dispatch payload."""
        from src.integrations.github.sync import notify_downstream_repos
        
        # Mock discovery
        mock_discover.return_value = ["org/satellite-1"]
        
        # Mock trust verification
        mock_verify.return_value = (True, "All checks passed")
        
        # Mock dispatch API success
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        notify_downstream_repos(
            upstream_repo="org/upstream",
            upstream_branch="main",
            secret="test-secret",
            token=mock_token,
            release_tag="v1.2.3",
        )
        
        # Verify release tag was included
        call_args = mock_urlopen.call_args[0][0]
        payload_data = call_args.data.decode()
        assert "v1.2.3" in payload_data


class TestVerifyDispatchSignature:
    """Tests for HMAC signature verification."""
    
    def test_valid_signature(self):
        """Valid HMAC signature should be verified."""
        from src.integrations.github.sync import verify_dispatch_signature
        import hmac
        import hashlib
        
        upstream_repo = "org/upstream-repo"
        upstream_branch = "main"
        timestamp = "2024-01-15T12:00:00Z"
        secret = "test-secret-key"
        
        # Create valid signature
        payload_data = f"{upstream_repo}|{upstream_branch}|{timestamp}"
        valid_signature = hmac.new(
            secret.encode('utf-8'),
            payload_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        result = verify_dispatch_signature(
            upstream_repo, upstream_branch, timestamp, valid_signature, secret
        )
        
        assert result is True
    
    def test_invalid_signature(self):
        """Invalid HMAC signature should be rejected."""
        from src.integrations.github.sync import verify_dispatch_signature
        
        upstream_repo = "org/upstream-repo"
        upstream_branch = "main"
        timestamp = "2024-01-15T12:00:00Z"
        secret = "test-secret-key"
        invalid_signature = "wrong_signature_12345"
        
        result = verify_dispatch_signature(
            upstream_repo, upstream_branch, timestamp, invalid_signature, secret
        )
        
        assert result is False
    
    def test_tampered_payload(self):
        """Signature should fail if payload is tampered."""
        from src.integrations.github.sync import verify_dispatch_signature
        import hmac
        import hashlib
        
        upstream_repo = "org/upstream-repo"
        upstream_branch = "main"
        timestamp = "2024-01-15T12:00:00Z"
        secret = "test-secret-key"
        
        # Create signature with original payload
        payload_data = f"{upstream_repo}|{upstream_branch}|{timestamp}"
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Verify with tampered upstream_repo
        result = verify_dispatch_signature(
            "org/different-repo", upstream_branch, timestamp, signature, secret
        )
        
        assert result is False


class TestDiscoverDownstreamRepos:
    """Tests for topic-based repository discovery."""
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_discovers_repos_with_topic(self, mock_urlopen, mock_token):
        """Should discover repos with specified topic in org."""
        from src.integrations.github.sync import discover_downstream_repos
        
        # Mock search API response
        search_response = {
            "total_count": 2,
            "items": [
                {"full_name": "test-org/satellite-1", "id": 1},
                {"full_name": "test-org/satellite-2", "id": 2},
            ]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(search_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        repos = discover_downstream_repos("test-org", mock_token)
        
        assert len(repos) == 2
        assert "test-org/satellite-1" in repos
        assert "test-org/satellite-2" in repos
        
        # Verify search query was constructed correctly
        call_args = mock_urlopen.call_args[0][0]
        assert "topic:speculum-downstream" in call_args.full_url
        assert "org:test-org" in call_args.full_url
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_custom_topic(self, mock_urlopen, mock_token):
        """Should search for custom topic."""
        from src.integrations.github.sync import discover_downstream_repos
        
        search_response = {"total_count": 0, "items": []}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(search_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        repos = discover_downstream_repos("test-org", mock_token, topic="custom-topic")
        
        assert repos == []
        call_args = mock_urlopen.call_args[0][0]
        assert "topic:custom-topic" in call_args.full_url
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_api_error(self, mock_urlopen, mock_token):
        """Should raise SyncError on API failure."""
        from src.integrations.github.sync import discover_downstream_repos, SyncError
        from urllib import error as urllib_error
        
        mock_error = urllib_error.HTTPError(
            url="https://api.github.com/search/repositories",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=MagicMock(read=lambda: b"Not found")
        )
        mock_urlopen.side_effect = mock_error
        
        with pytest.raises(SyncError, match="Failed to discover downstream repos"):
            discover_downstream_repos("test-org", mock_token)


class TestVerifySatelliteTrust:
    """Tests for satellite repository trust verification."""
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_trusted_repo(self, mock_urlopen, mock_token):
        """Should verify valid satellite repo."""
        from src.integrations.github.sync import verify_satellite_trust
        
        # Mock repo API response for valid satellite
        repo_response = {
            "fork": False,
            "template_repository": {
                "full_name": "org/upstream-template"
            },
            "topics": ["speculum-downstream", "research"]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(repo_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        is_trusted, reason = verify_satellite_trust(
            "org/satellite", "org/upstream-template", mock_token
        )
        
        assert is_trusted is True
        assert "passed" in reason.lower()
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_fork_rejected(self, mock_urlopen, mock_token):
        """Should reject repositories that are forks."""
        from src.integrations.github.sync import verify_satellite_trust
        
        repo_response = {
            "fork": True,
            "template_repository": {"full_name": "org/upstream-template"},
            "topics": ["speculum-downstream"]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(repo_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        is_trusted, reason = verify_satellite_trust(
            "org/satellite", "org/upstream-template", mock_token
        )
        
        assert is_trusted is False
        assert "fork" in reason.lower()
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_template_mismatch_rejected(self, mock_urlopen, mock_token):
        """Should reject repos with wrong template."""
        from src.integrations.github.sync import verify_satellite_trust
        
        repo_response = {
            "fork": False,
            "template_repository": {"full_name": "org/different-template"},
            "topics": ["speculum-downstream"]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(repo_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        is_trusted, reason = verify_satellite_trust(
            "org/satellite", "org/upstream-template", mock_token
        )
        
        assert is_trusted is False
        assert "mismatch" in reason.lower()
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_missing_topic_rejected(self, mock_urlopen, mock_token):
        """Should reject repos without required topic."""
        from src.integrations.github.sync import verify_satellite_trust
        
        repo_response = {
            "fork": False,
            "template_repository": {"full_name": "org/upstream-template"},
            "topics": ["other-topic"]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(repo_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        is_trusted, reason = verify_satellite_trust(
            "org/satellite", "org/upstream-template", mock_token
        )
        
        assert is_trusted is False
        assert "topic" in reason.lower()
    
    @patch('src.integrations.github.sync.request.urlopen')
    def test_no_template_rejected(self, mock_urlopen, mock_token):
        """Should reject repos not created from template."""
        from src.integrations.github.sync import verify_satellite_trust
        
        repo_response = {
            "fork": False,
            "template_repository": None,
            "topics": ["speculum-downstream"]
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(repo_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        is_trusted, reason = verify_satellite_trust(
            "org/satellite", "org/upstream-template", mock_token
        )
        
        assert is_trusted is False
        assert "template" in reason.lower()


class TestValidatePRFileScope:
    """Tests for PR file scope validation."""
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_valid_code_files(self, mock_fetch, mock_repository, mock_token):
        """Should accept PR with only code files."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        # Mock PR files - only code changes
        mock_fetch.return_value = [
            {"filename": "src/config.py"},
            {"filename": "tests/test_feature.py"},
            {"filename": "main.py"},
        ]
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is True
        assert "3 file(s)" in reason
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_rejects_protected_dirs(self, mock_fetch, mock_repository, mock_token):
        """Should reject PR modifying protected directories."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        # Mock PR files - includes protected directory
        mock_fetch.return_value = [
            {"filename": "src/config.py"},
            {"filename": "evidence/new-doc.pdf"},
        ]
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is False
        assert "protected" in reason.lower()
        assert "evidence/" in reason
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_rejects_non_code_files(self, mock_fetch, mock_repository, mock_token):
        """Should reject PR with files outside code directories."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        # Mock PR files - includes random file
        mock_fetch.return_value = [
            {"filename": "src/config.py"},
            {"filename": "random_file.txt"},
        ]
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is False
        assert "outside code directories" in reason.lower()
        assert "random_file.txt" in reason
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_empty_pr(self, mock_fetch, mock_repository, mock_token):
        """Should accept PR with no files."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        mock_fetch.return_value = []
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is True
        assert "no files" in reason.lower()
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_multiple_protected_files(self, mock_fetch, mock_repository, mock_token):
        """Should report multiple protected files."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        # Mock PR with multiple protected files
        mock_fetch.return_value = [
            {"filename": "evidence/doc1.pdf"},
            {"filename": "knowledge-graph/entity.yaml"},
            {"filename": "reports/analysis.md"},
        ]
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is False
        assert "protected" in reason.lower()
    
    @patch('src.integrations.github.sync.fetch_pull_request_files')
    def test_handles_api_error(self, mock_fetch, mock_repository, mock_token):
        """Should handle API errors gracefully."""
        from src.integrations.github.sync import validate_pr_file_scope
        
        mock_fetch.side_effect = Exception("API Error")
        
        is_valid, reason = validate_pr_file_scope(
            mock_repository, 123, mock_token
        )
        
        assert is_valid is False
        assert "error" in reason.lower()
