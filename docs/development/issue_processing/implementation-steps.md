# Implementation Steps: AI Content Extraction Feature

## Step-by-Step Implementation Guide

This document provides detailed implementation steps for transforming the issue processor to utilize AI-powered content extraction and specialist workflows.

> **Update — 2025-09-30:** Steps referring to the standalone `process-copilot-issues` CLI are now historical. The unified `process-issues` command owns Copilot handoff and specialist assignment.

## Phase 1: Foundation Enhancement

### Step 1.1: Copilot Assignment Detection

#### 1.1.1: Modify Issue Processor Core
**File**: `src/core/issue_processor.py`

**Add new methods**:
```python
def get_copilot_assigned_issues(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get issues assigned to GitHub Copilot for AI processing.
    
    Args:
        limit: Maximum number of issues to return
        
    Returns:
        List of Copilot-assigned issue data
    """
    try:
        # Query issues assigned to Copilot
        copilot_usernames = ['github-copilot[bot]', 'copilot', 'github-actions[bot]']
        
        issues = []
        for username in copilot_usernames:
            user_issues = self.github.get_issues_assigned_to(username, state='open')
            for issue in user_issues:
                if self._should_process_copilot_issue(issue):
                    issues.append(self._convert_issue_to_dict(issue))
                    if limit and len(issues) >= limit:
                        return issues[:limit]
        
        return issues
    except Exception as e:
        self.logger.error(f"Failed to get Copilot-assigned issues: {e}")
        return []

def is_copilot_assigned(self, issue_data: Union[Dict[str, Any], Any]) -> bool:
    """
    Check if issue is assigned to GitHub Copilot.
    
    Args:
        issue_data: Issue data or GitHub issue object
        
    Returns:
        True if assigned to Copilot
    """
    if isinstance(issue_data, dict):
        assignee = issue_data.get('assignee')
    else:
        assignee = getattr(issue_data, 'assignee', None)
        if assignee:
            assignee = assignee.login if hasattr(assignee, 'login') else str(assignee)
    
    copilot_identifiers = ['github-copilot[bot]', 'copilot', 'github-actions[bot]']
    return assignee in copilot_identifiers

def _should_process_copilot_issue(self, issue) -> bool:
    """Determine if Copilot-assigned issue should be processed."""
    # Check for required labels or content indicators
    labels = {label.name for label in issue.labels}
    content_indicators = ['intelligence', 'research', 'analysis', 'target', 'osint']
    
    # Must have at least one processing indicator
    return bool(labels.intersection(content_indicators) or 
               any(indicator in (issue.title + issue.body).lower() 
                   for indicator in content_indicators))
```

#### 1.1.2: Update Batch Processor
**File**: `src/core/batch_processor.py`

> **Historical note:** Earlier iterations introduced `process_copilot_assigned_issues()` to wrap Copilot-specific batching. As of 2025-09-30, this helper has been removed. Ensure `process_issues()` respects workflow state filters (`state::assigned`, `state::copilot`) so Copilot work queues route through the unified path.

#### 1.1.3: Update CLI Handler
**File**: `main.py`

> **Historical note:** The dedicated `process-copilot-issues` parser/handler has been retired. Extend `process-issues` CLI options (e.g., `--label-filter`, `--assignee-filter`, `--from-monitor`) to cover Copilot handoff scenarios and maintain dry-run safeguards.

### Step 1.2: AI Content Extraction Engine

#### 1.2.1: Create Content Extraction Agent
**File**: `src/agents/content_extraction_agent.py`

