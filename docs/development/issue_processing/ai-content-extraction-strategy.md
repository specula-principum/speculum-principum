# AI-Powered Content Extraction & Documentation Strategy

## Overview

Transform the Speculum Principum issue processor from template-based generation to AI-powered content extraction and structuring, focusing on intelligence analysis workflows for organizing information about target sites and organizations.

> **Update — 2025-09-30:** The standalone `process-copilot-issues` CLI has been retired. All Copilot-focused processing now flows through the unified `process-issues` command.

## Current State Assessment

### Existing Architecture
- **Issue Processing**: Template-based content generation with basic AI workflow assignment
- **Workflow System**: YAML-defined deliverables with static templates
- **Content Generation**: Fallback strategies with placeholder content
- **AI Usage**: Limited to workflow assignment via GitHub Models API

### Limitations
- No actual content extraction from issues
- Static template-based output
- Limited specialist workflow support
- No structured data organization for intelligence analysis

## Vision: Intelligence-Driven Documentation System

### Target Capabilities
1. **Automatic Content Extraction**: AI analyzes Copilot-assigned issues to extract structured information
2. **Specialist Workflows**: Intelligence analyst, OSINT researcher, threat analyst personas
3. **Entity Organization**: Structure information about people, places, things, events
4. **Dynamic Documentation**: AI-generated analysis rather than static templates
5. **Multi-Agent Processing**: Support for different specialist agents with unique capabilities

## Strategic Implementation Plan

### Phase 1: Foundation Enhancement (Infrastructure)

#### Step 1.1: Copilot Assignment Detection
**Objective**: Modify issue processor to identify and prioritize Copilot-assigned issues

**Implementation Areas**:
- `src/core/issue_processor.py`: Add Copilot assignment filtering
- `src/core/batch_processor.py`: Update batch discovery for assignee filtering
- `main.py`: Add CLI options for Copilot-assigned issue processing

**Changes Required**:
```python
# New method in GitHubIntegratedIssueProcessor
def get_copilot_assigned_issues(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get issues assigned to GitHub Copilot for AI processing."""
    
def is_copilot_assigned(self, issue_data: Dict[str, Any]) -> bool:
    """Check if issue is assigned to GitHub Copilot."""
    return issue_data.get('assignee') in ['github-copilot[bot]', 'copilot']
```

#### Step 1.2: AI Content Extraction Engine
**Objective**: Create core AI content extraction capabilities

**New Components**:
- `src/agents/content_extraction_agent.py`: Core AI content extraction logic
- `src/agents/specialist_agents/`: Directory for specialist agent implementations
- `src/utils/ai_prompt_builder.py`: Centralized prompt construction utilities

**Core Architecture**:
```python
class ContentExtractionAgent:
    """AI-powered content extraction from GitHub issues."""
    
    def extract_structured_data(self, issue_data: IssueData) -> StructuredContent:
        """Extract people, places, things, events from issue content."""
        
    def generate_specialist_analysis(self, content: StructuredContent, 
                                   specialist_type: str) -> AnalysisResult:
        """Generate analysis from specialist perspective."""
```

#### Step 1.3: Specialist Workflow Framework
**Objective**: Create framework for specialist-oriented workflows

**New Components**:
- `src/workflow/specialist_workflows.py`: Specialist workflow definitions
- `docs/workflow/specialists/`: Directory for specialist workflow definitions
- `src/workflow/entity_organizer.py`: Structured data organization

**Specialist Types**:
- **Intelligence Analyst**: Threat assessment, risk analysis, strategic insights
- **OSINT Researcher**: Open source intelligence gathering and verification
- **Target Profiler**: Comprehensive target organization profiling
- **Threat Hunter**: Security-focused analysis and IOC extraction
- **Business Analyst**: Commercial and operational intelligence

### Phase 2: AI Content Extraction Implementation

#### Step 2.1: Structured Data Extraction
**Objective**: Extract and categorize information from issue content

