# AI Workflow Assignment Telemetry Reference

_Last updated: 2025-10-09_

## Purpose
The criminal-law modernization program now emits rich telemetry whenever the AI workflow assignment agent evaluates or assigns a site-monitor issue. This guide documents those payloads so the analytics and reporting team can wire dashboards without reverse-engineering the Python implementation. All examples reflect the current `feature/workflow_type_refinement` branch and the `AIWorkflowAssignmentAgent` changes landed on 2025-10-09.

## Event Catalog
| Event Name | Emitted From | Trigger | Audience |
| --- | --- | --- | --- |
| `workflow_assignment.issue_result` | `AIWorkflowAssignmentAgent._emit_issue_result_telemetry` | Per issue after AI analysis (auto-assign, review request, clarification, or error) | Analytics, audit, legal QA |
| `workflow_assignment.batch_summary` | `AIWorkflowAssignmentAgent.process_issues_with_ai` | After each `assign-workflows` execution completes (including dry runs) | Operations leads, telemetry team |

Other legacy events remain unchanged; this document focuses on the criminal-law telemetry extensions.

## `workflow_assignment.issue_result`
Payload keys are shown with types and notes. Fields marked ⭐ were added or expanded for the criminal-law taxonomy.

| Field | Type | Description |
| --- | --- | --- |
| `issue_number` | integer | GitHub issue number processed. |
| `action_taken` | string | `auto_assigned`, `review_requested`, `clarification_requested`, or `error`. |
| `assigned_workflow` | string&#124;null | Workflow name applied (null when no assignment). |
| `labels_added` | array[string] | Labels appended to the issue (e.g., `workflow::person-entity-profiling`). |
| `dry_run` | boolean | True when run invoked with `--dry-run`. |
| `duration_seconds` | float | Wall-clock time to process the issue. |
| `note` | string&#124;null | Human-readable message surfaced to CLI. |
| `ai_summary` | string&#124;null | Trimmed summary from the AI analysis (max 240 chars). |
| `suggested_workflows` | array[string] | Up to three workflows returned by the model. |
| `confidence_scores` | object | Map of suggested workflow → model confidence (only populated for `suggested_workflows`). |
| `error` | string&#124;null | Diagnostic text when `action_taken == "error"`. |
| `reason_codes` ⭐ | array[string] | Ordered, de-duplicated reason codes describing entity coverage and legal signals (see Appendix). |
| `assignment_mode` | string | Currently always `"ai"` for this agent. |
| `entity_coverage` ⭐ | float&#124;null | 0–1 coverage score across person/place/thing requirements. |
| `entity_counts` ⭐ | object&#124;null | Approximate counts per entity type (`person`, `place`, `thing`). |
| `missing_base_entities` ⭐ | array[string]&#124;null | Entity types still missing after extraction. |
| `legal_signals` ⭐ | object&#124;null | Raw detection output (see table below). |
| `statute_references` ⭐ | array[[string, integer]] | Up to five `(citation, count)` tuples after normalization. |
| `precedent_references` ⭐ | array[[string, integer]] | Up to five normalized precedent references with counts. |
| `interagency_terms` ⭐ | array[[string, integer]] | Up to five inter-agency keywords (lower-cased) with counts. |
| `audit_trail` ⭐ | object&#124;null | Present when the assigned workflow requires GAO-compliant auditing (structure below). |

### Legal Signal Object
```
{
  "statutes": 1.0,
  "statute_matches": ["18 U.S.C.", "§ 371"],
  "precedent": 1.0,
  "precedent_matches": ["Smith v. Jones"],
  "interagency": 1.0,
  "interagency_terms": ["gao", "department of justice"]
}
```
- Scalar values are floats (`0.0` or `1.0`) indicating signal presence.
- Match lists retain the original capitalization except for inter-agency terms, which are lower-cased.

