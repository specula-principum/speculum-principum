"""
Simplified unit tests for Copilot assignment detection functionality.

Tests the new methods added to GitHubIntegratedIssueProcessor for
identifying issues assigned to GitHub Copilot.
"""

# pylint: disable=protected-access

from unittest.mock import Mock

from src.core.issue_processor import GitHubIntegratedIssueProcessor


class TestCopilotAssignmentLogic:
    """Test core Copilot assignment logic without complex initialization."""

    def test_is_copilot_assigned_with_dict(self):
        """Test is_copilot_assigned with dictionary input."""
        processor = GitHubIntegratedIssueProcessor.__new__(GitHubIntegratedIssueProcessor)

        test_cases = [
            ({'assignee': 'github-copilot[bot]'}, True),
            ({'assignee': 'copilot'}, True),
            ({'assignee': 'github-actions[bot]'}, True),
            ({'assignee': 'human-user'}, False),
            ({'assignee': None}, False),
            ({}, False),
        ]

        for issue_data, expected in test_cases:
            result = processor.is_copilot_assigned(issue_data)
            assert result == expected, f"Failed for {issue_data}: expected {expected}, got {result}"

    def test_is_copilot_assigned_with_object(self):
        """Test is_copilot_assigned with GitHub issue object."""
        processor = GitHubIntegratedIssueProcessor.__new__(GitHubIntegratedIssueProcessor)

        mock_issue = Mock()
        mock_issue.assignee = Mock()
        mock_issue.assignee.login = 'github-copilot[bot]'

        result = processor.is_copilot_assigned(mock_issue)
        assert result is True

        mock_issue.assignee.login = 'human-user'
        result = processor.is_copilot_assigned(mock_issue)
        assert result is False

        mock_issue.assignee = None
        result = processor.is_copilot_assigned(mock_issue)
        assert result is False

    def test_should_process_copilot_issue(self):
        """Test _should_process_copilot_issue method."""
        processor = GitHubIntegratedIssueProcessor.__new__(GitHubIntegratedIssueProcessor)

        mock_label_site_monitor = Mock()
        mock_label_site_monitor.name = 'site-monitor'
        mock_label_intelligence = Mock()
        mock_label_intelligence.name = 'intelligence'

        mock_issue = Mock()
        mock_issue.labels = [mock_label_site_monitor, mock_label_intelligence]
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test body"

        assert processor._should_process_copilot_issue(mock_issue) is True

        mock_label_site_monitor = Mock()
        mock_label_site_monitor.name = 'site-monitor'
        mock_issue.labels = [mock_label_site_monitor]
        mock_issue.title = "Target Analysis Required"
        mock_issue.body = "Analysis needed"

        assert processor._should_process_copilot_issue(mock_issue) is True

        mock_label_bug = Mock()
        mock_label_bug.name = 'bug'
        mock_issue.labels = [mock_label_bug]
        mock_issue.title = "Bug fix needed"
        mock_issue.body = "Fix this bug"

        assert processor._should_process_copilot_issue(mock_issue) is False

    def test_convert_issue_to_dict(self):
        """Test _convert_issue_to_dict method."""
        processor = GitHubIntegratedIssueProcessor.__new__(GitHubIntegratedIssueProcessor)

        mock_label_site_monitor = Mock()
        mock_label_site_monitor.name = 'site-monitor'
        mock_label_intelligence = Mock()
        mock_label_intelligence.name = 'intelligence'

        mock_assignee = Mock()
        mock_assignee.login = 'github-copilot[bot]'

        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Intelligence Analysis"
        mock_issue.body = "Research target organization"
        mock_issue.labels = [mock_label_site_monitor, mock_label_intelligence]
        mock_issue.assignees = [mock_assignee]
        mock_issue.assignee = mock_assignee
        mock_issue.created_at = Mock()
        mock_issue.created_at.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_issue.updated_at = Mock()
        mock_issue.updated_at.isoformat.return_value = "2023-01-01T01:00:00Z"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"

        result = processor._convert_issue_to_dict(mock_issue)

        expected = {
            'number': 123,
            'title': "Test Intelligence Analysis",
            'body': "Research target organization",
            'labels': ['site-monitor', 'intelligence'],
            'assignees': ['github-copilot[bot]'],
            'assignee': 'github-copilot[bot]',
            'created_at': "2023-01-01T00:00:00Z",
            'updated_at': "2023-01-01T01:00:00Z",
            'url': "https://github.com/owner/repo/issues/123"
        }

        assert result == expected