**Implementation**:
```python
@dataclass
class StructuredContent:
    """Structured content extracted from issues."""
    entities: Dict[str, List[Entity]]  # people, places, organizations, etc.
    events: List[Event]               # timeline of activities
    relationships: List[Relationship] # connections between entities
    indicators: List[Indicator]       # IOCs, TTPs, etc.
    metadata: ContentMetadata         # source, confidence, extraction_method
```

**AI Prompting Strategy**:
```python
def build_extraction_prompt(self, issue_content: str) -> str:
    return f"""Extract structured information from this intelligence report:

CONTENT:
{issue_content}

EXTRACTION REQUIREMENTS:
1. ENTITIES:
   - People: Names, roles, affiliations, contact info
   - Organizations: Companies, groups, government entities
   - Places: Locations, addresses, geographical references
   - Technical: Domains, IPs, email addresses, phone numbers

2. EVENTS:
   - Timeline of activities or incidents
   - Dates, times, locations of events
   - Participants and their roles

3. RELATIONSHIPS:
   - Connections between entities
   - Nature of relationships (employment, partnership, etc.)
   - Confidence levels

4. INDICATORS:
   - IOCs (Indicators of Compromise)
   - TTPs (Tactics, Techniques, Procedures)
   - Behavioral indicators

Return as structured JSON with confidence scores for each extraction."""
```

#### Step 2.2: Specialist Agent Implementation
**Objective**: Create AI agents with specialist perspectives

**Intelligence Analyst Agent**:
```python
class IntelligenceAnalystAgent(SpecialistAgent):
    """AI agent with intelligence analyst capabilities."""
    
    def analyze_threat_landscape(self, content: StructuredContent) -> ThreatAssessment:
        """Analyze threats and risks from extracted content."""
        
    def generate_strategic_insights(self, content: StructuredContent) -> StrategicAnalysis:
        """Generate high-level strategic analysis."""
```

**OSINT Researcher Agent**:
```python
class OSINTResearcherAgent(SpecialistAgent):
    """AI agent with OSINT research capabilities."""
    
    def verify_information(self, content: StructuredContent) -> VerificationReport:
        """Cross-reference and verify extracted information."""
        
    def identify_research_gaps(self, content: StructuredContent) -> ResearchGaps:
        """Identify areas needing additional research."""
```

#### Step 2.3: Dynamic Documentation Generation
**Objective**: Replace static templates with AI-generated documentation

**Enhanced Deliverable Generator**:
```python
class AIEnhancedDeliverableGenerator(DeliverableGenerator):
    """AI-powered deliverable generation."""
    
    def generate_ai_deliverable(self, 
                               structured_content: StructuredContent,
                               specialist_analysis: AnalysisResult,
                               deliverable_spec: DeliverableSpec) -> str:
        """Generate deliverable using AI analysis."""
```

**AI Prompting for Documentation**:
```python
def build_documentation_prompt(self, analysis: AnalysisResult, 
                              deliverable_type: str) -> str:
    return f"""Generate a professional {deliverable_type} document based on this analysis:

EXTRACTED DATA:
Entities: {analysis.entities}
Events: {analysis.events}
Relationships: {analysis.relationships}

ANALYSIS RESULTS:
{analysis.insights}

REQUIREMENTS:
- Professional intelligence document format
- Clear executive summary
- Detailed findings with confidence levels
- Actionable recommendations
- Proper citation of sources

Generate comprehensive documentation suitable for intelligence briefing."""
```

### Phase 3: Specialist Workflow Definitions

#### Step 3.1: Intelligence Analysis Workflows
**File**: `docs/workflow/specialists/intelligence-analyst.yaml`

```yaml
name: "Intelligence Analyst"
description: "Comprehensive intelligence analysis with threat assessment"
specialist_type: "intelligence_analyst"
persona: "Experienced intelligence analyst with expertise in threat assessment and strategic analysis"

trigger_conditions:
  assignee: ["github-copilot[bot]", "copilot"]
  labels: ["intelligence", "threat-analysis", "strategic"]
  content_indicators: ["threat", "adversary", "campaign", "intelligence"]

extraction_focus:
  - "threat_actors"
  - "attack_vectors"
  - "targets"
  - "capabilities"
  - "intentions"

deliverables:
  - name: "threat-assessment"
    title: "Threat Assessment Report"
    ai_prompt_template: "threat_assessment"
    required_sections: ["executive_summary", "threat_landscape", "risk_analysis", "recommendations"]
  
  - name: "entity-profile"
    title: "Target Entity Profile"
    ai_prompt_template: "entity_profiling"
    required_sections: ["organization_overview", "key_personnel", "infrastructure", "vulnerabilities"]
```

