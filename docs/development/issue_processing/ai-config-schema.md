# AI Content Extraction Configuration

## Enhanced Configuration Schema

This document defines the configuration updates needed to support AI-powered content extraction and specialist workflows.

### Updated config.yaml Structure

```yaml
# Existing configuration remains unchanged
github:
  token: "${GITHUB_TOKEN}"
  repository: "${GITHUB_REPOSITORY}"

google:
  api_key: "${GOOGLE_API_KEY}"
  search_engine_id: "${GOOGLE_SEARCH_ENGINE_ID}"

# ENHANCED: AI Configuration Section
ai:
  enabled: true
  provider: "github-models"  # GitHub Models is the only supported provider
  
  # Model configuration
  models:
    content_extraction: "gpt-4o"
    specialist_analysis: "gpt-4o"
    document_generation: "gpt-4o"
  
  # Performance settings
  settings:
    temperature: 0.3
    max_tokens: 3000
    timeout_seconds: 30
    retry_count: 3
  
  # Confidence thresholds for automated processing
  confidence_thresholds:
    entity_extraction: 0.7
    relationship_mapping: 0.6
    auto_assign_workflow: 0.8
    require_human_review: 0.5
  
  # Content extraction focus areas
  extraction_focus:
    default: ["entities", "relationships", "events", "indicators"]
    intelligence_analyst: ["threat_actors", "attack_vectors", "targets", "capabilities"]
    osint_researcher: ["digital_footprint", "public_records", "technical_infrastructure"]
    target_profiler: ["organizational_structure", "key_personnel", "business_operations"]
    threat_hunter: ["iocs", "ttps", "attack_patterns", "threat_indicators"]

# ENHANCED: Agent Configuration
agent:
  username: 'github-actions[bot]'
  
  # Processing configuration
  processing:
    default_timeout_minutes: 30
    max_concurrent_issues: 3
    enable_ai_extraction: true
    require_human_validation: false
  
  # Content extraction settings
  content_extraction:
    confidence_threshold: 0.7
    max_content_length: 10000  # characters
    enable_entity_linking: true
    enable_relationship_inference: true
  
  # Specialist workflow assignments
  specialist_assignments:
    auto_assign: true
    assignment_rules:
      - labels: ["intelligence", "threat-analysis"]
        specialist: "intelligence-analyst"
        confidence_required: 0.8
      - labels: ["osint", "research"]
        specialist: "osint-researcher"
        confidence_required: 0.7
      - labels: ["target", "profiling"]
        specialist: "target-profiler"
        confidence_required: 0.75
      - content_keywords: ["malware", "apt", "threat"]
        specialist: "threat-hunter"
        confidence_required: 0.8

  # Output configuration
  output_directory: 'intelligence'
  template_directory: 'templates'
  
  # Git configuration
  git:
    branch_prefix: 'intelligence'
    auto_push: true
    create_pr: false
    commit_message_template: "Intelligence analysis for issue #{issue_number}: {workflow_name}"

# ENHANCED: Workflow Configuration
workflows:
  directory: 'docs/workflow/specialists'
  
  # Default workflow settings
  defaults:
    require_review: false
    auto_assign: true
    processing_timeout: 30
    
  # Specialist workflow definitions loaded from directory
  specialist_types:
    - intelligence-analyst
    - osint-researcher  
    - target-profiler
    - threat-hunter
    - business-analyst

# Quality assurance settings
quality_assurance:
  enabled: true
  
  # Content validation rules
  validation:
    min_confidence_score: 0.6
    require_source_references: true
    max_extraction_time_seconds: 300
    
  # Review requirements
  review:
    require_human_review_when:
      - confidence_score < 0.7
      - sensitive_content_detected: true
      - extraction_errors > 2
    
    auto_approve_when:
      - confidence_score >= 0.9
      - specialist_analysis_complete: true
      - validation_passed: true

# Monitoring and logging
monitoring:
  enable_performance_metrics: true
  log_ai_interactions: true
  track_extraction_accuracy: true
  
  metrics:
    extraction_time_threshold: 120  # seconds
    processing_success_rate_threshold: 0.85
    content_quality_score_threshold: 0.8

# Security settings for AI processing
security:
  content_sanitization:
    remove_pii: true
    redact_sensitive_data: true
    allowed_content_types: ["text/plain", "text/markdown"]
  
  api_security:
    rate_limiting: true
    request_encryption: true
    audit_api_calls: true
```

