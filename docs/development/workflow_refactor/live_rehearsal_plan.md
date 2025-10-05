# Live Rehearsal Plan — Unified Workflow Pipeline

**Purpose**: Execute a supervised, production-like rehearsal of the unified monitor → assign → process pipeline to validate live behavior, telemetry, and rollback before enabling full automation.

**Owner**: Workflow Modernization Lead  \
**Last Updated**: October 3, 2025

---

## 1. Prerequisites
- ✅ Secret validation steps green in `ops-workflow-assignment`, `ops-issue-processing`, and `ops-daily-operations` (enforced in workflows).
- ✅ Sample issues available in `state::assigned` (or ability to tag fresh monitoring output) for controlled processing.
- ✅ Stakeholder availability: Site Monitoring Ops, Workflow Assignment, Copilot Operations, DevOps.
- ✅ Telemetry ingestion path verified (`SPECULUM_CLI_TELEMETRY_DIR` artifacts accessible and forwarded to dashboards).
- ✅ Rollback contact tree prepared (GitHub repo admins, Copilot escalation channel).

## 2. Scope & Constraints
- **Issue count**: Maximum of 3 issues for assignment, 2 issues for processing to limit surface area.
- **Mode**: Live writes allowed only during assignment and processing steps; monitoring remains aggregate-only to avoid new issue creation mid-rehearsal.
- **Time window**: 90-minute block with all stakeholders online (recommend 14:00–15:30 UTC).
- **Success metrics**:
  - No lingering `monitor::triage` on assigned issues post-run.
  - Copilot assignment sections populated and due dates applied.
  - Telemetry JSONL artifacts captured and archived.
  - No GitHub rate-limit or permission errors.

## 3. Execution Checklist

### 3.1 Pre-Run Alignment (T-30 min)
1. Confirm secrets coverage by triggering `ops-daily-operations` manually (dry-run) to verify guardrails.
2. Identify target issues and ensure labels/states reflect `state::assigned` for processing focus.
3. Open telemetry dashboards and GitHub Action runs in split view for real-time monitoring.
4. Assign note-taker to capture observations and potential rollback triggers.

### 3.2 Rehearsal Steps
1. **Workflow Assignment (Live)**
   - Manual dispatch `ops-workflow-assignment` with inputs:
     - `limit = 3`
     - `dry_run = false`
     - `verbose = true`
   - Observe guard step confirming secrets; ensure post-run summary reports zero `monitor::triage` drift.
2. **Issue Processing (Live)**
   - Manual dispatch `ops-issue-processing` with inputs:
     - `batch_size = 2`
     - `dry_run = false`
     - `continue-on-error` already set in workflow.
   - Monitor smoke test output followed by live execution log; confirm Markdown sections and Copilot assignments rendered.
3. **Daily Operations (Dry-Run Confirmation)**
   - Trigger `ops-daily-operations` (default dry-run) immediately after to confirm the guardrail view of the system post-live actions.
4. **Artifact Collection**
   - Download `issue-processing-telemetry`, `daily-operations-dry-run`, and assignment telemetry artifacts.
   - Upload to shared drive or attach to progress log if lightweight.

### 3.3 Post-Run Validation
- Verify backlog state: no issues stuck in `state::assigned` with `monitor::triage` labels.
- Confirm Copilot assignee notified and due dates set.
- Review telemetry JSONL for assignment mode (`ai` vs `fallback`) and command metadata.
- Catalog follow-up gaps (e.g., documentation tweaks, CLI messaging) in `progress_log.md`.

## 4. Rollback Protocol
- **Immediate abort**: If secrets validation fails or GH API returns 403/429, cancel jobs and revert labels via manual GitHub edits or CLI scripts.
- **Label rollback**: Reapply `monitor::triage` and clear `state::assigned/coplan::copilot` if Copilot assignment needs to be undone.
- **Documentation**: Record incident in progress log and open GitHub issue for root-cause.

## 5. Communication Plan
- Schedule rehearsal on shared calendar; include Zoom/Teams link.
- During run, post status updates in the Operations channel every 15 minutes.
- After completion, send summary email with metrics, telemetry locations, and next actions.

## 6. Sign-Off Checklist
- [ ] Assignment run succeeded without errors.
- [ ] Processing run succeeded and produced deliverables.
- [ ] Telemetry artifacts archived and linked in docs.
- [ ] Stakeholders confirm readiness to enable scheduled automation.
- [ ] Rollback plan tested (optional but recommended).

---
For questions or revisions, update this document and notify stakeholders in the Workflow Modernization forum.