#### Step 3.2: OSINT Research Workflows
**File**: `docs/workflow/specialists/osint-researcher.yaml`

```yaml
name: "OSINT Researcher"
description: "Open source intelligence research and verification"
specialist_type: "osint_researcher"
persona: "Skilled OSINT researcher with expertise in information verification and source analysis"

extraction_focus:
  - "digital_footprint"
  - "social_media_presence"
  - "public_records"
  - "technical_infrastructure"
  - "communication_channels"

deliverables:
  - name: "osint-report"
    title: "Open Source Intelligence Report"
    ai_prompt_template: "osint_analysis"
  
  - name: "verification-matrix"
    title: "Information Verification Matrix"
    ai_prompt_template: "verification_analysis"
```

### Phase 4: Integration and Enhancement

#### Step 4.1: Multi-Agent Coordination
**Objective**: Enable multiple specialist agents to collaborate

**Implementation**:
```python
class MultiAgentOrchestrator:
    """Coordinate multiple specialist agents for comprehensive analysis."""
    
    def orchestrate_analysis(self, issue_data: IssueData, 
                           requested_specialists: List[str]) -> CombinedAnalysis:
        """Coordinate analysis across multiple specialist agents."""
```

#### Step 4.2: Enhanced CLI Integration
**Objective**: Update CLI to support new AI-powered workflows

**New CLI Options**:
```bash
# Process Copilot-assigned issues with AI
python main.py process-issues --label-filter state::assigned --batch-size 10 --verbose

# Extract content with specific specialist
python main.py extract-content --issue 123 --specialist osint-researcher

# Generate specialist deliverables
python main.py generate-analysis --issue 123 --deliverable threat-assessment
```

#### Step 4.3: Quality Assurance and Validation
**Objective**: Ensure AI-generated content meets quality standards

**Validation Framework**:
```python
class ContentValidator:
    """Validate AI-generated content for quality and accuracy."""
    
    def validate_extraction_quality(self, content: StructuredContent) -> ValidationResult:
        """Validate extracted structured content."""
    
    def validate_analysis_completeness(self, analysis: AnalysisResult) -> ValidationResult:
        """Ensure analysis meets specialist standards."""
```

## Implementation Priority and Timeline

### Phase 1 (Weeks 1-2): Foundation
1. Copilot assignment detection
2. Basic AI content extraction framework
3. Specialist workflow structure

### Phase 2 (Weeks 3-4): Core AI Implementation
1. Structured data extraction
2. First specialist agent (Intelligence Analyst)
3. AI-powered deliverable generation

### Phase 3 (Weeks 5-6): Specialist Workflows
1. Multiple specialist agent types
2. Workflow definitions
3. Enhanced documentation templates

### Phase 4 (Weeks 7-8): Integration and Polish
1. Multi-agent coordination
2. CLI enhancements
3. Quality assurance framework

## Success Metrics

1. **Content Quality**: AI-generated documents meet professional intelligence standards
2. **Extraction Accuracy**: >90% accuracy in entity and relationship extraction
3. **Processing Efficiency**: Process Copilot-assigned issues within 5 minutes
4. **Specialist Coverage**: Support for 5+ specialist types
5. **User Adoption**: Issues processed through new system show improved actionability

## Risk Mitigation

1. **AI Accuracy**: Implement confidence scoring and human validation workflows
2. **Performance**: Add caching and optimize API calls
3. **Cost Management**: Monitor AI API usage and implement rate limiting
4. **Fallback Systems**: Maintain template-based generation as backup

This strategy provides a clear roadmap for transforming the issue processor into an AI-powered intelligence documentation system while maintaining the existing architecture's strengths.