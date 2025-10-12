# AI-Enhanced Workflow Assignment

This document describes the AI-enhanced workflow assignment system using GitHub Models API.

## Overview

The AI-enhanced workflow assignment agent analyzes GitHub issue content semantically to suggest appropriate workflows, going beyond simple label matching to understand issue context, urgency, and technical requirements.

## Features

### 🤖 Intelligent Content Analysis
- **Semantic Understanding**: Analyzes issue titles and descriptions for context
- **Technical Classification**: Identifies technical indicators, security concerns, architecture issues
- **Urgency Assessment**: Evaluates issue priority (low/medium/high/critical)
- **Content Categorization**: Classifies as research, bug, feature, security, or documentation

### 📊 Multi-Signal Confidence
- **AI Confidence**: Primary signal; high scores can auto-assign on their own
- **Entity & Legal Overrides**: Strong person/place/thing coverage plus citations elevate confidence even if AI hesitates
- **Label + History Boost**: Proven workflows with matching labels can raise the score when AI is uncertain
- **Fallback Blend**: If no single signal dominates, a lightweight blend still produces a score for review decisions

### 🛡️ Robust Fallback System
- **Graceful Degradation**: Falls back to label-based matching if AI fails
- **Error Recovery**: Continues processing other issues if one fails
- **Network Resilience**: Handles API timeouts and connection errors

### 🎯 Confidence-Based Actions
- **High Confidence (≥80%)**: Automatic workflow assignment
- **Medium Confidence (60-79%)**: Request human review
- **Low Confidence (<60%)**: Request clarification

## GitHub Models Integration

### Prerequisites
- GitHub repository with Actions enabled
- GitHub Models API access (available in GitHub Actions)
- No external AI service dependencies

### API Usage
- **Endpoint**: `https://models.github.ai/inference/chat/completions`
- **Authentication**: Uses `GITHUB_TOKEN` (automatically available in Actions)
- **Models Available**: `gpt-4o`, `llama-3.2`, and others
- **Rate Limits**: Governed by GitHub Models quotas

## Configuration

### Basic Configuration
```yaml
# config.yaml
ai:
  enabled: false  # Set to true to enable AI analysis
  model: "gpt-4o"  # GitHub Models API model
  confidence_thresholds:
    auto_assign: 0.8   # Threshold for automatic assignment
    request_review: 0.6  # Threshold for human review
  settings:
    max_tokens: 500
    temperature: 0.3  # Lower = more consistent analysis
  prompts:
    include_page_extract: true  # Include captured page content in prompts
    page_extract_max_chars: 1200  # Max chars from page extract
```

### Advanced Configuration
```yaml
ai:
  enabled: true
  model: "gpt-4o"
  confidence_thresholds:
    auto_assign: 0.8
    request_review: 0.6
  settings:
    max_tokens: 500
    temperature: 0.3
  prompts:
    include_page_extract: true  # Enable page content enrichment
    page_extract_max_chars: 1200  # Limit extract size
  history:
    storage_type: "gist"  # or "repo_file"
    file_path: ".github/ai_assignment_history.json"
```

### Page Extract Enrichment

The `prompts.include_page_extract` setting controls whether captured page content is included in AI prompts:

**When enabled (recommended)**:
- AI receives the actual page content from site monitoring
- Provides rich context for better workflow recommendations
- Uses either persisted artifacts or inline preview excerpts
- Automatically truncates to `page_extract_max_chars` to stay within API limits

**When disabled**:
- AI only receives issue title and description
- May result in lower confidence scores
- Suitable for issues without page captures

**Page Extract Sources** (in priority order):
1. Persisted artifact (`artifacts/discoveries/<hash>/content.md`)
2. Deduplication entry with artifact path
3. Inline preview excerpt in issue body (`<details><summary>Preview excerpt</summary>...`)

**Example**: For a site monitoring discovery, enabling page extract provides the AI with the full page content, helping it identify whether the content requires entity profiling, legal research, or other specialized workflows.

## Usage

### Command Line

#### Enable AI Analysis
```bash
# Use AI with dry-run
python main.py assign-workflows --config config.yaml --ai --dry-run --verbose

# Execute AI assignment
python main.py assign-workflows --config config.yaml --ai --limit 10

# Disable AI (label-based only)
python main.py assign-workflows --config config.yaml --no-ai
```

#### VS Code Tasks
- **AI Assign Workflows (Dry Run)**: Test AI assignment without changes
- **AI Assign Workflows (Execute)**: Run AI assignment with changes  
- **AI Workflow Assignment Statistics**: View current assignment state

### GitHub Actions

The system includes automated workflow assignment via GitHub Actions:

```yaml
# .github/workflows/ai-workflow-assignment.yml
name: AI Workflow Assignment
on:
  issues:
    types: [opened, labeled]
  # schedule:
  #   - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:
```

#### Triggers
- **New Issues**: Automatically processes issues with `site-monitor` label
- **Schedule**: Batch processes unassigned issues every 6 hours
- **Manual**: Workflow dispatch with configurable options

## AI Analysis Process

### 1. Content Extraction
```python
{
  "title": "Issue title",
  "body": "Issue description (first 2000 chars)",
  "labels": ["existing", "labels"],
  "available_workflows": [...] 
}
```

### 2. AI Prompt Construction
```text
Analyze this GitHub issue and suggest workflows:

ISSUE DETAILS:
Title: [issue title]
Labels: [current labels]
Body: [issue description]

AVAILABLE WORKFLOWS:
- Person Entity Profiling: Comprehensive witness and subject profiling
  Trigger labels: person-entity-profiling, investigative, witness
  Deliverables: entity-profile, credibility-matrix

...

TASK: Return JSON with workflow suggestions and confidence scores
```

