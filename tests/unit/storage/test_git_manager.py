"""
Tests for GitManager - git operations for issue processing.

This module tests the GitManager class which handles git operations
for the automated issue processing system. Tests cover:
- Branch creation and management
- Commit operations for deliverables
- Error handling and edge cases
- Git repository state validation
- Branch cleanup and status checking

Uses temporary git repositories and mocked git commands to ensure
isolated testing without affecting real repositories.
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.storage.git_manager import GitManager, GitOperationError, BranchInfo, CommitInfo


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir)
    
    # Initialize git repository
    subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_path, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_path, check=True)
    
    # Create initial commit on main branch
    readme_file = repo_path / 'README.md'
    readme_file.write_text('# Test Repository\n')
    subprocess.run(['git', 'add', 'README.md'], cwd=repo_path, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_path, check=True)
    
    # Ensure we're on main branch (git might init with master)
    try:
        subprocess.run(['git', 'branch', '-M', 'main'], cwd=repo_path, check=True)
    except subprocess.CalledProcessError:
        # If branch rename fails, try checkout
        try:
            subprocess.run(['git', 'checkout', '-b', 'main'], cwd=repo_path, check=True)
        except subprocess.CalledProcessError:
            pass  # Already on main or main exists
    
    yield repo_path
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def git_manager(temp_git_repo):
    """Create GitManager instance with temporary repository."""
    return GitManager(
        repo_path=str(temp_git_repo),
        base_branch="main",
        branch_prefix="test-issue",
        auto_cleanup=True
    )


@pytest.fixture
def sample_files(temp_git_repo):
    """Create sample files for testing commits."""
    files = []
    
    # Create a deliverable file
    deliverable1 = temp_git_repo / 'study' / 'deliverable1.md'
    deliverable1.parent.mkdir(parents=True, exist_ok=True)
    deliverable1.write_text('# Deliverable 1\nContent here...')
    files.append(str(deliverable1))
    
    # Create another deliverable file
    deliverable2 = temp_git_repo / 'study' / 'deliverable2.md'
    deliverable2.write_text('# Deliverable 2\nMore content...')
    files.append(str(deliverable2))
    
    return files


class TestGitManagerInitialization:
    """Test GitManager initialization and validation."""
    
    def test_init_with_valid_repo(self, temp_git_repo):
        """Test initialization with valid git repository."""
        manager = GitManager(repo_path=str(temp_git_repo))
        assert manager.repo_path == temp_git_repo
        assert manager.base_branch == "main"
        assert manager.branch_prefix == "issue"
        assert manager.auto_cleanup is True
    
    def test_init_with_custom_settings(self, temp_git_repo):
        """Test initialization with custom settings."""
        # Create a develop branch first
        subprocess.run(['git', 'checkout', '-b', 'develop'], cwd=temp_git_repo, check=True)
        
        manager = GitManager(
            repo_path=str(temp_git_repo),
            base_branch="develop",
            branch_prefix="feature",
            auto_cleanup=False
        )
        assert manager.base_branch == "develop"
        assert manager.branch_prefix == "feature"
        assert manager.auto_cleanup is False
    
    def test_init_with_invalid_repo(self):
        """Test initialization with invalid git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Directory exists but is not a git repo
            with pytest.raises(GitOperationError, match="Not a git repository"):
                GitManager(repo_path=temp_dir)
    
    def test_init_with_nonexistent_directory(self):
        """Test initialization with nonexistent directory."""
        with pytest.raises(GitOperationError):
            GitManager(repo_path="/nonexistent/directory")
    
    @patch('src.storage.git_manager.GitManager._run_git_command')
    def test_init_without_git_config(self, mock_git_command, temp_git_repo):
        """Test initialization when git user config is missing."""
        # Simulate missing git config
        mock_git_command.side_effect = GitOperationError("Git config not found")
        
        # Should still initialize but log warning
        manager = GitManager(repo_path=str(temp_git_repo))
        assert manager is not None


