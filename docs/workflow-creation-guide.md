# Workflow Creation Guide

## Overview

This guide provides comprehensive instructions for creating custom workflow definitions that the Issue Processor can use to automatically generate structured deliverables from GitHub issues.

Workflows are defined in YAML files stored in `docs/workflow/deliverables/` and specify how issues should be processed, what documents should be generated, and how the output should be structured.

## Quick Start

### 1. Basic Workflow Template

Create a new file in `docs/workflow/deliverables/` using this basic template:

```yaml
# Workflow metadata (required)
name: "My Custom Workflow"
description: "Brief description of what this workflow does"
version: "1.0.0"

# Labels that trigger this workflow (required)
trigger_labels:
  - "my-label"
  - "custom-workflow"

# Output configuration (required)
output:
  folder_structure: "study/{issue_number}/{workflow_name}"
  file_naming: "{deliverable_name}.md"
  branch_naming: "{workflow_name}-{issue_number}"

# Documents to generate (required)
deliverables:
  - name: "summary"
    template: "base_deliverable.md"
    required: true
    description: "Executive summary"

# Processing options (optional)
processing:
  research_depth: "standard"
  include_citations: true
```

### 2. Test Your Workflow

```bash
# Validate the workflow file
python main.py validate-workflows --file docs/workflow/deliverables/my-workflow.yaml

# Test workflow matching
python main.py test-workflow-match --labels "my-label,site-monitor"

# Dry run processing
python main.py process-issues --issue 123 --dry-run
```

### 3. Deploy and Use

1. Commit your workflow file to the repository
2. Add appropriate labels to a GitHub issue
3. The Issue Processor will automatically match and execute your workflow

## Workflow Structure

### Required Sections

#### Metadata
```yaml
name: "Human-readable workflow name"
description: "What this workflow accomplishes"
version: "Semantic version (e.g., 1.0.0)"
```

#### Trigger Labels
```yaml
trigger_labels:
  - "primary-label"      # Main category
  - "secondary-label"    # Subcategory
  - "specific-type"      # Specific use case
```

**Best Practices:**
- Include 2-4 trigger labels for flexibility
- Use hierarchical labels (general → specific)
- Avoid overlapping with other workflows
- Always assume `site-monitor` is already present

#### Output Configuration
```yaml
output:
  # Where to create files
  folder_structure: "study/{issue_number}/{workflow_name}"
  
  # How to name files
  file_naming: "{deliverable_name}_{timestamp}.md"
  
  # Git branch naming
  branch_naming: "{workflow_name}-{issue_number}"
```

**Available Variables:**
- `{issue_number}`: GitHub issue number
- `{workflow_name}`: Slugified workflow name
- `{deliverable_name}`: Individual deliverable name
- `{timestamp}`: ISO timestamp
- `{date}`: Current date (YYYY-MM-DD)
- `{issue_title}`: Slugified issue title

#### Deliverables
```yaml
deliverables:
  - name: "deliverable_name"          # Unique identifier
    template: "template_file.md"      # Template to use
    required: true                    # Whether this is mandatory
    description: "What this contains" # Human-readable description
```

### Optional Sections

#### Processing Configuration
```yaml
processing:
  # Research depth
  research_depth: "standard"  # basic, standard, comprehensive, deep
  
  # Content settings
  include_citations: true
  generate_diagrams: false
  include_code_examples: true
  
  # Output format
  format: "markdown"          # markdown, html, pdf
  language: "en"              # Output language
  
  # Analysis settings
  focus_areas: ["security", "performance", "usability"]
  analysis_framework: "custom"
  
  # Time constraints
  estimated_duration: "2-4 hours"
  max_processing_time: 3600   # seconds
```

#### Validation Rules
```yaml
validation:
  # Content requirements
  min_content_length: 1000     # Minimum characters
  required_sections: ["Overview", "Analysis", "Conclusions"]
  
  # Quality checks
  spell_check: true
  grammar_check: false
  citation_format: "academic"
  
  # Review requirements
  peer_review_required: false
  stakeholder_approval: false
```

