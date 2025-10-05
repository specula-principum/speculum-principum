# Copilot Instructions for Speculum Principum

## Architecture & Core Flow
Three-tier system: **Site Monitoring** (Google Search API → deduplication → GitHub issues) + **AI Workflow Assignment** (GitHub Models API → intelligent workflow matching) + **Issue Processing** (workflow-driven document generation)

**Core modules**:
- `src/core/site_monitor.py` - Site monitoring orchestration
- `src/core/issue_processor.py` - Automated workflow processing engine
- `src/core/batch_processor.py` - Batch processing for multiple issues with concurrent workers
- `src/core/processing_orchestrator.py` - High-level processing coordination and orchestration
- `src/agents/ai_workflow_assignment_agent.py` - AI-powered workflow assignment using GitHub Models API
- `src/agents/workflow_assignment_agent.py` - Label-based workflow assignment (fallback)
- `src/workflow/workflow_matcher.py` - Workflow discovery and matching logic
- `src/workflow/deliverable_generator.py` - Template-based document generation
- `src/workflow/template_engine.py` - Template processing and rendering
- `src/workflow/workflow_schemas.py` - Workflow validation schemas
- `src/storage/git_manager.py` - Git operations for branch/commit management
- `src/clients/search_client.py` - Google API + rate limiting
- `src/core/deduplication.py` - SHA256 content hashing in `processed_urls.json`
- `src/utils/config_manager.py` - YAML with `${ENV_VAR}` substitution
- `src/utils/cli_helpers.py` - Enhanced CLI utilities with progress reporting

**Site monitoring flow**: `search_all_sites()` → `_filter_new_results()` → `_create_individual_issues()` → `_mark_results_processed()`

**AI workflow assignment flow**: Issue analysis → GitHub Models API → Semantic content analysis → Multi-factor scoring → Workflow recommendation → Label assignment

**Issue processing flow**: Label detection → Workflow matching → Agent assignment → Document generation → Git commits → Issue status updates

## Key Commands

**Site monitoring**: `python main.py monitor --config config.yaml --no-individual-issues`
**AI workflow assignment**: `python main.py assign-workflows --dry-run --limit 10 --verbose`
**Issue processing**: `python main.py process-issues --issue 123 --dry-run --verbose`
**Batch processing**: `python main.py process-issues --batch-size 10 --from-monitor --continue-on-error`
**Status/validation**: `python main.py status`, `pytest tests/ -v`

## Code Quality Standards

**Testing**: Use centralized fixtures from `tests/conftest.py`. Mock GitHub API, GitHub Models API, and workflows. Validate with `ConfigValidator.validate_config_file()`.

**Naming**: `create_*` factories, `get_*` status/info, `_private_method` helpers, `handle_*_command` for CLI.

**Error handling**: Google API rate limiting via `daily_query_limit`, GitHub retry logic, GitHub Models API fallback, workflow validation, git conflict resolution, batch processing error recovery.

**Configuration**: All configs use `${VAR_NAME}` substitution. Required: `GITHUB_TOKEN`, `GOOGLE_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID`. AI features run exclusively through GitHub Models—no external provider secrets are needed. Workflows in `docs/workflow/deliverables/`.

## Enhanced Features

**AI-Powered Workflow Assignment**: 
- GitHub Models API integration for semantic content analysis
- Multi-factor scoring (labels + content + patterns)
- Automatic workflow recommendations with confidence scores
- Fallback to label-based matching when AI unavailable

**Advanced Batch Processing**:
- Concurrent worker pools for parallel issue processing
- Progress reporting with detailed metrics and timing
- Error recovery and continuation on failure
- Filter-based issue selection (assignee, labels, batch size)

**Conditional Workflows**:
- Dynamic deliverable selection based on issue characteristics
- Label-based conditions (urgent, security, performance)
- Adaptive content generation with multiple templates
- Custom branch and file naming patterns

**GitHub Actions Integration**:
- Automated workflow assignment every 2 hours
- Manual dispatch with configurable parameters
- Statistics and progress reporting
- Safety checks and dry-run modes

## Essential Patterns

**Deduplication**: Content hash = `sha256(normalized_url + title.lower())[:16]`. JSON storage with retention policies.

**Workflow system**: YAML definitions with `trigger_labels`, conditional deliverables, template-based generation, Git branch per issue.

**AI workflow assignment**: GitHub Models API → ContentAnalysis → Multi-factor scoring → Workflow recommendation → Label assignment.

**Batch processing**: ProcessingOrchestrator → BatchProcessor → Concurrent workers → Progress reporting → Error recovery.

**Safe testing**: Always use `--dry-run` and `--no-individual-issues` to avoid API/Git changes.

**VS Code integration**: Use F5 debug configs and tasks. Virtual environment at `.venv/bin/python`.

## Advanced Workflows

**Available GitHub Actions**:
- `ops-workflow-assignment.yml` - Automated AI workflow assignment every 2 hours
- `ops-issue-processing.yml` - Automated batch issue processing 
- `ops-daily-operations.yml` - Combined monitoring and processing pipeline
- `ops-site-monitoring.yml` - Daily site monitoring with Google API
- `ops-setup-monitoring.yml` - Repository initialization and label management
- `ops-weekly-cleanup.yml` - Automated cleanup of old monitoring data
- `ops-status-check.yml` - System health and configuration validation

**CLI Command Categories**:
- **Site monitoring**: `monitor`, `setup`, `status`, `cleanup`
- **AI workflow assignment**: `assign-workflows` with AI analysis and statistics
- **Issue processing**: `process-issues` with batch mode, filtering, and orchestration
- **Legacy**: `create-issue` for manual issue creation

**Advanced CLI Options**:
- `--from-monitor` - Process issues discovered during monitoring
- `--continue-on-error` - Batch processing with error recovery
- `--statistics` - Show detailed workflow assignment metrics
- `--disable-ai` - Fallback to label-based workflow matching
- `--assignee-filter` - Process only issues assigned to specific user
- `--label-filter` - Additional label-based filtering beyond site-monitor