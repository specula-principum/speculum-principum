"""Tests for repository resolution with git auto-detection."""

import os
import subprocess
from unittest.mock import patch

import pytest

from src.integrations.github.issues import (
    GitHubIssueError,
    _get_repository_from_git,
    resolve_repository,
)


class TestGetRepositoryFromGit:
    """Test git remote URL parsing."""

    def test_ssh_url(self):
        """Parse SSH-style GitHub URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "git@github.com:owner/repo.git\n"
            assert _get_repository_from_git() == "owner/repo"

    def test_ssh_url_without_git_suffix(self):
        """Parse SSH-style GitHub URL without .git suffix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "git@github.com:owner/repo\n"
            assert _get_repository_from_git() == "owner/repo"

    def test_https_url(self):
        """Parse HTTPS GitHub URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/owner/repo.git\n"
            assert _get_repository_from_git() == "owner/repo"

    def test_https_url_without_git_suffix(self):
        """Parse HTTPS GitHub URL without .git suffix."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/owner/repo\n"
            assert _get_repository_from_git() == "owner/repo"

    def test_non_github_url(self):
        """Return None for non-GitHub remotes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://gitlab.com/owner/repo.git\n"
            assert _get_repository_from_git() is None

    def test_git_command_fails(self):
        """Return None when git command fails."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            assert _get_repository_from_git() is None

    def test_git_not_installed(self):
        """Return None when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _get_repository_from_git() is None

    def test_git_timeout(self):
        """Return None when git command times out."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            assert _get_repository_from_git() is None


class TestResolveRepository:
    """Test repository resolution with multiple fallbacks."""

    def test_explicit_repo_takes_precedence(self, monkeypatch):
        """Explicit --repo argument should be used first."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "env/repo")
        with patch("src.integrations.github.issues._get_repository_from_git", return_value="git/repo"):
            assert resolve_repository("explicit/repo") == "explicit/repo"

    def test_env_var_fallback(self, monkeypatch):
        """Environment variable should be used if no explicit repo."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "env/repo")
        with patch("src.integrations.github.issues._get_repository_from_git", return_value="git/repo"):
            assert resolve_repository(None) == "env/repo"

    def test_git_auto_detection_fallback(self, monkeypatch):
        """Git auto-detection should be used as last resort."""
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        with patch("src.integrations.github.issues._get_repository_from_git", return_value="git/repo"):
            assert resolve_repository(None) == "git/repo"

    def test_raises_when_no_repository_found(self, monkeypatch):
        """Raise error when no repository can be determined."""
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        with patch("src.integrations.github.issues._get_repository_from_git", return_value=None):
            with pytest.raises(GitHubIssueError, match="Repository not provided"):
                resolve_repository(None)
