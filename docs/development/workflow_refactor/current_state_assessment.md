# Current State Assessment

**Document Purpose**: Capture how site monitoring, workflow assignment, and issue processing currently operate, highlighting friction and technical debt that motivate the refactor.

## 1. Site Monitoring Workflow
- **Entry Point**: `python main.py monitor --config config.yaml`
- **Key Module**: `src/core/site_monitor.py`
- **Flow**:
  1. Pull configured sites and queries via `search_client`.
  2. Deduplicate results with `processed_urls.json` (SHA256 hash of normalized URL + lowercase title).
  3. Create GitHub issues for new findings using `git_manager` + `github_issue_creator` utilities.
  4. Optionally mark results for individual issue creation (toggle via CLI flag).
- **Observed Gaps**:
  - Issues receive discovery labels (e.g., `monitor::queued`) but lack actionable descriptions.
  - Metadata about the retrieved page (rank, timestamp, raw excerpt) is inconsistently persisted.
  - Monitoring runs do not coordinate with downstream workload capacity (no batching/prioritization signals).

## 2. AI Workflow Assignment
- **Entry Point**: `python main.py assign-workflows`
- **Key Modules**: `src/agents/ai_workflow_assignment_agent.py`, `src/workflow/workflow_matcher.py`, `src/workflow/workflow_schemas.py`
- **Flow**:
  1. Identify candidate issues via label filters or search queries.
  2. Retrieve issue body + referenced URLs and (optionally) fetch target page content.
  3. Invoke GitHub Models API to classify content and recommend workflows.
  4. Apply recommended labels and confidence scores; fallback to rule-based matcher if AI unavailable.
- **Observed Gaps**:
  - AI label assignment supplements rather than replaces the discovery label, leaving issues tagged with both.
  - The agent does not consistently persist the content summary it uses, limiting transparency for specialists.
  - Workflow assignment does not confirm whether issue-processing has already acted, enabling duplicate work.

## 3. Issue Processing
- **Entry Point**:
  - `python main.py process-issues --dry-run` (unified path; supersedes the legacy `process-copilot-issues` command as of 2025-09-30)
- **Key Modules**: `src/core/issue_processor.py`, `src/workflow/deliverable_generator.py`, `src/workflow/template_engine.py`, `src/agents/specialist_agents/*`
- **Flow**:
  1. Gather issues matching target labels or filters.
  2. Select specialists and deliverables via workflow configuration.
  3. Generate structured documents or AI-enhanced outputs.
  4. Commit deliverables to Git branches and annotate the issue.
  5. (Copilot mode) Assign follow-up to Copilot for execution.
- **Observed Gaps**:
  - Prior parallel command surfaces diverged in purpose and code paths (✅ resolved with the unified entrypoint).
  - Generated guidance varies in format and depth, producing inconsistent Copilot instructions.
  - Assignment back to Copilot happens late, sometimes after manual intervention has already started.
  - Specialist insights are not stored in a reusable structure; each run rebuilds prompts from scratch.

## 4. Cross-Workflow Pain Points
- **Fragmented Ownership**: Each workflow is tuned in isolation, leading to duplicated configuration (labels, templates, schedule triggers).
- **State Drift**: Temporary labels and transition markers accumulate because no workflow takes responsibility for clearing them.
- **Documentation Debt**: Existing runbooks treat the workflows separately, complicating onboarding and automation.
- **Testing Challenges**: Integration tests span multiple CLI commands and require careful dry-run coordination, slowing regression validation.

## 5. Refactor Opportunities
- Promote a shared state contract (issue metadata + labels) that each workflow respects.
- ✅ Collapse the dual issue-processing commands into one path that always produces a Copilot-ready assignment.
- Persist AI-generated summaries and specialist guidance directly on the issue to aid the next workflow stage.
- Introduce guardrails so workflows recognize when an issue is already in-progress or completed.
