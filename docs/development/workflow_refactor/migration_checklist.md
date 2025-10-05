# Workflow Refactor Migration Checklist

**Purpose**: Track the operational steps required to promote the refactored workflow pipeline into GitHub Actions. This checklist ties implementation milestones to rollout activities defined in WF-08 (Integration Dry Run Suite) and WF-09 (GitHub Actions Update).

---

## 1. Pre-Launch Validation (WF-08)
- [x] Run `pytest tests/integration/test_workflow_pipeline.py -v` to confirm end-to-end label and section contracts. *(2025-10-03 — Executed on feature/issue_processing branch; captured coverage warning for `main` but test passed. CI wiring still pending.)*
- [x] Run `pytest tests/e2e/test_workflow_cli_pipeline.py -v` to validate CLI dry-run orchestration. *(2025-10-02 — Latest dry-run passed on feature/issue_processing branch; see progress log.)*
- [x] Capture sample issue bodies showcasing the enriched `## AI Assessment`, `## Specialist Guidance`, and `## Copilot Assignment` sections. *(2025-10-03 — Sample saved to [`artifacts/sample_issue_body.md`](./artifacts/sample_issue_body.md) using production handoff builder.)*
- [x] Document sample `assign-workflows` telemetry events for AI and fallback modes in [`telemetry_samples.md`](./telemetry_samples.md).
- [x] Document expected label/state transitions in `docs/workflow/deliverables/README.md` for reviewer reference. *(2025-10-02 — Added state machine overview, label family table, and required Markdown section contract.)*

## 2. GitHub Actions Alignment (WF-09)
- [x] Update `ops-workflow-assignment.yml` to require `state::discovery` inputs and confirm removal of `monitor::triage` during assignment. *(2025-10-03 — Added GH CLI discovery guard, triage telemetry, and post-run label validation step.)*
- [x] Update `ops-issue-processing.yml` to rely solely on `process-issues` with the new state machine flags (`state::assigned`, `state::copilot`). *(2025-10-03 — Added dedicated workflow with GH CLI gating, state::assigned enforcement, and monitor::triage drift checks.)*
- [x] Point CLI invocations in `ops-daily-operations.yml` to the validated dry-run sequence before enabling live mode. *(2025-10-03 — Created workflow with monitor/assign/process dry-run chain, telemetry archiving, and manual inputs for limit tuning.)*
- [x] Add smoke test step that runs `python main.py process-issues --config config.yaml --dry-run --batch-size 3 --verbose` to capture Markdown section updates in logs. *(2025-10-03 — Smoke test now codified in `ops-issue-processing.yml`, archiving logs/telemetry artifacts for review.)*
- [x] Verify GitHub Actions secrets cover the new GitHub Models usage pattern (token scopes + rate limits). *(2025-10-03 — Added preflight secret validation to workflow assignment, issue processing, and daily-ops pipelines; ensures at least one LLM key plus search credentials are present.)*
- [x] Retire legacy `ops-copilot-auto-process.yml` workflow in favor of the unified pipeline. *(2025-10-03 — Workflow removed; operators directed to assignment + issue-processing jobs.)*

## 3. Rollout Support
- [x] Publish a changelog entry summarizing workflow label/state changes and AI assessment enhancements. *(2025-10-03 — See [`CHANGELOG.md`](./CHANGELOG.md) for the consolidated history.)*
- [x] Share migration notes with Site Monitoring Ops and Copilot Operations, including example issues and failure-handling guidance. *(2025-10-03 — Distributed via [`ops_migration_brief.md`](./ops_migration_brief.md); circulated in `#wf-modernization` for sign-off.)*
- [x] Schedule a joint dry-run using production-like issues to validate handoffs before flipping automation to live mode. *(2025-10-03 — Proposed schedule logged in [`ops_migration_brief.md`](./ops_migration_brief.md) and referenced in [`live_rehearsal_plan.md`](./live_rehearsal_plan.md); pending participant acknowledgements.)*

---

**Owner**: Workflow Modernization Lead  \
**Last Updated**: October 3, 2025
