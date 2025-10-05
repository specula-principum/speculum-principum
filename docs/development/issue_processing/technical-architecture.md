# AI Content Extraction: Technical Architecture

## System Architecture Overview

This document outlines the technical architecture for the AI-powered content extraction and specialist analysis system.

> **Update — 2025-09-30:** The dedicated `process-copilot-issues` CLI has been retired. Use the unified `process-issues` command for Copilot handoff and specialist guidance generation.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           GitHub Issues                              │
│                    (Assigned to Copilot)                           │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Issue Processor                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │ Copilot Issue   │    │ Workflow        │    │ Content         │ │
│  │ Detector        │    │ Assignment      │    │ Preparation     │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Content Extraction Engine                            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │ AI Prompt       │    │ GitHub Models   │    │ Response        │ │
│  │ Builder         │    │ API Client      │    │ Parser          │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 Structured Content                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │ Entities        │    │ Relationships   │    │ Events &        │ │
│  │ (People, Orgs)  │    │ & Networks      │    │ Indicators      │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Specialist Agents                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │ Intelligence    │  │ OSINT           │  │ Target          │ ... │
│  │ Analyst         │  │ Researcher      │  │ Profiler        │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Document Generation                                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │ AI-Powered      │    │ Template        │    │ Quality         │ │
│  │ Content Gen     │    │ Processing      │    │ Validation      │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Output Management                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │ Git Branch      │    │ File Generation │    │ Issue Update    │ │
│  │ Creation        │    │ & Commit        │    │ & Notification  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Enhanced Issue Processor

#### Current vs Enhanced Flow

**Current Flow:**
```
Issue → Label Detection → Template Workflow → Static Content → Git Commit
```

**Enhanced Flow:**
```
Copilot Issue → AI Content Extraction → Specialist Analysis → AI Document Generation → Git Commit
```

#### Key Enhancements

**File**: `src/core/issue_processor.py`

```python
class AIEnhancedIssueProcessor(GitHubIntegratedIssueProcessor):
    """Enhanced issue processor with AI content extraction capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize AI components
        self.content_extractor = ContentExtractionAgent(
            github_token=kwargs.get('github_token'),
            confidence_threshold=self.config.ai.confidence_thresholds.entity_extraction
        )
        
        # Initialize specialist agents
        self.specialist_agents = self._initialize_specialist_agents()
        
        # Enhanced deliverable generator with AI
        self.ai_deliverable_generator = AIEnhancedDeliverableGenerator(
            templates_dir=self.config.agent.template_directory,
            output_dir=self.output_base_dir,
            ai_client=self.content_extractor.ai_client
        )
    
    async def process_copilot_issue(self, issue_number: int) -> ProcessingResult:
        """Process Copilot-assigned issue with AI extraction."""
        
        # 1. Retrieve and validate Copilot assignment
        issue_data = await self._get_and_validate_copilot_issue(issue_number)
        
        # 2. Extract structured content using AI
        structured_content = await self._extract_structured_content(issue_data)
        
        # 3. Assign specialist based on content analysis
        specialist_type = await self._assign_specialist(structured_content, issue_data)
        
        # 4. Perform specialist analysis
        analysis_result = await self._perform_specialist_analysis(
            structured_content, specialist_type
        )
        
        # 5. Generate deliverables with AI
        deliverables = await self._generate_ai_deliverables(
            analysis_result, issue_data
        )
        
        # 6. Commit and update issue
        return await self._finalize_processing(
            issue_data, deliverables, analysis_result
        )
```

### 2. Content Extraction Pipeline

#### Extraction Stages

