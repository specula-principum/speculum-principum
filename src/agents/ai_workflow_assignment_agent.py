"""
AI-Enhanced Workflow Assignment Agent using GitHub Models API

This module provides an intelligent agent that analyzes GitHub issue content
using GitHub Models API to suggest and assign appropriate workflows.

Key improvements over label-based matching:
- Semantic analysis of issue title and body
- Content-based workflow recommendations
- Learning from past assignments (stored in GitHub)
- Multi-factor scoring combining labels, content, and patterns
"""

import json
import logging
import time
import os
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from pathlib import Path

import requests
from github import Github

from ..workflow.workflow_matcher import WorkflowMatcher, WorkflowInfo, WorkflowMatcherError
from ..clients.github_issue_creator import GitHubIssueCreator
from ..utils.config_manager import ConfigManager, SiteMonitorSettings, AIPromptConfig
from ..utils.logging_config import get_logger, log_exception
from ..utils.markdown_sections import upsert_section
from ..workflow.workflow_state_manager import WorkflowState, plan_state_transition
from ..utils.telemetry import (
    TelemetryPublisher,
    normalize_publishers,
    publish_telemetry_event,
)
from ..core.deduplication import DeduplicationManager


@dataclass
class ContentAnalysis:
    """Results from AI content analysis"""
    summary: str
    key_topics: List[str]
    suggested_workflows: List[str]
    confidence_scores: Dict[str, float]
    technical_indicators: List[str]
    urgency_level: str  # low, medium, high, critical
    content_type: str  # research, bug, feature, security, documentation
    combined_scores: Dict[str, float] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)
    entity_summary: Dict[str, Any] = field(default_factory=dict)
    legal_signals: Dict[str, float] = field(default_factory=dict)


@dataclass
class AssignmentSignals:
    """Derived scoring signals used to evaluate workflow alignment."""

    entity_score: float
    base_counts: Dict[str, int]
    missing_entities: List[str]
    legal_signals: Dict[str, Any]
    reason_codes: List[str]
    source: str = "heuristic"


