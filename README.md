# Speculum Principum - Site Monitor Service

A comprehensive Python application that monitors websites for updates using Google Custom Search API and automatically creates GitHub issues when changes are detected. The service runs via GitHub Actions and includes sophisticated deduplication, rate limiting, and structured issue creation.

## 🎯 Features

### Core Monitoring
- **Automated Site Monitoring**: Daily monitoring of configured websites for new content
- **Google Custom Search Integration**: Uses Google Custom Search API for reliable, date-filtered search results
- **Smart Deduplication**: Prevents duplicate GitHub issues using content hashing and URL normalization
- **Rate Limiting**: Respects Google API limits (100 queries/day free tier) with intelligent quota management

### GitHub Integration  
- **Structured Issue Creation**: Creates detailed, formatted GitHub issues with search metadata
- **Daily Summary Reports**: Comprehensive daily summaries with statistics and trends
- **Label Management**: Automatic creation and management of monitoring labels
- **Issue Lifecycle**: Automatic cleanup of old monitoring issues

### Configuration & Deployment
- **YAML Configuration**: Flexible, environment-variable-enabled configuration system
- **GitHub Actions Workflows**: Fully automated execution with manual trigger options
- **Persistent Storage**: JSON-based deduplication tracking with data retention policies
- **Comprehensive Logging**: Detailed logging with configurable levels and file output

### Automated Issue Processing
- **AI-Powered Workflow Engine**: Automatically processes issues labeled with `site-monitor` using customizable workflow definitions
- **Dynamic Workflow Matching**: Intelligent matching of issues to appropriate workflows based on labels and content
- **Structured Document Generation**: Generates comprehensive research documents, analysis reports, and deliverables
- **Template-Based Content**: Flexible template system for consistent document formatting and structure
- **Git Integration**: Automatic branch creation, content versioning, and commit management
- **Adaptive Processing**: Workflows adapt based on issue characteristics, urgency, and complexity

## 📁 Project Structure

```
speculum-principum/
├── .github/
│   └── workflows/
│       ├── ops-site-monitoring.yml      # Daily monitoring workflow
│       ├── setup-monitoring.yml     # Repository setup workflow
│       └── weekly-cleanup.yml       # Weekly data cleanup workflow
├── .vscode/                         # VS Code debugging configurations and tasks
├── src/
│   ├── __init__.py
│   ├── clients/
│   │   ├── github_issue_creator.py  # GitHub API operations
│   │   └── search_client.py         # Google Custom Search API client
│   ├── core/
│   │   ├── site_monitor.py          # Main monitoring service orchestration
│   │   ├── issue_processor.py       # Automated issue processing engine
│   │   ├── batch_processor.py       # Batch processing for multiple issues
│   │   ├── deduplication.py         # URL/content deduplication system
│   │   └── processing_orchestrator.py # High-level processing coordination
│   ├── storage/
│   │   └── git_manager.py           # Git operations and version control
│   ├── utils/
│   │   ├── config_manager.py        # Configuration loading and validation
│   │   ├── cli_helpers.py           # Command-line interface utilities
│   │   └── logging_config.py        # Logging configuration
│   └── workflow/
│       ├── workflow_matcher.py      # Workflow discovery and matching logic
│       ├── deliverable_generator.py # Document generation system
│       ├── template_engine.py       # Template processing and rendering
│       └── workflow_schemas.py      # Workflow validation schemas
├── docs/
│   ├── issue-processor.md           # Issue processor documentation
│   ├── workflow-creation-guide.md   # Guide for creating workflows
│   ├── development/                 # Development documentation
│   └── workflow/
│       └── deliverables/            # Workflow definition files
├── templates/
│   ├── entity_backbone.md           # Standardized entity backbone section
│   ├── person_risk_core.md          # Person-centric risk assessment core
│   ├── place_intelligence_core.md   # Jurisdiction and venue intelligence core
│   ├── evidence_catalog_core.md     # Asset and evidence cataloguing core
│   ├── statute_research_core.md     # Statutory and regulatory research stack
│   ├── precedent_explorer_core.md   # Case law precedent explorer core
│   ├── lead_development_core.md     # Investigative lead development planner
│   ├── coordination_brief_core.md   # Inter-agency coordination brief core
│   ├── compliance_monitoring_core.md # Compliance and remediation scorecard
│   ├── gao_compliance_appendix.md   # GAO compliance appendix shared block
│   └── confidentiality_banner.md    # Confidentiality banner include
├── study/                           # Generated content output directory
├── tests/
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   ├── e2e/                         # End-to-end tests
│   └── [test files]                 # Individual test modules
├── main.py                          # Application entry point
├── config.yaml                      # Site monitoring configuration
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Project configuration
├── Makefile                         # Build and development tasks
├── run_tests.sh                     # Test execution script
└── README.md                        # This file
```

