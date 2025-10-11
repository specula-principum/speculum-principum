# Issue Processor Documentation

## Overview

The Issue Processor is an automated agent that processes GitHub issues labeled with `site-monitor` by selecting appropriate workflows from `docs/workflow/deliverables/**` and generating structured research documents. This system seamlessly integrates with the existing Speculum Principum site monitoring infrastructure.

## Architecture

### Core Components

#### 1. WorkflowMatcher (`src/workflow_matcher.py`)
- **Purpose**: Discovers and matches issues to appropriate workflows based on labels
- **Key Features**:
  - Scans `docs/workflow/deliverables/**` for workflow definitions
  - Caches workflow definitions for performance
  - Validates workflow structure and required fields
  - Matches issues to workflows using trigger labels
  - Handles ambiguous matches by requesting clarification

#### 2. IssueProcessor (`src/issue_processor.py`)
- **Purpose**: Orchestrates the complete issue processing pipeline
- **Key Features**:
  - Integrates with GitHub API for issue management
  - Manages agent assignment for processing state
  - Coordinates workflow execution
  - Handles error conditions and recovery
  - Generates status reports and updates

#### 3. DeliverableGenerator (`src/deliverable_generator.py`)
- **Purpose**: Creates structured documents based on workflow specifications
- **Key Features**:
  - Template-based content generation
  - Configurable output formats
  - Integration with research context
  - Validation of generated content

#### 4. GitManager (`src/git_manager.py`)
- **Purpose**: Manages git operations for version control
- **Key Features**:
  - Creates feature branches per issue
  - Commits generated documents
  - Handles merge conflicts
  - Provides natural versioning through git history

#### 5. TemplateEngine (`src/template_engine.py`)
- **Purpose**: Processes templates for consistent document generation
- **Key Features**:
  - Jinja2-based template processing
  - Context variable substitution
  - Template inheritance support
  - Custom filters and functions

### Data Flow

```
GitHub Issue (site-monitor label)
    ↓
WorkflowMatcher.find_matching_workflow()
    ↓
IssueProcessor.process_issue()
    ↓ (if clear match)
Agent Assignment + Branch Creation
    ↓
DeliverableGenerator.generate_deliverables()
    ↓
TemplateEngine.render_template()
    ↓
GitManager.commit_changes()
    ↓
GitHub Issue Update (completion/status)
```

### Error Handling Flow

```
Ambiguous Workflow Match
    ↓
Request Clarification Comment
    ↓ (pause processing)
Wait for Additional Labels
    ↓
Resume Processing

Processing Error
    ↓
Remove Agent Assignment
    ↓
Log Error Details
    ↓
Update Issue with Error Status
```

## Usage

### Command Line Interface

#### Process Individual Issue
```bash
# Process a specific issue
python main.py process-issues --issue 123

# Dry run to see what would be processed
python main.py process-issues --issue 123 --dry-run

# Use custom configuration
python main.py process-issues --config custom-config.yaml --issue 123
```

#### Batch Processing
```bash
# Process all unassigned site-monitor issues
python main.py process-issues --batch

# Process issues with specific workflow
python main.py process-issues --batch --workflow-category legal-research

# Limit number of issues processed
python main.py process-issues --batch --limit 5
```

#### Status and Monitoring
```bash
# Show processing status
python main.py status --show-processing

# List active processing
python main.py list-processing

# Show workflow statistics
python main.py workflow-stats
```

### GitHub Integration

#### Issue Labels
- **Primary Trigger**: `site-monitor` - Required for any processing
- **Workflow Selectors**: Additional labels that match workflow `trigger_labels`
- **Processing State**: `agent-processing` - Added during active processing
- **Status Labels**: `needs-clarification`, `processing-error`, `completed`

#### Agent Behavior
1. **Assignment**: Agent assigns itself when beginning processing
2. **Clarification**: Removes assignment when requesting clarification
3. **Completion**: Updates issue with results and removes assignment
4. **Error**: Removes assignment and adds error status

### Workflow Integration

#### Workflow Directory Structure
```
docs/workflow/deliverables/
└── criminal-law/
  ├── person-entity-profiling.yaml
  ├── place-intelligence-mapping.yaml
  ├── asset-evidence-cataloguing.yaml
  ├── statutory-regulatory-research-tracker.yaml
  ├── case-law-precedent-explorer.yaml
  ├── investigative-lead-development.yaml
  ├── witness-expert-reliability-assessment.yaml
  ├── sentencing-mitigation-scenario-planner.yaml
  ├── inter-agency-coordination-briefs.yaml
  └── compliance-remediation-monitoring.yaml
```

