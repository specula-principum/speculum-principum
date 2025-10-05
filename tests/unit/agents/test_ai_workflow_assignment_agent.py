"""
Test AI-Enhanced Workflow Assignment Agent

These tests validate the AI workflow assignment system while mocking
external API calls to ensure reliable testing.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.agents.ai_workflow_assignment_agent import (
    AIWorkflowAssignmentAgent,
    GitHubModelsClient, 
    ContentAnalysis
)
from src.workflow.workflow_matcher import WorkflowInfo


@pytest.fixture
def mock_github_token():
    """Mock GitHub token for testing"""
    return "ghp_test_token_123"


@pytest.fixture
def mock_repo_name():
    """Mock repository name for testing"""
    return "test-owner/test-repo"


@pytest.fixture
def sample_workflows():
    """Sample workflow definitions for testing"""
    return [
        WorkflowInfo(
            path="/test/research.yaml",
            name="Research Analysis", 
            description="Research workflow",
            version="1.0.0",
            trigger_labels=["research", "analysis"],
            deliverables=[{"name": "overview"}],
            processing={},
            validation={},
            output={}
        ),
        WorkflowInfo(
            path="/test/technical.yaml",
            name="Technical Review",
            description="Technical workflow", 
            version="1.0.0",
            trigger_labels=["technical-review", "code-review"],
            deliverables=[{"name": "review"}],
            processing={},
            validation={},
            output={}
        )
    ]


@pytest.fixture
def sample_issue_data():
    """Sample issue data for testing"""
    return {
        'number': 123,
        'title': 'Analyze VR market trends and competition',
        'body': '''We need to conduct comprehensive market research on the VR industry, 
                  including competitor analysis, market size, growth projections, 
                  and key technology trends. This research will inform our 
                  strategic planning for Q2 2025.''',
        'labels': ['site-monitor', 'research'],
        'assignee': None,
        'created_at': '2025-09-25T10:00:00Z',
        'updated_at': '2025-09-25T10:00:00Z',
        'url': 'https://github.com/test/repo/issues/123',
        'user': 'test-user'
    }


@pytest.fixture
def mock_ai_response():
    """Mock AI response for testing"""
    return {
        "summary": "Market research request for VR industry analysis and strategic planning",
        "key_topics": ["VR", "market research", "competitive analysis", "strategic planning"],
        "suggested_workflows": ["Research Analysis"],
        "confidence_scores": {"Research Analysis": 0.85},
        "technical_indicators": ["market analysis", "research methodology"],
        "urgency_level": "medium",
        "content_type": "research"
    }


class TestGitHubModelsClient:
    """Test GitHub Models API client"""
    
    def test_client_initialization(self, mock_github_token):
        """Test client initializes correctly"""
        client = GitHubModelsClient(mock_github_token, model="gpt-4o")
        
        assert client.token == mock_github_token
        assert client.model == "gpt-4o"
        assert client.BASE_URL == "https://models.inference.ai.github.com"
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == f"Bearer {mock_github_token}"
    
    @patch('requests.post')
    def test_successful_api_call(self, mock_post, mock_github_token, sample_workflows, mock_ai_response):
        """Test successful API call and response parsing"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": str(mock_ai_response).replace("'", '"')
                }
            }]
        }
        mock_post.return_value = mock_response
        
        client = GitHubModelsClient(mock_github_token)
        
        # Test analysis
        result = client.analyze_issue_content(
            title="Test Issue",
            body="Test body",
            labels=["test"],
            available_workflows=sample_workflows
        )
        
        # Verify API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == f"{client.BASE_URL}/v1/chat/completions"
        
        # Verify response parsing
        assert isinstance(result, ContentAnalysis)
        assert result.summary == mock_ai_response["summary"]
        assert result.suggested_workflows == ["Research Analysis"]
        assert result.confidence_scores["Research Analysis"] == 0.85
    
    @patch('requests.post')
    def test_api_failure_fallback(self, mock_post, mock_github_token, sample_workflows):
        """Test API failure handling"""
        # Mock API failure
        mock_post.side_effect = Exception("API Error")
        
        client = GitHubModelsClient(mock_github_token)
        
        result = client.analyze_issue_content(
            title="Test Issue",
            body="Test body", 
            labels=["test"],
            available_workflows=sample_workflows
        )
        
        # Should return fallback analysis
        assert isinstance(result, ContentAnalysis)
        assert result.summary == "Failed to analyze with AI"
        assert result.suggested_workflows == []
        assert result.confidence_scores == {}