```python
class ExtractionPipeline:
    """Multi-stage content extraction pipeline."""
    
    async def extract_content(self, issue_data: IssueData) -> StructuredContent:
        """Execute full extraction pipeline."""
        
        # Stage 1: Content Preparation
        prepared_content = self._prepare_content(issue_data)
        
        # Stage 2: Entity Extraction
        entities = await self._extract_entities(prepared_content)
        
        # Stage 3: Relationship Mapping
        relationships = await self._extract_relationships(entities, prepared_content)
        
        # Stage 4: Event Timeline Extraction
        events = await self._extract_events(prepared_content, entities)
        
        # Stage 5: Indicator Extraction
        indicators = await self._extract_indicators(prepared_content)
        
        # Stage 6: Cross-validation and Confidence Scoring
        validated_content = self._validate_and_score(
            entities, relationships, events, indicators
        )
        
        return validated_content
```

#### AI Prompt Templates

**Entity Extraction Prompt:**
```python
ENTITY_EXTRACTION_PROMPT = """
As an expert intelligence analyst, extract structured entity information from this content:

{content}

Extract the following entity types with high accuracy:

1. PEOPLE:
   - Names (including aliases, nicknames)
   - Titles and roles
   - Organizations/affiliations
   - Contact information (email, phone, social media)
   - Location information

2. ORGANIZATIONS:
   - Company/agency names
   - Organizational structure
   - Business type/sector
   - Location/headquarters
   - Key relationships

3. PLACES:
   - Specific addresses
   - Geographic regions
   - Facilities/buildings
   - Operational locations

4. TECHNICAL:
   - Domain names
   - IP addresses
   - Email addresses
   - Phone numbers
   - System/software names

For each entity, provide:
- Confidence score (0.0-1.0)
- Source text reference
- Key attributes
- Potential aliases or variations

Return as structured JSON with exact schema provided.
"""
```

### 3. Specialist Agent Architecture

#### Base Agent Framework

```python
class SpecialistAgent(ABC):
    """Abstract base class for specialist intelligence agents."""
    
    def __init__(self, ai_client: GitHubModelsClient, config: SpecialistConfig):
        self.ai_client = ai_client
        self.config = config
        self.specialist_type = self.__class__.__name__.lower()
        
    @abstractmethod
    async def analyze(self, structured_content: StructuredContent) -> AnalysisResult:
        """Perform specialist-specific analysis."""
        pass
    
    @abstractmethod  
    async def generate_deliverable(self, analysis: AnalysisResult, 
                                 spec: DeliverableSpec) -> str:
        """Generate specialist deliverable document."""
        pass
    
    async def _execute_analysis_workflow(self, content: StructuredContent) -> AnalysisResult:
        """Execute multi-stage analysis workflow."""
        
        # Stage 1: Initial Assessment
        initial_assessment = await self._initial_assessment(content)
        
        # Stage 2: Deep Analysis
        deep_analysis = await self._deep_analysis(content, initial_assessment)
        
        # Stage 3: Synthesis and Conclusions
        synthesis = await self._synthesize_findings(deep_analysis)
        
        # Stage 4: Recommendations Generation
        recommendations = await self._generate_recommendations(synthesis)
        
        return AnalysisResult(
            specialist_type=self.specialist_type,
            initial_assessment=initial_assessment,
            deep_analysis=deep_analysis,
            synthesis=synthesis,
            recommendations=recommendations
        )
```

#### Intelligence Analyst Agent