### 3. Response Processing
```json
{
  "summary": "Brief analysis of issue purpose",
  "key_topics": ["topic1", "topic2"],
  "suggested_workflows": ["Person Entity Profiling"],
  "confidence_scores": {"Person Entity Profiling": 0.85},
  "technical_indicators": ["entity", "credibility"],
  "urgency_level": "medium",
  "content_type": "investigative"
}
```

### 4. Decision Making
- **Score resolution**: Any high-confidence signal (AI, entity/legal cues, or label+history) can drive the final decision
- **Apply thresholds**: Auto-assign, review, or clarify
- **Execute action**: Add labels, create comments, assign workflow

## Output Examples

### High Confidence Assignment
```text
🤖 AI Workflow Assignment

Assigned Workflow: Person Entity Profiling
Confidence: 85%
Content Type: investigative  
Urgency: medium

AI Analysis Summary:
This issue requests a comprehensive profile of a cooperating witness, including credibility and association analysis for trial preparation.

Key Topics Identified:
witness background, investigative leads, credibility assessment, associations

Technical Indicators:
entity mapping, reliability scoring
```

### Medium Confidence Review Request
```text
🤖 Human Review Requested  

The AI analysis suggests these workflows but confidence is moderate:
- Person Entity Profiling (confidence: 65%)
- Witness Expert Reliability Assessment (confidence: 62%)

AI Summary: Mixed technical and research requirements need clarification

Content Type: investigative
Urgency: medium

Please review and either:
1. Confirm one of the suggested workflows by adding its trigger labels
2. Select a different workflow by adding appropriate labels  
3. Add more context to help improve the analysis
```

## Monitoring and Debugging

### Statistics Command
```bash
python main.py assign-workflows --config config.yaml --ai --statistics --verbose
```

### Output
```text
📊 Workflow Assignment Statistics
🤖 Agent Type: AI-enhanced

Issues Overview:
  Total site-monitor issues: 15
  Unassigned issues: 8
  Assigned issues: 7
  Need clarification: 2
  Need review: 1

Workflow Breakdown:
  Person Entity Profiling: 4
  Witness Expert Reliability Assessment: 3

Label Distribution:
  site-monitor: 15
  person-entity-profiling: 6
  witness-expert-reliability-assessment: 4
```

### Log Analysis
```bash
# View detailed logs
tail -f site_monitor.log

# Key log entries to monitor:
# - AI model initialization
# - API request/response cycles  
# - Confidence score calculations
# - Fallback activations
# - Assignment decisions
```

## Performance Considerations

### Token Usage
- **Average per issue**: ~400-500 tokens
- **Cost**: Free within GitHub Models quotas
- **Optimization**: Issue body truncated to 2000 chars

### Latency
- **AI analysis**: 2-5 seconds per issue
- **Traditional fallback**: <1 second per issue
- **Batch processing**: 0.5 second delay between issues

### Rate Limits
- **GitHub Models**: Subject to GitHub's quotas
- **GitHub API**: Standard GitHub API limits
- **Mitigation**: Automatic retry with exponential backoff

## Troubleshooting

### Common Issues

#### AI Analysis Fails
**Symptoms**: "Failed to analyze with AI" messages
**Causes**: 
- Network connectivity issues
- GitHub Models API unavailable
- Invalid API tokens

**Solutions**:
- Check network connectivity
- Verify GitHub Actions environment
- Review GitHub Models API status
- Use `--no-ai` flag as workaround

#### Low Confidence Scores
**Symptoms**: Many issues require clarification
**Causes**:
- Vague issue descriptions  
- Limited workflow variety
- Mismatched content types

**Solutions**:
- Improve issue templates
- Add more specific workflows
- Adjust confidence thresholds
- Train users on labeling

#### Configuration Errors
**Symptoms**: Schema validation failures
**Causes**:
- Invalid AI configuration syntax
- Missing required fields
- Type mismatches

**Solutions**:
- Validate YAML syntax
- Check configuration schema
- Use example configurations
- Enable verbose logging

### Debug Mode
```bash
# Maximum verbosity
python main.py assign-workflows \
  --config config.yaml \
  --ai \
  --verbose \
  --dry-run \
  --limit 1

# This will show:
# - Configuration loading
# - AI model initialization  
# - API request/response details
# - Score calculations
# - Decision reasoning
```

## Future Enhancements

### Planned Features
- **Learning System**: Store and analyze assignment success rates
- **Batch Optimization**: Process multiple issues in single API call
- **Custom Prompts**: Configurable AI prompts per workflow type
- **Confidence Tuning**: Machine learning-based threshold optimization

### Integration Opportunities  
- **GitHub Copilot Workspace**: Enhanced IDE integration
- **GitHub Discussions**: Community-driven workflow suggestions
- **GitHub Projects**: Automatic project board assignment
- **External Tools**: Jira, Linear, other issue trackers

## Security Considerations

### Data Privacy
- **Issue Content**: Sent to GitHub Models (within GitHub ecosystem)
- **API Tokens**: Standard GitHub token permissions
- **Logs**: No sensitive data stored in logs
- **History**: Optional, stored in GitHub (Gist or repository)

### Access Control
- **Repository Permissions**: Standard GitHub repository access
- **Actions Permissions**: `issues: write`, `contents: read`
- **Models Access**: Automatic in GitHub Actions environment
- **Token Scope**: Minimal required permissions

### Best Practices
- **Environment Variables**: Use GitHub secrets for configuration
- **Token Rotation**: Follow GitHub token lifecycle practices  
- **Audit Logging**: Monitor AI assignment decisions
- **Review Process**: Human oversight for critical workflows

---

*For implementation details, see the source code in `src/agents/ai_workflow_assignment_agent.py`*