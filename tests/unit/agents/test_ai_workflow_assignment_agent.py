"""
Test AI-Enhanced Workflow Assignment Agent

These tests validate the AI workflow assignment system while mocking
external API calls to ensure reliable testing.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from types import SimpleNamespace
from typing import Dict, Any

from src.agents.ai_workflow_assignment_agent import (
    AIWorkflowAssignmentAgent,
    GitHubModelsClient,
    ContentAnalysis,
    AssignmentSignals,
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
            path="/test/person.yaml",
            name="Person Entity Profiling",
            description="Entity-focused investigative workflow",
            version="1.0.0",
            trigger_labels=["person-entity-profiling", "investigative"],
            deliverables=[{"name": "entity-profile"}],
            processing={},
            validation={},
            output={}
        ),
        WorkflowInfo(
            path="/test/witness.yaml",
            name="Witness Expert Reliability Assessment",
            description="Witness reliability evaluation workflow",
            version="1.0.0",
            trigger_labels=["witness-expert-reliability-assessment", "trial-prep"],
            deliverables=[{"name": "reliability-brief"}],
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
    'title': 'Compile investigative profile for key witness',
    'body': '''We need to produce a comprehensive background profile for the primary cooperating witness,
          including prior testimony, professional affiliations, known associates, and potential credibility challenges.
          This will inform trial preparation for the upcoming evidentiary hearing.''',
    'labels': ['site-monitor', 'person-entity-profiling'],
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
        "summary": "Entity profiling request for a key individual tied to ongoing litigation",
        "key_topics": ["person of interest", "criminal procedure", "investigative leads", "court strategy"],
        "suggested_workflows": ["Person Entity Profiling"],
        "confidence_scores": {"Person Entity Profiling": 0.85},
        "technical_indicators": ["entity mapping", "legal strategy"],
        "urgency_level": "medium",
        "content_type": "investigative"
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
            available_workflows=sample_workflows,
            page_extract="Primary Content Summary: Sample"
        )
        
        # Verify API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == f"{client.BASE_URL}/v1/chat/completions"
        prompt_payload = call_args[1]['json']['messages'][1]['content']
        assert "PAGE EXTRACT" in prompt_payload
        assert "Primary Content Summary: Sample" in prompt_payload
        
        # Verify response parsing
        assert isinstance(result, ContentAnalysis)
        assert result.summary == mock_ai_response["summary"]
        assert result.suggested_workflows == ["Person Entity Profiling"]
        assert result.confidence_scores["Person Entity Profiling"] == 0.85
    
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

    def test_detect_legal_signals_returns_matches(self):
        sample_text = (
            "Coordinate with GAO and the Department of Justice on violations of 18 U.S.C. § 371 "
            "as referenced in Smith v. Jones." 
        )

        signals = AIWorkflowAssignmentAgent._detect_legal_signals(sample_text)

        assert signals['statutes'] == 1.0
        statute_matches = signals.get('statute_matches') or []
        assert any(match.strip() for match in statute_matches)

        assert signals['precedent'] == 1.0
        assert any('Smith v.' in match for match in signals.get('precedent_matches', []))

        assert signals['interagency'] == 1.0
        terms = {term.lower() for term in signals.get('interagency_terms', [])}
        assert 'gao' in terms
        assert 'department of justice' in terms

    def test_render_ai_assessment_section_includes_rationale(self):
        analysis = ContentAnalysis(
            summary="Synthesize threat landscape for Q4.",
            key_topics=["threat intelligence", "strategic outlook"],
            suggested_workflows=["Person Entity Profiling"],
            confidence_scores={"Person Entity Profiling": 0.92},
            technical_indicators=["emerging threat", "fusion required"],
            urgency_level="high",
            content_type="investigative",
            combined_scores={"Person Entity Profiling": 0.92},
            reason_codes=["PERSON_ENTITY_DETECTED", "STATUTE_CITATION_DETECTED"],
        )

        section = AIWorkflowAssignmentAgent._render_ai_assessment_section(
            analysis,
            assigned_workflow="Person Entity Profiling",
        )

        assert "Confidence: 92%" in section
        assert "Rationale: Matches topics" in section
        assert "(assigned)" in section
        assert "Reason Codes" in section
        assert "PERSON_ENTITY_DETECTED" in section
    
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

    @patch('src.agents.ai_workflow_assignment_agent.publish_telemetry_event')
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_issue_telemetry_includes_audit_payload(
        self,
        mock_matcher,
        mock_github,
        mock_publish,
        mock_github_token,
        mock_repo_name,
    ):
        mock_matcher_instance = mock_matcher.return_value
        mock_matcher_instance.get_available_workflows.return_value = []

        workflow_info = WorkflowInfo(
            path="/tmp/workflow.yaml",
            name="Person Entity Profiling & Risk Flagging",
            description="Profiles individuals and surfaces risk posture",
            version="1.0.0",
            trigger_labels=["person-profile"],
            deliverables=[{"name": "entity-backbone"}],
            processing={},
            validation={},
            output={},
            workflow_version="1.0.0",
            category="entity-foundation",
            confidence_threshold=0.75,
            audit_trail={
                'required': True,
                'fields': ['model_version', 'reason_codes', 'entity_evidence', 'citation_sources'],
            },
        )
        mock_matcher_instance.get_workflow_by_name.return_value = workflow_info

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True,
        )

        analysis = {
            'summary': 'Entity risk analysis',
            'entity_summary': {
                'coverage': 0.9,
                'counts': {'person': 3, 'place': 2, 'thing': 1},
                'missing_base_entities': [],
            },
            'legal_signals': {
                'statutes': 1.0,
                'statute_matches': ['18 U.S.C.', '§ 371'],
                'precedent': 1.0,
                'precedent_matches': ['Smith v. Jones'],
                'interagency': 1.0,
                'interagency_terms': ['gao', 'department of justice'],
            },
            'reason_codes': ['PERSON_ENTITY_DETECTED'],
        }

        result_payload = {
            'issue_number': 42,
            'action_taken': 'auto_assigned',
            'assigned_workflow': workflow_info.name,
            'labels_added': ['workflow::person-entity-profiling'],
            'dry_run': False,
            'message': 'Assigned automatically',
            'ai_analysis': analysis,
            'reason_codes': ['PERSON_ENTITY_DETECTED', 'HIGH_ENTITY_COVERAGE'],
        }

        agent._emit_issue_result_telemetry(result_payload, 0.42)

        assert mock_publish.called
        args, kwargs = mock_publish.call_args
        telemetry_payload = args[2]
        assert telemetry_payload['audit_trail']['required'] is True
        audit_data = telemetry_payload['audit_trail']['data']
        assert audit_data['model_version'] == agent.model_identifier
        assert audit_data['reason_codes'] == result_payload['reason_codes']
        assert audit_data['entity_evidence']['coverage'] == 0.9
        assert audit_data['citation_sources'] == ['18 U.S.C.', '§ 371', 'Smith v. Jones']
        assert telemetry_payload['legal_signals']['statute_matches'] == ['18 U.S.C.', '§ 371']
        assert telemetry_payload['statute_references'][0][0] == '18 U.S.C.'

    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_load_page_extract_reads_artifact(self, mock_matcher, mock_github, mock_github_token, mock_repo_name, tmp_path):
        mock_matcher.return_value.get_available_workflows.return_value = []

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True
        )

        agent.prompts_config.include_page_extract = True
        agent.prompts_config.page_extract_max_chars = 120
        agent.workspace_root = tmp_path
        agent.site_monitor_settings.page_capture.artifacts_dir = 'artifacts/discoveries'

        artifact_dir = tmp_path / 'artifacts' / 'discoveries' / 'abc123'
        artifact_dir.mkdir(parents=True)
        (artifact_dir / 'content.md').write_text(
            "# Headline\n\nThis is the leading paragraph.\n\n## Section One\n\nMore detail here.",
            encoding='utf-8'
        )

        entry = SimpleNamespace(content_hash='abc123', artifact_path='artifacts/discoveries/abc123')
        agent.dedup_manager = Mock()
        agent.dedup_manager.get_entry_by_hash.return_value = entry
        agent.dedup_manager.get_entry_by_url.return_value = None

        issue_data = {'body': '- **Discovery Hash:** `abc123`'}
        extract = agent._load_page_extract(issue_data)

        assert extract is not None
        assert 'Primary Content Summary' in extract
        assert 'Key Sections' in extract
        assert 'Captured Text' in extract
    
    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_load_page_extract_hash_only_path(
        self,
        mock_matcher,
        mock_github,
        mock_github_token,
        mock_repo_name,
        tmp_path,
    ):
        mock_matcher.return_value.get_available_workflows.return_value = []

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True,
        )

        agent.prompts_config.include_page_extract = True
        agent.prompts_config.page_extract_max_chars = 120
        agent.workspace_root = tmp_path
        agent.site_monitor_settings.page_capture.artifacts_dir = 'artifacts/discoveries'

        artifact_dir = tmp_path / 'artifacts' / 'discoveries' / 'def456'
        artifact_dir.mkdir(parents=True)
        (artifact_dir / 'content.md').write_text("Just a quick summary", encoding='utf-8')

        entry = SimpleNamespace(content_hash='def456', artifact_path='def456')
        agent.dedup_manager = Mock()
        agent.dedup_manager.get_entry_by_hash.return_value = entry
        agent.dedup_manager.get_entry_by_url.return_value = None

        issue_data = {'body': '- **Discovery Hash:** `def456`'}
        extract = agent._load_page_extract(issue_data)

        assert extract is not None
        assert 'def456' in extract

    @patch('src.agents.ai_workflow_assignment_agent.GitHubIssueCreator')
    @patch('src.agents.ai_workflow_assignment_agent.WorkflowMatcher')
    def test_load_page_extract_fallback_to_issue_excerpt(
        self,
        mock_matcher,
        mock_github,
        mock_github_token,
        mock_repo_name,
    ):
        mock_matcher.return_value.get_available_workflows.return_value = []

        agent = AIWorkflowAssignmentAgent(
            github_token=mock_github_token,
            repo_name=mock_repo_name,
            enable_ai=True,
        )

        agent.prompts_config.include_page_extract = True
        agent.prompts_config.page_extract_max_chars = 180
        agent.dedup_manager = Mock()
        agent.dedup_manager.get_entry_by_hash.return_value = None
        agent.dedup_manager.get_entry_by_url.return_value = None

        issue_body = (
            "# Discovery Intake\n\n"
            "<details>\n"
            "<summary>Preview excerpt</summary>\n\n"
            "> This is a captured preview with meaningful context.\n"
            "</details>\n"
        )

        extract = agent._load_page_extract({'body': issue_body})

        assert extract is not None
        assert 'Primary Content Summary' in extract
        assert 'meaningful context' in extract

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
        agent.prompts_config.include_page_extract = True
        agent.prompts_config.page_extract_max_chars = 200

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

        signals = AssignmentSignals(
            entity_score=1.0,
            base_counts={"person": 1, "place": 1, "thing": 1},
            missing_entities=[],
            legal_signals={"statutes": 0.5, "precedent": 0.0, "interagency": 0.2},
            reason_codes=["PERSON_ENTITY_DETECTED"],
            source="heuristic",
        )

        with patch.object(agent, '_load_page_extract', return_value='Primary summary block'):
            with patch.object(agent.ai_client, 'analyze_issue_content', return_value=mock_analysis) as mock_analyze:
                with patch.object(agent, '_compute_assignment_signals', return_value=signals):
                    workflow, analysis, message = agent.analyze_issue_with_ai(sample_issue_data)

        mock_analyze.assert_called_once()
        assert mock_analyze.call_args.kwargs.get('page_extract') == 'Primary summary block'
        assert workflow is not None
        assert workflow.name == "Person Entity Profiling"
        assert analysis.summary == mock_ai_response["summary"]
        assert analysis.combined_scores.get("Person Entity Profiling") is not None
        assert "score" in message
    
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
            summary="High confidence profiling request",
            key_topics=["entity profiling"],
            suggested_workflows=["Person Entity Profiling"],
            confidence_scores={"Person Entity Profiling": 0.9},
            technical_indicators=[],
            urgency_level="medium",
            content_type="investigative",
            combined_scores={"Person Entity Profiling": 0.9},
            reason_codes=["PERSON_ENTITY_DETECTED"],
        )
        
        with patch.object(agent, 'analyze_issue_with_ai', return_value=(sample_workflows[0], mock_analysis, "High confidence")):
            result = agent.process_issue_with_ai(sample_issue_data, dry_run=True)
        
        # Verify auto assignment
        assert result['action_taken'] == 'auto_assigned'
        assert result['assigned_workflow'] == 'Person Entity Profiling'
        assert result['issue_number'] == 123
        assert 'ai_analysis' in result
        assert "PERSON_ENTITY_DETECTED" in result['reason_codes']
    
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
            'assigned_workflow': 'Person Entity Profiling',
            'labels_added': ['workflow::person-entity-profiling'],
            'dry_run': True,
            'reason_codes': ['PERSON_ENTITY_DETECTED'],
            'ai_analysis': {
                'summary': 'High confidence assignment',
                'suggested_workflows': ['Person Entity Profiling'],
                'confidence_scores': {'Person Entity Profiling': 0.92},
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
        assert issue_event['suggested_workflows'] == ['Person Entity Profiling']
        assert issue_event['confidence_scores']['Person Entity Profiling'] == pytest.approx(0.92)
        assert issue_event['reason_codes'] == ['PERSON_ENTITY_DETECTED']
        assert issue_event['assignment_mode'] == 'ai'
        assert 'entity_coverage' in issue_event
        assert issue_event['entity_coverage'] is None
        assert issue_event['entity_counts'] is None
        assert issue_event['missing_base_entities'] is None
        assert issue_event['legal_signals'] is None

        summary_event = events[-1]
        assert summary_event['processed'] == 1
        assert summary_event['status'] == 'success'
        assert summary_event['assignment_mode'] == 'ai'
        assert summary_event['average_entity_coverage'] is None
        assert summary_event['entity_coverage_distribution'] == {'high': 0, 'partial': 0, 'low': 0}
        assert summary_event['issues_with_missing_entities'] == 0
        assert summary_event['top_reason_codes'] == [{'code': 'PERSON_ENTITY_DETECTED', 'count': 1}]
        assert summary_event['legal_signal_counts'] == {}


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
                summary="Profiling workflow needed",
                key_topics=["witness background"],
                suggested_workflows=["Person Entity Profiling"],
                confidence_scores={"Person Entity Profiling": 0.85},
                technical_indicators=[],
                urgency_level="medium", 
                content_type="investigative"
            )
            
            with patch.object(agent, 'analyze_issue_with_ai', return_value=(sample_workflows[0], mock_analysis, "High confidence")):
                result = agent.process_issues_batch(limit=1, dry_run=True)
        
        # Verify results
        assert result['total_issues'] == 1
        assert result['processed'] == 1
        assert result['statistics']['auto_assigned'] == 1
        assert len(result['results']) == 1
        assert result['explainability_summary'] is not None
        
        issue_result = result['results'][0]
        assert issue_result['issue_number'] == 123
        assert issue_result['action_taken'] == 'auto_assigned'
        assert issue_result['assigned_workflow'] == 'Person Entity Profiling'
        assert issue_result['dry_run'] is True


if __name__ == '__main__':
    pytest.main([__file__])