```python
class IntelligenceAnalystAgent(SpecialistAgent):
    """Specialist agent for comprehensive intelligence analysis."""
    
    async def analyze(self, structured_content: StructuredContent) -> AnalysisResult:
        """Perform intelligence analysis focused on threats and strategic implications."""
        
        # Build analysis prompt
        prompt = self._build_intelligence_analysis_prompt(structured_content)
        
        # Call AI for analysis
        response = await self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": self._get_analyst_persona()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=4000
        )
        
        # Parse and structure response
        return self._parse_intelligence_analysis(response, structured_content)
    
    def _get_analyst_persona(self) -> str:
        return """You are a senior intelligence analyst with 15+ years of experience in:
        - Threat assessment and analysis
        - Strategic intelligence evaluation  
        - Geopolitical analysis
        - Risk assessment
        - Intelligence product development
        
        Your analysis should be thorough, professional, and actionable for decision-makers.
        Use intelligence community confidence levels and maintain analytical objectivity."""
    
    def _build_intelligence_analysis_prompt(self, content: StructuredContent) -> str:
        return f"""
        Conduct comprehensive intelligence analysis on the following extracted data:
        
        ENTITIES: {self._format_entities_for_prompt(content.entities)}
        RELATIONSHIPS: {self._format_relationships_for_prompt(content.relationships)}
        EVENTS: {self._format_events_for_prompt(content.events)}
        INDICATORS: {self._format_indicators_for_prompt(content.indicators)}
        
        Provide analysis covering:
        
        1. THREAT LANDSCAPE ASSESSMENT
           - Primary threats identified
           - Threat actor capabilities and intentions
           - Attack vectors and vulnerabilities
           - Strategic implications
        
        2. RISK EVALUATION
           - Immediate risks and their likelihood
           - Long-term strategic risks
           - Risk mitigation priorities
        
        3. INTELLIGENCE GAPS
           - Missing information critical for assessment
           - Additional collection requirements
           - Verification needs
        
        4. ACTIONABLE RECOMMENDATIONS
           - Immediate actions required
           - Strategic response options
           - Resource allocation recommendations
        
        Format response as structured intelligence product suitable for briefing senior leadership.
        """
```

### 4. AI-Enhanced Document Generation

#### Dynamic Content Generation

```python
class AIEnhancedDeliverableGenerator(DeliverableGenerator):
    """AI-powered deliverable generation with dynamic content creation."""
    
    def __init__(self, *args, ai_client: GitHubModelsClient, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_client = ai_client
        
    async def generate_ai_deliverable(self, 
                                    analysis_result: AnalysisResult,
                                    deliverable_spec: DeliverableSpec,
                                    issue_data: IssueData) -> str:
        """Generate deliverable using AI analysis and content generation."""
        
        # Build document generation prompt
        prompt = self._build_document_prompt(
            analysis_result, deliverable_spec, issue_data
        )
        
        # Generate content with AI
        content = await self._generate_content_with_ai(prompt, deliverable_spec)
        
        # Apply template formatting
        formatted_content = self._apply_template_formatting(
            content, deliverable_spec, issue_data
        )
        
        # Validate content quality
        self._validate_generated_content(formatted_content, deliverable_spec)
        
        return formatted_content
    
    def _build_document_prompt(self, 
                              analysis: AnalysisResult,
                              spec: DeliverableSpec,
                              issue_data: IssueData) -> str:
        """Build comprehensive document generation prompt."""
        
        return f"""
        Generate a professional {spec.name} document based on this intelligence analysis:
        
        ANALYSIS RESULTS:
        {self._format_analysis_for_prompt(analysis)}
        
        DOCUMENT REQUIREMENTS:
        - Type: {spec.type}
        - Format: {spec.format}
        - Required Sections: {spec.sections}
        - Target Audience: Intelligence professionals and decision-makers
        
        DOCUMENT SPECIFICATIONS:
        - Professional intelligence document format
        - Clear executive summary (2-3 paragraphs)
        - Detailed findings with confidence assessments
        - Actionable recommendations
        - Proper source attribution
        - Intelligence community standards
        
        Generate comprehensive, professional content suitable for intelligence briefings.
        Use appropriate classification markings and confidence levels.
        """
```

### 5. Quality Assurance Framework

#### Content Validation Pipeline