#### Issue Processing Trigger
Issues are automatically processed when they:
1. Have the `site-monitor` label
2. Match at least one workflow's `trigger_labels`
3. Are not currently assigned to the agent
4. Don't have `processing-paused` or `processing-error` labels

## Configuration

### Agent Configuration (`config.yaml`)

```yaml
# Agent settings
agent:
  # GitHub username for issue assignment
  username: "github-actions[bot]"
  
  # Maximum processing time per issue (seconds)
  timeout: 3600
  
  # Maximum number of concurrent processing
  max_concurrent: 3
  
  # Workflow directory path
  workflow_directory: "docs/workflow/deliverables"
  
  # Output directory for generated content
  output_directory: "study"

# Processing settings
processing:
  # Retry failed operations
  retry_attempts: 3
  retry_delay: 60
  
  # Git settings
  git:
    branch_prefix: "issue-processor/"
    commit_message_template: "Generated content for issue #{issue_number}: {issue_title}"
    
  # Template settings
  templates:
    base_template: "templates/base_deliverable.md"
    custom_templates_dir: "templates/"
```

### Workflow Configuration

Each workflow file in `docs/workflow/deliverables/` must include:

```yaml
# Required metadata
name: "Statutory & Regulatory Research Tracker"
description: "Curates applicable statutes, directives, and compliance checkpoints for GAO criminal law engagements."
workflow_version: "1.0.0"
category: "legal-research"
priority: "high"
confidence_threshold: 0.7

# Trigger configuration
trigger_labels:
  - "statute-review"
  - "gao-directive"
  - "criminal-law"

required_entities:
  - entity_type: "person"
    min_count: 1
    min_confidence: 0.65
  - entity_type: "place"
    min_count: 1
    min_confidence: 0.6

deliverable_templates:
  - "entity_backbone"
  - "statute_research_core"
  - "gao_compliance_appendix"

# Deliverables specification
deliverables:
  - name: "entity-backbone"
    template: "entity_backbone.md"
    required: true
    description: "Standardized entity tables for people, places, and evidence."
    order: 1
    
  - name: "statute-research-core"
    template: "statute_research_core.md"
    required: true
    description: "Digest of applicable statutes, directives, and compliance checkpoints."
    order: 2
    
  - name: "gao-compliance-appendix"
    template: "gao_compliance_appendix.md"
    required: true
    description: "GAO alignment appendix capturing citations, audit trail, and reviewer notes."
    order: 3

# Processing configuration
processing:
  timeout: 180
  max_retries: 1

audit_trail:
  required: true
  fields:
    - "model_version"
    - "reason_codes"
    - "citation_sources"
```
  research_depth: "comprehensive"
  include_citations: true
  generate_diagrams: false
  validation_required: true
```

## Workflow Creation

### Basic Workflow Structure

1. **Create YAML file** in `docs/workflow/deliverables/`
2. **Define metadata**: name, description, version
3. **Specify triggers**: labels that activate this workflow
4. **Configure output**: folder structure and file naming
5. **List deliverables**: required documents to generate
6. **Set processing options**: workflow-specific settings

### Example: GAO Coordination Workflow

```yaml
name: "Inter-Agency Coordination Briefs"
description: "Generates GAO-ready coordination briefs, contact maps, and decision timelines."
workflow_version: "1.0.0"
category: "operational-coordination"
priority: "high"
confidence_threshold: 0.65

trigger_labels:
  - "coordination"
  - "gao-brief"
  - "criminal-law"

required_entities:
  - entity_type: "organization"
    min_count: 1
    min_confidence: 0.6
  - entity_type: "person"
    min_count: 1
    min_confidence: 0.6

deliverable_templates:
  - "entity_backbone"
  - "coordination_brief_core"
  - "gao_compliance_appendix"

