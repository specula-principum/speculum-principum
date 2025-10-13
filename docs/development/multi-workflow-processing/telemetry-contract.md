# Multi-Workflow Telemetry Contract Draft

## Event Inventory

### multi_workflow.plan_created
- **Purpose:** Records that a deterministic execution plan was produced for an issue or batch item.
- **Emitters:** `IssueProcessor._emit_plan_created_event` via `build_plan_created_event`.
- **Frequency:** Once per issue whenever multi-workflow planning succeeds.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| event_type | string | yes | Always `multi_workflow.plan_created` prior to publishing. Removed from payload before emission in current implementation. |
| plan_id | string | yes | Stable identifier generated per plan (`multiwf-<uuid>`). Used to correlate with downstream execution events. |
| issue_number | integer | conditional | Present when processing a single issue. Null when the planner is invoked outside the issue processor. |
| batch_id | string | conditional | Reserved for batch orchestration contexts. Currently unused. |
| stage_count | integer | yes | Number of execution stages produced. |
| workflow_count | integer | yes | Number of workflows contained across all stages. |
| allow_partial_success | boolean | yes | Mirrors planner configuration so analytics can filter mixed outcomes. |
| preview_only | boolean | yes | Indicates whether execution will be skipped due to preview guard. Added by `IssueProcessor` before publish. |
| selection_reason | string | optional | Short machine readable reason describing why multi-workflow was selected (for example `multi_label_match`). |
| selection_message | string | optional | Human readable explanation rendered in CLI previews and comments. |
| stages | array<object> | yes | Ordered list of stage descriptors. |
| stages[].index | integer | yes | Zero based stage index. |
| stages[].run_mode | string | yes | Either `sequential` or `parallel`. |
| stages[].workflows | array<string> | yes | Sorted workflow names included in the stage. |
| stages[].blocking_conflicts | array<string> | yes | Deterministic set of conflict keys that forced staging. Empty when not applicable. |

**Example Payload**
```json
{
  "plan_id": "multiwf-6e1f3f6a15c54f3a8366d77ba47cbe1d",
  "issue_number": 482,
  "stage_count": 2,
  "workflow_count": 3,
  "allow_partial_success": true,
  "preview_only": false,
  "selection_reason": "multi_label_match",
  "selection_message": "Labels matched compliance-advisory and enforcement-snapshot workflows",
  "stages": [
    {
      "index": 0,
      "run_mode": "parallel",
      "workflows": ["compliance-advisory", "policy-overview"],
      "blocking_conflicts": ["deliverable:weekly-report"]
    },
    {
      "index": 1,
      "run_mode": "sequential",
      "workflows": ["enforcement-snapshot"],
      "blocking_conflicts": []
    }
  ]
}
```

### multi_workflow.execution_summary
- **Purpose:** Captures multi-workflow execution outcomes (or preview skips) for a previously published plan.
- **Emitters:** `IssueProcessor._emit_execution_summary_event` after each plan executes or is skipped.
- **Frequency:** Once per plan per issue. Additional events may be considered if stage level roll-ups are required.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| issue_number | integer | yes | Issue identifier for correlation with plan events. |
| plan_id | string | yes | Mirrors the value from the corresponding `plan_created` event. |
| stage_count | integer | yes | Repeats planner metadata for ease of aggregation. |
| workflow_count | integer | yes | Repeats planner metadata for ease of aggregation. |
| stages | array<object> | yes | Same structure as `plan_created` summary; included for reference. |
| preview_only | boolean | yes | True when execution was bypassed. |
| selection_reason | string | optional | Echoed from the planning stage for completeness. |
| selection_message | string | optional | Echoed from the planning stage for completeness. |
| allow_partial_success | boolean | yes | Execution setting active for the run. |
| overall_timeout_seconds | integer | optional | Set when planner enforces a global timeout. |
| deliverable_manifest | object | optional | Present when deliverable aggregation is available; shape mirrors manifest schema. |
| stage_runs | array<object> | yes | Ordered list of per-stage execution outcomes. |
| stage_runs[].index | integer | yes | Stage index. |
| stage_runs[].run_mode | string | yes | Either `sequential` or `parallel`. |
| stage_runs[].blocking_conflicts | array<string> | yes | Carried forward from plan metadata. |
| stage_runs[].workflows | array<object> | yes | Workflow level execution status objects. |
| stage_runs[].workflows[].workflow_name | string | yes | Name of the workflow candidate. |
| stage_runs[].workflows[].status | string | yes | Current vocabulary: `executed`, `skipped`, `failed`. Needs confirmation with telemetry consumers. |
| stage_runs[].workflows[].created_files | array<string> | optional | List of deliverable paths produced by the workflow when execution succeeded. Empty or omitted when skipped or failed. |
| stage_runs[].workflows[].message | string | optional | Short human readable status string. |
| status | string | yes | Summary of the overall execution: `executed` or `skipped`. |
| skip_reason | string | optional | Present when `status` is `skipped` (for example `preview_only_guard`). |
| errors | array<object> | optional | Present when one or more workflows fail. Each entry includes `workflow_name` and `error` fields. |

