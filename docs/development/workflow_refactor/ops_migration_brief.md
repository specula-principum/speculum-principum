# Ops Migration Brief

**Audience**: Site Monitoring Operations, Copilot Operations  \
**Last Updated**: 2025-10-03  \
**Owner**: Workflow Modernization Lead

## Overview
The workflow refactor is now production-ready from an automation standpoint. This brief provides the context and quick-reference guidance operations teams need while we cut over from the legacy split pipeline to the unified monitor → assign → process sequence.

## What Changes for You
- **Single Entry Point**: All Copilot handoffs now originate from `process-issues`. The retired `process-copilot-issues` command and `ops-copilot-auto-process.yml` workflow are no longer in use.
- **State & Label Contract**: Expect issues to move deterministically through `monitor::triage → state::assigned → state::copilot → state::done`. Discovery labels are cleared automatically during assignment.
- **Embedded Guidance**: Issues now contain three canonical sections:
  - `## AI Assessment` (assignment summary & rationale)
  - `## Specialist Guidance` (persona-driven instructions)
  - `## Copilot Assignment` (checklist, due date, validation)

## Reference Artifacts
- **Sample Issue Body**: See [`artifacts/sample_issue_body.md`](./artifacts/sample_issue_body.md) for the gold-standard Markdown layout.
- **Telemetry Samples**: [`telemetry_samples.md`](./telemetry_samples.md) demonstrates JSONL events for AI and fallback runs.
- **Live Rehearsal Script**: [`live_rehearsal_plan.md`](./live_rehearsal_plan.md) details the supervised rollout rehearsal; summarized schedule below.

## Failure Handling Quick Guide
| Scenario | Detection | Immediate Action | Follow-up |
| --- | --- | --- | --- |
| Assignment skipped issue (still `monitor::triage`) | GH Action summary shows non-zero discovery backlog | Re-run `assign-workflows --limit <n> --verbose`; confirm AI key present | Open incident ticket if retry fails twice; attach telemetry JSONL |
| Processing dry run reports errors | `ops-issue-processing` smoke test step fails | Inspect archived CLI logs (`artifacts/logs/issue-processing/*.log`) | Engage Issue Processing on-call; tag Workflow Modernization Lead |
| Copilot assignment blocked (permission) | `process-issues` live run exits with `copilot_assignment_failed` | Manually assign issue to `@github-copilot` and leave comment with reason | File GitHub ticket; track in rollout retrospective |
| Label drift detected post-run | GH Action post-run validation fails on `monitor::triage` | Execute `assign-workflows --statistics` to identify offenders | Update workflow configs if new label introduced; document in changelog |

## Communication Plan
- **Status Channel**: `#wf-modernization` — live updates during rehearsal and cutover.
- **Escalation**: Pager rotation `Workflow Ops` (Ops), `Workflow Modernization Lead` (Engineering).
- **Daily Stand-up**: 15 minutes at 15:30 UTC through rollout to confirm telemetry checks and backlog health.

## Proposed Rehearsal Schedule
| Activity | Date | Time (UTC) | Participants | Notes |
| --- | --- | --- | --- | --- |
| Pre-flight secrets validation | 2025-10-06 | 13:00 | DevOps, Workflow Modernization Lead | Run `assign-workflows --dry-run --limit 3` to confirm AI credentials |
| Live-mode rehearsal (supervised) | 2025-10-07 | 14:00 | Ops, DevOps, Copilot Ops, Workflow Engineering | Follow [`live_rehearsal_plan.md`](./live_rehearsal_plan.md); process 3 assignment + 2 processing issues |
| Post-run telemetry review | 2025-10-07 | 16:00 | Workflow Modernization Lead, Observability | Review JSONL artifacts; log follow-ups in `progress_log.md` |

## Next Steps for Ops Teams
1. Review the sample issue body and familiarize yourself with the new guidance sections.
2. Confirm dashboards ingest the telemetry fields `workflow_stage`, `assignment_mode`, and `processing_mode`.
3. Acknowledge the rehearsal schedule in `#wf-modernization`; flag conflicts by 2025-10-04 EOD.
4. During rehearsal, archive CLI logs and telemetry artifacts to the shared Ops drive per the live plan.

## Questions & Feedback
Drop questions in `#wf-modernization` or add comments to this document. All updates should include a timestamp and owner initials for traceability.