#### Advanced Features
```yaml
# Conditional processing
conditions:
  # Only process if certain labels present
  required_labels: ["urgent", "security"]
  
  # Exclude if these labels present
  excluded_labels: ["duplicate", "wontfix"]
  
  # Issue age requirements
  min_age_hours: 24
  max_age_days: 30

# Dependencies on other workflows
dependencies:
  - workflow: "initial-assessment"
    required: true
  - workflow: "stakeholder-review"
    required: false

# Post-processing actions
post_processing:
  # Notifications
  notify_users: ["@security-team", "@project-lead"]
  notify_slack: "#project-updates"
  
  # Integration actions
  create_jira_ticket: true
  update_project_board: true
  
  # Follow-up issues
  create_follow_up_issues: 
    - template: "implementation-task"
    - template: "review-request"
```

## Deliverable Configuration

### Basic Deliverable
```yaml
deliverables:
  - name: "executive_summary"
    template: "executive_summary.md"
    required: true
    description: "High-level overview for stakeholders"
```

### Advanced Deliverable
```yaml
deliverables:
  - name: "technical_analysis"
    template: "technical_analysis.md"
    required: true
    description: "Detailed technical assessment"
    
    # Deliverable-specific variables
    variables:
      analysis_depth: "comprehensive"
      include_code_review: true
      focus_areas: ["architecture", "security", "performance"]
    
    # Output customization
    output:
      subfolder: "technical"
      filename: "analysis_{date}.md"
      format: "markdown"
    
    # Content requirements
    validation:
      min_length: 2000
      required_sections: ["Architecture", "Security", "Recommendations"]
      include_diagrams: true
    
    # Conditional generation
    conditions:
      labels_include: ["technical"]
      issue_body_regex: "technical|architecture|code"
      
    # Dependencies
    depends_on: ["initial_assessment"]
    generates_input_for: ["implementation_plan"]
```

### Template Integration
```yaml
deliverables:
  - name: "research_report"
    template: "research_analysis.md"
    required: true
    description: "Comprehensive research findings"
    
    # Template context
    template_context:
      report_type: "{{workflow_name}}"
      analysis_scope: "{{processing.research_depth}}"
      target_audience: "technical team"
      
    # Template processing options
    template_options:
      strict_variables: false     # Allow undefined variables
      auto_escape: true          # Escape HTML in variables
      trim_blocks: true          # Remove whitespace
      lstrip_blocks: true        # Remove leading whitespace
```

## Template System

### Template Locations

Templates are searched in this order:
1. `templates/{template_name}` (custom templates)
2. `docs/workflow/templates/{template_name}` (workflow-specific)
3. Built-in templates (system defaults)

### Template Variables

#### Standard Variables
Always available in templates:
```yaml
# Issue information
issue:
  number: 123
  title: "Issue title"
  body: "Issue description"
  author: "username"
  labels: ["label1", "label2"]
  created_at: "2023-01-01T00:00:00Z"
  updated_at: "2023-01-02T00:00:00Z"

# Workflow context
workflow:
  name: "Person Entity Profiling"
  version: "1.0.0"
  description: "Workflow description"
  
# Processing context
processing:
  timestamp: "2023-01-01T12:00:00Z"
  date: "2023-01-01"
  agent: "github-actions[bot]"
  branch: "person-entity-profiling-123"
  
# Repository context
repository:
  name: "owner/repo"
  url: "https://github.com/owner/repo"
  default_branch: "main"
```

#### Custom Variables
Defined in deliverable configuration:
```yaml
deliverables:
  - name: "report"
    template: "custom_report.md"
    variables:
      report_type: "Security Assessment"
      classification: "Confidential"
      review_period: "30 days"
```

### Template Functions

