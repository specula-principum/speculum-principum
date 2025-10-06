# Workflow Assignment Agent

The Workflow Assignment Agent is a crucial component in the Speculum Principum processing pipeline that bridges the gap between site monitoring and issue processing. It automatically reviews GitHub issues with the `site-monitor` label and assigns appropriate workflows based on issue content and labels.

## Purpose

This agent implements the missing step in the processing pipeline:

1. **Site Monitor** creates issues with `site-monitor` label ✅
2. **→ Workflow Assignment Agent assigns appropriate workflows** ← **THIS AGENT** ✅
3. **Issue Processor** processes issues according to assigned workflow ✅

## Core Functionality

### Discovery Context Enrichment
- Minimal "Discovery Intake" issues surface canonical URL, capture status, and quick actions without overwhelming the assignment prompt.
- Page capture extracts are embedded directly into the issue body for immediate reuse; optional persisted artifacts under `artifacts/discoveries/<hash>/` can be enabled via `persist_artifacts` when long-term retention is desired.
- Prompt enrichment is controlled via `ai.prompts.include_page_extract`, automatically falling back to the inline issue excerpt when no artifact is present, and respects configurable character budgets.

### Issue Review and Analysis
- Monitors unassigned issues with `site-monitor` label
- Analyzes issue labels and content to determine appropriate workflow
- Uses the existing `WorkflowMatcher` to find the best workflow match

### Smart Assignment Logic
- **High Confidence Match**: Assigns workflow when there's a single, clear match
- **Ambiguous Match**: Requests clarification when multiple workflows could apply
- **No Match**: Requests clarification and suggests available workflow labels

### Rule-Based Filtering
- **Skip Feature Issues**: Issues labeled with `feature` are not processed
- **Skip Clarification Issues**: Issues already labeled `needs clarification` are skipped
- **Skip Assigned Issues**: Issues already assigned to users are not processed

## CLI Usage

### Assign Workflows to Issues

```bash
# Dry run - see what would be done without making changes
python main.py assign-workflows --dry-run --verbose

# Process up to 10 issues
python main.py assign-workflows --limit 10

# Process with custom configuration
python main.py assign-workflows --config custom-config.yaml

# Show detailed progress information
python main.py assign-workflows --verbose
```

### Show Assignment Statistics

```bash
# Display comprehensive assignment statistics
python main.py assign-workflows --statistics

# Statistics include:
# - Total site-monitor issues
# - Assignment status breakdown
# - Workflow distribution
# - Label usage patterns
```

## VS Code Tasks

The agent includes pre-configured VS Code tasks:

- **Assign Workflows (Dry Run)** - Preview changes without execution
- **Assign Workflows (Execute)** - Process up to 20 issues
- **Show Workflow Assignment Statistics** - Display current assignment state

## Configuration

The agent uses the existing `config.yaml` structure and respects:

```yaml
agent:
  username: "github-actions[bot]"  # Agent username for assignments
  workflow_directory: "docs/workflow/deliverables"  # Workflow definitions
```

## Workflow Assignment Process

### 1. Issue Discovery
```python
# Get unassigned site-monitor issues
issues = agent.get_unassigned_site_monitor_issues(limit=20)
```

### 2. Workflow Analysis
```python
# Analyze each issue for workflow match
workflow, message = agent.analyze_issue_for_workflow(issue_data)
```

### 3. Action Determination
- **Single Match** → Assign workflow labels
- **Multiple Matches** → Request clarification
- **No Match** → Request clarification with suggestions
- **Skip Conditions** → Skip processing

### 4. GitHub Operations
```python
# Assign workflow by adding trigger labels
current_issue.add_to_labels(trigger_label)

# Or request clarification
current_issue.add_to_labels('needs clarification')
current_issue.create_comment(clarification_message)
```

## Assignment Actions

The agent can take the following actions:

| Action | Description | Labels Added | Comment Created |
|--------|-------------|--------------|-----------------|
| `ASSIGN_WORKFLOW` | Clear workflow match found | Workflow trigger labels | Assignment explanation |
| `REQUEST_CLARIFICATION` | No clear match, need more info | `needs clarification` | Suggestions and instructions |
| `SKIP_FEATURE` | Issue labeled as feature | None | None |
| `SKIP_NEEDS_CLARIFICATION` | Already needs clarification | None | None |
| `ERROR` | Processing error occurred | None | None |

## Example Workflow Assignment

### Before Assignment
```
Issue #123: "New security vulnerability in API"
Labels: site-monitor
Status: Unassigned
```

### After Assignment (High Confidence Match)
```
Issue #123: "New security vulnerability in API"
Labels: site-monitor, security-assessment, technical-review
Status: Unassigned (ready for Issue Processor)

Comment:
🤖 Workflow Assignment

I've assigned the Security Assessment workflow to this issue.

Added labels: security-assessment, technical-review

The issue will be processed according to this workflow's specifications...
```

### After Assignment (Needs Clarification)
```
Issue #124: "Website content changed"
Labels: site-monitor, needs clarification
Status: Unassigned

Comment:
🤖 Workflow Clarification Needed

Issue: No workflows match the current labels. Add specific workflow labels.

Suggested workflow labels:
- research
- technical-review
- compliance-audit
- content-analysis

Please add one or more workflow labels to help me determine how to process this issue...
```

## Integration with Existing Components

### WorkflowMatcher Integration
```python
# Uses existing workflow discovery and matching
self.workflow_matcher = WorkflowMatcher(workflow_directory)
workflow, message = self.workflow_matcher.get_best_workflow_match(labels)
suggestions = self.workflow_matcher.get_workflow_suggestions(labels)
```

### GitHub Operations Integration
```python
# Uses existing GitHub client
self.github = GitHubIssueCreator(github_token, repo_name)
issues = self.github.get_issues_with_labels(['site-monitor'], state='open')
```

### Configuration Integration
```python
# Uses existing configuration system
self.config = ConfigManager.load_config(config_path)
self.agent_username = self.config.agent.username if self.config.agent else 'github-actions[bot]'
```

## Error Handling

The agent includes comprehensive error handling:

- **GitHub API Errors**: Graceful handling of rate limits and API issues
- **Workflow Loading Errors**: Clear error messages for invalid workflow definitions
- **Configuration Errors**: Fallback to default values when config is unavailable
- **Processing Errors**: Individual issue errors don't stop batch processing

## Monitoring and Logging

- Detailed logging of all assignment decisions
- Statistics tracking for assignment patterns
- Progress reporting for batch operations
- Dry run mode for safe testing

## Testing

Comprehensive test coverage includes:
- Unit tests for all assignment logic
- Mock GitHub API interactions
- Workflow matching scenarios
- Error condition handling
- Batch processing validation

Run tests with:
```bash
pytest tests/unit/agents/test_workflow_assignment_agent.py -v
```

## Future Enhancements

Potential improvements for the agent:
- **Machine Learning**: Learn from manual label corrections
- **Issue Content Analysis**: Analyze issue body text for better matching
- **Priority-Based Processing**: Process high-priority issues first
- **Webhook Integration**: Real-time processing of new issues
- **Approval Workflows**: Human review before assignment in sensitive cases