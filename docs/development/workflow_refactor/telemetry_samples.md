# Telemetry Sample Artifacts

These examples illustrate the JSONL records emitted by the refactored CLI flows. Use them when updating dashboards, writing rollout guides, or validating downstream ingestion jobs.

## AI Workflow Assignment (`assign-workflows --dry-run`)

The statistics invocation records the active mode (`"ai"`) along with the returned snapshot:

```json
{
  "event_type": "workflow_assignment.statistics_view",
  "timestamp": "2025-10-02T18:35:42.011260+00:00",
  "cli_command": "assign-workflows",
  "cli_session_id": "f6de6f3d9d924554acdf40aa9abc9d45",
  "assignment_mode": "ai",
  "success": true,
  "statistics_snapshot": {
    "total_site_monitor_issues": 5,
    "unassigned": 2,
    "assigned": 3,
    "needs_clarification": 1,
    "needs_review": 0,
    "feature_labeled": 1,
    "workflow_breakdown": {
      "Example Workflow": 3
    },
    "label_distribution": {
      "workflow::example": 3,
      "state::assigned": 2,
      "monitor::triage": 1
    }
  }
}
```

## Fallback Workflow Assignment (`assign-workflows --disable-ai --dry-run`)

Fallback runs export batch summaries that capture label transitions and clarifications alongside `"assignment_mode": "fallback"`:

```json
{
  "event_type": "workflow_assignment.batch_summary",
  "timestamp": "2025-10-02T18:36:07.447208+00:00",
  "cli_command": "assign-workflows",
  "cli_session_id": "7b0ea5d04d514ecaa1e4d8fedb209edf",
  "assignment_mode": "fallback",
  "total_issues": 2,
  "processed": 1,
  "duration_seconds": 0.41,
  "statistics": {
    "assign_workflow": 1,
    "request_clarification": 1,
    "skip_feature": 0,
    "skip_needs_clarification": 0,
    "error": 0
  },
  "results": [
    {
      "issue_number": 401,
      "action_taken": "assign_workflow",
      "assigned_workflow": "Fallback Workflow",
      "labels_added": [
        "workflow::fallback",
        "state::assigned",
        "analysis"
      ],
      "labels_removed": [
        "monitor::triage",
        "state::discovery"
      ],
      "message": "Assigned via fallback heuristics",
      "dry_run": true
    },
    {
      "issue_number": 402,
      "action_taken": "request_clarification",
      "assigned_workflow": null,
      "labels_added": [
        "needs clarification"
      ],
      "labels_removed": [],
      "message": "Awaiting additional context",
      "dry_run": true
    }
  ]
}
```

## Where the Files Appear

## Unified Stage Metadata

Every CLI invocation now enriches telemetry events with stage-aware metadata:

- `workflow_stage` identifies the pipeline segment (e.g., `"monitoring"`, `"issue-processing"`, `"workflow-assignment"`).
- Site monitor runs add `monitor_mode` (`"full"` vs. `"aggregate-only"` depending on `--no-individual-issues`).
- Issue processing commands attach `processing_mode` (`"batch"`, `"from-monitor"`, `"single-issue"`, or `"find-issues-only"`).

Dashboards and rollout scripts can rely on these static fields to pivot telemetry by stage without inspecting command arguments.

By default, CLI telemetry lives under `artifacts/telemetry/<command>.jsonl`. Override the location with:

- `SPECULUM_CLI_TELEMETRY_PATH` — full file path (highest precedence)
- `SPECULUM_CLI_TELEMETRY_DIR` — directory for per-command JSONL files
- `SPECULUM_ARTIFACTS_DIR` — fallback when a telemetry directory is not set

## Reproducing in a Dry Run

1. Ensure the virtual environment is active and dependencies installed.
2. Export required credentials (`GITHUB_TOKEN`, `GOOGLE_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID`).
3. Run the CLI commands:
   - `python main.py assign-workflows --config config.yaml --limit 3 --dry-run --verbose`
   - `python main.py assign-workflows --config config.yaml --limit 3 --dry-run --disable-ai --verbose`
4. Inspect the generated JSONL artifacts in the telemetry directory and compare with the samples above.