deliverables:
  - name: "entity-backbone"
    template: "entity_backbone.md"
    required: true
    description: "Entity backbone shared component"
    order: 1

  - name: "coordination-brief-core"
    template: "coordination_brief_core.md"
    required: true
    description: "Inter-agency coordination summary with contact map and timeline"
    order: 2

  - name: "gao-compliance-appendix"
    template: "gao_compliance_appendix.md"
    required: true
    description: "GAO compliance appendix with citations and audit notes"
    order: 3

processing:
  timeout: 150
  max_retries: 1

audit_trail:
  required: true
  fields:
    - "model_version"
    - "reason_codes"
    - "contact_sources"
```

### Advanced Features

#### Conditional Deliverables
```yaml
deliverables:
  - name: "security_assessment"
    template: "security_review.md"
    required: false
    conditions:
      labels_include: ["security"]
      issue_body_contains: ["security", "vulnerability"]
```

#### Template Variables
```yaml
deliverables:
  - name: "analysis"
    template: "analysis.md"
    variables:
      analysis_type: "{{workflow_name}}"
      depth_level: "{{processing.research_depth}}"
      include_diagrams: "{{processing.generate_diagrams}}"
```

## Troubleshooting

### Common Issues

#### 1. No Workflow Matched
**Symptoms**: Issue remains unprocessed, no agent assignment
**Causes**:
- Missing `site-monitor` label
- No workflow has matching `trigger_labels`
- Workflow files have validation errors

**Solutions**:
```bash
# Check available workflows
python main.py list-workflows

# Validate workflow files
python main.py validate-workflows

# Test workflow matching
python main.py test-workflow-match --issue 123
```

#### 2. Ambiguous Workflow Match
**Symptoms**: Agent comments requesting clarification
**Causes**:
- Multiple workflows match the same labels
- Overlapping `trigger_labels` in workflow definitions

**Solutions**:
- Add more specific labels to the issue
- Review workflow `trigger_labels` for conflicts
- Use workflow priority settings

#### 3. Processing Timeout
**Symptoms**: Issue marked with `processing-error`, agent unassigned
**Causes**:
- Complex deliverable generation taking too long
- Network issues with GitHub API
- Resource constraints

**Solutions**:
```bash
# Increase timeout in config
agent:
  timeout: 7200  # 2 hours

# Check system resources
python main.py system-status

# Retry processing
python main.py retry-issue --issue 123
```

#### 4. Template Rendering Errors
**Symptoms**: Deliverables not generated, template errors in logs
**Causes**:
- Missing template files
- Invalid template syntax
- Missing template variables

**Solutions**:
```bash
# Validate templates
python main.py validate-templates

# Test template rendering
python main.py test-template --template research_analysis.md

# Check template variables
python main.py template-vars --workflow person-entity-profiling
```

### Debug Commands

#### Issue Processing Debug
```bash
# Detailed processing log for specific issue
python main.py debug-issue --issue 123 --verbose

# Show workflow matching process
python main.py debug-workflow-match --issue 123

# Trace deliverable generation
python main.py debug-deliverable --issue 123 --deliverable summary
```

#### System Health Checks
```bash
# Check all system components
python main.py health-check

# Validate configuration
python main.py validate-config

# Test GitHub connectivity
python main.py test-github-api
```

#### Performance Analysis
```bash
# Show processing statistics
python main.py processing-stats --days 30

# Analyze workflow performance
python main.py workflow-performance

# Resource usage monitoring
python main.py resource-monitor
```

## Integration Points

### Site Monitor Integration

The Issue Processor integrates with existing site monitoring through:

1. **Shared Configuration**: Uses `config_manager.py` for consistent settings
2. **GitHub Operations**: Extends `GitHubIssueCreator` for issue management
3. **Logging**: Integrates with `logging_config.py` for consistent logging
4. **Deduplication**: Uses `deduplication.py` for avoiding duplicate processing

### External Dependencies

#### Required
- **GitHub API**: Issue management and updates
- **Git**: Version control for generated content
- **PyYAML**: Workflow definition parsing
- **Jinja2**: Template processing

#### Optional
- **GitLab**: Alternative git hosting (planned)
- **Slack**: Processing notifications (planned)
- **Elasticsearch**: Advanced logging (planned)

## Performance Considerations

### Optimization Strategies

1. **Workflow Caching**: Workflows loaded once and cached in memory
2. **Template Precompilation**: Templates compiled on startup
3. **Batch Processing**: Multiple issues processed in parallel
4. **Incremental Updates**: Only regenerate changed deliverables

### Resource Limits

- **Memory**: ~100MB per concurrent processing
- **Disk**: Variable based on deliverable size
- **Network**: GitHub API rate limits apply
- **CPU**: Template rendering is CPU-intensive

### Scaling Guidelines

```yaml
# High-volume configuration
agent:
  max_concurrent: 10
  timeout: 1800