### Audit Trail Object (when required)
```
{
  "required": true,
  "fields": ["model_version", "reason_codes", "entity_evidence", "citation_sources"],
  "workflow_version": "1.0.0",
  "workflow_category": "entity-foundation",
  "data": {
    "model_version": "github:gpt-4o",
    "reason_codes": ["PERSON_ENTITY_DETECTED", "HIGH_ENTITY_COVERAGE", "STATUTE_CITATION_DETECTED"],
    "entity_evidence": {
      "coverage": 0.9,
      "counts": {"person": 3, "place": 2, "thing": 1},
      "missing_base_entities": []
    },
    "citation_sources": ["18 U.S.C.", "§ 371", "Smith v. Jones"],
    "reviewer_notes": null
  }
}
```
- Field order mirrors the workflow definition.
- Additional workflow-specific audit fields (e.g., `reviewer_notes`) are passed through with null defaults when unavailable.

### Example Event
```json
{
  "issue_number": 542,
  "action_taken": "auto_assigned",
  "assigned_workflow": "Person Entity Profiling & Risk Flagging",
  "labels_added": ["workflow::person-entity-profiling"],
  "dry_run": false,
  "duration_seconds": 2.74,
  "note": "Assigned automatically",
  "ai_summary": "Profile cooperating witness, assess conflicts, flag GAO concerns.",
  "suggested_workflows": ["Person Entity Profiling & Risk Flagging", "Witness & Expert Reliability Assessment"],
  "confidence_scores": {
    "Person Entity Profiling & Risk Flagging": 0.86,
    "Witness & Expert Reliability Assessment": 0.63
  },
  "reason_codes": [
    "PERSON_ENTITY_DETECTED",
    "PLACE_ENTITY_DETECTED",
    "THING_ENTITY_DETECTED",
    "HIGH_ENTITY_COVERAGE",
    "STATUTE_CITATION_DETECTED",
    "INTERAGENCY_CONTEXT_DETECTED"
  ],
  "assignment_mode": "ai",
  "entity_coverage": 0.9,
  "entity_counts": {"person": 4, "place": 2, "thing": 1},
  "missing_base_entities": [],
  "legal_signals": {
    "statutes": 1.0,
    "statute_matches": ["18 U.S.C.", "§ 371"],
    "precedent": 0.0,
    "precedent_matches": [],
    "interagency": 1.0,
    "interagency_terms": ["gao", "department of justice"]
  },
  "statute_references": [["18 U.S.C.", 1], ["§ 371", 1]],
  "precedent_references": [],
  "interagency_terms": [["gao", 1], ["department of justice", 1]],
  "audit_trail": {
    "required": true,
    "fields": ["model_version", "reason_codes", "entity_evidence", "citation_sources"],
    "workflow_version": "1.0.0",
    "workflow_category": "entity-foundation",
    "data": {
      "model_version": "github:gpt-4o",
      "reason_codes": [
        "PERSON_ENTITY_DETECTED",
        "PLACE_ENTITY_DETECTED",
        "THING_ENTITY_DETECTED",
        "HIGH_ENTITY_COVERAGE",
        "STATUTE_CITATION_DETECTED",
        "INTERAGENCY_CONTEXT_DETECTED"
      ],
      "entity_evidence": {
        "coverage": 0.9,
        "counts": {"person": 4, "place": 2, "thing": 1},
        "missing_base_entities": []
      },
      "citation_sources": ["18 U.S.C.", "§ 371"],
      "reviewer_notes": null
    }
  }
}
```

## `workflow_assignment.batch_summary`
Generated once per command invocation, summarising overall performance.