#### Built-in Functions
```jinja2
<!-- Date formatting -->
{{ processing.timestamp | dateformat('%Y-%m-%d') }}

<!-- Text processing -->
{{ issue.title | title }}
{{ issue.body | truncate(200) }}
{{ workflow.name | slugify }}

<!-- Lists and iteration -->
{% for label in issue.labels %}
- {{ label }}
{% endfor %}

<!-- Conditional content -->
{% if 'security' in issue.labels %}
## Security Considerations
{{ security_content }}
{% endif %}

<!-- Include other templates -->
{% include 'common/header.md' %}
```

#### Custom Functions
Define in workflow processing section:
```yaml
processing:
  template_functions:
    priority_level: |
      {% if 'urgent' in issue.labels %}High
      {% elif 'important' in issue.labels %}Medium
      {% else %}Low{% endif %}
      
    estimated_effort: |
      {% set complexity = issue.body | regex_search('complexity:\\s*(\\w+)') %}
      {% if complexity == 'high' %}5-8 days
      {% elif complexity == 'medium' %}2-3 days
      {% else %}1 day{% endif %}
```

## Workflow Examples

### Example 1: Security Assessment

```yaml
name: "Security Assessment Workflow"
description: "Comprehensive security analysis and recommendations"
version: "1.0.0"

trigger_labels:
  - "security"
  - "vulnerability"
  - "security-review"

output:
  folder_structure: "study/{issue_number}/security-assessment"
  file_naming: "{deliverable_name}_{date}.md"
  branch_naming: "security-assessment-{issue_number}"

deliverables:
  - name: "vulnerability_assessment"
    template: "security/vulnerability_assessment.md"
    required: true
    description: "Detailed vulnerability analysis"
    
  - name: "security_recommendations"
    template: "security/recommendations.md"
    required: true
    description: "Prioritized security recommendations"
    
  - name: "compliance_checklist"
    template: "security/compliance.md"
    required: false
    description: "Compliance verification checklist"
    conditions:
      labels_include: ["compliance"]

processing:
  research_depth: "comprehensive"
  focus_areas: ["authentication", "authorization", "data protection", "network security"]
  include_citations: true
  analysis_framework: "OWASP"
  
validation:
  min_content_length: 3000
  required_sections: ["Executive Summary", "Findings", "Recommendations", "Risk Assessment"]
  peer_review_required: true
```

### Example 2: Quick Research

```yaml
name: "Quick Research Workflow"
description: "Fast-turnaround research for urgent questions"
version: "1.0.0"

trigger_labels:
  - "quick-research"
  - "urgent"
  - "fast-track"

output:
  folder_structure: "study/{issue_number}/quick-research"
  file_naming: "research_{timestamp}.md"
  branch_naming: "quick-research-{issue_number}"

deliverables:
  - name: "research_brief"
    template: "research/quick_brief.md"
    required: true
    description: "Concise research summary"

processing:
  research_depth: "basic"
  max_processing_time: 1800  # 30 minutes
  include_citations: false
  format: "markdown"
  
validation:
  min_content_length: 500
  max_content_length: 2000
  required_sections: ["Key Findings", "Quick Recommendations"]
```

### Example 3: Technical Review

```yaml
name: "Technical Review Workflow"
description: "Code and architecture review process"
version: "1.0.0"

trigger_labels:
  - "technical-review"
  - "code-review"
  - "architecture-review"

output:
  folder_structure: "study/{issue_number}/technical-review"
  file_naming: "{deliverable_name}_{date}.md"
  branch_naming: "tech-review-{issue_number}"

deliverables:
  - name: "architecture_analysis"
    template: "technical/architecture_review.md"
    required: true
    description: "System architecture assessment"
    conditions:
      labels_include: ["architecture", "system-design"]
    
  - name: "code_quality_review"
    template: "technical/code_review.md"
    required: true
    description: "Code quality and best practices review"
    conditions:
      labels_include: ["code", "implementation"]
    
  - name: "performance_analysis"
    template: "technical/performance_review.md"
    required: false
    description: "Performance characteristics and optimization opportunities"
    conditions:
      labels_include: ["performance"]
    
  - name: "technical_recommendations"
    template: "technical/recommendations.md"
    required: true
    description: "Technical improvement recommendations"

processing:
  research_depth: "standard"
  focus_areas: ["architecture", "code_quality", "performance", "maintainability"]
  include_code_examples: true
  generate_diagrams: true
  
validation:
  min_content_length: 2000
  required_sections: ["Analysis", "Findings", "Recommendations"]
  include_diagrams: true
```