processing:
  batch_size: 20
  parallel_deliverables: true
  
github:
  rate_limit_buffer: 100
  request_timeout: 30
```

## Security Considerations

### Access Control
- **GitHub Token**: Requires `repo` and `issues` permissions
- **Git Access**: Repository write access for commits
- **File System**: Write access to output directories

### Data Protection
- **Issue Content**: Processed data remains in repository
- **Template Variables**: Sanitized before rendering
- **Git History**: Full audit trail of all changes

### Best Practices
- Use dedicated GitHub App for agent operations
- Limit agent permissions to minimum required
- Regular security audits of workflow definitions
- Monitor for unauthorized workflow modifications

## Monitoring and Observability

### Metrics Collection

Key metrics tracked:
- Processing success/failure rates
- Average processing time per workflow
- Workflow popularity and usage patterns
- Error frequencies and types

### Logging

Log levels and categories:
- **DEBUG**: Detailed processing steps
- **INFO**: Normal operation events
- **WARNING**: Recoverable issues
- **ERROR**: Processing failures
- **CRITICAL**: System-level problems

### Alerting

Configure alerts for:
- High error rates (>10% in 1 hour)
- Processing timeouts (>5 in 1 hour)
- GitHub API rate limit approaching
- Disk space low in output directories

## API Reference

### IssueProcessor Class

#### Methods

##### `process_issue(issue_number: int) -> ProcessingResult`
Process a single GitHub issue.

**Parameters:**
- `issue_number`: GitHub issue number to process

**Returns:**
- `ProcessingResult`: Object containing processing status and details

**Raises:**
- `IssueProcessingError`: When processing fails
- `WorkflowMatchingError`: When no workflow can be matched

##### `batch_process(criteria: Dict) -> List[ProcessingResult]`
Process multiple issues matching criteria.

**Parameters:**
- `criteria`: Dictionary specifying issue selection criteria

**Returns:**
- List of `ProcessingResult` objects

##### `get_processing_status(issue_number: int) -> ProcessingStatus`
Get current processing status for an issue.

**Parameters:**
- `issue_number`: GitHub issue number

**Returns:**
- `ProcessingStatus`: Current status information

### WorkflowMatcher Class

#### Methods

##### `find_matching_workflow(labels: List[str]) -> Optional[WorkflowInfo]`
Find workflow matching the provided labels.

**Parameters:**
- `labels`: List of issue labels

**Returns:**
- `WorkflowInfo` object if match found, None otherwise

##### `list_available_workflows() -> List[WorkflowInfo]`
Get list of all available workflows.

**Returns:**
- List of `WorkflowInfo` objects

##### `validate_workflow(workflow_path: str) -> ValidationResult`
Validate a workflow definition file.

**Parameters:**
- `workflow_path`: Path to workflow YAML file

**Returns:**
- `ValidationResult`: Validation status and any errors

### Data Models

#### ProcessingResult
```python
@dataclass
class ProcessingResult:
    issue_number: int
    status: ProcessingStatus
    workflow_used: Optional[str]
    deliverables_created: List[str]
    processing_time: float
    errors: List[str]
    git_branch: Optional[str]
    git_commits: List[str]
```

#### WorkflowInfo
```python
@dataclass
class WorkflowInfo:
    path: str
    name: str
    description: str
    version: str
    trigger_labels: List[str]
    deliverables: List[Dict]
    processing: Dict
    validation: Dict
    output: Dict
```

## Change Log

### Version 1.0.0 (Current)
- Initial implementation
- Basic workflow matching and processing
- Template-based deliverable generation
- Git integration for version control
- GitHub API integration

### Planned Features

#### Version 1.1.0
- Workflow priority system
- Advanced template functions
- Processing queue management
- Enhanced error recovery

#### Version 1.2.0
- Multi-repository support
- Workflow inheritance
- Custom plugin system
- Performance optimizations

#### Version 2.0.0
- AI-powered content generation
- Advanced workflow orchestration
- External system integrations
- Enterprise features