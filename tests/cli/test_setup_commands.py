"""Unit tests for setup CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.cli.commands.setup import validate_setup
from src.integrations.github.discussions import DiscussionCategory


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_token() -> str:
    return "test-token-12345"


@pytest.fixture
def mock_repository() -> str:
    return "test-org/test-repo"


# =============================================================================
# Tests for validate_setup
# =============================================================================


class TestValidateSetup:
    """Tests for repository setup validation."""
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_fully_valid_setup(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should pass all checks for properly configured repo."""
        # Mock UPSTREAM_REPO variable
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock repository details
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream", "research"],
            "template_repository": {
                "full_name": "org/upstream-repo"
            }
        }
        
        # Mock Sources discussion category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert result["valid"] is True
        assert len(result["issues"]) == 0
        assert len(result["warnings"]) == 0
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_missing_upstream_repo_var(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should detect missing UPSTREAM_REPO variable."""
        # Mock missing variable
        mock_get_var.return_value = None
        
        # Mock repository details
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert result["valid"] is False
        assert any("UPSTREAM_REPO" in issue for issue in result["issues"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_fork_rejected(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should reject repository that is a fork."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock fork repository
        mock_get_details.return_value = {
            "fork": True,
            "topics": ["speculum-downstream"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert result["valid"] is False
        assert any("fork" in issue.lower() for issue in result["issues"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_missing_topic_warning(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should warn about missing speculum-downstream topic."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock repository without required topic
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["other-topic"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert len(result["warnings"]) > 0
        assert any("topic" in warning.lower() for warning in result["warnings"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_no_template_warning(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should warn if repo not created from template."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock repository without template
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": None
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert len(result["warnings"]) > 0
        assert any("template" in warning.lower() for warning in result["warnings"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_template_mismatch_warning(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should warn if template doesn't match UPSTREAM_REPO."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock repository with different template
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": {
                "full_name": "org/different-template"
            }
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert len(result["warnings"]) > 0
        assert any("differs" in warning.lower() for warning in result["warnings"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_api_error_handling(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should handle API errors gracefully."""
        # Mock API error
        mock_get_var.side_effect = Exception("API Error")
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Sources category exists
        mock_discussions.get_category_by_name.return_value = DiscussionCategory(
            id="CAT123", name="Sources", slug="sources", is_answerable=False
        )
        
        result = validate_setup(mock_repository, mock_token)
        
        assert result["valid"] is False
        assert any("Could not verify" in issue for issue in result["issues"])
    
    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_multiple_issues(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should detect multiple configuration issues."""
        # Mock missing variable
        mock_get_var.return_value = None
        
        # Mock fork without topic
        mock_get_details.return_value = {
            "fork": True,
            "topics": [],
            "template_repository": None
        }
        
        # Mock Sources category missing
        mock_discussions.get_category_by_name.return_value = None
        
        result = validate_setup(mock_repository, mock_token)
        
        assert result["valid"] is False
        assert len(result["issues"]) >= 2  # UPSTREAM_REPO + fork
        assert len(result["warnings"]) >= 2  # missing topic + missing Sources category

    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_missing_sources_category_warning(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should warn if Sources discussion category is missing."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock valid repository
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Sources category missing
        mock_discussions.get_category_by_name.return_value = None
        
        result = validate_setup(mock_repository, mock_token)
        
        assert len(result["warnings"]) > 0
        assert any("Sources" in warning for warning in result["warnings"])
        assert any("discussion category" in warning.lower() for warning in result["warnings"])

    @patch('src.cli.commands.setup.github_discussions')
    @patch('src.cli.commands.setup.get_repository_details')
    @patch('src.cli.commands.setup.get_repository_variable')
    @patch('builtins.print')
    def test_discussions_api_error_warning(
        self, mock_print, mock_get_var, mock_get_details, mock_discussions, mock_repository, mock_token
    ):
        """Should warn if discussion category check fails (e.g., Discussions not enabled)."""
        mock_get_var.return_value = "org/upstream-repo"
        
        # Mock valid repository
        mock_get_details.return_value = {
            "fork": False,
            "topics": ["speculum-downstream"],
            "template_repository": {"full_name": "org/upstream-repo"}
        }
        
        # Mock Discussions API error (e.g., Discussions not enabled)
        mock_discussions.get_category_by_name.side_effect = Exception("Discussions not enabled")
        
        result = validate_setup(mock_repository, mock_token)
        
        assert len(result["warnings"]) > 0
        assert any("discussion categories" in warning.lower() for warning in result["warnings"])
