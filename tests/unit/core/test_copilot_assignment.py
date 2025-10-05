"""
Unit tests for Copilot assignment detection functionality.

Tests the new methods added to GitHubIntegratedIssueProcessor and BatchProcessor
for identifying and processing issues assigned to GitHub Copilot.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.core.issue_processor import GitHubIntegratedIssueProcessor


@pytest.fixture
def mock_github_token():
    """Mock GitHub token."""
    return "mock_token"


@pytest.fixture
def mock_repo():
    """Mock repository name."""
    return "owner/repo"


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock()
    config.agent = Mock()
    config.agent.username = 'github-actions[bot]'
    config.agent.output_directory = 'study'
    config.agent.workflow_directory = 'docs/workflow/deliverables'
    config.agent.processing = Mock()
    config.agent.processing.default_timeout_minutes = 30
    config.agent.git = Mock()
    config.agent.git.branch_prefix = 'issue'
    config.agent.git.auto_push = True
    return config


@pytest.fixture
def mock_issue():
    """Create a mock GitHub issue."""
    issue = Mock()
    issue.number = 123
    issue.title = "Test Intelligence Analysis"
    issue.body = "Research target organization for intelligence gathering"
    # Create mock labels with name attribute
    site_monitor_label = Mock()
    site_monitor_label.name = 'site-monitor'
    intelligence_label = Mock()
    intelligence_label.name = 'intelligence'
    issue.labels = [site_monitor_label, intelligence_label]
    issue.assignee = Mock(login='github-copilot[bot]')
    issue.assignees = [Mock(login='github-copilot[bot]')]
    issue.created_at = datetime.now(timezone.utc)
    issue.updated_at = datetime.now(timezone.utc)
    issue.html_url = "https://github.com/owner/repo/issues/123"
    return issue


@pytest.fixture
def mock_non_copilot_issue():
    """Create a mock GitHub issue not assigned to Copilot."""
    issue = Mock()
    issue.number = 456
    issue.title = "Regular Issue"
    issue.body = "This is not a Copilot issue"
    issue.labels = [Mock(name='site-monitor')]
    issue.assignee = Mock(login='human-user')
    issue.assignees = [Mock(login='human-user')]
    issue.created_at = datetime.now(timezone.utc)
    issue.updated_at = datetime.now(timezone.utc)
    issue.html_url = "https://github.com/owner/repo/issues/456"
    return issue


class TestCopilotAssignmentDetection:
    """Test Copilot assignment detection methods."""
    
    @patch('src.core.issue_processor.GitManager')
    @patch('src.core.issue_processor.DeliverableGenerator')
    @patch('src.core.issue_processor.WorkflowMatcher')
    @patch('src.core.issue_processor.ConfigManager')
    @patch('src.clients.github_issue_creator.GitHubIssueCreator')
    def test_is_copilot_assigned_with_dict(self, mock_github_creator, mock_config_manager, mock_workflow, mock_deliverable, mock_git, mock_config):
        """Test is_copilot_assigned with dictionary input."""
        # Setup mocks
        mock_config_manager.load_config_with_env_substitution.return_value = mock_config
        mock_github_creator.return_value = Mock()
        
        # Mock GitHubIssueCreator to prevent GitHub API calls
        with patch('src.clients.github_issue_creator.Github') as mock_github_class:
            mock_github_class.return_value = Mock()
            processor = GitHubIntegratedIssueProcessor(
                github_token="mock_token",
                repository="owner/repo"
            )
            
            # Test Copilot assignment
            issue_data = {'assignee': 'github-copilot[bot]'}
            assert processor.is_copilot_assigned(issue_data) is True
            
            # Test non-Copilot assignment
            issue_data = {'assignee': 'human-user'}
            assert processor.is_copilot_assigned(issue_data) is False
            
            # Test no assignee
            issue_data = {'assignee': None}
            assert processor.is_copilot_assigned(issue_data) is False
            
            # Test other Copilot variants
            issue_data = {'assignee': 'copilot'}
            assert processor.is_copilot_assigned(issue_data) is True
            
            issue_data = {'assignee': 'github-actions[bot]'}
            assert processor.is_copilot_assigned(issue_data) is True
    
    @patch('src.core.issue_processor.ConfigManager')
    @patch('src.core.issue_processor.WorkflowMatcher')
    @patch('src.core.issue_processor.DeliverableGenerator')
    def test_is_copilot_assigned_with_object(self, mock_deliverable, mock_workflow, mock_config_manager, mock_config, mock_issue):
        """Test is_copilot_assigned with GitHub issue object."""
        mock_config_manager.load_config_with_env_substitution.return_value = mock_config
        
        # Mock GitHubIssueCreator to prevent GitHub API calls
        with patch('src.clients.github_issue_creator.Github') as mock_github_class:
            mock_github_class.return_value = Mock()
            processor = GitHubIntegratedIssueProcessor(
                github_token="mock_token",
                repository="owner/repo"
            )
            
            assert processor.is_copilot_assigned(mock_issue) is True
    
    @patch('src.core.issue_processor.ConfigManager')
    @patch('src.core.issue_processor.WorkflowMatcher')
    @patch('src.core.issue_processor.DeliverableGenerator')
    def test_should_process_copilot_issue(self, mock_deliverable, mock_workflow, mock_config_manager, mock_config, mock_issue):
        """Test _should_process_copilot_issue method."""
        mock_config_manager.load_config_with_env_substitution.return_value = mock_config
        
        # Mock GitHubIssueCreator to prevent GitHub API calls
        with patch('src.clients.github_issue_creator.Github') as mock_github_class:
            mock_github_class.return_value = Mock()
            processor = GitHubIntegratedIssueProcessor(
                github_token="mock_token",
                repository="owner/repo"
            )
            
            # Should process with intelligence label
            assert processor._should_process_copilot_issue(mock_issue) is True
            
            # Should process with content indicator in title/body
            mock_issue.labels = [Mock(name='site-monitor')]  # No intelligence label
            mock_issue.title = "Target Analysis Required"
            assert processor._should_process_copilot_issue(mock_issue) is True
            
            # Should not process without indicators
            mock_issue.labels = [Mock(name='bug')]  # No intelligence indicators
            mock_issue.title = "Bug fix needed"
            mock_issue.body = "Fix this bug"
            assert processor._should_process_copilot_issue(mock_issue) is False
    
    @patch('src.core.issue_processor.ConfigManager')
    @patch('src.core.issue_processor.WorkflowMatcher')
    @patch('src.core.issue_processor.DeliverableGenerator')
    def test_convert_issue_to_dict(self, mock_deliverable, mock_workflow, mock_config_manager, mock_config, mock_issue):
        """Test _convert_issue_to_dict method."""
        mock_config_manager.load_config_with_env_substitution.return_value = mock_config
        
        # Mock GitHubIssueCreator to prevent GitHub API calls
        with patch('src.clients.github_issue_creator.Github') as mock_github_class:
            mock_github_class.return_value = Mock()
            processor = GitHubIntegratedIssueProcessor(
                github_token="mock_token",
                repository="owner/repo"
            )
            
            result = processor._convert_issue_to_dict(mock_issue)
            
            assert result['number'] == 123
            assert result['title'] == "Test Intelligence Analysis"
            assert result['assignee'] == 'github-copilot[bot]'
            # Labels are converted from mock objects using .name attribute
            assert 'site-monitor' in result['labels']
            assert 'intelligence' in result['labels']
            assert 'github-copilot[bot]' in result['assignees']
            assert 'url' in result
    
    @patch('src.core.issue_processor.ConfigManager')
    @patch('src.core.issue_processor.WorkflowMatcher')
    @patch('src.core.issue_processor.DeliverableGenerator')
    def test_get_copilot_assigned_issues(self, mock_deliverable, mock_workflow, mock_config_manager, mock_config, mock_issue, mock_non_copilot_issue):
        """Test get_copilot_assigned_issues method."""
        mock_config_manager.load_config_with_env_substitution.return_value = mock_config
        
        # Mock GitHubIssueCreator to prevent GitHub API calls
        with patch('src.clients.github_issue_creator.Github') as mock_github_class:
            mock_github_class.return_value = Mock()
            
            processor = GitHubIntegratedIssueProcessor(
                github_token="mock_token",
                repository="owner/repo"
            )
            
            # Patch the method directly to return test data
            with patch.object(processor, '_should_process_copilot_issue', return_value=True):
                with patch.object(processor, '_convert_issue_to_dict', return_value={'number': 123, 'title': 'Test Issue'}):
                    # Mock repo.get_issues to return our mock_issue
                    processor.github.repo.get_issues = Mock(return_value=[mock_issue])
                    
                    issues = processor.get_copilot_assigned_issues()
                    
                    assert len(issues) == 1
                    assert issues[0]['number'] == 123
                    
                    # Test with limit
                    processor.github.repo.get_issues = Mock(return_value=[])  # Empty for limit test
                    issues = processor.get_copilot_assigned_issues(limit=0)
                    assert len(issues) == 0