```python
"""
AI-powered content extraction from GitHub issues for intelligence analysis.
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from ..utils.ai_prompt_builder import AIPromptBuilder
from ..clients.github_models_client import GitHubModelsClient
from ..utils.logging_config import get_logger, log_exception


@dataclass
class Entity:
    """Represents an extracted entity (person, place, organization, etc.)"""
    name: str
    type: str  # person, organization, place, technical, etc.
    attributes: Dict[str, Any]  # roles, contact_info, location, etc.
    confidence: float
    source_references: List[str]  # where in the content this was found


@dataclass
class Event:
    """Represents an extracted event or incident"""
    description: str
    date: Optional[str]
    location: Optional[str]
    participants: List[str]  # entity names involved
    event_type: str  # incident, meeting, campaign, etc.
    confidence: float
    source_references: List[str]


@dataclass
class Relationship:
    """Represents a relationship between entities"""
    source_entity: str
    target_entity: str
    relationship_type: str  # employment, partnership, ownership, etc.
    description: str
    confidence: float
    source_references: List[str]


@dataclass
class Indicator:
    """Represents an indicator of compromise or behavior"""
    value: str
    indicator_type: str  # ip, domain, email, behavior, etc.
    description: str
    confidence: float
    source_references: List[str]


@dataclass
class ContentMetadata:
    """Metadata about the extraction process"""
    extraction_timestamp: str
    extraction_method: str  # ai, manual, hybrid
    source_issue_number: int
    confidence_threshold: float
    model_version: str


@dataclass
class StructuredContent:
    """Complete structured content extracted from an issue"""
    entities: Dict[str, List[Entity]]  # grouped by type
    events: List[Event]
    relationships: List[Relationship]
    indicators: List[Indicator]
    metadata: ContentMetadata
    raw_extractions: Dict[str, Any]  # for debugging/validation


class ContentExtractionAgent:
    """
    AI-powered content extraction agent for intelligence analysis.
    
    Extracts structured information from GitHub issues including entities,
    relationships, events, and indicators for further specialist analysis.
    """
    
    def __init__(self, 
                 github_token: str,
                 model: str = "gpt-4o",
                 confidence_threshold: float = 0.7):
        """
        Initialize content extraction agent.
        
        Args:
            github_token: GitHub API token for Models API access
            model: AI model to use for extraction
            confidence_threshold: Minimum confidence for extracted items
        """
        self.logger = get_logger(__name__)
        self.ai_client = GitHubModelsClient(github_token, model=model)
        self.prompt_builder = AIPromptBuilder()
        self.confidence_threshold = confidence_threshold
        self.model = model
    
    def extract_structured_data(self, 
                               issue_data: Any,
                               extraction_focus: Optional[List[str]] = None) -> StructuredContent:
        """
        Extract structured data from issue content.
        
        Args:
            issue_data: Issue data object or dictionary
            extraction_focus: Areas to focus extraction on
            
        Returns:
            StructuredContent with extracted entities, events, relationships, indicators
        """
        try:
            # Prepare content for extraction
            content = self._prepare_content_for_extraction(issue_data)
            
            # Build extraction prompt
            prompt = self.prompt_builder.build_extraction_prompt(
                content=content,
                focus_areas=extraction_focus or []
            )
            
            # Call AI for extraction
            raw_response = self._call_extraction_api(prompt)
            
            # Parse and structure response
            structured_content = self._parse_extraction_response(
                raw_response, 
                issue_data
            )
            
            self.logger.info(
                f"Extracted {len(structured_content.entities)} entity types, "
                f"{len(structured_content.events)} events, "
                f"{len(structured_content.relationships)} relationships, "
                f"{len(structured_content.indicators)} indicators"
            )
            
            return structured_content
            
        except Exception as e:
            log_exception(self.logger, "Content extraction failed", e)
            # Return empty but valid structured content
            return self._create_empty_structured_content(issue_data)
    
    def _prepare_content_for_extraction(self, issue_data: Any) -> str:
        """Prepare issue content for AI extraction."""
        if isinstance(issue_data, dict):
            title = issue_data.get('title', '')
            body = issue_data.get('body', '')
            labels = issue_data.get('labels', [])
        else:
            title = getattr(issue_data, 'title', '')
            body = getattr(issue_data, 'body', '')
            labels = [label.name if hasattr(label, 'name') else str(label) 
                     for label in getattr(issue_data, 'labels', [])]
        
        return f"""TITLE: {title}

LABELS: {', '.join(labels)}

CONTENT:
{body}"""
    
    def _call_extraction_api(self, prompt: str) -> Dict[str, Any]:
        """Call AI API for content extraction."""
        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert intelligence analyst specializing in extracting structured information from reports. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Lower temperature for more consistent extraction
                max_tokens=2000
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"AI extraction API call failed: {e}")
            raise
    
    def _parse_extraction_response(self, 
                                  response: Dict[str, Any], 
                                  issue_data: Any) -> StructuredContent:
        """Parse AI response into StructuredContent."""
        try:
            # Extract content from AI response
            if "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                
                # Clean up JSON response
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:-3]
                elif content.startswith("```"):
                    content = content[3:-3]
                
                extraction_data = json.loads(content)
            else:
                raise ValueError("Invalid AI response structure")
            
            # Convert to structured objects
            entities = self._convert_entities(extraction_data.get('entities', {}))
            events = self._convert_events(extraction_data.get('events', []))
            relationships = self._convert_relationships(extraction_data.get('relationships', []))
            indicators = self._convert_indicators(extraction_data.get('indicators', []))
            
            # Create metadata
            issue_number = (issue_data.get('number') if isinstance(issue_data, dict) 
                           else getattr(issue_data, 'number', 0))
            
            metadata = ContentMetadata(
                extraction_timestamp=datetime.now().isoformat(),
                extraction_method="ai",
                source_issue_number=issue_number,
                confidence_threshold=self.confidence_threshold,
                model_version=self.model
            )
            
            return StructuredContent(
                entities=entities,
                events=events,
                relationships=relationships,
                indicators=indicators,
                metadata=metadata,
                raw_extractions=extraction_data
            )
            
        except Exception as e:
            log_exception(self.logger, "Failed to parse extraction response", e)
            return self._create_empty_structured_content(issue_data)
    
    def _convert_entities(self, entities_data: Dict[str, List[Dict]]) -> Dict[str, List[Entity]]:
        """Convert raw entity data to Entity objects."""
        entities = {}
        for entity_type, entity_list in entities_data.items():
            entities[entity_type] = []
            for entity_data in entity_list:
                if entity_data.get('confidence', 0) >= self.confidence_threshold:
                    entity = Entity(
                        name=entity_data.get('name', ''),
                        type=entity_type,
                        attributes=entity_data.get('attributes', {}),
                        confidence=entity_data.get('confidence', 0.0),
                        source_references=entity_data.get('source_references', [])
                    )
                    entities[entity_type].append(entity)
        return entities
    
    def _convert_events(self, events_data: List[Dict]) -> List[Event]:
        """Convert raw event data to Event objects."""
        events = []
        for event_data in events_data:
            if event_data.get('confidence', 0) >= self.confidence_threshold:
                event = Event(
                    description=event_data.get('description', ''),
                    date=event_data.get('date'),
                    location=event_data.get('location'),
                    participants=event_data.get('participants', []),
                    event_type=event_data.get('event_type', 'unknown'),
                    confidence=event_data.get('confidence', 0.0),
                    source_references=event_data.get('source_references', [])
                )
                events.append(event)
        return events
    
    def _convert_relationships(self, relationships_data: List[Dict]) -> List[Relationship]:
        """Convert raw relationship data to Relationship objects."""
        relationships = []
        for rel_data in relationships_data:
            if rel_data.get('confidence', 0) >= self.confidence_threshold:
                relationship = Relationship(
                    source_entity=rel_data.get('source_entity', ''),
                    target_entity=rel_data.get('target_entity', ''),
                    relationship_type=rel_data.get('relationship_type', ''),
                    description=rel_data.get('description', ''),
                    confidence=rel_data.get('confidence', 0.0),
                    source_references=rel_data.get('source_references', [])
                )
                relationships.append(relationship)
        return relationships
    
    def _convert_indicators(self, indicators_data: List[Dict]) -> List[Indicator]:
        """Convert raw indicator data to Indicator objects."""
        indicators = []
        for ind_data in indicators_data:
            if ind_data.get('confidence', 0) >= self.confidence_threshold:
                indicator = Indicator(
                    value=ind_data.get('value', ''),
                    indicator_type=ind_data.get('indicator_type', ''),
                    description=ind_data.get('description', ''),
                    confidence=ind_data.get('confidence', 0.0),
                    source_references=ind_data.get('source_references', [])
                )
                indicators.append(indicator)
        return indicators
    
    def _create_empty_structured_content(self, issue_data: Any) -> StructuredContent:
        """Create empty structured content for error cases."""
        issue_number = (issue_data.get('number') if isinstance(issue_data, dict) 
                       else getattr(issue_data, 'number', 0))
        
        metadata = ContentMetadata(
            extraction_timestamp=datetime.now().isoformat(),
            extraction_method="fallback",
            source_issue_number=issue_number,
            confidence_threshold=self.confidence_threshold,
            model_version=self.model
        )
        
        return StructuredContent(
            entities={},
            events=[],
            relationships=[],
            indicators=[],
            metadata=metadata,
            raw_extractions={}
        )
