# Multi-Workflow Processing Technical Design

## Overview
This document expands the requirements into a concrete implementation strategy for enabling multi-workflow processing within Speculum Principum. The design extends the existing issue processing pipeline with a planning layer, staged workflow execution, and deterministic reconciliation of outputs.

## Objectives Recap
- Permit one issue to run multiple workflows deterministically.
- Keep processing resilient (partial success allowed) and observable (clear telemetry and comments).
- Preserve compatibility with single-workflow scenarios and existing deliverables.

## Architecture Summary
```
GitHub Issue
   │
   ▼
Workflow Matcher (extended) ──► Workflow Execution Planner ──► Execution Engine
                                                         │
                                                         ▼
                                              Merge & Reconciliation
                                                         │
                                                         ▼
                                                  Reporting Layer
```

### Components
1. **Workflow Matcher Extension**
   - New method: `get_workflow_plan(issue_labels, *, categories=None)` returning a `WorkflowPlan` object rather than aborting on ambiguity.
   - `WorkflowPlan` contains ordered `WorkflowCandidate` entries with metadata:
     - `workflow_info`: existing `WorkflowInfo` reference
     - `priority`: integer priority (lower number = earlier execution)
     - `conflict_keys`: set of strings representing shared resources (deliverable paths, git modes, telemetry buckets)
     - `dependencies`: optional list of workflow names that must complete first
   - Fallback path preserves existing single-workflow behaviour if plan size is 1.

2. **Workflow Execution Planner**
   - Consumes `WorkflowPlan` and builds a `WorkflowExecutionPlan` describing execution groups.
   - Algorithm:
     1. Sort candidates by priority and name for determinism.
     2. Build conflict graph using `conflict_keys`.
     3. Topologically sort by explicit dependencies.
     4. Partition into stages: workflows without conflicts may share a stage (parallel stage); conflicting or dependent workflows form sequential stages.
   - Output schema:
     ```python
     class WorkflowExecutionPlan:
         stages: list[ExecutionStage]
         overall_timeout: int
         allow_partial_success: bool
     
     class ExecutionStage:
         workflows: list[WorkflowRunSpec]
         run_mode: Literal['parallel', 'sequential']
     
     class WorkflowRunSpec:
         workflow: WorkflowInfo
         sandbox_path: Path
         git_branch: str
     ```
   - Planner is deterministic: identical inputs yield identical plans.

3. **Execution Engine Enhancements**
   - For each stage:
     - Create isolated sandbox directory (temporary under `study/multi/{issue}/{workflow_slug}`) and optional Git worktree branch (configuration driven).
     - Execute workflows using existing `IssueProcessor` hooks but redirect their output to the sandbox. Introduce helper `execute_workflow_in_sandbox(issue_data, workflow_info, sandbox)`.
     - Collect `WorkflowRunResult` objects with metadata (files created, git branch, duration, errors).
   - Parallel stages use `ThreadPoolExecutor` with deterministic ordering of futures; sequential stages run in order.

4. **Merge & Reconciliation Layer**
   - Responsibilities:
     - Deduplicate filenames: default strategy appends workflow slug to conflicting filenames (`report.md` → `report--workflow-slug.md`).
     - Merge Git branches if configured for consolidated branch mode, otherwise push branches independently.
     - Aggregate deliverable manifests into a single dataset for reporting.
     - Detect irreconcilable conflicts (e.g., same workflow requiring exclusive git branch) and mark overall result as `partial` with remediation instructions.
   - Provide plugin point for future custom resolvers per workflow category.

5. **Reporting Layer**
   - Generate combined GitHub comment with sections per workflow:
     - Summary table (status, duration, outputs)
     - Links to deliverables
     - Conflict/Failure notes
   - Update labels:
     - `workflow::multi` to signal automated multi-workflow run
     - `workflow::partial-complete` when one or more workflows fail
   - Telemetry events:
     - `multi_workflow.plan_created`
     - `multi_workflow.stage_completed`
     - `multi_workflow.summary`
   - Extend progress log to store per-workflow status in processing state for resumability.

## Data Structures
```python
@dataclass
class WorkflowCandidate:
    workflow_info: WorkflowInfo
    priority: int
    conflict_keys: set[str]
    dependencies: list[str] = field(default_factory=list)

@dataclass
class WorkflowRunResult:
    workflow_name: str
    status: IssueProcessingStatus
    created_files: list[str]
    sandbox_path: str
    git_branch: Optional[str]
    git_commit: Optional[str]
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
```

## Configuration Changes
- `config.processing.enable_multi_workflow: bool` (default `false`).
- `config.processing.multi_workflow` block:
  ```yaml
  processing:
    enable_multi_workflow: true
    multi_workflow:
      allow_parallel_stages: true
      max_parallel_workflows: 3
      conflict_resolution: suffix
      stop_on_first_failure: false
  preview_only: false  # Set true to force planner-only dry runs when needed
  ```
- CLI flag `--allow-multi-workflow` toggles runtime behaviour.

## Telemetry Schema Updates
- Introduce new fields in `BatchMetrics` for multi-workflow breakdown:
  - `multi_workflow_count`
  - `partial_success_count`
  - `conflict_count`
- Each telemetry event includes `plan_id` (UUID) to correlate stages.

## Error Handling Strategy
- Stage-level try/except ensures one workflow failure does not cancel siblings unless `stop_on_first_failure` is true.
- Aggregate fatal errors trigger fallback to previous single-workflow `needs_clarification` behaviour with explanatory comment referencing new flag.

## Testing Plan
1. **Unit Tests**
   - Workflow matcher returns deterministic plans for specific label combinations.
   - Planner partitions workflows into expected stages (including dependency and conflict cases).
   - Reconciliation handles filename collisions.

2. **Integration Tests**
   - End-to-end run with two compatible workflows (no conflicts).
   - Run where one workflow fails; confirm partial completion reporting.
   - Run with conflicting deliverables verifying suffix strategy.

3. **CLI Acceptance Tests**
   - `process-issues --allow-multi-workflow` path ensures comment includes per-workflow sections.
   - Telemetry assertions for summary event.

4. **Performance Tests (Optional)**
   - Measure processing time with parallel stages vs sequential to verify guardrails.

## Prototype Plan
- Phase 1: Implement `WorkflowMatcher.get_workflow_plan` and new data classes with unit tests.
- Phase 2: Build execution planner producing stages without executing workflows (dry-run plan visualization).
- Phase 3: Add sandbox execution wrapper feeding existing workflow execution path; limit to sequential mode initially.
- Phase 4: Introduce reconciliation and reporting stub that prints to logs. Once validated, wire into GitHub comment pipeline.
- Phase 5: Enable parallel stages guarded by configuration; add telemetry instrumentation.

## Rollout Considerations
- Feature flag remains off by default. Enable in staging via config and CLI flag for incremental testing.
- Document new behaviour in user guides and update Copilot operations docs.
- Monitor telemetry for partial success spikes to refine conflict heuristics.

## Risks & Mitigations
- **Complex conflict resolution**: start with conservative suffix strategy; allow manual override in future iterations.
- **Increased runtime**: enforce per-stage timeout and limit parallelism.
- **Git branch complexity**: start with one branch per workflow; evaluate combined branch once prototype proves safe.

## Open Items
- Define canonical naming for suffixed deliverables to keep downstream tooling compatible.
- Decide whether AI workflow assignment should change to recommend multiple workflows proactively.
- Determine user notification cadence when partial successes require manual follow-up.