## 🚀 Quick Start

### 1. Setup Google Custom Search API

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable Custom Search API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Custom Search API" and enable it

3. **Create API Key**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the generated API key

4. **Create Custom Search Engine**:
   - Go to [Google Custom Search](https://cse.google.com/)
   - Click "Add" to create a new search engine
   - Configure sites to search (or use `*` for entire web)
   - Copy the Search Engine ID

### 2. Configure Repository Secrets

Add these secrets to your GitHub repository:

- `GOOGLE_API_KEY`: Your Google API key
- `GOOGLE_SEARCH_ENGINE_ID`: Your Custom Search Engine ID

### 3. Configure Sites to Monitor

Edit `config.yaml` to specify the sites you want to monitor:

```yaml
sites:
  - url: docs.python.org
    name: Python Documentation
    keywords:
      - "new"
      - "updated"
      - "release"
    max_results: 10
    search_paths:
      - /3/
      - /release/
    exclude_paths:
      - /bugs/
      - /archives/

  - url: github.blog
    name: GitHub Blog
    keywords:
      - "features"
      - "announcement"
    max_results: 5

github:
  repository: ${GITHUB_REPOSITORY}
  issue_labels:
    - site-monitor
    - automated
    - documentation
  default_assignees:
    - ${GITHUB_ACTOR}

search:
  api_key: ${GOOGLE_API_KEY}
  search_engine_id: ${GOOGLE_SEARCH_ENGINE_ID}
  daily_query_limit: 90
  results_per_query: 10
  date_range_days: 1

storage_path: processed_urls.json
log_level: INFO
```

### 4. Initialize Repository

Run the setup workflow to create necessary labels and verify configuration:

1. Go to Actions tab in your repository
2. Select "Setup Site Monitoring" workflow
3. Click "Run workflow"

### 5. Run Monitoring

The monitoring runs automatically daily at 9:00 AM UTC, or you can trigger it manually:

1. Go to Actions tab
2. Select "Daily Site Monitoring" workflow  
3. Click "Run workflow"

## 🤖 Automated Issue Processing

The Issue Processor is an intelligent agent that automatically processes GitHub issues labeled with `site-monitor` by executing customizable workflows and generating structured research documents.

### Key Features

- **Smart Workflow Matching**: Automatically selects appropriate workflows based on issue labels
- **Document Generation**: Creates structured research reports, analysis documents, and deliverables
- **Git Integration**: Manages branches, commits, and version control for generated content
- **Template System**: Uses customizable templates for consistent document formatting
- **Adaptive Processing**: Workflows adapt based on issue characteristics and complexity

### Quick Start with Issue Processing

#### 1. Create Workflow Definitions

Create workflow files in `docs/workflow/deliverables/criminal-law/`:

```yaml
# docs/workflow/deliverables/criminal-law/person-entity-profiling.yaml
name: "Person Entity Profiling & Risk Flagging"
description: "Profiles involved individuals, scores risk posture, and identifies conflicts relevant to GAO-aligned criminal matters."
workflow_version: "1.0.0"
category: "entity-foundation"
priority: "high"
confidence_threshold: 0.75

trigger_labels:
  - "person-profile"
  - "risk-flag"
  - "criminal-law"

required_entities:
  - entity_type: "person"
    min_count: 1
    min_confidence: 0.7
  - entity_type: "place"
    min_count: 0
    min_confidence: 0.6
  - entity_type: "thing"
    min_count: 0
    min_confidence: 0.6

deliverable_templates:
  - "entity_backbone"
  - "person_risk_core"
  - "gao_compliance_appendix"

deliverables:
  - name: "entity-backbone"
    title: "Entity Backbone"
    description: "Standardized person/place/thing tables with confidentiality banner."
    template: "entity_backbone.md"
    required: true
    order: 1
  - name: "person-risk-core"
    title: "Risk Posture Core"
    description: "Risk matrix, conflict markers, and sanctions checks for all involved persons."
    template: "person_risk_core.md"
    required: true
    order: 2
  - name: "gao-compliance-appendix"
    title: "GAO Compliance Appendix"
    description: "Citations, audit evidence, and decision log for GAO review."
    template: "gao_compliance_appendix.md"
    required: true
    order: 3
```

#### 2. Configure Agent Settings

Add agent configuration to your `config.yaml`:

```yaml
agent:
  username: "github-actions[bot]"
  timeout: 3600
  workflow_directory: "docs/workflow/deliverables"
  output_directory: "study"
```

#### 3. Process Issues

```bash
# Process a specific issue
python main.py process-issues --issue 123

# Batch process all site-monitor issues
python main.py process-issues --batch

# Dry run to see what would be processed
python main.py process-issues --issue 123 --dry-run
```

#### 4. Issue Processing Flow

1. **Label your issue** with `site-monitor` and workflow-specific labels (e.g., `person-profile`, `criminal-law`)
2. **Agent assigns itself** and begins processing
3. **Workflow executes** and generates deliverables in the `study/` directory
4. **Git branch created** with generated content
5. **Issue updated** with completion status and links to generated documents

### Available Commands

```bash
# Workflow assignment
python main.py assign-workflows --dry-run              # Assign workflows to issues (safe)
python main.py assign-workflows --limit 10             # Process up to 10 issues
python main.py assign-workflows --statistics           # Show assignment statistics

# Issue processing
python main.py process-issues --issue 123              # Process specific issue
python main.py process-issues --batch                  # Process all eligible issues
python main.py process-issues --workflow-category legal-research  # Filter by taxonomy category

# Workflow management
python main.py list-workflows                          # Show available workflows
python main.py validate-workflows                      # Check workflow syntax
python main.py workflow-stats                          # Show taxonomy adoption statistics

# Status and monitoring
python main.py status --show-processing                # Show active processing
python main.py list-processing                         # List in-progress issues
```

### Example Workflows

Explore the GAO-aligned criminal law workflows under `docs/workflow/deliverables/criminal-law/`:

- **Person Entity Profiling & Risk Flagging** (`person-entity-profiling.yaml`): Builds entity dossiers and conflict checks.
- **Statutory & Regulatory Research Tracker** (`statutory-regulatory-research-tracker.yaml`): Compiles statute digests and compliance checklists.
- **Inter-Agency Coordination Briefs** (`inter-agency-coordination-briefs.yaml`): Generates coordination playbooks for GAO engagements.

### Documentation

For comprehensive information about creating and using workflows:

- 📖 **[Issue Processor Documentation](docs/issue-processor.md)**: Complete system documentation
- 🛠️ **[Workflow Creation Guide](docs/workflow-creation-guide.md)**: Step-by-step workflow creation
- 💡 **[Criminal Law Workflows](docs/workflow/deliverables/criminal-law/)**: GAO-aligned workflow definitions

## 📖 Detailed Configuration

### Site Configuration Options

```yaml
sites:
  - url: example.com                 # Required: Domain to monitor
    name: Human Readable Name        # Required: Display name
    keywords:                        # Optional: Keywords to search for
      - documentation
      - changelog
      - release
    max_results: 10                  # Optional: Max results per search (default: 10)
    search_paths:                    # Optional: Limit search to specific paths
      - /docs/
      - /blog/
    exclude_paths:                   # Optional: Exclude specific paths
      - /admin/
      - /private/
    custom_search_terms:             # Optional: Additional search terms
      - "new features"
      - "what's new"
```

### GitHub Configuration

```yaml
github:
  repository: owner/repo-name        # Required: GitHub repository
  issue_labels:                      # Optional: Labels to apply to issues
    - site-monitor
    - automated
    - documentation
  default_assignees:                 # Optional: Default issue assignees
    - maintainer-username
```

### Search Configuration

```yaml
search:
  api_key: YOUR_API_KEY             # Required: Google API key
  search_engine_id: YOUR_ENGINE_ID  # Required: Custom Search Engine ID
  daily_query_limit: 90             # Optional: Daily API call limit (max 100)
  results_per_query: 10             # Optional: Results per query (max 10)
  date_range_days: 1                # Optional: Search in last N days
```

### Environment Variables

The configuration supports environment variable substitution:

- `${VARIABLE_NAME}`: Required variable (fails if not set)
- `${VARIABLE_NAME:default}`: Optional with default value

Common variables:
- `${GITHUB_REPOSITORY}`: Current repository (auto-provided in Actions)
- `${GITHUB_ACTOR}`: Current user (auto-provided in Actions)
- `${GOOGLE_API_KEY}`: Your Google API key (from secrets)
- `${GOOGLE_SEARCH_ENGINE_ID}`: Your search engine ID (from secrets)

## 🔧 Local Development

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/speculum-principum.git
cd speculum-principum

# Install dependencies
pip install -r requirements.txt

# Copy and configure settings
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

### Local Usage

```bash
# Set environment variables
export GITHUB_TOKEN="your_token"
export GOOGLE_API_KEY="your_api_key"
export GOOGLE_SEARCH_ENGINE_ID="your_engine_id"

# Site monitoring commands
python main.py monitor --config config.yaml
python main.py setup --config config.yaml
python main.py status --config config.yaml
python main.py cleanup --config config.yaml --days-old 7 --dry-run

# Workflow assignment commands
python main.py assign-workflows --config config.yaml --dry-run --verbose    # Safe test run
python main.py assign-workflows --config config.yaml --limit 10             # Assign to 10 issues
python main.py assign-workflows --config config.yaml --statistics           # Show statistics

# Issue processing commands
python main.py process-issues --issue 123                 # Process specific issue
python main.py process-issues --batch                     # Process all eligible issues
python main.py process-issues --issue 123 --dry-run       # Preview processing
python main.py list-workflows                             # Show available workflows
python main.py validate-workflows                         # Validate workflow files
python main.py workflow-stats                             # Show workflow statistics

# Legacy command
python main.py create-issue --title "Test Issue" --body "Test content"
```

### GitHub Workflows & VS Code Integration

The repository includes automated GitHub workflows and VS Code integration:

#### GitHub Workflows
- **ops-workflow-assignment.yml**: Automatically assigns workflows to unassigned site-monitor issues
  - Triggers on new issues, manual dispatch, or every 2 hours
  - Includes safety checks and statistics reporting
  - Supports dry-run mode for testing

#### VS Code Tasks (F1 → "Tasks: Run Task")
- **Assign Workflows (Dry Run)**: Safe testing with 10 issue limit
- **Assign Workflows (Execute)**: Production run with 20 issue limit  
- **Show Workflow Assignment Statistics**: Display current GitHub statistics

#### VS Code Debug Configurations (F5)
- **Assign Workflows (Dry Run)**: Debug workflow assignment safely
- **Assign Workflows (Execute)**: Debug production workflow assignment
- **Show Workflow Assignment Statistics**: Debug statistics gathering

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov=main --cov-report=html

# Run specific test file
pytest tests/test_config_manager.py -v
```

### VS Code Development & Debugging

The project includes comprehensive VS Code configurations for easy development and debugging:

#### Debug Configurations (F5 or Run & Debug panel)

- **Monitor Sites (Safe Mode - No Issues)**: Run monitoring without creating any GitHub issues
- **Monitor Sites (Create Individual Issues)**: Run monitoring with individual issues but no summary
- **Monitor Sites (Full - All Issues)**: Complete monitoring cycle with all issue creation
- **Show Status**: Display current monitoring status and configuration
- **Setup Repository**: Initialize repository with monitoring setup
- **Cleanup (Dry Run)**: Preview cleanup operations without executing them
- **Cleanup (Execute)**: Perform actual cleanup of old data
- **Create Test Issue**: Create a test GitHub issue for debugging
- **Debug Current File**: Debug the currently open Python file

#### Available Tasks (Ctrl+Shift+P → "Tasks: Run Task")

- **Install Dependencies**: Install/update Python packages from requirements.txt
- **Run Tests**: Execute all tests with verbose output
- **Run Tests with Coverage**: Run tests and generate coverage reports
- **Monitor Sites (Safe)**: Safe monitoring run without creating issues
- **Show Monitoring Status**: Display current monitoring status
- **Cleanup (Dry Run)**: Preview cleanup operations
- **Lint Code**: Check code style with flake8
- **Format Code**: Auto-format code with black
- **Build Package**: Build distributable package

#### Environment Setup

The workspace is pre-configured with:
- Python virtual environment (`.venv/bin/python`)
- Automatic environment activation in terminals
- Environment variables loaded from `.env` file
- PyTest integration for testing

To start debugging:
1. Open the project in VS Code
2. Press F5 or go to Run & Debug panel
3. Select a configuration from the dropdown
4. Set breakpoints as needed
5. Start debugging!

## 🔄 Workflows

### Daily Site Monitoring (`ops-site-monitoring.yml`)

- **Schedule**: Daily at 9:00 AM UTC
- **Trigger**: Automatic (cron) or manual
- **Function**: Searches configured sites and creates GitHub issues for new content

**Manual Options**:
- `no_individual_issues`: Skip creating individual issues per site
- `no_summary_issue`: Skip creating daily summary issue

### Setup Monitoring (`setup-monitoring.yml`)

- **Schedule**: Manual trigger only
- **Function**: Sets up repository with necessary labels and configuration
- **Use**: Run once when first setting up the monitoring system

### Weekly Cleanup (`weekly-cleanup.yml`)

- **Schedule**: Weekly on Sundays at 2:00 AM UTC
- **Trigger**: Automatic or manual
- **Function**: Cleans up old monitoring data and closes old issues

**Manual Options**:
- `days_old`: Age threshold for cleanup (default: 7 days)
- `dry_run`: Show what would be cleaned without making changes

## 📊 Issue Structure

### Individual Site Issues

Created when new content is found on a monitored site:

```markdown
# New Updates Found on Python Documentation

🔍 **Monitoring Results** | 📅 **Date**: 2024-01-15 09:00 UTC

Found 2 new update(s) on **Python Documentation**:

## 1. What's New in Python 3.12

**🔗 URL**: https://docs.python.org/3/whatsnew/3.12.html
**📝 Snippet**: Python 3.12 introduces new features including...

## 2. Python 3.11.8 Release Notes

**🔗 URL**: https://docs.python.org/3/whatsnew/changelog.html
**📝 Snippet**: This release includes security fixes and...

## 🤖 Automation Details
- **Search Engine**: Google Custom Search API
- **Detection Time**: 2024-01-15 09:00 UTC
- **Total Results**: 2
```

### Daily Summary Issues

Created daily with overview of all monitoring activities:

```markdown
# Daily Site Monitoring Summary - 2024-01-15

🔍 **Monitoring Overview** | 📊 **Summary Statistics**

## 📈 Summary Statistics

| Metric | Value |
|--------|-------|
| **Sites Monitored** | 5 |
| **Sites with Updates** | 2 |
| **Total Updates Found** | 7 |
| **Success Rate** | 40.0% |

## 🏠 Per-Site Breakdown

### Python Documentation (3 updates)
1. [What's New in Python 3.12](https://docs.python.org/3/whatsnew/3.12.html)
2. [Python 3.11.8 Release Notes](https://docs.python.org/3/whatsnew/changelog.html)
3. [Tutorial Updates](https://docs.python.org/3/tutorial/)

### GitHub Blog (4 updates)
1. [New GitHub Features](https://github.blog/features)
...
```

## 🛠️ Advanced Configuration

### Rate Limiting Strategy

The system implements intelligent rate limiting:

- **Daily Limit**: Configurable up to 100 queries/day (Google free tier)
- **Query Spacing**: Minimum 1 second between API calls
- **Quota Management**: Tracks daily usage and stops before exceeding limits
- **Error Handling**: Graceful degradation when limits are approached

### Deduplication Logic

Prevents duplicate issues through multiple mechanisms:

1. **Content Hashing**: SHA-256 hash of normalized URL + title
2. **URL Normalization**: Removes tracking parameters, normalizes case
3. **Similar Title Detection**: Finds entries with similar titles (configurable threshold)
4. **Temporal Tracking**: Tracks when entries were last processed

### Storage Management

- **File Format**: JSON with metadata and entry arrays
- **Retention**: Configurable retention period (default: 30 days)
- **Backup**: Automatic backup of corrupted files
- **Compression**: Efficient storage of large datasets

## 🔍 Monitoring & Debugging

### Log Levels

Configure logging detail in `config.yaml`:

```yaml
log_level: DEBUG    # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Log Files

- `site_monitor.log`: Main application log
- Workflow artifacts: Logs uploaded to GitHub Actions artifacts

### Status Monitoring

Check system status:

```bash
python main.py status --config config.yaml
```

Returns:
- Repository information
- Sites configured
- Rate limit status
- Deduplication statistics
- Configuration summary

### Troubleshooting

**Common Issues**:

1. **API Rate Limit Exceeded**:
   - Reduce `daily_query_limit` in config
   - Reduce number of monitored sites
   - Check for other applications using the same API key

2. **No Results Found**:
   - Verify site URLs are accessible
   - Check Custom Search Engine configuration
   - Adjust search keywords and paths
   - Verify `date_range_days` setting

3. **Configuration Errors**:
   - Validate YAML syntax
   - Check required environment variables
   - Verify API credentials

4. **GitHub API Issues**:
   - Check `GITHUB_TOKEN` permissions
   - Verify repository access
   - Check repository label configuration

## 🤝 Contributing

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-fork/speculum-principum.git
cd speculum-principum

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov pytest-mock responses

# Run tests
pytest
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write comprehensive docstrings
- Include unit tests for new features

### Testing

- Write unit tests for all new functionality
- Maintain test coverage above 80%
- Test both success and error scenarios
- Mock external API calls in tests

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🙏 Acknowledgments

- Google Custom Search API for reliable search functionality
- GitHub Actions for automated execution platform
- PyGitHub library for GitHub API integration
- The Python community for excellent tooling and libraries

---

## 📞 Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review [existing issues](https://github.com/your-username/speculum-principum/issues)
3. Create a [new issue](https://github.com/your-username/speculum-principum/issues/new) with detailed information

**When reporting issues, include**:
- Configuration file (with secrets redacted)
- Error messages and log output
- Steps to reproduce the issue
- Expected vs actual behavior

Edit `.env` with your values:
- `GITHUB_TOKEN`: Your GitHub personal access token
- `GITHUB_REPOSITORY`: Your repository in format `owner/repo`

### 4. GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Create a new token with the following permissions:
   - `repo` (full repository access)
   - `workflow` (if you want to trigger workflows)
3. The `GITHUB_TOKEN` secret is automatically available in GitHub Actions

## Usage

### Manual Issue Creation

You can manually trigger issue creation through GitHub Actions:

1. Go to your repository on GitHub
2. Click on "Actions" tab
3. Select "Create Issue" workflow
4. Click "Run workflow"
5. Fill in the form:
   - **Title**: Required issue title
   - **Body**: Optional issue description
   - **Labels**: Comma-separated labels (e.g., `bug,urgent`)
   - **Assignees**: Comma-separated usernames (e.g., `user1,user2`)

### Scheduled Operations

The project includes automated scheduled operations:

- **Daily Standup Issues**: Created every day at 9 AM UTC
- **Weekly Review Issues**: Can be triggered manually
- **Monthly Report Issues**: Can be triggered manually

### Local Development

Run the application locally (requires proper environment setup):

```bash
# Create a simple issue
python main.py create-issue --title "Test Issue" --body "This is a test issue"

# Create an issue with labels and assignees
python main.py create-issue --title "Bug Report" --body "Found a bug" --labels bug urgent --assignees username1 username2
```

## Available Operations

### create-issue

Creates a new GitHub issue in the repository.

**Arguments:**
- `--title` (required): Issue title
- `--body` (optional): Issue description/body
- `--labels` (optional): Space-separated list of labels
- `--assignees` (optional): Space-separated list of usernames to assign

**Example:**
```bash
python main.py create-issue \
  --title "New Feature Request" \
  --body "Detailed description of the feature" \
  --labels "enhancement" "feature-request" \
  --assignees "developer1" "developer2"
```

## GitHub Actions Workflows

### create-issue.yml

Manual workflow for creating issues with custom parameters.

**Triggers:**
- Manual dispatch (`workflow_dispatch`)

**Inputs:**
- `title`: Issue title (required)
- `body`: Issue description (optional)
- `labels`: Comma-separated labels (optional)
- `assignees`: Comma-separated assignees (optional)

### scheduled-operations.yml

Automated and manual operations for regular maintenance tasks.

**Triggers:**
- Scheduled: Daily at 9 AM UTC
- Manual dispatch with operation type selection

**Operations:**
- `daily-standup-issue`: Creates daily standup template
- `weekly-review-issue`: Creates weekly review template
- `monthly-report-issue`: Creates monthly report template

## Extending the Framework

### Adding New Operations

1. **Add the operation to `main.py`**:
   ```python
   parser.add_argument('operation', choices=['create-issue', 'your-new-operation'])
   ```

2. **Implement the operation in `src/github_issue_creator.py`**:
   ```python
   def your_new_operation(self, **kwargs):
       # Implementation here
       pass
   ```

3. **Add the operation logic to `main.py`**:
   ```python
   elif args.operation == 'your-new-operation':
       # Handle your new operation
   ```

### Adding New Workflows

Create new workflow files in `.github/workflows/` following the existing patterns:

```yaml
name: Your New Workflow

on:
  workflow_dispatch:
    # Your trigger configuration

jobs:
  your-job:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write  # Add permissions as needed
    steps:
      # Your workflow steps
```

## Security Considerations

- The `GITHUB_TOKEN` is automatically provided in GitHub Actions
- Workflows run with minimal required permissions
- No sensitive data is logged or exposed
- All operations are auditable through GitHub Actions logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run the test suite: `./run_tests.sh all`
6. Submit a pull request

## Testing

The project includes a comprehensive test suite with unit tests, integration tests, and automated CI/CD testing.

### Running Tests

**Quick test run:**
```bash
./run_tests.sh unit
```

**Full test suite with coverage:**
```bash
./run_tests.sh coverage
```

**All available test options:**
```bash
./run_tests.sh help
```

**Using Make (alternative):**
```bash
make test          # Run all tests
make test-unit     # Run unit tests only
make coverage      # Run with coverage report
make lint          # Run linting checks
make security      # Run security scans
```

**Manual pytest execution:**
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov=main --cov-report=html

# Run only unit tests
pytest tests/ -v -m "not integration"

# Run only integration tests
pytest tests/ -v -m integration
```

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Test fixtures and configuration
├── test_smoke.py            # Basic smoke tests
├── test_github_issue_creator.py # Unit tests for GitHub operations
└── test_main.py            # Integration tests for main application
```

### Test Categories

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test complete workflows and CLI interactions
- **Smoke Tests**: Basic tests to validate test suite setup

### Continuous Integration

The project uses GitHub Actions for automated testing:

- **dev-ci.yml**: Runs full test suite on multiple Python versions
- Tests run on every push and pull request
- Includes linting, security scanning, and type checking
- Coverage reports are uploaded to Codecov

### Test Configuration

Test configuration is managed through:
- `pyproject.toml`: pytest and coverage settings
- `conftest.py`: shared fixtures and test utilities
- GitHub Actions workflows for CI/CD

## License

This project is open source. Please check the LICENSE file for details.

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure your GitHub token has the necessary permissions
2. **Invalid Labels**: Labels must exist in the repository before they can be applied
3. **Invalid Assignees**: Users must have access to the repository to be assigned

### Debugging

Check the GitHub Actions logs for detailed error messages and execution traces.

### Getting Help

- Create an issue in this repository for bugs or feature requests
- Check the GitHub Actions documentation for workflow-related questions