```

#### 1.2.2: Create AI Prompt Builder
**File**: `src/utils/ai_prompt_builder.py`

```python
"""
Centralized AI prompt building utilities for content extraction and analysis.
"""

from typing import List, Dict, Any, Optional


class AIPromptBuilder:
    """
    Centralized prompt builder for AI-powered content extraction and analysis.
    """
    
    def build_extraction_prompt(self, 
                               content: str,
                               focus_areas: Optional[List[str]] = None) -> str:
        """
        Build prompt for structured content extraction.
        
        Args:
            content: Raw content to extract from
            focus_areas: Specific areas to focus extraction on
            
        Returns:
            Formatted extraction prompt
        """
        focus_section = ""
        if focus_areas:
            focus_section = f"""
EXTRACTION FOCUS AREAS:
{chr(10).join(f"- {area}" for area in focus_areas)}
"""
        
        return f"""Extract structured information from this intelligence content for analysis:

{focus_section}
CONTENT TO ANALYZE:
{content[:3000]}  # Limit content to avoid token limits

EXTRACTION REQUIREMENTS:

1. ENTITIES (extract with confidence scores 0.0-1.0):
   - people: Names, roles, titles, contact information, affiliations
   - organizations: Companies, government entities, groups, agencies
   - places: Locations, addresses, geographical references, facilities
   - technical: Domains, IP addresses, email addresses, phone numbers, systems

2. EVENTS (extract with confidence scores 0.0-1.0):
   - Timeline of activities, incidents, meetings, campaigns
   - Dates, times, locations, participants, event types
   - Connections between events

3. RELATIONSHIPS (extract with confidence scores 0.0-1.0):
   - Connections between entities (employment, partnership, ownership, etc.)
   - Nature and strength of relationships
   - Hierarchical structures

4. INDICATORS (extract with confidence scores 0.0-1.0):
   - IOCs (Indicators of Compromise): malicious IPs, domains, file hashes
   - TTPs (Tactics, Techniques, Procedures): attack methods, tools
   - Behavioral indicators: patterns, anomalies, signatures

Return response as valid JSON with this exact structure:
{{
  "entities": {{
    "people": [
      {{
        "name": "person name",
        "attributes": {{
          "role": "job title",
          "organization": "company name",
          "contact_info": {{}}
        }},
        "confidence": 0.9,
        "source_references": ["paragraph 1", "section 2"]
      }}
    ],
    "organizations": [...],
    "places": [...],
    "technical": [...]
  }},
  "events": [
    {{
      "description": "event description",
      "date": "2024-01-15" or null,
      "location": "location" or null,
      "participants": ["entity names"],
      "event_type": "incident/meeting/campaign/other",
      "confidence": 0.8,
      "source_references": ["reference text"]
    }}
  ],
  "relationships": [
    {{
      "source_entity": "entity 1",
      "target_entity": "entity 2", 
      "relationship_type": "employment/partnership/ownership/other",
      "description": "relationship description",
      "confidence": 0.85,
      "source_references": ["reference text"]
    }}
  ],
  "indicators": [
    {{
      "value": "indicator value",
      "indicator_type": "ip/domain/email/behavior/other",
      "description": "indicator description",
      "confidence": 0.75,
      "source_references": ["reference text"]
    }}
  ]
}}

IMPORTANT: Only include information explicitly mentioned in the content. Include confidence scores based on how clearly each item is stated in the source material."""

    def build_specialist_analysis_prompt(self,
                                       structured_content: Dict[str, Any],
                                       specialist_type: str,
                                       deliverable_type: str) -> str:
        """
        Build prompt for specialist analysis based on extracted content.
        
        Args:
            structured_content: Previously extracted structured content
            specialist_type: Type of specialist (intelligence-analyst, osint-researcher, etc.)
            deliverable_type: Type of deliverable to generate
            
        Returns:
            Formatted specialist analysis prompt
        """
        specialist_personas = {
            "intelligence-analyst": "You are a senior intelligence analyst with 10+ years of experience in threat assessment, strategic analysis, and risk evaluation. You specialize in synthesizing complex information into actionable intelligence.",
            "osint-researcher": "You are an expert OSINT researcher with deep knowledge of open source intelligence techniques, information verification, and digital footprint analysis.",
            "target-profiler": "You are a professional target profiling specialist with expertise in comprehensive organizational analysis, stakeholder mapping, and operational intelligence.",
            "threat-hunter": "You are a cybersecurity threat hunter with extensive experience in threat intelligence, IOC analysis, and adversary tracking."
        }
        
        persona = specialist_personas.get(specialist_type, 
                                        "You are an intelligence professional with broad analytical expertise.")
        
        return f"""{persona}

Analyze the following extracted intelligence data and generate a comprehensive {deliverable_type}:

EXTRACTED DATA:
Entities: {structured_content.get('entities', {})}
Events: {structured_content.get('events', [])}
Relationships: {structured_content.get('relationships', [])}
Indicators: {structured_content.get('indicators', [])}

Generate a professional intelligence document with:

1. EXECUTIVE SUMMARY (2-3 paragraphs)
   - Key findings and their significance
   - Primary threats or opportunities identified
   - Critical recommendations

2. DETAILED ANALYSIS
   - Comprehensive analysis of extracted entities and their roles
   - Timeline analysis of events and their implications
   - Relationship mapping and network analysis
   - Indicator analysis and threat assessment

3. INTELLIGENCE GAPS
   - Areas requiring additional collection
   - Information that needs verification
   - Missing pieces for complete picture

4. ACTIONABLE RECOMMENDATIONS
   - Immediate actions based on findings
   - Long-term strategic recommendations
   - Risk mitigation strategies

5. CONFIDENCE ASSESSMENT
   - Overall confidence in analysis
   - Reliability of sources
   - Areas of uncertainty

Format as professional intelligence document with clear sections, bullet points where appropriate, and confidence levels for major assessments. Use intelligence community standards for confidence expressions (High/Medium/Low confidence)."""

    def build_verification_prompt(self,
                                 content_to_verify: str,
                                 verification_type: str = "general") -> str:
        """Build prompt for information verification and source analysis."""
        
        return f"""As an information verification specialist, analyze this content for accuracy and reliability:

CONTENT TO VERIFY:
{content_to_verify}

VERIFICATION REQUIREMENTS:

1. SOURCE ANALYSIS:
   - Assess credibility of information sources
   - Identify potential biases or limitations
   - Evaluate source access and expertise

2. CONSISTENCY CHECK:
   - Identify any internal contradictions
   - Check for logical consistency
   - Note any implausible claims

3. VERIFICATION OPPORTUNITIES:
   - Suggest ways to verify key claims
   - Identify corroborating sources needed
   - Recommend additional research directions

4. RELIABILITY ASSESSMENT:
   - Rate overall reliability (High/Medium/Low)
   - Identify most/least reliable elements
   - Suggest confidence levels for key facts

Return analysis in structured format with specific recommendations for verification actions."""
```

### Step 1.3: Basic Specialist Framework

#### 1.3.1: Create Specialist Agent Base Class
**File**: `src/agents/specialist_agents/__init__.py`

```python
"""
Specialist agents for intelligence analysis workflows.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from ..content_extraction_agent import StructuredContent


@dataclass
class AnalysisResult:
    """Result of specialist analysis."""
    specialist_type: str
    analysis_type: str
    findings: Dict[str, Any]
    recommendations: Dict[str, Any]
    confidence_assessment: Dict[str, float]
    intelligence_gaps: List[str]
    generated_content: str
    metadata: Dict[str, Any]


class SpecialistAgent(ABC):
    """Base class for specialist intelligence agents."""
    
    def __init__(self, ai_client, prompt_builder):
        """Initialize specialist agent with AI capabilities."""
        self.ai_client = ai_client
        self.prompt_builder = prompt_builder
        self.specialist_type = self.__class__.__name__.lower().replace('agent', '')
    
    @abstractmethod
    def analyze(self, structured_content: StructuredContent, 
                analysis_type: str = "general") -> AnalysisResult:
        """Perform specialist analysis on structured content."""
        pass
    
    @abstractmethod
    def generate_deliverable(self, analysis_result: AnalysisResult,
                           deliverable_spec: Dict[str, Any]) -> str:
        """Generate deliverable document from analysis results."""
        pass
    
    def _call_specialist_ai(self, prompt: str) -> Dict[str, Any]:
        """Call AI with specialist-specific configuration."""
        return self.ai_client.chat_completion(
            messages=[
                {
                    "role": "system", 
                    "content": f"You are a {self.specialist_type} specialist. Provide professional intelligence analysis."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3000
        )
```

This implementation plan provides the foundational steps needed to begin transforming the system. Each step includes specific file changes, code additions, and architectural decisions that other agents can follow to implement the AI-powered content extraction feature.

The strategy focuses on:
1. **Incremental Implementation**: Each step builds on the previous one
2. **Clear Specifications**: Detailed code examples and file locations
3. **Maintainable Architecture**: Proper separation of concerns and extensibility
4. **Error Handling**: Robust fallback mechanisms
5. **Testing Hooks**: Structure that supports unit testing and validation

Would you like me to continue with the remaining phases or focus on any specific aspect of the implementation?