### Environment Variables Required

```bash
# Existing variables
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPOSITORY=owner/repo-name
GOOGLE_API_KEY=AIxxxxxxxxxxxxxxxxxxxxx
GOOGLE_SEARCH_ENGINE_ID=xxxxxxxxxxxxxxxxx

# NEW: AI Configuration Variables (optional overrides)
AI_ENABLED=true
AI_PROVIDER=github-models
AI_MODEL_CONTENT_EXTRACTION=gpt-4o
AI_MODEL_SPECIALIST_ANALYSIS=gpt-4o
AI_CONFIDENCE_THRESHOLD=0.7

# NEW: Security and Performance
AI_MAX_TOKENS=3000
AI_TIMEOUT_SECONDS=30
AI_RATE_LIMIT_REQUESTS_PER_MINUTE=20

# NEW: Processing Options
ENABLE_AUTO_SPECIALIST_ASSIGNMENT=true
REQUIRE_HUMAN_VALIDATION=false
MAX_CONCURRENT_EXTRACTIONS=3
```

### Specialist Workflow Configuration Examples

#### Intelligence Analyst Workflow
**File**: `docs/workflow/specialists/intelligence-analyst.yaml`

```yaml
name: "Intelligence Analyst"
description: "Comprehensive intelligence analysis with threat assessment and strategic insights"
specialist_type: "intelligence_analyst"
version: "2.0.0"

# Specialist persona for AI interactions
persona: "You are a senior intelligence analyst with 15+ years of experience in threat assessment, geopolitical analysis, and strategic intelligence. You specialize in synthesizing complex information from multiple sources into actionable intelligence products for decision-makers."

# Assignment triggers
triggers:
  assignee: ["github-copilot[bot]", "copilot"]
  labels: ["intelligence", "threat-analysis", "strategic", "geopolitical"]
  content_indicators: ["threat", "adversary", "campaign", "intelligence", "analysis"]
  confidence_threshold: 0.8

# Content extraction focus
extraction_focus:
  - "threat_actors"
  - "attack_vectors" 
  - "strategic_objectives"
  - "capabilities_assessment"
  - "intentions_analysis"
  - "geopolitical_context"

# AI prompting configuration
ai_prompting:
  extraction_temperature: 0.2  # More deterministic for facts
  analysis_temperature: 0.4    # More creative for analysis
  max_extraction_tokens: 2000
  max_analysis_tokens: 4000

# Deliverable specifications
deliverables:
  - name: "intelligence-assessment"
    title: "Intelligence Assessment Report"
    description: "Comprehensive intelligence analysis with threat assessment"
    ai_generation: true
    required_sections:
      - "executive_summary"
      - "threat_landscape"  
      - "actor_analysis"
      - "capabilities_assessment"
      - "intentions_analysis"
      - "risk_assessment"
      - "recommendations"
      - "intelligence_gaps"
    
    # AI prompt template for this deliverable
    prompt_template: |
      Generate a comprehensive intelligence assessment based on the extracted data.
      Focus on threat analysis, strategic implications, and actionable recommendations.
      Use intelligence community confidence levels (High/Medium/Low confidence).
      
      Structure the report with clear executive summary, detailed analysis sections,
      and specific recommendations for decision-makers.
  
  - name: "target-profile"
    title: "Target Entity Profile"
    description: "Detailed profile of target organization or individual"
    ai_generation: true
    required_sections:
      - "entity_overview"
      - "organizational_structure"
      - "key_personnel"
      - "capabilities"
      - "vulnerabilities"
      - "relationships_network"
      - "operational_patterns"

# Quality validation rules
validation:
  required_entities: ["organizations", "people"]
  min_confidence_entity_extraction: 0.7
  min_confidence_analysis: 0.6
  required_analysis_depth: "comprehensive"
  
  # Content quality checks
  quality_checks:
    - min_word_count: 1000
    - requires_executive_summary: true
    - requires_recommendations: true
    - requires_confidence_assessments: true

# Output configuration  
output:
  folder_structure: "intelligence/{specialist_type}/{issue_number}-{title_slug}"
  file_pattern: "{deliverable_name}-{date}.md"
  branch_pattern: "intelligence/{specialist_type}/issue-{issue_number}"
  
  # Additional output formats
  export_formats: ["markdown", "pdf", "json"]
  include_metadata: true
  include_extraction_data: true

# Processing configuration
processing:
  timeout_minutes: 45
  require_review: false
  auto_commit: true
  auto_push: false
  
  # Multi-stage processing
  stages:
    1: "content_extraction"    # Extract structured data
    2: "entity_analysis"       # Analyze extracted entities  
    3: "relationship_mapping"  # Map relationships
    4: "threat_assessment"     # Assess threats and risks
    5: "document_generation"   # Generate final deliverable
```