| Field | Type | Description |
| --- | --- | --- |
| `total_issues` | integer | Total issues discovered for the current run. |
| `processed` | integer | Number of issues successfully analyzed (excludes early skips). |
| `statistics` | object | Counts for `auto_assigned`, `review_requested`, `clarification_requested`, `errors`. |
| `duration_seconds` | float | Total elapsed runtime. |
| `dry_run` | boolean | Mirrors CLI flag. |
| `status` | string | `success`, `partial`, `error`, or `empty`. |
| `issue_numbers` | array[integer] | Issues included in `results`. |
| `error_count` | integer | Shortcut for `statistics.errors`. |
| `assignment_mode` | string | Always `"ai"` here. |
| `average_entity_coverage` ⭐ | float&#124;null | Mean entity coverage of processed issues. |
| `entity_coverage_distribution` ⭐ | object | Buckets: `high` ≥0.67, `partial` ≥0.34, `low` <0.34. |
| `issues_with_missing_entities` ⭐ | integer | Count of issues missing at least one base entity. |
| `top_reason_codes` ⭐ | array[object] | Up to five `{code, count}` entries sorted by frequency. |
| `legal_signal_counts` ⭐ | object | Map of signal name → number of issues where signal >0. |
| `statute_references` ⭐ | array[[string, integer]] | Top five normalized citations across the batch. |
| `precedent_references` ⭐ | array[[string, integer]] | Top five precedents across the batch. |
| `interagency_terms` ⭐ | array[[string, integer]] | Top five inter-agency keywords across the batch. |

### Example Summary
```json
{
  "total_issues": 6,
  "processed": 5,
  "statistics": {
    "auto_assigned": 3,
    "review_requested": 1,
    "clarification_requested": 1,
    "errors": 0
  },
  "duration_seconds": 14.52,
  "dry_run": false,
  "status": "success",
  "issue_numbers": [538, 539, 540, 542, 543],
  "error_count": 0,
  "assignment_mode": "ai",
  "average_entity_coverage": 0.78,
  "entity_coverage_distribution": {"high": 3, "partial": 1, "low": 1},
  "issues_with_missing_entities": 1,
  "top_reason_codes": [
    {"code": "PERSON_ENTITY_DETECTED", "count": 5},
    {"code": "HIGH_ENTITY_COVERAGE", "count": 3},
    {"code": "STATUTE_CITATION_DETECTED", "count": 2}
  ],
  "legal_signal_counts": {
    "statutes": 2,
    "precedent": 1,
    "interagency": 4
  },
  "statute_references": [["18 U.S.C.", 2], ["§ 371", 2]],
  "precedent_references": [["Smith v. Jones", 1]],
  "interagency_terms": [["gao", 4], ["department of justice", 3], ["fbi", 1]]
}
```

## Analytics Integration Notes
- **Normalization**: Statute references are emitted without trailing punctuation and may be split into code and section fragments (e.g., `18 U.S.C.` and `§ 371`). Combine as needed for dashboards.
- **Dry Runs**: Dry-run executions still publish telemetry; use the `dry_run` flag to filter if only committed actions should appear in reports.
- **Sampling**: `assign-workflows --limit N` limits AI processing but still includes skipped issues in `total_issues` when discovered.
- **Category Filters**: When CLI users supply `--workflow-category`, the agent restricts search to those taxonomy buckets yet continues emitting full telemetry for downstream parity.

## Reason Code Appendix
| Code | Meaning |
| --- | --- |
| `PERSON_ENTITY_DETECTED`, `PLACE_ENTITY_DETECTED`, `THING_ENTITY_DETECTED` | Required base entities were detected above threshold. |
| `PERSON_ENTITY_MISSING`, `PLACE_ENTITY_MISSING`, `THING_ENTITY_MISSING` | Base entity missing; expect `issues_with_missing_entities` > 0. |
| `HIGH_ENTITY_COVERAGE`, `PARTIAL_ENTITY_COVERAGE`, `LOW_ENTITY_COVERAGE` | Entity coverage tiers (≥0.67, ≥0.34, otherwise). |
| `STATUTE_CITATION_DETECTED` | Statutory reference matched modernized regex heuristics. |
| `PRECEDENT_REFERENCE_DETECTED` | Case law detected. |
| `INTERAGENCY_CONTEXT_DETECTED` | GAO/DOJ/FBI (etc.) language present. |
| `LEGACY_HIGH_CONFIDENCE_OVERRIDE` | Legacy workflow override; rare in criminal-law taxonomy but retained for compatibility. |

## Next Steps
- Align this telemetry spec with dashboard schemas once the analytics team finalises aggregation requirements.
- Extend the document when additional events (e.g., `process-issues` telemetry) adopt the same legal signal payloads.