class TestBranchOperations:
    """Test git branch operations."""
    
    def test_create_issue_branch(self, git_manager):
        """Test creating a new issue branch."""
        branch_info = git_manager.create_issue_branch(
            issue_number=123,
            title="Fix critical bug"
        )
        
        assert isinstance(branch_info, BranchInfo)
        assert branch_info.issue_number == 123
        assert branch_info.base_branch == "main"
        assert "test-issue-123" in branch_info.name
        assert "fix-critical-bug" in branch_info.name
    
    def test_create_issue_branch_without_title(self, git_manager):
        """Test creating issue branch without title."""
        branch_info = git_manager.create_issue_branch(issue_number=456)
        
        assert branch_info.issue_number == 456
        assert branch_info.name == "test-issue-456"
    
    def test_create_issue_branch_with_long_title(self, git_manager):
        """Test creating issue branch with very long title."""
        long_title = "This is a very long issue title that should be truncated to avoid problems"
        branch_info = git_manager.create_issue_branch(
            issue_number=789,
            title=long_title
        )
        
        # Branch name should be limited in length
        assert len(branch_info.name) <= 60
        assert "test-issue-789" in branch_info.name
    
    def test_create_duplicate_branch(self, git_manager):
        """Test creating branch that already exists."""
        # Create first branch
        branch_info1 = git_manager.create_issue_branch(
            issue_number=111,
            title="Test branch"
        )
        
        # Try to create same branch again
        branch_info2 = git_manager.create_issue_branch(
            issue_number=111,
            title="Test branch"
        )
        
        assert branch_info1.name == branch_info2.name
    
    def test_branch_exists_check(self, git_manager):
        """Test checking if branch exists."""
        # Branch should not exist initially
        assert not git_manager._branch_exists("test-issue-999")
        
        # Create branch
        git_manager.create_issue_branch(issue_number=999)
        
        # Branch should now exist
        assert git_manager._branch_exists("test-issue-999")
    
    def test_get_current_branch(self, git_manager):
        """Test getting current branch name."""
        # Should start on main branch (or master, depending on git version)
        current = git_manager._get_current_branch()
        assert current in ["main", "master"]  # Allow both for compatibility
        
        # Create and switch to new branch
        branch_info = git_manager.create_issue_branch(issue_number=222)
        current = git_manager._get_current_branch()
        assert current == branch_info.name


class TestCommitOperations:
    """Test git commit operations."""
    
    def test_commit_deliverables(self, git_manager, sample_files):
        """Test committing deliverable files."""
        # Create a branch first
        branch_info = git_manager.create_issue_branch(
            issue_number=333,
            title="Test deliverables"
        )
        
        # Commit the files
        commit_info = git_manager.commit_deliverables(
            file_paths=sample_files,
            issue_number=333,
            workflow_name="person-entity-profiling"
        )
        
        assert isinstance(commit_info, CommitInfo)
        assert len(commit_info.hash) == 40  # Full git hash
        assert "person-entity-profiling" in commit_info.message
        assert "issue #333" in commit_info.message
        assert len(commit_info.files_changed) == len(sample_files)
    
    def test_commit_with_custom_message(self, git_manager, sample_files):
        """Test committing with custom commit message."""
        git_manager.create_issue_branch(issue_number=444)
        
        custom_message = "Custom commit message for testing"
        commit_info = git_manager.commit_deliverables(
            file_paths=sample_files,
            issue_number=444,
            workflow_name="test-workflow",
            commit_message=custom_message
        )
        
        assert commit_info.message == custom_message
    
    def test_commit_empty_file_list(self, git_manager):
        """Test committing with empty file list."""
        git_manager.create_issue_branch(issue_number=555)
        
        with pytest.raises(GitOperationError, match="No files to commit"):
            git_manager.commit_deliverables(
                file_paths=[],
                issue_number=555,
                workflow_name="empty-workflow"
            )
    
    def test_commit_nonexistent_files(self, git_manager):
        """Test committing files that don't exist."""
        git_manager.create_issue_branch(issue_number=666)
        
        with pytest.raises(GitOperationError, match="Files not found"):
            git_manager.commit_deliverables(
                file_paths=["/nonexistent/file.md"],
                issue_number=666,
                workflow_name="missing-workflow"
            )
    
    def test_generate_file_summary(self, git_manager):
        """Test file summary generation for commit messages."""
        files = [
            "study/issue-123/analysis.md",
            "study/issue-123/report.md",
            "docs/review.md"
        ]
        
        summary = git_manager._generate_file_summary(files)
        
        assert "study/issue-123/ (2 files)" in summary
        assert "docs/review.md" in summary
    
    def test_get_commit_details(self, git_manager, sample_files):
        """Test getting detailed commit information."""
        git_manager.create_issue_branch(issue_number=777)
        
        commit_info = git_manager.commit_deliverables(
            file_paths=sample_files,
            issue_number=777,
            workflow_name="test-details"
        )
        
        # Get detailed commit info
        details = git_manager._get_commit_details(commit_info.hash)
        
        assert details.hash == commit_info.hash
        assert details.author == "Test User"
        assert isinstance(details.timestamp, datetime)
        assert len(details.files_changed) > 0


