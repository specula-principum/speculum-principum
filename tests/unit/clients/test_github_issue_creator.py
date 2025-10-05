"""
Unit tests for GitHub operations module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.clients.github_issue_creator import GitHubIssueCreator
from src.clients.search_client import SearchResult
from tests.conftest import MockGitHubException


class TestGitHubIssueCreator:
    """Test cases for GitHubIssueCreator class"""
    
    def test_init(self, mock_github_token, mock_repository_name):
        """Test GitHubIssueCreator initialization"""
        with patch('src.clients.github_issue_creator.Github') as mock_github_class, \
             patch('src.clients.github_issue_creator.Auth') as mock_auth_class:
            mock_github_instance = Mock()
            mock_repo = Mock()
            mock_auth_token = Mock()
            mock_github_class.return_value = mock_github_instance
            mock_github_instance.get_repo.return_value = mock_repo
            mock_auth_class.Token.return_value = mock_auth_token
            
            creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
            
            mock_auth_class.Token.assert_called_once_with(mock_github_token)
            mock_github_class.assert_called_once_with(auth=mock_auth_token)
            mock_github_instance.get_repo.assert_called_once_with(mock_repository_name)
            assert creator.repository == mock_repository_name
            assert creator.repo == mock_repo
    
    @patch('src.clients.github_issue_creator.Github')
    def test_create_issue_success(self, mock_github_class, mock_github_token, mock_repository_name, mock_issue_data, mock_github_issue):
        """Test successful issue creation"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.create_issue.return_value = mock_github_issue
        mock_repo.get_labels.return_value = [Mock(name="bug"), Mock(name="urgent")]
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.create_issue(
            title=mock_issue_data["title"],
            body=mock_issue_data["body"],
            labels=mock_issue_data["labels"],
            assignees=mock_issue_data["assignees"]
        )
        
        # Assertions
        mock_repo.create_issue.assert_called_once_with(
            title=mock_issue_data["title"],
            body=mock_issue_data["body"],
            labels=mock_issue_data["labels"],
            assignees=mock_issue_data["assignees"]
        )
        assert result == mock_github_issue
    
    @patch('src.clients.github_issue_creator.Github')
    def test_create_issue_minimal(self, mock_github_class, mock_github_token, mock_repository_name, mock_github_issue):
        """Test issue creation with minimal parameters"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.create_issue.return_value = mock_github_issue
        mock_repo.get_labels.return_value = []
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.create_issue(title="Test Issue")
        
        # Assertions
        mock_repo.create_issue.assert_called_once_with(
            title="Test Issue",
            body="",
            labels=[],
            assignees=[]
        )
        assert result == mock_github_issue
    
    @patch('src.clients.github_issue_creator.Github')
    def test_create_issue_invalid_labels(self, mock_github_class, mock_github_token, mock_repository_name, mock_github_issue, capsys):
        """Test issue creation with invalid labels"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.create_issue.return_value = mock_github_issue
        mock_repo.get_labels.return_value = [Mock(name="bug")]  # Only 'bug' exists
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.create_issue(
            title="Test Issue",
            labels=["bug", "nonexistent-label"]
        )
        
        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning: Labels not found in repository: ['nonexistent-label']" in captured.out
        
        # Check only valid labels were used
        mock_repo.create_issue.assert_called_once_with(
            title="Test Issue",
            body="",
            labels=["bug"],
            assignees=[]
        )
        assert result == mock_github_issue
    
    @patch('src.clients.github_issue_creator.Github')
    def test_create_issue_github_exception(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test issue creation with GitHub API exception"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_labels.return_value = []
        
        # Configure exception
        github_exception = MockGitHubException("API rate limit exceeded")
        mock_repo.create_issue.side_effect = github_exception
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        
        with pytest.raises(RuntimeError, match="Failed to create GitHub issue: API rate limit exceeded"):
            creator.create_issue(title="Test Issue")
    
    @patch('src.clients.github_issue_creator.Github')
    def test_create_issue_unexpected_exception(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test issue creation with unexpected exception"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_labels.return_value = []
        mock_repo.create_issue.side_effect = ValueError("Unexpected error")
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        
        with pytest.raises(RuntimeError, match="Unexpected error creating issue: Unexpected error"):
            creator.create_issue(title="Test Issue")

    def test_create_individual_result_issue_applies_discovery_template(self, mock_github_token, mock_repository_name, mock_github_issue):
        """Ensure individual issues include discovery template and required labels."""
        with patch('src.clients.github_issue_creator.Github') as mock_github_class, \
             patch('src.clients.github_issue_creator.Auth') as mock_auth_class:
            mock_github_instance = Mock()
            mock_repo = Mock()
            mock_github_class.return_value = mock_github_instance
            mock_github_instance.get_repo.return_value = mock_repo
            mock_repo.create_issue.return_value = mock_github_issue
            mock_repo.get_labels.return_value = [
                Mock(name='site-monitor'),
                Mock(name='daily-summary'),
                Mock(name='automated'),
                Mock(name='documentation'),
                Mock(name='monitor::triage'),
                Mock(name='state::discovery'),
                Mock(name='state::assigned'),
                Mock(name='state::copilot'),
                Mock(name='state::done'),
                Mock(name='custom-label'),
            ]
            mock_auth_class.Token.return_value = Mock()

            creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
            search_result = SearchResult(
                title="Example Discovery",
                link="https://example.com/article",
                snippet="Example snippet detailing the discovery.",
                display_link="example.com"
            )

            issue = creator.create_individual_result_issue(
                site_name="Example Site",
                result=search_result,
                labels=['site-monitor', 'custom-label']
            )

            mock_repo.create_issue.assert_called_once()
            _, kwargs = mock_repo.create_issue.call_args

            labels = kwargs['labels']
            assert 'site-monitor' in labels
            assert 'custom-label' in labels
            assert 'monitor::triage' in labels
            assert 'state::discovery' in labels

            body = kwargs['body']
            assert body.startswith('# Workflow Intake: Example Site')
            assert '## Discovery' in body
            assert 'Example snippet detailing the discovery.' in body
            assert '## AI Assessment' in body
            assert 'Pending automated assignment' in body
            assert '## Specialist Guidance' in body
            assert '## Copilot Assignment' in body

            assert issue == mock_github_issue

    def test_create_monitoring_labels_includes_state_labels(self, mock_github_token, mock_repository_name):
        """Default monitoring labels should include workflow state entries."""
        with patch('src.clients.github_issue_creator.Github') as mock_github_class, \
             patch('src.clients.github_issue_creator.Auth') as mock_auth_class:
            mock_github_instance = Mock()
            mock_repo = Mock()
            mock_github_class.return_value = mock_github_instance
            mock_github_instance.get_repo.return_value = mock_repo
            mock_repo.get_labels.return_value = []
            mock_repo.create_label = Mock()
            mock_auth_class.Token.return_value = Mock()

            creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
            created_labels = creator.create_monitoring_labels()

            expected_labels = {
                'site-monitor',
                'daily-summary',
                'automated',
                'documentation',
                'monitor::triage',
                'state::discovery',
                'state::assigned',
                'state::copilot',
                'state::done',
            }

            assert set(created_labels) == expected_labels

            created_names = {call.kwargs['name'] for call in mock_repo.create_label.call_args_list}
            assert expected_labels == created_names
    
    @patch('src.clients.github_issue_creator.Github')
    def test_get_repository_info_success(self, mock_github_class, mock_github_token, mock_repository_name, sample_repo_info):
        """Test successful repository info retrieval"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        
        # Configure repo attributes
        mock_repo.name = sample_repo_info['name']
        mock_repo.full_name = sample_repo_info['full_name']
        mock_repo.description = sample_repo_info['description']
        mock_repo.html_url = sample_repo_info['url']
        mock_repo.open_issues_count = sample_repo_info['issues_count']
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.get_repository_info()
        
        # Assertions
        assert result == sample_repo_info
    
    @patch('src.clients.github_issue_creator.Github')
    def test_get_repository_info_exception(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test repository info retrieval with exception"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        
        # Configure exception
        github_exception = MockGitHubException("Repository not found")
        # Use type() to set the property on the mock's class
        type(mock_repo).name = property(lambda self: (_ for _ in ()).throw(github_exception))
        
        # Create instance and test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        
        with pytest.raises(RuntimeError, match="Failed to get repository info: Repository not found"):
            creator.get_repository_info()
    
    @patch('src.clients.github_issue_creator.Github')
    def test_get_issue_success(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test successful issue retrieval"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.get_issue(123)
        
        # Assertions
        mock_repo.get_issue.assert_called_once_with(123)
        assert result == mock_issue
    
    @patch('src.clients.github_issue_creator.Github')
    def test_get_issues_with_labels(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test getting issues with specific labels"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_issue1 = Mock()
        mock_issue1.number = 1
        mock_issue2 = Mock()
        mock_issue2.number = 2
        
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issues.return_value = [mock_issue1, mock_issue2]
        
        # Test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.get_issues_with_labels(["site-monitor", "bug"], state="open", limit=5)
        
        # Assertions
        mock_repo.get_issues.assert_called_once_with(state="open", labels=["site-monitor", "bug"])
        assert len(result) == 2
        assert result[0] == mock_issue1
        assert result[1] == mock_issue2
    
    @patch('src.clients.github_issue_creator.Github')
    def test_assign_issue(self, mock_github_class, mock_github_token, mock_repository_name):
        """Test issue assignment"""
        # Setup mocks
        mock_github_instance = Mock()
        mock_repo = Mock()
        mock_issue = Mock()
        
        mock_github_class.return_value = mock_github_instance
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue
        
        # Test
        creator = GitHubIssueCreator(mock_github_token, mock_repository_name)
        result = creator.assign_issue(123, ["user1", "user2"])
        
        # Assertions
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.add_to_assignees.assert_called_once_with("user1", "user2")
        assert result is True


@pytest.mark.integration
class TestGitHubOperationsIntegration:
    """Integration tests for GitHub operations (requires real API calls)"""
    
    @pytest.mark.skip(reason="Requires real GitHub token and repository")
    def test_real_issue_creation(self):
        """Test real issue creation (skipped by default)"""
        # This test would require real credentials and a test repository
        # It's marked as skip by default to avoid accidental API calls
        pass