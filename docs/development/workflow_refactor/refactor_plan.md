# Refactor Plan

**Plan Owner**: Workflow Modernization Lead  \
**Last Updated**: October 2, 2025

## Phase Overview
1. **Discovery & Alignment (Week 1)**
   - Validate current runbooks with Site Monitoring, Assignment, and Processing owners.
   - Inventory all labels, CLI options, GitHub Actions, and templates in use.
   - Capture integration pain points and document them in the shared backlog.
   - Deliverable: Updated [`current_state_assessment.md`](./current_state_assessment.md) with sign-off.

2. **Architecture & Contract Finalization (Week 2)**
   - Ratify target state design, including issue template updates and label taxonomy.
   - Define the JSON/markdown schemas for AI assessments and specialist guidance blocks.
   - Publish migration notes for team review.
   - Deliverable: Approved [`target_state_design.md`](./target_state_design.md) and schema definitions.

3. **Implementation Sprint (Weeks 3-4)**
   - Update site monitoring templates and label application logic.
   - Extend AI workflow assignment to remove discovery labels, persist summaries, and set state labels.
   - Refactor `process-issues` to generate specialist guidance + Copilot assignment; deprecate `process-copilot-issues`.
   - Introduce shared utilities for state transitions and metadata persistence.
   - Deliverable: Feature branch with passing tests, migration guide, and updated CLI docs.

4. **Validation & Rollout (Week 5)**
   - Execute end-to-end dry runs using mocked GitHub + search services.
   - Update GitHub Actions to invoke the unified pipeline with new labels/state.
   - Conduct performance/regression testing on large issue batches.
   - Deliverable: Rollout checklist completed; production launch scheduled.

## Detailed Task Backlog
| ID | Task | Owner | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- |
| WF-01 | Normalize discovery issue template | Site Monitoring | None | New issues include discovery metadata and `monitor::triage`. |
| WF-02 | Label taxonomy decision record | Workflow Assignment | WF-01 | ADR published; teams aligned on label/state usage. |
| WF-03 | AI assessment persistence | Workflow Assignment | WF-02 | AI summaries stored under `## AI Assessment`; unit tests added. |
| WF-04 | Discovery label removal automation | Workflow Assignment | WF-03 | Temporary labels removed; state label set to `state::assigned`. |
| WF-05 | Unified issue processor scaffolding | Issue Processing | WF-02 | `process-issues` generates specialist guidance template. |
| WF-06 | Copilot assignment automation | Issue Processing | WF-05 | Issues assigned to Copilot with due date + acceptance criteria. |
| WF-07 | Deprecate `process-copilot-issues` | Issue Processing | WF-06 | Command removed; documentation updated; legacy scripts migrated. |
| WF-08 | Integration dry run suite | QA | WF-01..WF-07 | Automated scenario covers monitor → assign → process path. |
| WF-09 | GitHub Actions update | DevOps | WF-08 | Actions use unified command; secrets validated. |

> ✅ **Update 2025-09-30**: WF-07 completed — legacy CLI removed, documentation refreshed, and unit tests updated to cover the unified processor.
> 🔄 **Update 2025-10-01**: WF-05 specialist guidance contract aligned with template specs; integration/unit coverage updated while CLI wiring remains in progress.
> ⚠️ **Update 2025-10-02**: WF-08 in progress — CLI dry-run suite validated and logged; integration run, artifact capture, and GH Actions updates remain open ahead of rollout rehearsal. WF-09 preparation queued for next sprint with DevOps partnership.
> 🔄 **Update 2025-10-03**: WF-08 integration pytest executed successfully; builder-generated sample issue body published for rollout collateral. Added canonical `trigger_labels` to legacy intelligence and OSINT workflows so matcher validation passes ahead of CI gating. GH Actions workstreams remain queued.

## Risk Register
| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| AI classification exceeds rate limits | Label delays cause backlog | Medium | Cache page content; add exponential backoff + fallback heuristics. |
| Workflow state drift during rollout | Duplicate processing | Medium | Introduce feature flag to guard new labels; monitor logs. |
| Copilot assignment failure (permissions) | Issues stall in assigned state | Low | Pre-flight check ensures Copilot account access; add retry workflow. |
| Documentation lag | Onboarding confusion | Medium | Schedule doc review in each phase; assign doc owner. |

## Testing Strategy
- **Unit Tests**: Expand coverage for state transition helpers, AI assessment persistence, and specialist guidance generators.
- **Integration Tests**: Execute `pytest tests/integration/test_workflow_pipeline.py -v` once GitHub Actions updates are in place to mirror final automation.
- **Regression Tests**: Ensure existing workflows (e.g., batch processing, manual override) remain functional.
- **User Acceptance**: Run pilot with 5 monitored items, track resolution time and label accuracy.

## Communication & Change Management
- Weekly sync with stakeholders across monitoring, workflow assignment, and specialist teams.
- Publish changelog entries in `docs/development/workflow_refactor/CHANGELOG.md` (create as needed).
- Coordinate rollout with Copilot operations to guarantee availability during transition windows.

## Definition of Done
- Legacy command paths removed and archived in documentation.
- All target state data contracts implemented and validated through automated tests.
- GitHub Actions updated; on-call runbooks refreshed.
- Post-launch metrics in place to confirm workflow throughput and label accuracy.