class GitHubModelsClient:
    """
    Client for GitHub Models API
    
    GitHub Models provides access to AI models directly within GitHub,
    perfect for GitHub Actions workflows.
    """
    
    BASE_URL = "https://models.inference.ai.github.com"
    
    def __init__(self, github_token: str, model: str = "gpt-4o"):
        """
        Initialize GitHub Models client.
        
        Args:
            github_token: GitHub token with models API access
            model: Model to use (gpt-4o, llama-3.2, etc.)
        """
        self.logger = get_logger(__name__)
        self.token = github_token
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
    def analyze_issue_content(
        self,
        title: str,
        body: str,
        labels: List[str],
        available_workflows: List[WorkflowInfo],
        page_extract: Optional[str] = None,
    ) -> ContentAnalysis:
        """
        Use GitHub Models to analyze issue content and suggest workflows.
        
        Args:
            title: Issue title
            body: Issue body/description
            labels: Current issue labels
            available_workflows: List of available workflow definitions
            
        Returns:
            ContentAnalysis with AI-generated insights
        """
        try:
            # Prepare workflow context for the model
            workflow_descriptions = []
            for wf in available_workflows:
                deliverable_types = [d.get('name', '') for d in wf.deliverables[:3]]  # First 3
                workflow_descriptions.append(
                    f"- {wf.name}: {wf.description}\n"
                    f"  Trigger labels: {', '.join(wf.trigger_labels)}\n"
                    f"  Deliverables: {', '.join(deliverable_types)}"
                )
            
            # Construct prompt for issue analysis
            prompt = self._build_analysis_prompt(
                title,
                body,
                labels,
                workflow_descriptions,
                page_extract=page_extract,
            )
            
            # Call GitHub Models API
            response = self._call_models_api(prompt)
            
            # Parse AI response into structured analysis
            return self._parse_ai_response(response, available_workflows)
            
        except Exception as e:
            log_exception(self.logger, "GitHub Models analysis failed", e)
            # Return fallback analysis
            return ContentAnalysis(
                summary="Failed to analyze with AI",
                key_topics=[],
                suggested_workflows=[],
                confidence_scores={},
                technical_indicators=[],
                urgency_level="medium",
                content_type="unknown"
            )
    
    def _build_analysis_prompt(
        self,
        title: str,
        body: str,
        labels: List[str],
        workflow_descriptions: List[str],
        page_extract: Optional[str] = None,
    ) -> str:
        """Build prompt for GitHub Models API"""

        extract_section = ""
        if page_extract:
            extract_section = f"\nPAGE EXTRACT (captured content):\n{page_extract}\n"
        
        return f"""Analyze this GitHub issue and suggest the most appropriate workflow(s).

ISSUE DETAILS:
Title: {title}
Labels: {', '.join(labels) if labels else 'None'}
Body:
{body[:2000] if body else 'No description provided'}

{extract_section}

AVAILABLE WORKFLOWS:
{chr(10).join(workflow_descriptions)}

TASK:
1. Summarize the issue's main purpose (50 words max)
2. Identify key topics/technologies mentioned
3. Suggest the most appropriate workflow(s) from the list above
4. Rate confidence (0-1) for each suggested workflow
5. Identify technical indicators (e.g., security issue, performance, architecture)
6. Assess urgency level (low/medium/high/critical)
7. Categorize content type (research/bug/feature/security/documentation)

Return response as valid JSON only:
{{
  "summary": "Brief summary of the issue",
  "key_topics": ["topic1", "topic2"],
  "suggested_workflows": ["workflow_name1", "workflow_name2"],
  "confidence_scores": {{"workflow_name1": 0.9, "workflow_name2": 0.7}},
  "technical_indicators": ["indicator1", "indicator2"],
  "urgency_level": "medium",
  "content_type": "research"
}}"""
    
    def _call_models_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call GitHub Models API endpoint.
        
        Note: This uses the GitHub Models inference endpoint which is
        available in GitHub Actions with proper authentication.
        """
        endpoint = f"{self.BASE_URL}/v1/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant analyzing GitHub issues to suggest appropriate processing workflows. Always respond with valid JSON only, no additional text or explanation."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,  # Lower temperature for more consistent analysis
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the AI's response
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                # Clean up response and parse JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                return json.loads(content)
            else:
                raise ValueError("Invalid response structure from GitHub Models")
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"GitHub Models API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {e}")
            self.logger.error(f"Raw response content: {content}")
            raise
    
    def _parse_ai_response(self, 
                          response: Dict[str, Any],
                          available_workflows: List[WorkflowInfo]) -> ContentAnalysis:
        """Parse AI response into ContentAnalysis object"""
        
        # Validate suggested workflows exist
        valid_workflows = {wf.name for wf in available_workflows}
        suggested = response.get("suggested_workflows", [])
        validated_suggestions = [w for w in suggested if w in valid_workflows]
        
        # Filter confidence scores to valid workflows
        confidence_scores = response.get("confidence_scores", {})
        validated_scores = {
            k: v for k, v in confidence_scores.items() 
            if k in valid_workflows
        }
        
        return ContentAnalysis(
            summary=response.get("summary", ""),
            key_topics=response.get("key_topics", []),
            suggested_workflows=validated_suggestions,
            confidence_scores=validated_scores,
            technical_indicators=response.get("technical_indicators", []),
            urgency_level=response.get("urgency_level", "medium"),
            content_type=response.get("content_type", "unknown")
        )


class AIWorkflowAssignmentAgent:
    """
    Enhanced workflow assignment agent using GitHub Models AI.
    
    Improvements over label-based assignment:
    - Semantic understanding of issue content
    - Multi-factor scoring combining AI analysis and labels
    - Learning from historical assignments
    - Intelligent fallback strategies
    """
    
    # Confidence thresholds for automatic assignment
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD = 0.6
    LEGACY_HIGH_CONFIDENCE_THRESHOLD = 0.8
    LEGACY_REVIEW_THRESHOLD = 0.6

    # Signal detection patterns
    STATUTE_PATTERN = re.compile(
        r"""
        (?:(?:\d+\s+U\.?\s*S\.?\s*C\.?|\d+\s+C\.?\s*F\.?\s*R\.?)\s*(?:§+\s*[\w().-]+)?)
        |
        (?:§+\s*[\dA-Za-z().-]+)
        |
        (?:Fed\.?\s+R\.?\s+(?:Crim|Civ|App|Evid|Bankr)\.?\s+P\.?\s*[\dA-Za-z().-]+)
        |
        (?:Sentencing\s+Guidelines?\s+§+\s*[\dA-Za-z().-]+)
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    PRECEDENT_PATTERN = re.compile(r"\b[A-Z][A-Za-z\-]+\s+v\.?\s+[A-Z][A-Za-z\-]+\b")
    PERSON_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")
    INTERAGENCY_KEYWORDS = {
        "gao",
        "department of justice",
        "doj",
        "fbi",
        "dea",
        "atf",
        "dhs",
        "oig",
        "u.s. attorney",
        "us attorney",
        "federal defender",
        "probation",
        "marshal service",
        "bureau of prisons",
    }
    PERSON_KEYWORDS = {
        "defendant",
        "suspect",
        "witness",
        "victim",
        "attorney",
        "counsel",
        "agent",
        "informant",
        "officer",
        "judge",
        "probation officer",
        "parole",
    }
    PLACE_KEYWORDS = {
        "district court",
        "county",
        "parish",
        "washington",
        "virginia",
        "federal courthouse",
        "detention center",
        "correctional",
        "facility",
        "jurisdiction",
        "circuit",
        "state of",
    }
    THING_KEYWORDS = {
        "evidence",
        "asset",
        "document",
        "record",
        "ledger",
        "weapon",
        "firearm",
        "phone",
        "laptop",
        "data",
        "chain of custody",
        "mitigation",
    }
    
    # Skip labels (same as original agent)
    SKIP_LABELS = {'feature', 'needs clarification', 'needs-review'}
    DISCOVERY_HASH_PATTERN = re.compile(
        r'Discovery Hash:[^`]*`([a-z0-9\-]{2,64})`',
        re.IGNORECASE,
    )
    URL_PATTERN = re.compile(r'https?://[^\s)`>]+', re.IGNORECASE)
    
    def __init__(self,
                 github_token: str,
                 repo_name: str,
                 config_path: str = "config.yaml",
                 workflow_directory: str = "docs/workflow/deliverables",
                 enable_ai: bool = True,
                 allowed_categories: Optional[Iterable[str]] = None,
                 telemetry_publishers: Optional[Iterable[TelemetryPublisher]] = None):
        """
        Initialize AI-enhanced workflow assignment agent.
        
        Args:
            github_token: GitHub API token
            repo_name: Repository name in format 'owner/repo'
            config_path: Path to configuration file
            workflow_directory: Directory containing workflow definitions
            enable_ai: Whether to use GitHub Models AI (can disable for testing)
            telemetry_publishers: Optional iterable of telemetry publishers for emitting assignment events
        """
        self.logger = get_logger(__name__)
        self.github = GitHubIssueCreator(github_token, repo_name)
        self.repo_name = repo_name
        self.enable_ai = enable_ai
        self.telemetry_publishers = normalize_publishers(telemetry_publishers)
        self.allowed_categories = (
            sorted({category.lower() for category in allowed_categories})
            if allowed_categories
            else None
        )
        
        # Load configuration
        try:
            self.config = ConfigManager.load_config(config_path)
            self.config_path = config_path
            self.workspace_root = Path(config_path).parent.resolve()
            self.site_monitor_settings = getattr(self.config, 'site_monitor', None) or SiteMonitorSettings()
            storage_path = getattr(self.config, 'storage_path', 'processed_urls.json')
            self.dedup_manager = DeduplicationManager(storage_path=storage_path)
            # Load AI configuration if available
            ai_config = getattr(self.config, 'ai', None)
            if ai_config:
                self.enable_ai = ai_config.get('enabled', enable_ai)
                self.HIGH_CONFIDENCE_THRESHOLD = ai_config.get('confidence_thresholds', {}).get('auto_assign', 0.8)
                self.MEDIUM_CONFIDENCE_THRESHOLD = ai_config.get('confidence_thresholds', {}).get('request_review', 0.6)
                ai_model = ai_config.get('model', 'gpt-4o')
                self.prompts_config = getattr(ai_config, 'prompts', None) or AIPromptConfig()
            else:
                ai_model = 'gpt-4o'
                self.prompts_config = AIPromptConfig()
        except Exception as e:
            self.logger.warning(f"Could not load config from {config_path}: {e}")
            ai_model = 'gpt-4o'
            self.prompts_config = AIPromptConfig()
            self.site_monitor_settings = SiteMonitorSettings()
            self.workspace_root = Path('.').resolve()
            self.dedup_manager = DeduplicationManager()
        
        self.model_identifier = ai_model if self.enable_ai else "ai-disabled"

        # Initialize workflow matcher for fallback
        self.workflow_matcher = WorkflowMatcher(workflow_directory)
        if self.allowed_categories:
            available_count = len(
                self.workflow_matcher.get_available_workflows(categories=self.allowed_categories)
            )
        else:
            available_count = len(self.workflow_matcher.get_available_workflows())
        self.logger.info(
            "Workflow matcher initialised with %d workflows (category filter=%s)",
            available_count,
            ",".join(self.allowed_categories or []) or "none",
        )
        
        # Initialize AI client if enabled
        if self.enable_ai:
            self.ai_client = GitHubModelsClient(github_token, model=ai_model)
        else:
            self.ai_client = None
            
        # Load learning data from previous assignments
        self.assignment_history = self._load_assignment_history()
        
        self.logger.info(
            f"Initialized AI workflow agent (AI={'enabled' if self.enable_ai else 'disabled'}, "
            f"model={ai_model if self.enable_ai else 'none'})"
        )
    
    def add_telemetry_publisher(self, publisher: TelemetryPublisher) -> None:
        """Register an additional telemetry publisher at runtime."""

        self.telemetry_publishers.append(publisher)

    def _publish_telemetry(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit a telemetry event if publishers are configured."""

        publish_telemetry_event(self.telemetry_publishers, event_type, payload, logger=self.logger)

    def _emit_issue_result_telemetry(self, result: Dict[str, Any], duration_seconds: float) -> None:
        """Emit telemetry for a single issue assignment result."""

        analysis = result.get('ai_analysis') or {}
        summary = analysis.get('summary')
        if summary:
            summary = summary.strip()
            if len(summary) > 240:
                summary = f"{summary[:237]}..."

        suggested = (analysis.get('suggested_workflows') or [])[:3]
        confidence_scores = analysis.get('confidence_scores') or {}

        payload = {
            'issue_number': result.get('issue_number'),
            'action_taken': result.get('action_taken'),
            'assigned_workflow': result.get('assigned_workflow'),
            'labels_added': list(result.get('labels_added') or []),
            'dry_run': result.get('dry_run'),
            'duration_seconds': duration_seconds,
            'note': result.get('message'),
            'ai_summary': summary,
            'suggested_workflows': suggested,
            'confidence_scores': {name: confidence_scores.get(name) for name in suggested},
            'error': result.get('message') if result.get('action_taken') == 'error' else None,
            'reason_codes': list(result.get('reason_codes') or []),
            'assignment_mode': 'ai',
        }

        entity_summary = analysis.get('entity_summary') if isinstance(analysis, dict) else {}
        legal_signals = analysis.get('legal_signals') if isinstance(analysis, dict) else {}
        if isinstance(entity_summary, dict):
            payload['entity_coverage'] = entity_summary.get('coverage')
            payload['entity_counts'] = entity_summary.get('counts')
            payload['missing_base_entities'] = entity_summary.get('missing_base_entities')
        else:
            payload['entity_coverage'] = None
            payload['entity_counts'] = None
            payload['missing_base_entities'] = None

        payload['legal_signals'] = legal_signals if isinstance(legal_signals, dict) else None

        statute_references: List[Tuple[str, int]] = []
        precedent_references: List[Tuple[str, int]] = []
        interagency_references: List[Tuple[str, int]] = []
        if isinstance(legal_signals, dict):
            statute_counter: Counter[str] = Counter()
            for citation in legal_signals.get('statute_matches') or []:
                normalised = self._normalize_legal_reference(citation)
                if normalised:
                    statute_counter[normalised] += 1
            precedent_counter: Counter[str] = Counter()
            for precedent in legal_signals.get('precedent_matches') or []:
                cleaned = self._normalize_legal_reference(precedent)
                if cleaned:
                    precedent_counter[cleaned] += 1
            interagency_counter: Counter[str] = Counter()
            for agency in legal_signals.get('interagency_terms') or []:
                if isinstance(agency, str) and agency.strip():
                    interagency_counter[agency.strip().lower()] += 1

            statute_references = statute_counter.most_common(5)
            precedent_references = precedent_counter.most_common(5)
            interagency_references = interagency_counter.most_common(5)

        payload['statute_references'] = statute_references
        payload['precedent_references'] = precedent_references
        payload['interagency_terms'] = interagency_references

        assigned_workflow_name = result.get('assigned_workflow')
        workflow_info: Optional[WorkflowInfo] = None
        if assigned_workflow_name:
            try:
                workflow_info = self.workflow_matcher.get_workflow_by_name(assigned_workflow_name)
            except Exception as exc:  # noqa: BLE001
                log_exception(
                    self.logger,
                    f"Unable to resolve workflow '{assigned_workflow_name}' for audit telemetry",
                    exc,
                )

        if workflow_info and isinstance(workflow_info.audit_trail, dict):
            audit_config = workflow_info.audit_trail
            audit_required = bool(audit_config.get('required'))
            required_fields = list(audit_config.get('fields') or [])

            if audit_required and required_fields:
                audit_data: Dict[str, Any] = {}
                for field_name in required_fields:
                    identifier = (field_name or "").strip().lower()
                    if identifier == 'model_version':
                        audit_data[field_name] = self.model_identifier
                    elif identifier == 'reason_codes':
                        audit_data[field_name] = list(payload.get('reason_codes') or [])
                    elif identifier == 'entity_evidence':
                        audit_data[field_name] = {
                            'coverage': entity_summary.get('coverage') if isinstance(entity_summary, dict) else None,
                            'counts': entity_summary.get('counts') if isinstance(entity_summary, dict) else None,
                            'missing_base_entities': entity_summary.get('missing_base_entities') if isinstance(entity_summary, dict) else None,
                        }
                    elif identifier == 'citation_sources':
                        citations: List[Any] = []
                        if isinstance(legal_signals, dict):
                            citations.extend(list(legal_signals.get('statute_matches') or []))
                            citations.extend(list(legal_signals.get('precedent_matches') or []))
                        audit_data[field_name] = citations
                    elif identifier == 'entity_evidence_details':
                        audit_data[field_name] = entity_summary if isinstance(entity_summary, dict) else None
                    else:
                        value = None
                        if isinstance(analysis, dict):
                            value = analysis.get(field_name)
                        if value is None:
                            value = result.get(field_name)
                        audit_data[field_name] = value

                payload['audit_trail'] = {
                    'required': True,
                    'fields': required_fields,
                    'workflow_version': workflow_info.workflow_version,
                    'workflow_category': workflow_info.category,
                    'data': audit_data,
                }

        self._publish_telemetry("workflow_assignment.issue_result", payload)

    def get_unassigned_site_monitor_issues(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get unassigned issues with 'site-monitor' label that need workflow assignment.
        
        Args:
            limit: Maximum number of issues to return
            
        Returns:
            List of issue data dictionaries
        """
        try:
            # Get all open site-monitor issues
            issues = self.github.get_issues_with_labels(['site-monitor'], state='open')
            
            candidate_issues = []
            for issue in issues:
                issue_labels = set(self._extract_label_names(issue.labels))
                
                # Skip if already assigned
                if issue.assignee is not None:
                    continue
                
                # Skip if has exclusion labels
                if issue_labels.intersection(self.SKIP_LABELS):
                    continue
                
                # Convert to dictionary format
                issue_data = {
                    'number': issue.number,
                    'title': issue.title,
                    'body': issue.body or "",
                    'labels': list(issue_labels),
                    'assignee': None,
                    'created_at': issue.created_at.isoformat() if issue.created_at else None,
                    'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
                    'url': issue.html_url,
                    'user': issue.user.login if issue.user else None
                }
                
                candidate_issues.append(issue_data)
                
                # Apply limit
                if limit and len(candidate_issues) >= limit:
                    break
            
            self.logger.info(f"Found {len(candidate_issues)} candidate issues for AI workflow assignment")
            return candidate_issues
        
        except Exception as e:
            log_exception(self.logger, "Failed to get unassigned site-monitor issues", e)
            return []

    def _load_page_extract(self, issue_data: Dict[str, Any]) -> Optional[str]:
        prompts_config = getattr(self, 'prompts_config', None)
        if not prompts_config or not getattr(prompts_config, 'include_page_extract', False):
            self.logger.debug(
                f"Page extract disabled for issue #{issue_data.get('number', 'unknown')} "
                f"(include_page_extract={getattr(prompts_config, 'include_page_extract', False) if prompts_config else False})"
            )
            return None

        issue_number = issue_data.get('number', 'unknown')
        self.logger.debug(f"Loading page extract for issue #{issue_number}")
        
        body = issue_data.get('body') or ""
        content_hash = self._extract_discovery_hash(body)
        entry = None

        if content_hash:
            self.logger.debug(f"Found discovery hash {content_hash} for issue #{issue_number}")
            entry = self.dedup_manager.get_entry_by_hash(content_hash)

        if not entry:
            primary_url = self._extract_primary_url(body)
            if primary_url:
                self.logger.debug(f"Attempting to load page extract by URL: {primary_url}")
                entry = self.dedup_manager.get_entry_by_url(primary_url)
                if entry and not content_hash:
                    content_hash = entry.content_hash

        if not entry:
            self.logger.debug(f"No deduplication entry found, checking for preview excerpt in issue #{issue_number}")
            excerpt = self._extract_issue_preview_excerpt(body)
            if excerpt:
                max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
                self.logger.info(
                    f"Using inline preview excerpt for issue #{issue_number} "
                    f"({len(excerpt)} chars, truncating to {max_chars})"
                )
                return self._format_page_extract(excerpt, max_chars, content_hash)
            self.logger.warning(f"No page extract available for issue #{issue_number} (no entry or preview excerpt)")
            return None

        artifact_path = entry.artifact_path
        if not artifact_path and content_hash:
            artifact_path = str(Path(self.site_monitor_settings.page_capture.artifacts_dir) / content_hash)

        artifact_dir = self._resolve_artifact_path(artifact_path)
        if not artifact_dir:
            self.logger.debug(f"No artifact directory found for issue #{issue_number}, falling back to preview excerpt")
            excerpt = self._extract_issue_preview_excerpt(body)
            if excerpt:
                max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
                self.logger.info(
                    f"Using inline preview excerpt for issue #{issue_number} "
                    f"({len(excerpt)} chars, truncating to {max_chars})"
                )
                return self._format_page_extract(excerpt, max_chars, content_hash)
            self.logger.warning(f"No page extract available for issue #{issue_number} (no artifact dir or preview excerpt)")
            return None

        content_file = artifact_dir / "content.md"
        if not content_file.exists():
            self.logger.debug(f"Artifact content.md not found for issue #{issue_number}, falling back to preview excerpt")
            excerpt = self._extract_issue_preview_excerpt(body)
            if excerpt:
                max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
                self.logger.info(
                    f"Using inline preview excerpt for issue #{issue_number} "
                    f"({len(excerpt)} chars, truncating to {max_chars})"
                )
                return self._format_page_extract(excerpt, max_chars, content_hash)
            self.logger.warning(f"No page extract available for issue #{issue_number} (content.md missing, no preview excerpt)")
            return None

        try:
            raw_text = content_file.read_text(encoding="utf-8")
            max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
            self.logger.info(
                f"Loaded page extract from artifact for issue #{issue_number} "
                f"(source: {content_file}, {len(raw_text)} chars, truncating to {max_chars})"
            )
        except OSError as e:
            self.logger.warning(f"Failed to read artifact content.md for issue #{issue_number}: {e}")
            excerpt = self._extract_issue_preview_excerpt(body)
            if excerpt:
                max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
                self.logger.info(
                    f"Using inline preview excerpt for issue #{issue_number} after artifact read failure "
                    f"({len(excerpt)} chars, truncating to {max_chars})"
                )
                return self._format_page_extract(excerpt, max_chars, content_hash)
            self.logger.warning(f"No page extract available for issue #{issue_number} (artifact read failed, no preview excerpt)")
            return None

        max_chars = getattr(prompts_config, 'page_extract_max_chars', 1200)
        return self._format_page_extract(raw_text, max_chars, content_hash)

    @staticmethod
    def _extract_issue_preview_excerpt(body: str) -> Optional[str]:
        if not body:
            return None

        details_match = re.search(
            r"<details>\s*<summary>\s*Preview excerpt\s*</summary>(?P<content>.*?)</details>",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        if not details_match:
            return None
        block = details_match.group("content")
        excerpt_lines: List[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith(">"):
                excerpt_lines.append(stripped.lstrip(">").strip())

        excerpt = " ".join(excerpt_lines).strip()
        return excerpt or None

    def _resolve_artifact_path(self, artifact_path: Optional[str]) -> Optional[Path]:
        if not artifact_path:
            return None

        raw_path = Path(artifact_path)
        candidate_paths = []

        if raw_path.is_absolute():
            candidate_paths.append(raw_path)
        else:
            candidate_paths.append((self.workspace_root / raw_path).resolve())

            if len(raw_path.parts) == 1:
                artifacts_dir = getattr(
                    self.site_monitor_settings.page_capture,
                    'artifacts_dir',
                    'artifacts/discoveries',
                )
                candidate_paths.append(
                    (self.workspace_root / artifacts_dir / raw_path).resolve()
                )

        for candidate in candidate_paths:
            if candidate.exists():
                return candidate
        return None

    def _extract_discovery_hash(self, body: str) -> Optional[str]:
        if not body:
            return None
        match = self.DISCOVERY_HASH_PATTERN.search(body)
        if match:
            hash_value = match.group(1).strip()
            if hash_value.lower() in {"n/a", "na", "none", "unknown"}:
                return None
            return hash_value
        return None

    def _extract_primary_url(self, body: str) -> Optional[str]:
        if not body:
            return None
        link_match = re.search(r'\[[^\]]+\]\((https?://[^)]+)\)', body)
        if link_match:
            return link_match.group(1)
        url_match = self.URL_PATTERN.search(body)
        if url_match:
            return url_match.group(0)
        return None

    def _format_page_extract(self, text: str, max_chars: int, content_hash: Optional[str]) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        paragraphs = lines
        primary_summary = paragraphs[0] if paragraphs else ""

        headings = [
            line.lstrip('#').strip()
            for line in text.splitlines()
            if line.strip().startswith('#')
        ]
        if not headings:
            headings = paragraphs[1:4]

        truncated_text = text.strip()
        if max_chars and len(truncated_text) > max_chars:
            truncated_text = truncated_text[:max_chars].rsplit(' ', 1)[0].strip() + '…'

        parts = []
        if content_hash:
            parts.append(f"Discovery Hash: {content_hash}")
        if primary_summary:
            summary = primary_summary
            if len(summary) > 300:
                summary = summary[:300].rsplit(' ', 1)[0].strip() + '…'
            parts.append(f"Primary Content Summary: {summary}")
        if headings:
            parts.append("Key Sections:\n" + "\n".join(f"- {section}" for section in headings[:5]))
        parts.append(f"Captured Text:\n{truncated_text}")

        extract = "\n\n".join(parts)
        if max_chars and len(extract) > max_chars:
            extract = extract[:max_chars].rsplit(' ', 1)[0].strip() + '…'
        return extract
    
    def analyze_issue_with_ai(self, 
                             issue_data: Dict[str, Any]) -> Tuple[Optional[WorkflowInfo], ContentAnalysis, str]:
        """
        Analyze issue using AI to determine best workflow match.
        
        Args:
            issue_data: Issue data dictionary
            
        Returns:
            Tuple of (WorkflowInfo if found, AI analysis, explanation message)
            
        Raises:
            RuntimeError: If AI is required but unavailable
        """
        available_workflows = self.workflow_matcher.get_available_workflows(
            categories=self.allowed_categories
        )
        
        # Check if we're in GitHub Actions environment
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        if not is_github_actions:
            raise RuntimeError(
                "AI workflow assignment requires GitHub Actions environment with access to GitHub Models API. "
                "This feature is not available when running locally. "
                "Please run this command within a GitHub Actions workflow."
            )
        
        # Get AI analysis
        if not self.enable_ai or not self.ai_client:
            raise RuntimeError(
                "AI workflow assignment is disabled but required for operation. "
                "Please enable AI in configuration or run in GitHub Actions environment."
            )
        
        try:
            issue_number = issue_data.get('number', 'unknown')
            page_extract = self._load_page_extract(issue_data)
            
            if page_extract:
                self.logger.info(
                    f"Analyzing issue #{issue_number} with AI (WITH page extract, {len(page_extract)} chars)"
                )
            else:
                self.logger.info(
                    f"Analyzing issue #{issue_number} with AI (NO page extract - limited context)"
                )
            
            analysis = self.ai_client.analyze_issue_content(
                title=issue_data.get('title', ''),
                body=issue_data.get('body', ''),
                labels=issue_data.get('labels', []),
                available_workflows=available_workflows,
                page_extract=page_extract,
            )
            
            # Combine AI analysis with label-based validation
            return self._combine_ai_and_label_analysis(
                issue_data,
                analysis,
                available_workflows,
                page_extract=page_extract,
            )
            
        except Exception as e:
            error_msg = f"AI analysis failed: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(
                f"AI workflow assignment failed and no fallback is available. "
                f"Error: {error_msg}. "
                f"This feature requires a working connection to GitHub Models API."
            ) from e
    
    def _compute_assignment_signals(
        self,
        issue_data: Dict[str, Any],
        ai_analysis: ContentAnalysis,
        *,
        page_extract: Optional[str] = None,
    ) -> AssignmentSignals:
        """Derive heuristic signals about entities and legal context."""

        text_segments: List[str] = [issue_data.get('title', ''), issue_data.get('body', '')]
        if page_extract:
            text_segments.append(page_extract)
        if ai_analysis.summary:
            text_segments.append(ai_analysis.summary)

        combined_text = "\n".join(segment for segment in text_segments if segment)
        lower_text = combined_text.lower()

        base_counts = self._estimate_entity_counts(combined_text, lower_text)
        present = [entity for entity, count in base_counts.items() if count > 0]
        missing = [entity for entity in ('person', 'place', 'thing') if base_counts.get(entity, 0) <= 0]

        coverage = sum(1 for entity in ('person', 'place', 'thing') if base_counts.get(entity, 0) > 0) / 3.0

        legal_signals = self._detect_legal_signals(combined_text, lower_text)

        reason_codes: List[str] = []
        for entity in ('person', 'place', 'thing'):
            if base_counts.get(entity, 0) > 0:
                reason_codes.append(f"{entity.upper()}_ENTITY_DETECTED")
            else:
                reason_codes.append(f"{entity.upper()}_ENTITY_MISSING")

        if coverage >= 0.67:
            reason_codes.append("HIGH_ENTITY_COVERAGE")
        elif coverage >= 0.34:
            reason_codes.append("PARTIAL_ENTITY_COVERAGE")
        else:
            reason_codes.append("LOW_ENTITY_COVERAGE")

        if legal_signals.get('statutes'):
            reason_codes.append("STATUTE_CITATION_DETECTED")
        if legal_signals.get('precedent'):
            reason_codes.append("PRECEDENT_REFERENCE_DETECTED")
        if legal_signals.get('interagency'):
            reason_codes.append("INTERAGENCY_CONTEXT_DETECTED")

        reason_codes = list(dict.fromkeys(reason_codes))

        ai_analysis.entity_summary = {
            'coverage': round(coverage, 3),
            'counts': base_counts,
            'present_base_entities': present,
            'missing_base_entities': missing,
            'source': 'heuristic',
        }
        ai_analysis.legal_signals = legal_signals
        ai_analysis.reason_codes = reason_codes

        return AssignmentSignals(
            entity_score=coverage,
            base_counts=base_counts,
            missing_entities=missing,
            legal_signals=legal_signals,
            reason_codes=reason_codes,
            source='heuristic',
        )

    @classmethod
    def _estimate_entity_counts(
        cls,
        text: str,
        lower_text: Optional[str] = None,
    ) -> Dict[str, int]:
        """Approximate entity counts using lightweight heuristics."""

        lower_text = lower_text if lower_text is not None else text.lower()

        counts = {entity: 0 for entity in ('person', 'place', 'thing')}

        person_keywords = {kw for kw in cls.PERSON_KEYWORDS if kw in lower_text}
        name_matches = {
            match
            for match in cls.PERSON_NAME_PATTERN.findall(text)
            if len(match.split()) >= 2
        }
        counts['person'] = min(5, len(person_keywords) + len(name_matches))

        place_hits = {kw for kw in cls.PLACE_KEYWORDS if kw in lower_text}
        geographic_patterns = re.findall(r"\b[A-Z][a-z]+\s+(County|District|Parish)\b", text)
        counts['place'] = min(5, len(place_hits) + len(geographic_patterns))

        thing_hits = {kw for kw in cls.THING_KEYWORDS if kw in lower_text}
        counts['thing'] = min(5, len(thing_hits))

        return counts

    @classmethod
    def _normalize_legal_reference(cls, value: str) -> str:
        """Normalize legal citation references for consistent telemetry reporting."""

        if not isinstance(value, str):
            return ""

        cleaned = re.sub(r"\s+", " ", value.strip())
        cleaned = cleaned.strip('"\'')
        cleaned = cleaned.lstrip("(")
        cleaned = cleaned.rstrip(";,)")
        if cleaned.endswith('.') and not re.search(r"[A-Za-z]\.\Z", cleaned):
            cleaned = cleaned[:-1]
        cleaned = cleaned.rstrip(":")

        # Ensure section symbols maintain a single leading space.
        cleaned = re.sub(r"\s*§", " §", cleaned)
        cleaned = cleaned.strip()

        return cleaned

    @classmethod
    def _detect_legal_signals(
        cls,
        text: str,
        lower_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Identify legal research signals from text content."""

        lower_text = lower_text if lower_text is not None else text.lower()

        statute_matches: List[str] = []
        statute_seen: Set[str] = set()
        for match in cls.STATUTE_PATTERN.finditer(text):
            raw_citation = match.group(0)
            citation = cls._normalize_legal_reference(raw_citation)
            if not citation:
                continue

            upper_citation = citation.upper()
            if "§" in citation and (
                "U.S.C" in upper_citation
                or "C.F.R" in upper_citation
                or "GUIDELINE" in upper_citation
            ):
                section_match = re.search(r"(§\s*[\dA-Za-z().-]+)", citation)
                if section_match:
                    section_fragment = cls._normalize_legal_reference(section_match.group(1))
                    code_fragment = cls._normalize_legal_reference(
                        citation[: section_match.start()]
                    )
                    for fragment in (code_fragment, section_fragment):
                        if fragment and fragment not in statute_seen:
                            statute_seen.add(fragment)
                            statute_matches.append(fragment)
                    continue

            if citation not in statute_seen:
                statute_seen.add(citation)
                statute_matches.append(citation)

        precedent_matches: List[str] = []
        precedent_seen: Set[str] = set()
        for match in cls.PRECEDENT_PATTERN.finditer(text):
            citation = cls._normalize_legal_reference(match.group(0))
            if citation and citation not in precedent_seen:
                precedent_seen.add(citation)
                precedent_matches.append(citation)

        interagency_terms: List[str] = []
        interagency_seen: Set[str] = set()
        for keyword in cls.INTERAGENCY_KEYWORDS:
            if keyword in lower_text:
                normalised = keyword.strip().lower()
                if normalised not in interagency_seen:
                    interagency_seen.add(normalised)
                    interagency_terms.append(normalised)

        statute_signal = 1.0 if statute_matches else 0.0
        precedent_signal = 1.0 if precedent_matches else 0.0
        interagency_signal = 1.0 if interagency_terms else 0.0

        return {
            'statutes': statute_signal,
            'statute_matches': statute_matches,
            'precedent': precedent_signal,
            'precedent_matches': precedent_matches,
            'interagency': interagency_signal,
            'interagency_terms': interagency_terms,
        }

    def _is_taxonomy_workflow(self, workflow: WorkflowInfo) -> bool:
        """Determine whether a workflow adheres to the modern criminal-law taxonomy."""

        try:
            return workflow.is_taxonomy()  # type: ignore[attr-defined]
        except AttributeError:
            return False

    def _calculate_combined_score(
        self,
        *,
        workflow: WorkflowInfo,
        ai_confidence: float,
        label_signal: float,
        historical_signal: float,
        signals: AssignmentSignals,
    ) -> Tuple[float, Optional[str]]:
        """Compute combined score for a workflow and return optional reason code."""

        reason_code: Optional[str] = None

        if self._is_taxonomy_workflow(workflow):
            score = (
                signals.entity_score * 0.4
                + ai_confidence * 0.35
                + label_signal * 0.08
                + historical_signal * 0.07
                + signals.legal_signals.get('statutes', 0.0) * 0.05
                + signals.legal_signals.get('precedent', 0.0) * 0.03
                + signals.legal_signals.get('interagency', 0.0) * 0.02
            )
            return score, reason_code

        # Legacy workflows rely more heavily on AI confidence and label agreement.
        score = (
            ai_confidence * 0.6
            + label_signal * 0.25
            + historical_signal * 0.15
        )

        if ai_confidence >= self.LEGACY_HIGH_CONFIDENCE_THRESHOLD and (
            label_signal > 0 or historical_signal >= 0.7
        ):
            score = max(score, ai_confidence)
            reason_code = "LEGACY_HIGH_CONFIDENCE_OVERRIDE"

        return score, reason_code

    def _resolve_confidence_threshold(self, workflow: WorkflowInfo) -> float:
        """Resolve the confidence threshold required for automatic assignment."""

        workflow_threshold = getattr(workflow, "confidence_threshold", None)
        if isinstance(workflow_threshold, (int, float)):
            return max(0.0, min(1.0, float(workflow_threshold)))

        if self._is_taxonomy_workflow(workflow):
            return self.HIGH_CONFIDENCE_THRESHOLD

        return self.LEGACY_HIGH_CONFIDENCE_THRESHOLD

    def _resolve_review_threshold(self, workflow: WorkflowInfo, high_threshold: float) -> float:
        """Determine the threshold that should trigger a human review."""

        if self._is_taxonomy_workflow(workflow):
            candidate = min(self.MEDIUM_CONFIDENCE_THRESHOLD, max(high_threshold - 0.1, 0.5))
            return min(candidate, high_threshold)

        review_threshold = min(self.LEGACY_REVIEW_THRESHOLD, high_threshold)
        if review_threshold >= high_threshold:
            review_threshold = max(high_threshold - 0.05, 0.5)
        return review_threshold

    def _combine_ai_and_label_analysis(self,
                                      issue_data: Dict[str, Any],
                                      ai_analysis: ContentAnalysis,
                                      available_workflows: List[WorkflowInfo],
                                      *,
                                      page_extract: Optional[str] = None) -> Tuple[Optional[WorkflowInfo], ContentAnalysis, str]:
        """Combine AI analysis with taxonomy-aware scoring signals."""

        combined_scores: Dict[str, float] = {}

        # Determine label alignment and heuristic signals
        label_matches = self.workflow_matcher.find_matching_workflows(
            issue_data.get('labels', [])
        )
        label_match_names = {wf.name for wf in label_matches}
        signals = self._compute_assignment_signals(
            issue_data,
            ai_analysis,
            page_extract=page_extract,
        )

        if label_match_names:
            ai_analysis.reason_codes.append("LABEL_TRIGGER_MATCH")
        else:
            ai_analysis.reason_codes.append("LABEL_TRIGGER_GAP")

        if not any(signals.legal_signals.values()):
            ai_analysis.reason_codes.append("LEGAL_CONTEXT_NOT_DETECTED")

        score_reason_codes: List[str] = []

        for workflow in available_workflows:
            ai_confidence = ai_analysis.confidence_scores.get(workflow.name, 0.0)
            label_signal = 1.0 if workflow.name in label_match_names else 0.0
            historical_signal = self._get_historical_success_rate(
                workflow.name,
                ai_analysis.content_type,
            )

            score, score_reason = self._calculate_combined_score(
                workflow=workflow,
                ai_confidence=ai_confidence,
                label_signal=label_signal,
                historical_signal=historical_signal,
                signals=signals,
            )

            if score_reason:
                score_reason_codes.append(score_reason)

            if score > 0:
                combined_scores[workflow.name] = score

        if score_reason_codes:
            ai_analysis.reason_codes.extend(score_reason_codes)

        ai_analysis.combined_scores = combined_scores
        ai_analysis.reason_codes = list(dict.fromkeys(ai_analysis.reason_codes))

        if combined_scores:
            best_workflow_name = max(
                combined_scores.keys(), key=lambda name: combined_scores[name]
            )
            best_score = combined_scores[best_workflow_name]
            best_workflow = next(
                wf for wf in available_workflows if wf.name == best_workflow_name
            )

            high_threshold = self._resolve_confidence_threshold(best_workflow)
            review_threshold = self._resolve_review_threshold(best_workflow, high_threshold)

            if best_score >= high_threshold:
                ai_analysis.reason_codes.append("AUTO_ASSIGN_THRESHOLD_MET")
                ai_analysis.reason_codes = list(dict.fromkeys(ai_analysis.reason_codes))
                message = (
                    f"AI analysis selected '{best_workflow_name}' "
                    f"(score: {best_score:.2f}, threshold: {high_threshold:.2f}, content type: {ai_analysis.content_type})"
                )
                return best_workflow, ai_analysis, message

            if best_score >= review_threshold:
                message = (
                    f"AI suggests '{best_workflow_name}' "
                    f"(score: {best_score:.2f}, threshold: {review_threshold:.2f}) but recommends human review"
                )
                return None, ai_analysis, message

        message = "AI analysis inconclusive - no workflow has sufficient confidence"
        return None, ai_analysis, message
    
    def _get_historical_success_rate(self, 
                                    workflow_name: str,
                                    content_type: str) -> float:
        """
        Get historical success rate for a workflow/content type combination.
        
        Returns:
            Success rate between 0 and 1
        """
        # This would query historical assignment data stored in GitHub
        # For now, return a default value based on content type matching
        if workflow_name == "Person Entity Profiling" and content_type in ["investigative", "profiling", "entity-analysis"]:
            return 0.8
        elif workflow_name == "Witness Expert Reliability Assessment" and content_type in ["trial-prep", "witness", "expert"]:
            return 0.8
        else:
            return 0.5
    
    def _load_assignment_history(self) -> Dict[str, Any]:
        """
        Load historical assignment data from GitHub.
        
        Could be stored as:
        - GitHub Gist
        - Repository file
        - GitHub Actions artifacts
        """
        # Placeholder - would load from GitHub storage
        return {}

    @staticmethod
    def _slugify_label(value: str) -> str:
        """Convert arbitrary workflow names into label-friendly slugs."""

        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "workflow"

    @staticmethod
    def _determine_specialist_label(workflow: WorkflowInfo) -> Optional[str]:
        """Extract the specialist label from workflow metadata if available."""

        sources = []
        if isinstance(workflow.processing, dict):
            sources.extend(
                workflow.processing.get(key)
                for key in ("specialist_type", "specialist")
            )
        # Some workflows embed specialist under config-style keys
        config = getattr(workflow, "config", None)
        if isinstance(config, dict):
            sources.append(config.get("specialist_type"))

        for specialist in sources:
            if isinstance(specialist, str) and specialist.strip():
                return specialist.strip().lower()
        return None

    @staticmethod
    def _extract_label_names(labels: Iterable[Any]) -> List[str]:
        """Normalise heterogeneous label representations into plain strings."""

        normalised: List[str] = []
        for label in labels:
            candidate: Optional[str] = None

            if isinstance(label, str):
                candidate = label
            else:
                name_attr = getattr(label, "name", None)
                if isinstance(name_attr, str):
                    candidate = name_attr
                else:
                    mock_name = getattr(label, "_mock_name", None)
                    if isinstance(mock_name, str) and mock_name:
                        candidate = mock_name
                    elif name_attr is not None and hasattr(name_attr, "_mock_name"):
                        nested_mock_name = getattr(name_attr, "_mock_name", None)
                        if isinstance(nested_mock_name, str) and nested_mock_name:
                            candidate = nested_mock_name

            if candidate:
                stripped = candidate.strip()
                if stripped:
                    normalised.append(stripped)

        return normalised

    @staticmethod
    def _apply_transition_plan(
        current_labels: List[str],
        plan,
        *,
        extra_labels: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """Apply the transition plan to the label set and return updates."""

        label_lookup: Dict[str, str] = {label.lower(): label for label in current_labels}
        initial_keys = set(label_lookup.keys())

        # Remove labels scheduled for removal
        for label in getattr(plan, "labels_to_remove", []):
            label_lookup.pop(label, None)

        # Add labels from the plan (already normalised)
        for label in getattr(plan, "labels_to_add", []):
            label_lookup[label] = label

        # Include additional workflow trigger labels for compatibility
        if extra_labels:
            for label in extra_labels:
                if not isinstance(label, str):
                    continue
                normalised = label.lower()
                if normalised not in label_lookup:
                    label_lookup[normalised] = label

        final_labels = sorted(label_lookup.values(), key=str.lower)
        added_labels = [label_lookup[key] for key in set(label_lookup.keys()) - initial_keys]
        return final_labels, added_labels

    @staticmethod
    def _build_workflow_rationale(
        analysis: ContentAnalysis,
    ) -> str:
        """Create a short rationale string using the AI analysis signals."""

        rationale_parts: List[str] = []

        if analysis.key_topics:
            topics = ", ".join(topic for topic in analysis.key_topics[:2] if topic)
            if topics:
                rationale_parts.append(f"topics {topics}")

        if analysis.technical_indicators:
            indicators = ", ".join(indicator for indicator in analysis.technical_indicators[:2] if indicator)
            if indicators:
                rationale_parts.append(f"indicators {indicators}")

        if analysis.content_type and analysis.content_type.strip():
            rationale_parts.append(f"content type {analysis.content_type.strip().lower()}")

        if analysis.urgency_level and analysis.urgency_level.strip():
            rationale_parts.append(f"urgency {analysis.urgency_level.strip().lower()}")

        if not rationale_parts:
            return "Aligned with the discovery summary and AI assessment signals."

        rationale = "; ".join(rationale_parts)
        return f"Matches {rationale}."

    @staticmethod
    def _render_ai_assessment_section(
        analysis: ContentAnalysis,
        assigned_workflow: Optional[str] = None,
    ) -> str:
        """Build the Markdown content for the AI Assessment section."""

        lines: List[str] = []
        summary = analysis.summary.strip() if analysis.summary else "No summary available."
        lines.append("**Summary**")
        lines.append(f"- {summary}")
        lines.append("")

        lines.append("**Recommended Workflows**")
        if analysis.suggested_workflows:
            for workflow_name in analysis.suggested_workflows[:5]:
                confidence = analysis.confidence_scores.get(workflow_name)
                confidence_text = (
                    f" — Confidence: {confidence:.0%}"
                    if confidence is not None
                    else ""
                )
                suffix = " (assigned)" if assigned_workflow and workflow_name == assigned_workflow else ""
                rationale = AIWorkflowAssignmentAgent._build_workflow_rationale(analysis)
                lines.append(
                    f"- {workflow_name}{confidence_text} — Rationale: {rationale}{suffix}"
                )
        else:
            lines.append("- No clear matches identified.")
        lines.append("")

        if analysis.key_topics:
            lines.append("**Key Topics**")
            for topic in analysis.key_topics[:10]:
                lines.append(f"- {topic}")
            lines.append("")

        if analysis.technical_indicators:
            lines.append("**Indicators**")
            for indicator in analysis.technical_indicators[:10]:
                lines.append(f"- {indicator}")
            lines.append("")

        lines.append("**Classification**")
        urgency = analysis.urgency_level.title() if analysis.urgency_level else "Unknown"
        content_type = analysis.content_type.title() if analysis.content_type else "Unknown"
        lines.append(f"- Urgency: {urgency}")
        lines.append(f"- Content Type: {content_type}")

        if analysis.reason_codes:
            lines.append("")
            lines.append("**Reason Codes**")
            for code in analysis.reason_codes[:12]:
                lines.append(f"- {code}")

        return "\n".join(lines).strip()
    
    def process_issue_with_ai(self,
                             issue_data: Dict[str, Any],
                             dry_run: bool = False) -> Dict[str, Any]:
        """
        Process issue using AI-enhanced workflow assignment.
        
        Args:
            issue_data: Issue data dictionary
            dry_run: If True, don't make actual changes
            
        Returns:
            Assignment result with AI insights
        """
        issue_number = issue_data['number']
        
        # Analyze with AI
        workflow, ai_analysis, message = self.analyze_issue_with_ai(issue_data)
        
        result = {
            'issue_number': issue_number,
            'ai_analysis': asdict(ai_analysis),
            'message': message,
            'action_taken': None,
            'assigned_workflow': None,
            'labels_added': [],
            'dry_run': dry_run,
            'reason_codes': list(ai_analysis.reason_codes),
        }
        
        best_score = None
        threshold = None
        if workflow:
            threshold = self._resolve_confidence_threshold(workflow)
            best_score = ai_analysis.combined_scores.get(workflow.name)
            if best_score is None:
                best_score = ai_analysis.confidence_scores.get(workflow.name)

        if workflow and threshold is not None and (best_score is not None and best_score >= threshold):
            # High confidence - assign automatically
            labels_added = self._assign_workflow_with_ai_context(
                issue_number, workflow, ai_analysis, dry_run
            )
            result['action_taken'] = 'auto_assigned'
            result['assigned_workflow'] = workflow.name
            result['labels_added'] = labels_added
            
        elif ai_analysis.suggested_workflows:
            # Medium confidence - request human review
            labels_added = self._request_review_with_ai_context(
                issue_number, ai_analysis, dry_run
            )
            result['action_taken'] = 'review_requested'
            result['labels_added'] = labels_added
            
        else:
            # Low confidence - request more information
            labels_added = self._request_clarification_with_ai_context(
                issue_number, ai_analysis, dry_run
            )
            result['action_taken'] = 'clarification_requested'
            result['labels_added'] = labels_added
        
        return result
    
    def _assign_workflow_with_ai_context(self,
                                        issue_number: int,
                                        workflow: WorkflowInfo,
                                        analysis: ContentAnalysis,
                                        dry_run: bool = False) -> List[str]:
        """Assign workflow with AI analysis context in comment"""

        issue = self.github.repo.get_issue(issue_number)
        current_labels = self._extract_label_names(issue.labels)

        workflow_slug = self._slugify_label(workflow.name)
        specialist_label = self._determine_specialist_label(workflow)
        specialist_labels = [specialist_label] if specialist_label else None

        transition_plan = plan_state_transition(
            current_labels,
            WorkflowState.ASSIGNED,
            ensure_labels=[workflow_slug],
            specialist_labels=specialist_labels,
            clear_temporary=True,
        )

        final_labels, labels_added = self._apply_transition_plan(
            current_labels,
            transition_plan,
            extra_labels=list(workflow.trigger_labels),
        )

        assessment_section = self._render_ai_assessment_section(
            analysis,
            assigned_workflow=workflow.name,
        )

        if not dry_run:
            updated_body = upsert_section(issue.body or "", "AI Assessment", assessment_section)
            edit_kwargs: Dict[str, Any] = {"labels": final_labels}
            if updated_body != (issue.body or ""):
                edit_kwargs["body"] = updated_body
            issue.edit(**edit_kwargs)

            combined_score = analysis.combined_scores.get(workflow.name, 0.0)
            reason_codes_text = (
                ", ".join(analysis.reason_codes) if analysis.reason_codes else "None recorded"
            )
            comment = f"""🤖 **AI Workflow Assignment**

**Assigned Workflow:** {workflow.name}
**Confidence:** {combined_score:.0%}
**Content Type:** {analysis.content_type}
**Urgency:** {analysis.urgency_level}
**Labels Applied:** {', '.join(sorted(labels_added)) if labels_added else 'None (labels already present)'}
**Reason Codes:** {reason_codes_text}

AI assessment details have been recorded in the issue body under `## AI Assessment`.

**Key Topics Identified:**
{', '.join(analysis.key_topics) if analysis.key_topics else 'None identified'}

**Technical Indicators:**
{', '.join(analysis.technical_indicators) if analysis.technical_indicators else 'None identified'}

---
*This assignment was made using GitHub Models AI analysis combined with label matching.*
"""
            issue.create_comment(comment)

        return labels_added
    
    def _request_review_with_ai_context(self,
                                       issue_number: int,
                                       analysis: ContentAnalysis,
                                       dry_run: bool = False) -> List[str]:
        """Request human review with AI suggestions"""
        
        labels_added: List[str] = []
        issue = self.github.repo.get_issue(issue_number)
        current_labels = set(self._extract_label_names(issue.labels))

        needs_review_label = 'needs-review'
        if needs_review_label not in current_labels:
            if not dry_run:
                issue.add_to_labels(needs_review_label)
            labels_added.append(needs_review_label)

        if not dry_run:
            assessment_section = self._render_ai_assessment_section(analysis)
            updated_body = upsert_section(issue.body or "", "AI Assessment", assessment_section)
            if updated_body != (issue.body or ""):
                issue.edit(body=updated_body)

            suggestions = []
            for workflow_name in analysis.suggested_workflows[:3]:  # Top 3
                combined = analysis.combined_scores.get(workflow_name)
                confidence = analysis.confidence_scores.get(workflow_name, 0)
                if combined is not None:
                    suggestions.append(
                        f"- **{workflow_name}** (score: {combined:.0%}, AI confidence: {confidence:.0%})"
                    )
                else:
                    suggestions.append(
                        f"- **{workflow_name}** (AI confidence: {confidence:.0%})"
                    )

            reason_codes_text = (
                ", ".join(analysis.reason_codes) if analysis.reason_codes else "None recorded"
            )

            comment = f"""🤖 **Human Review Requested**

The AI analysis suggests these workflows but confidence is moderate:

{chr(10).join(suggestions) if suggestions else '- No clear workflow matches found'}

**AI Summary:** {analysis.summary}

**Content Type:** {analysis.content_type}
**Urgency:** {analysis.urgency_level}
**Reason Codes:** {reason_codes_text}

The AI assessment details have been recorded in the issue body under `## AI Assessment`.

Please review and either:
1. Confirm one of the suggested workflows by adding its trigger labels
2. Select a different workflow by adding appropriate labels
3. Add more context to help improve the analysis

---
*Analysis powered by GitHub Models AI*
"""
            issue.create_comment(comment)

        return labels_added
    
    def _request_clarification_with_ai_context(self,
                                              issue_number: int,
                                              analysis: ContentAnalysis,
                                              dry_run: bool = False) -> List[str]:
        """Request clarification with AI insights"""
        
        labels_added: List[str] = []
        issue = self.github.repo.get_issue(issue_number)
        current_labels = set(self._extract_label_names(issue.labels))

        clarification_label = 'needs clarification'
        if clarification_label not in current_labels:
            if not dry_run:
                issue.add_to_labels(clarification_label)
            labels_added.append(clarification_label)

        if not dry_run:
            assessment_section = self._render_ai_assessment_section(analysis)
            updated_body = upsert_section(issue.body or "", "AI Assessment", assessment_section)
            if updated_body != (issue.body or ""):
                issue.edit(body=updated_body)

            reason_codes_text = (
                ", ".join(analysis.reason_codes) if analysis.reason_codes else "None recorded"
            )
            comment = f"""🤖 **Additional Information Needed**

The AI couldn't confidently match this issue to a workflow.

**What I understood:**
{analysis.summary if analysis.summary else "Unable to determine issue purpose"}

**Topics identified:** {', '.join(analysis.key_topics) if analysis.key_topics else 'None'}
**Reason Codes:** {reason_codes_text}

To help with assignment, please:
1. Add more descriptive labels
2. Clarify the issue's purpose in the description
3. Specify the type of deliverable needed

Available workflow families:
- `entity-profiling` - Person dossiers, evidence catalogues, and risk posture analysis
- `legal-research` - Statutory digests, precedent exploration, and sentencing scenarios
- `operational-coordination` - Coordination briefs, remediation monitoring, and lead development

The AI assessment details have been recorded under `## AI Assessment` for reference.

---
*Analysis powered by GitHub Models AI*
"""
            issue.create_comment(comment)

        return labels_added
    
    def process_issues_batch(self, 
                           limit: Optional[int] = None,
                           dry_run: bool = False) -> Dict[str, Any]:
        """
        Process a batch of issues using AI-enhanced workflow assignment.
        
        Args:
            limit: Maximum number of issues to process
            dry_run: If True, don't make actual changes
            
        Returns:
            Dictionary with processing statistics and results
        """
        start_time = time.time()
        self.logger.info(
            f"Starting AI workflow assignment batch processing (limit: {limit}, dry_run: {dry_run})"
        )

        try:
            issues = self.get_unassigned_site_monitor_issues(limit)
            candidate_count = len(issues)

            self._publish_telemetry(
                "workflow_assignment.batch_start",
                {
                    'limit': limit,
                    'dry_run': dry_run,
                    'candidate_count': candidate_count,
                    'ai_enabled': self.enable_ai,
                    'assignment_mode': 'ai',
                },
            )

            if not issues:
                self.logger.info("No issues found for AI workflow assignment")
                duration = time.time() - start_time
                statistics = {
                    'auto_assigned': 0,
                    'review_requested': 0,
                    'clarification_requested': 0,
                    'errors': 0,
                }
                self._publish_telemetry(
                    "workflow_assignment.batch_summary",
                    {
                        'total_issues': candidate_count,
                        'processed': 0,
                        'duration_seconds': duration,
                        'dry_run': dry_run,
                        'status': 'empty',
                        'issue_numbers': [],
                        'error_count': 0,
                        'assignment_mode': 'ai',
                    },
                )
                return {
                    'total_issues': candidate_count,
                    'processed': 0,
                    'results': [],
                    'statistics': statistics,
                    'duration_seconds': duration,
                }

            results: List[Dict[str, Any]] = []
            statistics: Dict[str, int] = {
                'auto_assigned': 0,
                'review_requested': 0,
                'clarification_requested': 0,
                'errors': 0,
            }

            reason_counter: Counter[str] = Counter()
            coverage_values: List[float] = []
            high_coverage = 0
            partial_coverage = 0
            low_coverage = 0
            missing_entity_issues = 0
            legal_signal_counts: Counter[str] = Counter()
            statute_reference_counter: Counter[str] = Counter()
            precedent_reference_counter: Counter[str] = Counter()
            interagency_reference_counter: Counter[str] = Counter()

            for issue_data in issues:
                issue_start = time.time()
                try:
                    result = self.process_issue_with_ai(issue_data, dry_run)
                    results.append(result)

                    action = result.get('action_taken', 'error')
                    if action in statistics:
                        statistics[action] += 1
                    else:
                        statistics['errors'] += 1

                    reason_counter.update(result.get('reason_codes') or [])

                    ai_analysis = result.get('ai_analysis') or {}
                    if isinstance(ai_analysis, dict):
                        entity_summary = ai_analysis.get('entity_summary') or {}
                        if isinstance(entity_summary, dict):
                            coverage_value = entity_summary.get('coverage')
                            if isinstance(coverage_value, (int, float)):
                                coverage_float = float(coverage_value)
                                coverage_values.append(coverage_float)
                                if coverage_float >= 0.67:
                                    high_coverage += 1
                                elif coverage_float >= 0.34:
                                    partial_coverage += 1
                                else:
                                    low_coverage += 1
                            missing_entities = entity_summary.get('missing_base_entities') or []
                            if missing_entities:
                                missing_entity_issues += 1

                        legal_signals = ai_analysis.get('legal_signals') or {}
                        if isinstance(legal_signals, dict):
                            for signal_name, signal_value in legal_signals.items():
                                try:
                                    numeric_value = float(signal_value)
                                except (TypeError, ValueError):
                                    continue
                                if numeric_value > 0:
                                    legal_signal_counts[signal_name] += 1

                            for citation in legal_signals.get('statute_matches') or []:
                                normalised_citation = self._normalize_legal_reference(citation)
                                if normalised_citation:
                                    statute_reference_counter[normalised_citation] += 1
                            for precedent in legal_signals.get('precedent_matches') or []:
                                if isinstance(precedent, str) and precedent.strip():
                                    cleaned_precedent = self._normalize_legal_reference(precedent)
                                    precedent_reference_counter[cleaned_precedent] += 1
                            for agency in legal_signals.get('interagency_terms') or []:
                                if isinstance(agency, str) and agency.strip():
                                    interagency_reference_counter[agency.strip().lower()] += 1

                    self._emit_issue_result_telemetry(result, time.time() - issue_start)

                except Exception as e:  # noqa: BLE001
                    issue_number = issue_data.get('number')
                    error_message = f"Processing error: {e}"
                    error_result = {
                        'issue_number': issue_number,
                        'action_taken': 'error',
                        'message': error_message,
                        'ai_analysis': {},
                        'assigned_workflow': None,
                        'labels_added': [],
                        'dry_run': dry_run,
                    }
                    results.append(error_result)
                    statistics['errors'] += 1
                    self._emit_issue_result_telemetry(error_result, time.time() - issue_start)
                    context_issue = f"#{issue_number}" if issue_number is not None else "(unknown)"
                    log_exception(self.logger, f"Failed to process issue {context_issue}", e)
                finally:
                    time.sleep(0.5)

            duration = time.time() - start_time
            processed_count = len([r for r in results if r.get('action_taken') != 'error'])

            self.logger.info(
                f"AI batch processing completed: {processed_count}/{len(issues)} issues processed "
                f"in {duration:.1f}s"
            )

            for action, count in statistics.items():
                if count > 0:
                    self.logger.info(f"  {action}: {count}")

            status = 'success'
            if statistics['errors'] and processed_count == 0:
                status = 'error'
            elif statistics['errors']:
                status = 'partial'

            average_coverage = (
                sum(coverage_values) / len(coverage_values)
                if coverage_values
                else None
            )
            coverage_distribution = {
                'high': high_coverage,
                'partial': partial_coverage,
                'low': low_coverage,
            }
            top_reason_codes = [
                {'code': code, 'count': count}
                for code, count in reason_counter.most_common(5)
            ]
            top_statutes = statute_reference_counter.most_common(5)
            top_precedents = precedent_reference_counter.most_common(5)
            top_interagency = interagency_reference_counter.most_common(5)
            explainability_summary = {
                'average_entity_coverage': average_coverage,
                'entity_coverage_distribution': coverage_distribution,
                'issues_with_missing_entities': missing_entity_issues,
                'top_reason_codes': {code: count for code, count in reason_counter.items()},
                'legal_signal_counts': dict(legal_signal_counts),
                'statute_references': top_statutes,
                'precedent_references': top_precedents,
                'interagency_terms': top_interagency,
            }

            self._publish_telemetry(
                "workflow_assignment.batch_summary",
                {
                    'total_issues': len(issues),
                    'processed': processed_count,
                    'statistics': statistics,
                    'duration_seconds': duration,
                    'dry_run': dry_run,
                    'status': status,
                    'issue_numbers': [r.get('issue_number') for r in results],
                    'error_count': statistics.get('errors', 0),
                    'assignment_mode': 'ai',
                    'average_entity_coverage': average_coverage,
                    'entity_coverage_distribution': coverage_distribution,
                    'issues_with_missing_entities': missing_entity_issues,
                    'top_reason_codes': top_reason_codes,
                    'legal_signal_counts': dict(legal_signal_counts),
                    'statute_references': top_statutes,
                    'precedent_references': top_precedents,
                    'interagency_terms': top_interagency,
                },
            )

            return {
                'total_issues': len(issues),
                'processed': processed_count,
                'results': results,
                'statistics': statistics,
                'duration_seconds': duration,
                'explainability_summary': explainability_summary,
            }

        except Exception as e:  # noqa: BLE001
            duration = time.time() - start_time
            error_stats = {
                'auto_assigned': 0,
                'review_requested': 0,
                'clarification_requested': 0,
                'errors': 1,
            }
            self._publish_telemetry(
                "workflow_assignment.batch_summary",
                {
                    'total_issues': 0,
                    'processed': 0,
                    'statistics': error_stats,
                    'duration_seconds': duration,
                    'dry_run': dry_run,
                    'status': 'error',
                    'issue_numbers': [],
                    'error_message': str(e),
                    'error_count': 1,
                    'average_entity_coverage': None,
                    'entity_coverage_distribution': None,
                    'issues_with_missing_entities': None,
                    'top_reason_codes': [],
                    'legal_signal_counts': {},
                },
            )
            log_exception(self.logger, "AI batch processing failed", e)
            return {
                'total_issues': 0,
                'processed': 0,
                'results': [],
                'statistics': error_stats,
                'duration_seconds': duration,
                'error': str(e),
                'explainability_summary': None,
            }
    
    def get_assignment_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about current workflow assignment state.
        
        Returns:
            Dictionary with assignment statistics
        """
        try:
            # Get all site-monitor issues
            all_issues = self.github.get_issues_with_labels(['site-monitor'], state='open')
            
            stats = {
                'total_site_monitor_issues': len(all_issues),
                'unassigned': 0,
                'assigned': 0,
                'needs_clarification': 0,
                'needs_review': 0,
                'feature_labeled': 0,
                'workflow_breakdown': {},
                'label_distribution': {},
                'ai_enabled': self.enable_ai
            }
            
            for issue in all_issues:
                issue_labels = set(self._extract_label_names(issue.labels))
                
                # Count by assignment status
                if issue.assignee:
                    stats['assigned'] += 1
                else:
                    stats['unassigned'] += 1
                
                # Count special labels
                if 'needs clarification' in issue_labels:
                    stats['needs_clarification'] += 1
                if 'needs-review' in issue_labels:
                    stats['needs_review'] += 1
                if 'feature' in issue_labels:
                    stats['feature_labeled'] += 1
                
                # Count workflow assignments
                workflows = self.workflow_matcher.get_available_workflows(
                    categories=self.allowed_categories
                )
                for workflow in workflows:
                    workflow_labels = set(workflow.trigger_labels)
                    if workflow_labels.intersection(issue_labels):
                        if workflow.name not in stats['workflow_breakdown']:
                            stats['workflow_breakdown'][workflow.name] = 0
                        stats['workflow_breakdown'][workflow.name] += 1
                
                # Count label distribution
                for label_name in issue_labels:
                    if label_name not in stats['label_distribution']:
                        stats['label_distribution'][label_name] = 0
                    stats['label_distribution'][label_name] += 1
            
            return stats
            
        except Exception as e:
            log_exception(self.logger, "Failed to get assignment statistics", e)
            return {'error': str(e)}