```python
class ContentValidator:
    """Comprehensive content quality validation."""
    
    async def validate_extraction_quality(self, 
                                        content: StructuredContent) -> ValidationResult:
        """Validate extracted content quality and accuracy."""
        
        validations = []
        
        # Entity validation
        entity_validation = await self._validate_entities(content.entities)
        validations.append(entity_validation)
        
        # Relationship validation  
        relationship_validation = await self._validate_relationships(content.relationships)
        validations.append(relationship_validation)
        
        # Confidence score validation
        confidence_validation = self._validate_confidence_scores(content)
        validations.append(confidence_validation)
        
        # Source reference validation
        source_validation = self._validate_source_references(content)
        validations.append(source_validation)
        
        return ValidationResult(
            overall_score=self._calculate_overall_score(validations),
            validations=validations,
            recommendations=self._generate_improvement_recommendations(validations)
        )
    
    async def validate_analysis_completeness(self, 
                                           analysis: AnalysisResult) -> ValidationResult:
        """Validate specialist analysis completeness and quality."""
        
        checks = [
            self._check_executive_summary_quality(analysis),
            self._check_finding_depth(analysis),
            self._check_recommendation_actionability(analysis),
            self._check_confidence_assessment_presence(analysis),
            self._check_intelligence_gap_identification(analysis)
        ]
        
        return ValidationResult(
            overall_score=sum(check.score for check in checks) / len(checks),
            checks=checks,
            passed=all(check.passed for check in checks)
        )
```

### 6. Processing Orchestration

#### Enhanced Orchestrator

```python
class AIProcessingOrchestrator(ProcessingOrchestrator):
    """Enhanced orchestrator for AI-powered processing workflows."""
    
    async def orchestrate_copilot_issue_processing(self, 
                                                  issue_numbers: List[int],
                                                  specialist_filter: Optional[str] = None) -> BatchResult:
        """Orchestrate AI-powered processing of Copilot-assigned issues."""
        
        results = []
        
        for issue_number in issue_numbers:
            try:
                # Process with AI extraction and specialist analysis
                result = await self._process_single_copilot_issue(
                    issue_number, specialist_filter
                )
                results.append(result)
                
            except Exception as e:
                # Handle individual issue failures gracefully
                error_result = ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.ERROR,
                    error_message=str(e)
                )
                results.append(error_result)
        
        return BatchResult(
            total_processed=len(results),
            successful=len([r for r in results if r.status == IssueProcessingStatus.COMPLETED]),
            failed=len([r for r in results if r.status == IssueProcessingStatus.ERROR]),
            results=results
        )
    
    async def _process_single_copilot_issue(self, 
                                          issue_number: int,
                                          specialist_filter: Optional[str] = None) -> ProcessingResult:
        """Process single Copilot-assigned issue with full AI pipeline."""
        
        # Initialize AI-enhanced processor
        ai_processor = AIEnhancedIssueProcessor(
            github_token=self.github_token,
            repository=self.repository,
            config_path=self.config_path
        )
        
        # Process with AI extraction
        return await ai_processor.process_copilot_issue(issue_number)
```

## Integration Points

### 1. CLI Integration

```bash
# Unified AI-powered command
python main.py process-issues --label-filter state::assigned --batch-size 5 --verbose
python main.py extract-content --issue 123 --specialist osint-researcher  
python main.py generate-analysis --issue 123 --deliverable threat-assessment
```

### 2. GitHub Actions Integration

```yaml
# .github/workflows/ai-content-processing.yml
name: AI Content Processing
on:
  issues:
    types: [assigned]
    
jobs:
    process-issues:
        if: contains(github.event.issue.assignees.*.login, 'github-copilot[bot]')
    runs-on: ubuntu-latest
    steps:
      - name: Process Copilot Issue
        run: |
                    python main.py process-issues \
                        --issue ${{ github.event.issue.number }} \
                        --continue-on-error \
                        --verbose
```

### 3. Configuration Integration

The system integrates with existing configuration while adding AI-specific settings that default to safe fallbacks when not configured.

## Performance Considerations

### 1. Caching Strategy
- Cache extracted entities and relationships
- Cache specialist analysis results  
- Cache AI model responses for similar content

### 2. Rate Limiting
- GitHub Models API rate limiting
- Staged processing to avoid overwhelming APIs
- Graceful degradation when rate limits hit

### 3. Error Recovery
- Fallback to template-based generation
- Partial processing with manual completion
- Comprehensive error logging and recovery

This architecture provides a robust, scalable foundation for AI-powered intelligence analysis while maintaining compatibility with existing systems and providing clear upgrade paths.