## Best Practices

### Workflow Design

#### 1. Clear Scope Definition
- **Single Purpose**: Each workflow should have one clear objective
- **Specific Triggers**: Use precise labels that indicate when to use this workflow
- **Defined Outputs**: Clearly specify what deliverables will be generated

#### 2. Label Strategy
```yaml
# Good: Hierarchical and specific
trigger_labels:
  - "security"           # Category
  - "vulnerability"      # Type
  - "web-application"    # Scope

# Avoid: Too broad or overlapping
trigger_labels:
  - "review"            # Too generic
  - "analysis"          # Overlaps with many workflows
```

#### 3. Template Organization
```
templates/
├── base_deliverable.md           # Common base template
├── security/
│   ├── vulnerability_assessment.md
│   └── recommendations.md
├── technical/
│   ├── architecture_review.md
│   ├── code_review.md
│   └── performance_analysis.md
└── research/
    ├── quick_brief.md
    ├── comprehensive_analysis.md
    └── literature_review.md
```

### Content Quality

#### 1. Consistent Structure
Use standardized sections across similar deliverables:
```markdown
# Standard Research Report Structure
## Executive Summary
## Background and Context
## Methodology
## Key Findings
## Analysis
## Recommendations
## Conclusions
## References
```

#### 2. Template Variables
```yaml
# Provide meaningful defaults
variables:
  analysis_depth: "standard"
  target_audience: "development team"
  classification: "internal"
  review_period: "quarterly"
```

#### 3. Validation Rules
```yaml
validation:
  # Ensure content quality
  min_content_length: 1000
  required_sections: ["Summary", "Analysis", "Recommendations"]
  
  # Check completeness
  spell_check: true
  citation_format: "academic"
```

### Maintenance

#### 1. Version Management
```yaml
name: "Security Assessment Workflow"
version: "2.1.0"  # Semantic versioning

# Document changes
changelog:
  "2.1.0":
    - "Added compliance checklist deliverable"
    - "Updated validation requirements"
  "2.0.0":
    - "Major restructure for new security framework"
    - "Breaking changes to template variables"
```

#### 2. Testing Strategy
```bash
# Regular validation
python main.py validate-workflows

# Test with sample issues
python main.py test-workflow --workflow security-assessment --issue 123

# Performance testing
python main.py benchmark-workflow --workflow security-assessment
```

#### 3. Documentation
```yaml
# Include usage examples
examples:
  - issue_labels: ["security", "web-application"]
    expected_deliverables: ["vulnerability_assessment"]
    estimated_time: "2-3 hours"
    
  - issue_labels: ["security", "compliance", "financial"]
    expected_deliverables: ["vulnerability_assessment", "compliance_checklist"]
    estimated_time: "4-6 hours"
```

## Advanced Features

### Workflow Composition

#### Workflow Dependencies
```yaml
name: "Comprehensive Security Review"
version: "1.0.0"

# This workflow depends on others
dependencies:
  - workflow: "initial-assessment"
    required: true
    timeout: "24 hours"
    
  - workflow: "stakeholder-review"
    required: false
    timeout: "1 week"

# Inherit from base workflow
extends: "base-security-assessment"

# Override specific sections
overrides:
  processing:
    research_depth: "comprehensive"
  deliverables:
    - name: "detailed_threat_model"
      extends: "threat_model"
      template: "security/detailed_threat_model.md"
```