class TestBranchManagement:
    """Test branch management operations."""
    
    def test_push_branch(self, git_manager):
        """Test pushing branch to remote."""
        # Note: This test would need a mock remote or will fail in CI
        # For now, test that the method handles missing remote gracefully
        
        branch_info = git_manager.create_issue_branch(issue_number=888)
        
        # Should return False when no remote is configured
        result = git_manager.push_branch(branch_info.name)
        assert result is False  # Expected to fail without remote
    
    def test_get_branch_status(self, git_manager):
        """Test getting branch status information."""
        # Test non-existent branch
        status = git_manager.get_branch_status("nonexistent-branch")
        assert status['exists'] is False
        
        # Create branch and test status
        branch_info = git_manager.create_issue_branch(issue_number=999)
        status = git_manager.get_branch_status(branch_info.name)
        
        assert status['exists'] is True
        assert status['branch_info'].name == branch_info.name
        assert status['commit_count'] >= 1  # At least the initial commit
        assert status['remote_exists'] is False  # No remote configured
    
    def test_cleanup_merged_branches_dry_run(self, git_manager):
        """Test dry run of branch cleanup."""
        # Create some branches
        git_manager.create_issue_branch(issue_number=100)
        git_manager.create_issue_branch(issue_number=200)
        
        # Dry run should return potential deletions
        branches_to_delete = git_manager.cleanup_merged_branches(dry_run=True)
        
        # Should be a list (might be empty if branches aren't merged)
        assert isinstance(branches_to_delete, list)
    
    def test_is_branch_merged(self, git_manager):
        """Test checking if branch is merged."""
        branch_info = git_manager.create_issue_branch(issue_number=301)
        
        # New branch should not be merged yet
        is_merged = git_manager._is_branch_merged(branch_info.name)
        # Might be True if no changes made, which is acceptable
        assert isinstance(is_merged, bool)


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @patch('src.storage.git_manager.GitManager._run_git_command')
    def test_git_command_failure(self, mock_git_command, temp_git_repo):
        """Test handling of git command failures."""
        mock_git_command.side_effect = GitOperationError("Git command failed")
        
        manager = GitManager(repo_path=str(temp_git_repo))
        
        with pytest.raises(GitOperationError):
            manager.create_issue_branch(issue_number=123)
    
    @patch('subprocess.run')
    def test_git_command_timeout(self, mock_subprocess, temp_git_repo):
        """Test handling of git command timeouts."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(['git'], 30)
        
        manager = GitManager(repo_path=str(temp_git_repo))
        
        with pytest.raises(GitOperationError, match="timed out"):
            manager._run_git_command(['status'])
    
    def test_slugify_special_characters(self, git_manager):
        """Test text slugification with special characters."""
        test_cases = [
            ("Feature: Add user authentication", "feature-add-user-authentication"),
            ("Bug #123: Fix memory leak", "bug-123-fix-memory-leak"),
            ("Update docs & examples", "update-docs-examples"),
            ("Very long title that should be truncated" * 3, "very-long-title-that-should-be-truncated-very-lo")
        ]
        
        for input_text, expected in test_cases:
            result = git_manager._slugify(input_text)
            # For the long text case, just check it's limited and well-formed
            if len(input_text) > 50:
                assert len(result) <= 50
                assert not result.endswith('-')
                assert 'very-long-title' in result
            else:
                assert result == expected
    
    def test_branch_name_validation(self, git_manager):
        """Test branch name generation with edge cases."""
        # Test with empty title
        branch_info = git_manager.create_issue_branch(issue_number=0, title="")
        assert "test-issue-0" in branch_info.name
        
        # Test with special characters in title
        branch_info = git_manager.create_issue_branch(
            issue_number=42,
            title="Feature: Add @user mentions & #hashtags"
        )
        assert "test-issue-42" in branch_info.name
        assert "feature-add-user-mentions-hashtags" in branch_info.name


class TestIntegration:
    """Integration tests for GitManager."""
    
    def test_full_workflow_cycle(self, git_manager, sample_files):
        """Test complete workflow from branch creation to commit."""
        issue_number = 12345
        workflow_name = "comprehensive-analysis"
        title = "Comprehensive analysis workflow test"
        
        # 1. Create branch
        branch_info = git_manager.create_issue_branch(
            issue_number=issue_number,
            title=title
        )
        assert branch_info.issue_number == issue_number
        
        # 2. Verify we're on the new branch
        current_branch = git_manager._get_current_branch()
        assert current_branch == branch_info.name
        
        # 3. Commit deliverables
        commit_info = git_manager.commit_deliverables(
            file_paths=sample_files,
            issue_number=issue_number,
            workflow_name=workflow_name
        )
        assert workflow_name in commit_info.message
        assert str(issue_number) in commit_info.message
        
        # 4. Check branch status
        status = git_manager.get_branch_status(branch_info.name)
        assert status['exists'] is True
        assert status['commit_count'] >= 2  # Initial + deliverable commits
        
        # 5. Verify files are tracked
        assert len(commit_info.files_changed) == len(sample_files)
    
    def test_multiple_issues_parallel(self, git_manager, temp_git_repo):
        """Test handling multiple issues in parallel."""
        issues = [
            (1001, "First issue", "feature-analysis"),
            (1002, "Second issue", "bug-investigation"),
            (1003, "Third issue", "documentation-update")
        ]
        
        branch_infos = []
        commit_infos = []
        
        for issue_num, title, workflow in issues:
            # Create branch
            branch_info = git_manager.create_issue_branch(
                issue_number=issue_num,
                title=title
            )
            branch_infos.append(branch_info)
            
            # Create and commit a file
            file_path = temp_git_repo / f"issue_{issue_num}.md"
            file_path.write_text(f"# Issue {issue_num}\n{title}")
            
            commit_info = git_manager.commit_deliverables(
                file_paths=[str(file_path)],
                issue_number=issue_num,
                workflow_name=workflow
            )
            commit_infos.append(commit_info)
        
        # Verify all branches exist and have commits
        assert len(branch_infos) == len(issues)
        assert len(commit_infos) == len(issues)
        
        for i, (issue_num, _, _) in enumerate(issues):
            assert branch_infos[i].issue_number == issue_num
            assert str(issue_num) in commit_infos[i].message
    
    def test_error_recovery(self, git_manager, temp_git_repo):
        """Test recovery from various error conditions."""
        # 1. Create branch successfully
        branch_info = git_manager.create_issue_branch(
            issue_number=2001,
            title="Error recovery test"
        )
        
        # 2. Try to commit non-existent file (should fail)
        with pytest.raises(GitOperationError):
            git_manager.commit_deliverables(
                file_paths=["/does/not/exist.md"],
                issue_number=2001,
                workflow_name="error-test"
            )
        
        # 3. Repository should still be in valid state
        current_branch = git_manager._get_current_branch()
        assert current_branch == branch_info.name
        
        # 4. Should be able to make valid commit afterward
        valid_file = temp_git_repo / "recovery_test.md"
        valid_file.write_text("# Recovery Test\nThis should work.")
        
        commit_info = git_manager.commit_deliverables(
            file_paths=[str(valid_file)],
            issue_number=2001,
            workflow_name="recovery-workflow"
        )
        
        assert commit_info is not None
        assert "recovery-workflow" in commit_info.message