"""
Unit tests for the WorkflowAssignmentAgent class.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import asdict

from src.agents.workflow_assignment_agent import (
    WorkflowAssignmentAgent, 
    AssignmentResult, 
    AssignmentAction
)
from src.workflow.workflow_matcher import WorkflowInfo


class TestWorkflowAssignmentAgent:
    """Test cases for WorkflowAssignmentAgent class"""
    
    @pytest.fixture
    def mock_github_creator(self):
        """Create a mock GitHubIssueCreator"""
        mock_creator = Mock()
        mock_creator.repo = Mock()
        return mock_creator
    
    @pytest.fixture
    def mock_workflow_matcher(self):
        """Create a mock WorkflowMatcher"""
        mock_matcher = Mock()
        mock_matcher.get_available_workflows.return_value = [
            WorkflowInfo(
                path="test_workflow.yaml",
                name="Test Workflow",
                description="A test workflow",
                version="1.0.0",
                trigger_labels=["test", "research"],
                deliverables=[{"name": "overview", "title": "Overview", "description": "Test deliverable", "required": True, "order": 1}],
                processing={},
                validation={},
                output={}
            )
        ]
        return mock_matcher
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file"""
        config_content = {
            'sites': [{'url': 'https://example.com', 'name': 'Example'}],
            'github': {'repository': 'owner/repo'},
            'search': {'api_key': 'test', 'search_engine_id': 'test'},
            'agent': {'username': 'test-agent'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            # Convert to YAML manually for simplicity
            import yaml
            yaml.dump(config_content, f)
            temp_config_path = f.name
        
        yield temp_config_path
        Path(temp_config_path).unlink()
    
    @pytest.fixture
    def agent(self, mock_github_creator, mock_workflow_matcher, temp_config_file):
        """Create a WorkflowAssignmentAgent instance with mocked dependencies"""
        with patch('src.agents.workflow_assignment_agent.GitHubIssueCreator', return_value=mock_github_creator), \
             patch('src.agents.workflow_assignment_agent.WorkflowMatcher', return_value=mock_workflow_matcher), \
             patch('src.agents.workflow_assignment_agent.ConfigManager.load_config') as mock_load_config:
            
            # Mock config
            mock_config = Mock()
            mock_config.agent = Mock()
            mock_config.agent.username = 'test-agent'
            mock_load_config.return_value = mock_config
            
            agent = WorkflowAssignmentAgent(
                github_token='fake_token',
                repo_name='owner/repo',
                config_path=temp_config_file
            )
            
            return agent
    
    def test_init_successful(self, agent):
        """Test successful initialization"""
        assert agent.agent_username == 'test-agent'
        assert agent.repo_name == 'owner/repo'
        assert agent.SKIP_LABELS == {'feature', 'needs clarification'}
        assert agent.NEEDS_CLARIFICATION_LABEL == 'needs clarification'
    
    def test_init_config_failure(self):
        """Test initialization with config failure"""
        with patch('src.agents.workflow_assignment_agent.GitHubIssueCreator'), \
             patch('src.agents.workflow_assignment_agent.WorkflowMatcher'), \
             patch('src.agents.workflow_assignment_agent.ConfigManager.load_config', side_effect=Exception("Config error")):
            
            agent = WorkflowAssignmentAgent(
                github_token='fake_token',
                repo_name='owner/repo'
            )
            
            assert agent.agent_username == 'github-actions[bot]'
    
    def test_get_unassigned_site_monitor_issues(self, agent):
        """Test getting unassigned site-monitor issues"""
        # Mock GitHub issues
        mock_issue1 = Mock()
        mock_issue1.number = 1
        mock_issue1.title = "Issue 1"
        mock_issue1.body = "Description 1"
        mock_issue1.assignee = None
        
        # Set up labels with proper name attribute
        label1 = Mock()
        label1.name = 'site-monitor'
        label2 = Mock()
        label2.name = 'research'
        mock_issue1.labels = [label1, label2]
        
        mock_issue1.created_at = None
        mock_issue1.updated_at = None
        mock_issue1.html_url = "https://github.com/owner/repo/issues/1"
        mock_issue1.user = Mock(login='user1')
        
        mock_issue2 = Mock()
        mock_issue2.number = 2
        mock_issue2.title = "Issue 2"
        mock_issue2.body = "Description 2"
        mock_issue2.assignee = Mock(login='someone')  # This should be filtered out
        
        label3 = Mock()
        label3.name = 'site-monitor'
        label4 = Mock()
        label4.name = 'bug'
        mock_issue2.labels = [label3, label4]
        
        mock_issue2.created_at = None
        mock_issue2.updated_at = None
        mock_issue2.html_url = "https://github.com/owner/repo/issues/2"
        mock_issue2.user = Mock(login='user2')
        
        mock_issue3 = Mock()
        mock_issue3.number = 3
        mock_issue3.title = "Issue 3"
        mock_issue3.body = "Description 3"
        mock_issue3.assignee = None
        
        # This one has feature label, should be filtered out
        label5 = Mock()
        label5.name = 'site-monitor'
        label6 = Mock()
        label6.name = 'feature'
        mock_issue3.labels = [label5, label6]
        
        mock_issue3.created_at = None
        mock_issue3.updated_at = None
        mock_issue3.html_url = "https://github.com/owner/repo/issues/3"
        mock_issue3.user = Mock(login='user3')
        
        agent.github.get_issues_with_labels.return_value = [mock_issue1, mock_issue2, mock_issue3]
        
        issues = agent.get_unassigned_site_monitor_issues()
        
        assert len(issues) == 1  # Only issue 1 should be returned
        assert issues[0]['number'] == 1
        assert issues[0]['title'] == "Issue 1"
        assert set(issues[0]['labels']) == {'site-monitor', 'research'}
        assert issues[0]['assignee'] is None
        
        agent.github.get_issues_with_labels.assert_called_once_with(['site-monitor'], state='open')
    
    def test_get_unassigned_site_monitor_issues_with_limit(self, agent):
        """Test getting issues with limit"""
        # Create more mock issues than the limit
        mock_issues = []
        for i in range(5):
            mock_issue = Mock()
            mock_issue.number = i + 1
            mock_issue.title = f"Issue {i + 1}"
            mock_issue.body = f"Description {i + 1}"
            mock_issue.assignee = None
            
            # Set up proper label mocks
            label = Mock()
            label.name = 'site-monitor'
            mock_issue.labels = [label]
            
            mock_issue.created_at = None
            mock_issue.updated_at = None
            mock_issue.html_url = f"https://github.com/owner/repo/issues/{i + 1}"
            mock_issue.user = Mock(login=f'user{i + 1}')
            mock_issues.append(mock_issue)
        
        agent.github.get_issues_with_labels.return_value = mock_issues
        
        issues = agent.get_unassigned_site_monitor_issues(limit=3)
        
        assert len(issues) == 3
        assert [issue['number'] for issue in issues] == [1, 2, 3]
    
    def test_analyze_issue_for_workflow(self, agent):
        """Test analyzing issue for workflow match"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'research']
        }
        
        # Mock workflow matcher
        mock_workflow = Mock()
        mock_workflow.name = "Research Workflow"
        agent.workflow_matcher.get_best_workflow_match.return_value = (mock_workflow, "Selected workflow: Research Workflow")
        
        workflow, message = agent.analyze_issue_for_workflow(issue_data)
        
        assert workflow == mock_workflow
        assert "Selected workflow" in message
        agent.workflow_matcher.get_best_workflow_match.assert_called_once_with(['site-monitor', 'research'])
    
    def test_analyze_issue_for_workflow_no_match(self, agent):
        """Test analyzing issue with no workflow match"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'unknown']
        }
        
        agent.workflow_matcher.get_best_workflow_match.return_value = (None, "No workflows match the current labels")
        
        workflow, message = agent.analyze_issue_for_workflow(issue_data)
        
        assert workflow is None
        assert "No workflows match" in message
    
    def test_assign_workflow_to_issue(self, agent):
        """Test assigning workflow to issue"""
        # Mock workflow
        mock_workflow = Mock()
        mock_workflow.name = "Test Workflow"
        mock_workflow.trigger_labels = ['test', 'analysis']
        mock_workflow.processing = {}
        
        # Mock GitHub issue
        mock_issue = Mock()
        monitor_label = Mock()
        monitor_label.name = 'monitor::triage'
        state_label = Mock()
        state_label.name = 'state::discovery'
        site_label = Mock()
        site_label.name = 'site-monitor'
        mock_issue.labels = [monitor_label, state_label, site_label]
        mock_issue.body = "Existing body"
        mock_issue.edit = Mock()
        mock_issue.create_comment = Mock()
        
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.assign_workflow_to_issue(1, mock_workflow, dry_run=False)
        
        assert result.issue_number == 1
        assert result.action == AssignmentAction.ASSIGN_WORKFLOW
        assert result.workflow_name == "Test Workflow"
        assert set(result.labels_added) == {'test', 'analysis', 'workflow::test-workflow', 'state::assigned'}
        assert set(result.labels_removed) == {'monitor::triage', 'state::discovery'}

        agent.github.repo.get_issue.assert_called_once_with(1)
        mock_issue.edit.assert_called_once()
        edit_kwargs = mock_issue.edit.call_args.kwargs
        assert 'labels' in edit_kwargs
        assert set(edit_kwargs['labels']) == {
            'analysis',
            'site-monitor',
            'state::assigned',
            'test',
            'workflow::test-workflow',
        }
        assert 'body' in edit_kwargs
        assert 'AI Assessment' in edit_kwargs['body']
        mock_issue.create_comment.assert_called_once()
        comment_text = mock_issue.create_comment.call_args[0][0]
        assert 'Fallback Mode' in comment_text
        assert 'Labels Removed' in comment_text
    
    def test_assign_workflow_to_issue_dry_run(self, agent):
        """Test assigning workflow in dry run mode"""
        mock_workflow = Mock()
        mock_workflow.name = "Test Workflow"
        mock_workflow.trigger_labels = ['test', 'analysis']
        mock_workflow.processing = {}
        
        mock_issue = Mock()
        monitor_label = Mock()
        monitor_label.name = 'monitor::triage'
        state_label = Mock()
        state_label.name = 'state::discovery'
        site_label = Mock()
        site_label.name = 'site-monitor'
        mock_issue.labels = [monitor_label, state_label, site_label]
        mock_issue.body = "Existing body"
        mock_issue.edit = Mock()
        mock_issue.create_comment = Mock()
        
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.assign_workflow_to_issue(1, mock_workflow, dry_run=True)
        
        assert result.action == AssignmentAction.ASSIGN_WORKFLOW
        assert set(result.labels_added) == {'test', 'analysis', 'workflow::test-workflow', 'state::assigned'}
        assert set(result.labels_removed) == {'monitor::triage', 'state::discovery'}
        # Verify no GitHub operations in dry run
        mock_issue.edit.assert_not_called()
        mock_issue.create_comment.assert_not_called()
    
    def test_request_clarification_for_issue(self, agent):
        """Test requesting clarification for issue"""
        mock_issue = Mock()
        label = Mock()
        label.name = 'site-monitor'
        mock_issue.labels = [label]
        mock_issue.add_to_labels = Mock()
        mock_issue.create_comment = Mock()
        
        agent.github.repo.get_issue.return_value = mock_issue
        agent.workflow_matcher.get_workflow_suggestions.return_value = ['research', 'analysis', 'technical']
        
        result = agent.request_clarification_for_issue(1, "No clear workflow match", dry_run=False)
        
        assert result.issue_number == 1
        assert result.action == AssignmentAction.REQUEST_CLARIFICATION
        assert 'needs clarification' in result.labels_added
        
        # Verify GitHub operations
        mock_issue.add_to_labels.assert_called_once_with('needs clarification')
        mock_issue.create_comment.assert_called_once()
        
        # Check comment contains suggestions
        comment_call = mock_issue.create_comment.call_args[0][0]
        assert 'research' in comment_call
        assert 'analysis' in comment_call
    
    def test_request_clarification_dry_run(self, agent):
        """Test requesting clarification in dry run mode"""
        mock_issue = Mock()
        label = Mock()
        label.name = 'site-monitor'
        mock_issue.labels = [label]
        
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.request_clarification_for_issue(1, "No clear workflow match", dry_run=True)
        
        assert result.action == AssignmentAction.REQUEST_CLARIFICATION
        # Verify no GitHub operations in dry run
        mock_issue.add_to_labels.assert_not_called()
        mock_issue.create_comment.assert_not_called()
    
    def test_process_issue_assignment_skip_feature(self, agent):
        """Test processing issue that should be skipped (feature label)"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'feature']
        }
        
        result = agent.process_issue_assignment(issue_data)
        
        assert result.issue_number == 1
        assert result.action == AssignmentAction.SKIP_FEATURE
        assert "Skipping issue with 'feature' label" in result.message
    
    def test_process_issue_assignment_skip_needs_clarification(self, agent):
        """Test processing issue that should be skipped (needs clarification label)"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'needs clarification']
        }
        
        result = agent.process_issue_assignment(issue_data)
        
        assert result.issue_number == 1
        assert result.action == AssignmentAction.SKIP_NEEDS_CLARIFICATION
    
    def test_process_issue_assignment_workflow_match(self, agent):
        """Test processing issue with successful workflow match"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'research']
        }
        
        # Mock workflow analysis
        mock_workflow = Mock()
        mock_workflow.name = "Research Workflow"
        mock_workflow.trigger_labels = ['research']
        mock_workflow.processing = {}
        
        agent.workflow_matcher.get_best_workflow_match.return_value = (mock_workflow, "Matched")
        
        # Mock GitHub operations
        mock_issue = Mock()
        monitor_label = Mock()
        monitor_label.name = 'monitor::triage'
        state_label = Mock()
        state_label.name = 'state::discovery'
        site_label = Mock()
        site_label.name = 'site-monitor'
        mock_issue.labels = [monitor_label, state_label, site_label]
        mock_issue.body = "Existing body"
        mock_issue.edit = Mock()
        mock_issue.create_comment = Mock()
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.process_issue_assignment(issue_data, dry_run=False)
        
        assert result.action == AssignmentAction.ASSIGN_WORKFLOW
        assert result.workflow_name == "Research Workflow"
        mock_issue.edit.assert_called_once()
        mock_issue.create_comment.assert_called_once()
    
    def test_process_issue_assignment_no_workflow_match(self, agent):
        """Test processing issue with no workflow match"""
        issue_data = {
            'number': 1,
            'labels': ['site-monitor', 'unknown']
        }
        
        # Mock no workflow match
        agent.workflow_matcher.get_best_workflow_match.return_value = (None, "No matches found")
        agent.workflow_matcher.get_workflow_suggestions.return_value = ['research', 'technical']
        
        # Mock GitHub operations  
        mock_issue = Mock()
        label = Mock()
        label.name = 'site-monitor'
        mock_issue.labels = [label]
        mock_issue.add_to_labels = Mock()
        mock_issue.create_comment = Mock()
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.process_issue_assignment(issue_data, dry_run=False)
        
        assert result.action == AssignmentAction.REQUEST_CLARIFICATION
    
    def test_process_issues_batch(self, agent):
        """Test processing a batch of issues"""
        # Mock getting issues
        mock_issues = [
            {'number': 1, 'labels': ['site-monitor', 'research']},
            {'number': 2, 'labels': ['site-monitor', 'feature']},  # Should be skipped
            {'number': 3, 'labels': ['site-monitor', 'unknown']},  # Should request clarification
        ]
        
        agent.get_unassigned_site_monitor_issues = Mock(return_value=mock_issues)
        
        # Mock workflow matching
        mock_workflow = Mock()
        mock_workflow.name = "Research Workflow"
        mock_workflow.trigger_labels = ['research']
        
        def mock_workflow_match(labels):
            if 'research' in labels:
                return mock_workflow, "Matched"
            return None, "No match"
        
        agent.workflow_matcher.get_best_workflow_match.side_effect = mock_workflow_match
        agent.workflow_matcher.get_workflow_suggestions.return_value = ['research', 'technical']
        
        # Mock GitHub operations
        mock_issue = Mock()
        label = Mock()
        label.name = 'site-monitor'
        mock_issue.labels = [label]
        mock_issue.add_to_labels = Mock()
        mock_issue.create_comment = Mock()
        agent.github.repo.get_issue.return_value = mock_issue
        
        result = agent.process_issues_batch(dry_run=True)
        
        assert result['total_issues'] == 3
        assert result['processed'] == 2  # One skipped due to feature label
        assert len(result['results']) == 3
        
        # Check statistics
        stats = result['statistics']
        assert stats[AssignmentAction.SKIP_FEATURE.value] == 1
        assert stats[AssignmentAction.ASSIGN_WORKFLOW.value] == 1
        assert stats[AssignmentAction.REQUEST_CLARIFICATION.value] == 1
    
    def test_process_issues_batch_no_issues(self, agent):
        """Test processing batch when no issues found"""
        agent.get_unassigned_site_monitor_issues = Mock(return_value=[])
        
        result = agent.process_issues_batch()
        
        assert result['total_issues'] == 0
        assert result['processed'] == 0
        assert len(result['results']) == 0
    
    def test_get_assignment_statistics(self, agent):
        """Test getting assignment statistics"""
        # Mock GitHub issues
        mock_issues = []
        
        # Unassigned issue
        mock_issue1 = Mock()
        mock_issue1.assignee = None
        label1 = Mock()
        label1.name = 'site-monitor'
        label2 = Mock()
        label2.name = 'research'
        mock_issue1.labels = [label1, label2]
        mock_issues.append(mock_issue1)
        
        # Assigned issue
        mock_issue2 = Mock()
        mock_issue2.assignee = Mock(login='user')
        label3 = Mock()
        label3.name = 'site-monitor'
        label4 = Mock()
        label4.name = 'technical'
        mock_issue2.labels = [label3, label4]
        mock_issues.append(mock_issue2)
        
        # Issue needing clarification
        mock_issue3 = Mock()
        mock_issue3.assignee = None
        label5 = Mock()
        label5.name = 'site-monitor'
        label6 = Mock()
        label6.name = 'needs clarification'
        mock_issue3.labels = [label5, label6]
        mock_issues.append(mock_issue3)
        
        agent.github.get_issues_with_labels.return_value = mock_issues
        
        # Mock available workflows
        research_workflow = Mock(trigger_labels=['research'])
        research_workflow.name = "Research Workflow"
        
        technical_workflow = Mock(trigger_labels=['technical'])
        technical_workflow.name = "Technical Workflow"
        
        mock_workflows = [research_workflow, technical_workflow]
        agent.workflow_matcher.get_available_workflows.return_value = mock_workflows
        
        stats = agent.get_assignment_statistics()
        
        assert stats['total_site_monitor_issues'] == 3
        assert stats['unassigned'] == 2
        assert stats['assigned'] == 1
        assert stats['needs_clarification'] == 1
        
        # Verify workflow assignments
        assert stats['workflow_breakdown']['Research Workflow'] == 1
        assert stats['workflow_breakdown']['Technical Workflow'] == 1
            
        assert stats['label_distribution']['site-monitor'] == 3
        assert stats['label_distribution']['research'] == 1


class TestAssignmentResult:
    """Test cases for AssignmentResult dataclass"""
    
    def test_assignment_result_initialization(self):
        """Test AssignmentResult initialization with defaults"""
        result = AssignmentResult(
            issue_number=1,
            action=AssignmentAction.ASSIGN_WORKFLOW
        )
        
        assert result.issue_number == 1
        assert result.action == AssignmentAction.ASSIGN_WORKFLOW
        assert result.workflow_name is None
        assert result.message == ""
        assert result.labels_added == []
        assert result.labels_removed == []
    
    def test_assignment_result_with_data(self):
        """Test AssignmentResult with full data"""
        result = AssignmentResult(
            issue_number=5,
            action=AssignmentAction.ASSIGN_WORKFLOW,
            workflow_name="Research Workflow",
            message="Successfully assigned workflow",
            labels_added=['research', 'analysis'],
            labels_removed=['needs-clarification']
        )
        
        assert result.issue_number == 5
        assert result.action == AssignmentAction.ASSIGN_WORKFLOW
        assert result.workflow_name == "Research Workflow"
        assert result.message == "Successfully assigned workflow"
        assert result.labels_added == ['research', 'analysis']
        assert result.labels_removed == ['needs-clarification']


class TestAssignmentAction:
    """Test cases for AssignmentAction enum"""
    
    def test_assignment_action_values(self):
        """Test AssignmentAction enum values"""
        assert AssignmentAction.SKIP_FEATURE.value == "skip_feature"
        assert AssignmentAction.SKIP_NEEDS_CLARIFICATION.value == "skip_needs_clarification"
        assert AssignmentAction.SKIP_ALREADY_ASSIGNED.value == "skip_already_assigned"
        assert AssignmentAction.ASSIGN_WORKFLOW.value == "assign_workflow"
        assert AssignmentAction.REQUEST_CLARIFICATION.value == "request_clarification"
        assert AssignmentAction.ERROR.value == "error"