#### Conditional Workflows
```yaml
name: "Adaptive Research Workflow"
version: "1.0.0"

trigger_labels:
  - "research"

# Dynamic deliverable selection
deliverables:
  - name: "quick_summary"
    template: "research/quick_summary.md"
    required: true
    conditions:
      labels_include: ["urgent"]
      
  - name: "comprehensive_analysis"
    template: "research/comprehensive_analysis.md"
    required: true
    conditions:
      labels_exclude: ["urgent"]
      issue_age_hours: ">= 48"
      
  - name: "stakeholder_briefing"
    template: "research/stakeholder_briefing.md"
    required: false
    conditions:
      labels_include: ["stakeholder-review"]
      issue_author_teams: ["leadership", "product"]
```

### Integration Features

#### External System Integration
```yaml
processing:
  # External data sources
  data_sources:
    - type: "jira"
      query: "project = PROJ AND labels = security"
      credentials: "jira_service_account"
      
    - type: "confluence"
      space: "SECURITY"
      page_filter: "security assessment"
      
    - type: "github"
      repositories: ["org/security-docs", "org/compliance"]
      file_patterns: ["*.md", "security/**"]

  # External notifications
  notifications:
    slack:
      channel: "#security-reviews"
      message_template: "Security assessment completed for issue #{issue_number}"
      
    email:
      recipients: ["security-team@company.com"]
      subject: "Security Assessment: {issue_title}"
      
    jira:
      project: "SEC"
      issue_type: "Task"
      summary: "Follow-up from security assessment #{issue_number}"
```

#### Custom Processing Logic
```yaml
processing:
  # Custom processing scripts
  pre_processing:
    - script: "scripts/gather_security_context.py"
      args: ["--issue", "{issue_number}"]
      
  post_processing:
    - script: "scripts/validate_security_findings.py"
      args: ["--output-dir", "{output_directory}"]
      
    - script: "scripts/create_security_tickets.py"
      args: ["--findings-file", "{output_directory}/vulnerability_assessment.md"]

  # Custom validation
  custom_validation:
    - script: "scripts/security_content_validator.py"
      required: true
      timeout: 300
```

## Troubleshooting

### Common Issues

#### 1. Workflow Not Triggering
**Check:**
- Issue has `site-monitor` label
- Issue has at least one matching trigger label
- Workflow file is valid YAML
- Workflow passes validation

**Debug:**
```bash
python main.py debug-workflow-match --issue 123 --verbose
python main.py list-workflows --show-triggers
```

#### 2. Template Rendering Errors
**Check:**
- Template file exists in expected location
- Template syntax is valid Jinja2
- All required variables are provided
- No circular template includes

**Debug:**
```bash
python main.py test-template --template security/threat_model.md --context '{"issue": {"number": 123}}'
python main.py validate-templates --workflow security-assessment
```

#### 3. Deliverable Generation Failures
**Check:**
- Output directory is writable
- Template context contains all required variables
- Content validation rules are achievable
- No dependency conflicts

**Debug:**
```bash
python main.py debug-deliverable --issue 123 --deliverable threat_model --verbose
python main.py test-deliverable-generation --workflow security-assessment --dry-run
```

### Validation and Testing

#### Comprehensive Workflow Testing
```bash
# Test workflow definition
python main.py validate-workflow --file docs/workflow/deliverables/security-assessment.yaml

# Test with sample data
python main.py test-workflow --workflow security-assessment --mock-issue tests/fixtures/security_issue.json

# Performance testing
python main.py benchmark-workflow --workflow security-assessment --iterations 10

# Integration testing
python main.py test-workflow-integration --workflow security-assessment --github-issue 123
```

#### Template Testing
```bash
# Validate template syntax
python main.py validate-template --template security/threat_model.md

# Test rendering with sample data
python main.py render-template --template security/threat_model.md --context tests/fixtures/security_context.json

# Test all templates in workflow
python main.py test-workflow-templates --workflow security-assessment
```

This guide provides the foundation for creating effective, maintainable workflows that integrate seamlessly with the Issue Processor system. Start with simple workflows and gradually add complexity as you become familiar with the features and capabilities.