**Example Payload (Executed)**
```json
{
  "issue_number": 482,
  "plan_id": "multiwf-6e1f3f6a15c54f3a8366d77ba47cbe1d",
  "stage_count": 2,
  "workflow_count": 3,
  "preview_only": false,
  "allow_partial_success": true,
  "overall_timeout_seconds": null,
  "stage_runs": [
    {
      "index": 0,
      "run_mode": "parallel",
      "blocking_conflicts": ["deliverable:weekly-report"],
      "workflows": [
  {"workflow_name": "compliance-advisory", "status": "executed", "created_files": ["study/482/compliance-advisory/report.md"], "message": "Workflow executed successfully."},
  {"workflow_name": "policy-overview", "status": "executed", "created_files": ["study/482/policy-overview/summary.md"], "message": "Workflow executed successfully."}
      ]
    },
    {
      "index": 1,
      "run_mode": "sequential",
      "blocking_conflicts": [],
      "workflows": [
  {"workflow_name": "enforcement-snapshot", "status": "executed", "created_files": ["study/482/enforcement-snapshot/digest.md"], "message": "Workflow executed successfully."}
      ]
    }
  ],
  "status": "executed",
  "errors": []
}
```

**Example Payload (Preview Skip)**
```json
{
  "issue_number": 482,
  "plan_id": "multiwf-6e1f3f6a15c54f3a8366d77ba47cbe1d",
  "stage_count": 2,
  "workflow_count": 3,
  "preview_only": true,
  "allow_partial_success": true,
  "stage_runs": [
    {
      "index": 0,
      "run_mode": "parallel",
      "blocking_conflicts": ["deliverable:weekly-report"],
      "workflows": [
  {"workflow_name": "compliance-advisory", "status": "skipped", "message": "Multi-workflow execution skipped due to preview-only mode."},
  {"workflow_name": "policy-overview", "status": "skipped", "message": "Multi-workflow execution skipped due to preview-only mode."}
      ]
    },
    {
      "index": 1,
      "run_mode": "sequential",
      "blocking_conflicts": [],
      "workflows": [
  {"workflow_name": "enforcement-snapshot", "status": "skipped", "message": "Multi-workflow execution skipped due to preview-only mode."}
      ]
    }
  ],
  "status": "skipped",
  "skip_reason": "preview_only_guard"
}
```

## Batch Metrics Alignment
- `BatchMetrics` already includes `multi_workflow_count`, `partial_success_count`, and `conflict_count` for aggregation.
- Need confirmation that analytics pipelines ingest these counters and correlate them with plan level events using `plan_id` or per-issue identifiers.

## Pending Decisions
1. Confirm whether telemetry consumers require additional identifiers (for example `batch_id`, `run_id`).
2. Validate the status vocabulary (`executed`, `skipped`, `failed`) and expand if partial success signaling needs finer granularity (such as `retrying`, `reconciled`).
3. Decide if emitted deliverable paths should be redacted or hashed before publishing to production telemetry sinks.
4. Determine whether deliverable manifests require normalization before emission (for example sorting keys, truncating large payloads).
5. Align on retention expectations for plan vs execution events to guarantee correlation windows.

## Action Items
- Share this draft with the telemetry platform team for schema approval.
- Produce JSON Schema definitions once field inventory is signed off.
- Update automated tests to validate event payloads against the finalized schema.
- Extend documentation in `docs/ai-workflow-assignment.md` and operations guides after the contract is ratified.
