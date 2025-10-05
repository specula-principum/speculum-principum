# GitHub Actions Workflows

This directory contains GitHub Actions workflows for automating various operations in the Speculum Principum project.

## Overview

The workflows are organized into two main categories:

### Development Workflows
- **`dev-ci.yml`** - Development CI/CD Pipeline (testing, linting, security scanning)

### Operations Workflows

#### Site Monitoring & Issue Processing
- **`ops-site-monitoring.yml`** - On-demand site monitoring operations
- **`ops-workflow-assignment.yml`** - Assign workflows to unassigned site-monitor issues
- **`ops-issue-processing.yml`** - Automated issue processing with workflow-based deliverable generation

#### Maintenance & Utilities
- **`ops-daily-operations.yml`** - Daily maintenance tasks
- **`ops-weekly-cleanup.yml`** - Weekly cleanup operations
- **`ops-status-check.yml`** - System status monitoring
- **`ops-setup-monitoring.yml`** - Initial repository setup

## Development CI/CD Pipeline (`dev-ci.yml`)

### Purpose

Provides continuous integration and quality assurance for the codebase through:

1. **Multi-version Testing**: Tests across Python 3.9, 3.10, 3.11, and 3.12
2. **Code Quality**: Linting with flake8 and formatting checks
3. **Test Coverage**: Comprehensive test suite with coverage reporting
4. **Integration Testing**: End-to-end functionality validation
5. **Security Scanning**: Vulnerability detection with safety and bandit
6. **CLI Testing**: Command-line interface functionality validation

### Triggers

- **Push/Pull Request**: On main and develop branches
- **Manual Dispatch**: For on-demand testing

## Operations - Workflow Assignment (`ops-workflow-assignment.yml`)

### Purpose

Automatically assigns appropriate workflows to unassigned `site-monitor` issues by:

1. **Analyzing Labels**: Examines issue labels to determine suitable workflows
2. **High-Confidence Assignment**: Directly assigns workflows when confidence is high
3. **Clarification Requests**: Adds "needs clarification" label when no workflows match
4. **Statistics Tracking**: Provides comprehensive assignment metrics

### Triggers

- **Issue Events**: When new issues are opened or labeled (especially `site-monitor`)
- **Scheduled**: Every 2 hours to catch unassigned issues
- **Manual Dispatch**: With configurable parameters for testing and operations

### Manual Dispatch Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 10 | Maximum issues to process |
| `dry_run` | boolean | true | Preview mode without changes |
| `verbose` | boolean | true | Detailed progress output |
| `statistics_only` | boolean | false | Show stats without processing |

### Jobs
### Safety Features

- **Dry-run by default** for manual execution
- **Statistics tracking** for assignment success rates
- **Conditional execution** based on issue triggers

### Jobs

1. **check-assignment-needed**: Determines if unassigned site-monitor issues exist
2. **assign-workflows**: Processes issues based on trigger and parameters

### Operations - Site Monitoring (`ops-site-monitoring.yml`)

### Purpose

Performs scheduled monitoring of configured websites and creates issues for new content:

1. **Content Discovery**: Uses Google Search API to find new content
2. **Deduplication**: Prevents duplicate issues using content hashing
3. **Issue Creation**: Creates GitHub issues for monitoring results
4. **Rate Limiting**: Respects API limits and quotas

### Triggers

- **Manual Dispatch**: For on-demand monitoring with safety options

## Operations - Issue Processing (`ops-issue-processing.yml`)

### Purpose

Processes site-monitor issues through automated workflows to generate deliverables:

1. **Workflow Execution**: Runs assigned workflows on labeled issues
2. **Document Generation**: Creates deliverables using template system
3. **Git Integration**: Commits results to dedicated branches
4. **Progress Tracking**: Updates issues with processing status

### Triggers

- **Issue Events**: When issues are labeled or assigned
- **Manual Dispatch**: For testing and batch processing

## Operations - Daily Maintenance (`ops-daily-operations.yml`)

### Purpose

Performs daily maintenance tasks including system health checks and routine operations.

## Operations - Weekly Cleanup (`ops-weekly-cleanup.yml`)

### Purpose

Performs weekly cleanup operations to maintain repository health and manage storage.

## Usage Guidelines

### Development Workflows
- `dev-ci.yml` runs automatically on code changes and can be triggered manually for testing

### Operations Workflows
- Site monitoring and issue processing workflows are designed to run on schedules
- All operations workflows support manual dispatch with safety options (dry-run modes)
- Use the setup workflow (`ops-setup-monitoring.yml`) for initial repository configuration
- Status check workflow (`ops-status-check.yml`) provides system health monitoring

### Safety Considerations
- Most workflows default to dry-run mode when triggered manually
- Monitor API quotas and rate limits for external services
- Review logs and artifacts for troubleshooting and verification
- **Conservative limits** for scheduled runs (5 issues max)
- **Statistics reporting** before and after processing
- **No production changes** on scheduled runs without manual override

## Operations - Issue Processing (`ops-issue-processing.yml`)

### Purpose

Automatically processes GitHub issues labeled with `site-monitor` by:

1. Matching issues to appropriate workflows from `docs/workflow/deliverables/`
2. Generating structured research documents based on workflow specifications
3. Committing generated content to the repository
4. Managing issue assignment and status updates

### Triggers

The workflow is triggered by:

- **Issue Events**: When issues are labeled or assigned
- **Manual Dispatch**: For testing or processing specific issues

### Workflow Jobs

#### 1. `check-issues`

Discovers and validates issues that need processing:

- Filters for open issues with `site-monitor` label
- Excludes issues already assigned to `github-actions[bot]`
- Outputs a list of issues for parallel processing
- Uses Python-based issue discovery integrated with the project's existing components

#### 2. `process-issues`

Processes each issue in parallel:

- Assigns issue to `github-actions[bot]` during processing
- Runs the issue processor with appropriate workflow matching
- Generates deliverables based on matched workflow specifications
- Handles both dry-run and live processing modes

#### 3. `summary`

Provides processing results and summary:

- Reports success/failure status for all issues
- Generates workflow summary for GitHub Actions UI
- Provides links to detailed logs for troubleshooting

### Required Secrets

Configure these secrets in your repository settings (`Settings > Secrets and variables > Actions`):

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `GITHUB_TOKEN` | GitHub authentication token | ✅ Auto-provided |
| `GOOGLE_API_KEY` | Google Custom Search API key | ✅ |
| `GOOGLE_SEARCH_ENGINE_ID` | Google Custom Search Engine ID | ✅ |

**Note**: `GITHUB_TOKEN` is automatically provided by GitHub Actions and doesn't need manual configuration.

### Manual Workflow Dispatch

You can manually trigger the workflow with custom parameters:

1. Go to **Actions** tab in your repository
2. Select **Process Issues with Automated Workflows**
3. Click **Run workflow**
4. Configure options:
   - **Issue number**: Process a specific issue (optional)
   - **Dry run**: Test without making changes (default: true)

### Configuration

The workflow uses the same `config.yaml` file as the local application. Ensure your configuration includes:

```yaml
# Agent configuration for GitHub Actions
agent:
  username: "github-actions[bot]"
  processing_timeout: 300
  max_batch_size: 10

# Workflow configuration
workflows:
  directory: "docs/workflow/deliverables"
  cache_enabled: true

# Output configuration
output:
  base_directory: "study"
  create_branches: false  # GitHub Actions commits to main
```

### Workflow Processing Logic

1. **Issue Discovery**: Finds issues with `site-monitor` label
2. **Workflow Matching**: Matches issues to workflows based on additional labels
3. **Assignment**: Assigns issues to `github-actions[bot]` during processing
4. **Generation**: Creates deliverables according to workflow specifications
5. **Commit**: Commits generated content with descriptive commit messages
6. **Cleanup**: Removes assignment and updates issue status

### Output Structure

Generated deliverables are committed to the repository following the structure defined in the matched workflow:

```
study/
  {issue_number}/
    analysis.md
    research.md
    summary.md
    ...
```

### Error Handling

The workflow includes comprehensive error handling:

- **Graceful Degradation**: Falls back to manual processing if automation fails
- **Parallel Processing**: Failures in one issue don't affect others
- **Detailed Logging**: Comprehensive logs for troubleshooting
- **Status Reporting**: Clear success/failure indicators

### Troubleshooting

#### Common Issues

**1. "No issues found to process"**
- Verify issues have the `site-monitor` label
- Check that issues aren't already assigned to `github-actions[bot]`
- Ensure issues are in "open" state

**2. "Workflow matching failed"**
- Verify workflow definitions exist in `docs/workflow/deliverables/`
- Check that workflows have proper YAML front matter with `trigger_labels`
- Review issue labels to ensure they match workflow trigger conditions

**3. "Permission denied" errors**
- Verify `GITHUB_TOKEN` has sufficient permissions
- Check repository settings for Actions permissions
- Ensure branch protection rules allow automated commits

**4. "API rate limit exceeded"**
- Monitor Google API usage quotas
- Consider implementing request batching for large issue volumes
- Review `daily_query_limit` in configuration

#### Debugging Steps

1. **Check workflow logs**:
   - Go to Actions tab > Select failed workflow run
   - Review individual job logs for detailed error messages

2. **Test locally**:
   ```bash
   python main.py process-issues --issue {number} --dry-run
   ```

3. **Validate configuration**:
   ```bash
   python main.py status --config config.yaml
   ```

4. **Manual workflow trigger**:
   - Use manual dispatch with dry-run enabled
   - Process single issues first before batch operations

### Best Practices

#### Security

- Never commit secrets to the repository
- Use GitHub secrets for all sensitive configuration
- Regularly rotate API keys and tokens
- Review workflow permissions periodically

#### Performance

- Process issues in small batches to avoid API rate limits
- Use parallel processing judiciously (max 3 concurrent jobs)
- Implement caching for workflow definitions
- Monitor resource usage and adjust timeouts as needed

#### Maintenance

- Regularly review and update workflow definitions
- Monitor processing success rates and adjust error handling
- Keep dependencies updated in `requirements.txt`
- Document any custom workflow additions

### Integration with Existing Workflows

The issue processing workflow integrates seamlessly with existing automation:

- **Site Monitoring**: Issues created by site monitoring automatically trigger processing
- **Manual Issues**: Manually created issues with appropriate labels are also processed
- **Batch Operations**: Supports both individual and batch processing modes
- **Cleanup**: Integrates with existing cleanup workflows for maintenance

### Workflow Customization

To customize the workflow behavior:

1. **Modify triggers**: Edit the `on:` section to change when the workflow runs
2. **Adjust parallelism**: Change `max-parallel` in the strategy matrix
3. **Update timeouts**: Modify timeout values in individual steps
4. **Add custom steps**: Insert additional processing steps as needed

### Monitoring and Metrics

The workflow provides several monitoring capabilities:

- **GitHub Actions UI**: Visual workflow status and history
- **Step summaries**: Detailed processing results
- **Commit messages**: Clear traceability of automated changes
- **Issue comments**: Status updates and clarification requests

For additional monitoring, consider integrating with external tools or implementing custom webhook notifications.