#### OSINT Researcher Workflow  
**File**: `docs/workflow/specialists/osint-researcher.yaml`

```yaml
name: "OSINT Researcher"
description: "Open source intelligence research with information verification"
specialist_type: "osint_researcher" 
version: "2.0.0"

persona: "You are an expert OSINT researcher with deep knowledge of open source intelligence techniques, digital forensics, and information verification methodologies. You excel at finding, analyzing, and verifying information from publicly available sources."

triggers:
  assignee: ["github-copilot[bot]", "copilot"]
  labels: ["osint", "research", "verification", "digital-footprint"]
  content_indicators: ["osint", "social media", "public records", "verification"]
  confidence_threshold: 0.7

extraction_focus:
  - "digital_footprint"
  - "social_media_presence"
  - "public_records"
  - "technical_infrastructure"
  - "communication_channels" 
  - "online_activities"

deliverables:
  - name: "osint-report"
    title: "OSINT Research Report"
    description: "Comprehensive open source intelligence findings"
    ai_generation: true
    required_sections:
      - "research_methodology"
      - "sources_analyzed"
      - "key_findings"
      - "digital_footprint_analysis"
      - "verification_status"
      - "additional_leads"
      - "research_gaps"
    
  - name: "source-verification"
    title: "Source Verification Matrix"
    description: "Analysis of source credibility and information verification"
    ai_generation: true
    required_sections:
      - "source_assessment"
      - "credibility_analysis"
      - "cross_reference_results"
      - "verification_confidence"

validation:
  required_entities: ["technical", "people", "organizations"]
  min_sources_analyzed: 3
  requires_verification_assessment: true
  
output:
  folder_structure: "intelligence/osint/{issue_number}-{title_slug}"
  include_source_links: true
  include_verification_metadata: true
```

### Database Schema for Tracking

```sql
-- New tables for tracking AI-powered processing

CREATE TABLE extraction_sessions (
    id SERIAL PRIMARY KEY,
    issue_number INTEGER NOT NULL,
    specialist_type VARCHAR(50) NOT NULL,
    extraction_timestamp TIMESTAMP DEFAULT NOW(),
    model_version VARCHAR(20),
    confidence_threshold FLOAT,
    processing_time_seconds INTEGER,
    extraction_status VARCHAR(20), -- success, partial, failed
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE extracted_entities (
    id SERIAL PRIMARY KEY,
    extraction_session_id INTEGER REFERENCES extraction_sessions(id),
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT NOT NULL,
    attributes JSONB,
    source_references TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE extracted_relationships (
    id SERIAL PRIMARY KEY,
    extraction_session_id INTEGER REFERENCES extraction_sessions(id),
    source_entity VARCHAR(255) NOT NULL,
    target_entity VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    description TEXT,
    source_references TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE specialist_analyses (
    id SERIAL PRIMARY KEY,
    extraction_session_id INTEGER REFERENCES extraction_sessions(id),
    specialist_type VARCHAR(50) NOT NULL,
    analysis_type VARCHAR(100) NOT NULL,
    findings JSONB,
    recommendations JSONB,
    confidence_assessment JSONB,
    generated_content TEXT,
    processing_time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

This configuration framework provides the foundation for implementing AI-powered content extraction while maintaining backward compatibility with existing functionality.