class TestAIWorkflowAssignmentAgent:
    """Test AI workflow assignment agent"""

    def test_render_ai_assessment_section_includes_rationale(self):
        analysis = ContentAnalysis(
            summary="Synthesize threat landscape for Q4.",
            key_topics=["threat intelligence", "strategic outlook"],
            suggested_workflows=["Research Analysis"],
            confidence_scores={"Research Analysis": 0.92},
            technical_indicators=["emerging threat", "fusion required"],
            urgency_level="high",
            content_type="research",
        )

        section = AIWorkflowAssignmentAgent._render_ai_assessment_section(
            analysis,
            assigned_workflow="Research Analysis",
        )

        assert "Confidence: 92%" in section
        assert "Rationale: Matches topics" in section
        assert "(assigned)" in section
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_agent_initialization_ai_enabled(self, mock_matcher, mock_github, mock_github_token, mock_repo_name):
        """Test agent initializes with AI enabled"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = []
        
        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )
        
        assert agent.enable_ai is True
        assert agent.ai_client is not None
        assert isinstance(agent.ai_client, GitHubModelsClient)
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher') 
    def test_agent_initialization_ai_disabled(self, mock_matcher, mock_github, mock_github_token, mock_repo_name):
        """Test agent initializes with AI disabled"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = []
        
        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=False
        )
        
        assert agent.enable_ai is False
        assert agent.ai_client is None
    
    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'})
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_analyze_issue_with_ai_success(self, mock_matcher, mock_github, mock_github_token, mock_repo_name,
                                          sample_workflows, sample_issue_data, mock_ai_response):
        """Test successful AI issue analysis"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = sample_workflows
        mock_matcher.return_value.find_matching_workflows.return_value = [sample_workflows[0]]

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )

        # Mock AI client response
        mock_analysis = ContentAnalysis(
            summary=mock_ai_response["summary"],
            key_topics=mock_ai_response["key_topics"],
            suggested_workflows=mock_ai_response["suggested_workflows"],
            confidence_scores=mock_ai_response["confidence_scores"],
            technical_indicators=mock_ai_response["technical_indicators"],
            urgency_level=mock_ai_response["urgency_level"],
            content_type=mock_ai_response["content_type"]
        )

        with patch.object(agent.ai_client, 'analyze_issue_content', return_value=mock_analysis):
            workflow, analysis, message = agent.analyze_issue_with_ai(sample_issue_data)        # Verify high confidence workflow assignment
        assert workflow is not None
        assert workflow.name == "Research Analysis"
        assert analysis.summary == mock_ai_response["summary"]
        assert "Research Analysis" in message
    
    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'})
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_analyze_issue_ai_failure_raises_error(self, mock_matcher, mock_github, mock_github_token,
                                                  mock_repo_name, sample_workflows, sample_issue_data):
        """Test AI failure raises RuntimeError (no fallback)"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = sample_workflows

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )

        # Mock AI client failure
        with patch.object(agent.ai_client, 'analyze_issue_content', side_effect=Exception("AI Error")):
            with pytest.raises(RuntimeError, match="AI workflow assignment failed and no fallback is available"):
                agent.analyze_issue_with_ai(sample_issue_data)
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_process_issue_with_ai_high_confidence(self, mock_matcher, mock_github, mock_github_token,
                                                  mock_repo_name, sample_workflows, sample_issue_data):
        """Test processing issue with high confidence AI analysis"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = sample_workflows
        
        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )
        
        # Mock high confidence analysis
        mock_analysis = ContentAnalysis(
            summary="High confidence research request",
            key_topics=["research"],
            suggested_workflows=["Research Analysis"],
            confidence_scores={"Research Analysis": 0.9},
            technical_indicators=[],
            urgency_level="medium",
            content_type="research"
        )
        
        with patch.object(agent, 'analyze_issue_with_ai', return_value=(sample_workflows[0], mock_analysis, "High confidence")):
            result = agent.process_issue_with_ai(sample_issue_data, dry_run=True)
        
        # Verify auto assignment
        assert result['action_taken'] == 'auto_assigned'
        assert result['assigned_workflow'] == 'Research Analysis'
        assert result['issue_number'] == 123
        assert 'ai_analysis' in result
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')  
    def test_confidence_threshold_configuration(self, mock_matcher, mock_github, mock_github_token, mock_repo_name):
        """Test confidence threshold configuration"""
        # Mock workflow matcher
        mock_matcher.return_value.get_available_workflows.return_value = []
        
        # Test with custom thresholds
        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )
        
        # Should use default thresholds
        assert agent.HIGH_CONFIDENCE_THRESHOLD == 0.8
        assert agent.MEDIUM_CONFIDENCE_THRESHOLD == 0.6

    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_process_issues_batch_emits_telemetry(
        self,
        mock_matcher,
        mock_github,
        mock_github_token,
        mock_repo_name,
    ) -> None:
        """Telemetry publishers receive batch lifecycle events."""

        mock_matcher.return_value.get_available_workflows.return_value = []

        events: list[dict[str, Any]] = []

        def publisher(event: dict[str, Any]) -> None:
            events.append(event)

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=False,
            telemetry_publishers=[publisher],
        )

        issue_payload = {'number': 321}
        mock_result = {
            'issue_number': 321,
            'action_taken': 'auto_assigned',
            'assigned_workflow': 'Research Analysis',
            'labels_added': ['workflow::research-analysis'],
            'dry_run': True,
            'ai_analysis': {
                'summary': 'High confidence assignment',
                'suggested_workflows': ['Research Analysis'],
                'confidence_scores': {'Research Analysis': 0.92},
            },
            'message': 'High confidence assignment',
        }

        with patch.object(agent, 'get_unassigned_site_monitor_issues', return_value=[issue_payload]):
            with patch.object(agent, 'process_issue_with_ai', return_value=mock_result):
                with patch('time.sleep', return_value=None):
                    result = agent.process_issues_batch(limit=1, dry_run=True)

        assert result['total_issues'] == 1
        assert result['processed'] == 1
        assert len(events) == 3

        event_types = [event['event_type'] for event in events]
        assert event_types == [
            'workflow_assignment.batch_start',
            'workflow_assignment.issue_result',
            'workflow_assignment.batch_summary',
        ]

        issue_event = events[1]
        assert issue_event['issue_number'] == 321
        assert issue_event['action_taken'] == 'auto_assigned'
        assert issue_event['ai_summary'] == 'High confidence assignment'
        assert issue_event['suggested_workflows'] == ['Research Analysis']
        assert issue_event['confidence_scores']['Research Analysis'] == pytest.approx(0.92)
        assert issue_event['assignment_mode'] == 'ai'

        summary_event = events[-1]
        assert summary_event['processed'] == 1
        assert summary_event['status'] == 'success'
        assert summary_event['assignment_mode'] == 'ai'


class TestIntegration:
    """Integration tests for the complete AI workflow assignment system"""
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_end_to_end_ai_assignment_dry_run(self, mock_matcher, mock_github, mock_github_token,
                                             mock_repo_name, sample_workflows, sample_issue_data):
        """Test complete end-to-end AI assignment flow in dry-run mode"""
        # Setup mocks
        mock_matcher.return_value.get_available_workflows.return_value = sample_workflows
        mock_github.return_value.get_issues_with_labels.return_value = []
        
        # Mock issue objects
        mock_issue = Mock()
        mock_issue.labels = [Mock(name='site-monitor'), Mock(name='automated')]
        mock_issue.assignee = None
        mock_github.return_value.get_issues_with_labels.return_value = [mock_issue]
        
        # Mock repo get_issue
        mock_repo_issue = Mock()
        mock_repo_issue.labels = [Mock(name='site-monitor'), Mock(name='automated')]
        mock_github.return_value.repo.get_issue.return_value = mock_repo_issue
        
        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )
        
        # Override get_unassigned_site_monitor_issues to return our test data
        with patch.object(agent, 'get_unassigned_site_monitor_issues', return_value=[sample_issue_data]):
            # Mock AI analysis to return high confidence
            mock_analysis = ContentAnalysis(
                summary="Research workflow needed",
                key_topics=["research"],
                suggested_workflows=["Research Analysis"],
                confidence_scores={"Research Analysis": 0.85},
                technical_indicators=[],
                urgency_level="medium", 
                content_type="research"
            )
            
            with patch.object(agent, 'analyze_issue_with_ai', return_value=(sample_workflows[0], mock_analysis, "High confidence")):
                result = agent.process_issues_batch(limit=1, dry_run=True)
        
        # Verify results
        assert result['total_issues'] == 1
        assert result['processed'] == 1
        assert result['statistics']['auto_assigned'] == 1
        assert len(result['results']) == 1
        
        issue_result = result['results'][0]
        assert issue_result['issue_number'] == 123
        assert issue_result['action_taken'] == 'auto_assigned'
        assert issue_result['assigned_workflow'] == 'Research Analysis'
        assert issue_result['dry_run'] is True


if __name__ == '__main__':
    pytest.main([__file__])