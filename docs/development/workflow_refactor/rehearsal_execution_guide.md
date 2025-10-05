# Rehearsal Execution Guide — Step-by-Step Instructions

**Target Date**: October 7, 2025 at 14:00 UTC  
**Duration**: 90 minutes (14:00–15:30 UTC)  
**Status**: Ready for Execution ✅

---

## Quick Reference

**Participants Required**:
- Workflow Modernization Lead (facilitator)
- Site Monitoring Ops representative
- Workflow Assignment team representative
- Copilot Operations representative
- DevOps representative (for GitHub Actions monitoring)

**Communication Channels**:
- Primary: Video conference (Zoom/Teams link TBD)
- Secondary: Operations Slack channel (#wf-modernization)
- Emergency: Contact tree (see Section 7)

**Validation Report**: See [`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md) for technical readiness details.

---

## Section 1: Pre-Rehearsal Setup (T-30 minutes)

### 1.1 Environment Verification

**Facilitator Actions**:
```bash
# Verify system status
python main.py status --config config.yaml

# Expected output:
# - Repository: terrence-giggy/speculum-principum ✅
# - Sites configured: 1 ✅
# - Rate limit: Available API calls ✅
# - Processed entries: Count visible ✅
```

### 1.2 Issue Preparation

**Required Issues**:
- **For Assignment** (3 issues): Must have `monitor::triage` or `state::discovery` label
- **For Processing** (2 issues): Must have `state::assigned` label

**Pre-flight Check**:
```bash
# List issues for assignment
gh issue list --label "monitor::triage" --state open --json number,title,labels --limit 10

# List issues for processing
gh issue list --label "state::assigned" --state open --json number,title,labels --limit 10
```

**Issue Selection Criteria**:
- ✅ Representative content (diverse URL patterns)
- ✅ No blocking dependencies or manual holds
- ✅ Clear ownership (not assigned to other automation)
- ❌ Avoid production-critical issues during rehearsal

**Backup Issues**: Record 2 additional issue numbers for each category in case primary targets are unsuitable.

### 1.3 Dashboard & Monitoring Setup

**Open in Split View**:
1. **GitHub Actions**: https://github.com/terrence-giggy/speculum-principum/actions
2. **Issue List**: https://github.com/terrence-giggy/speculum-principum/issues
3. **Telemetry Dashboard**: (If available, or prepare for artifact download)
4. **Video Conference**: Primary communication channel

**Note-Taker Setup**:
- Open shared document for observations (Google Doc or Markdown file)
- Template sections: Pre-run state, Observations, Anomalies, Action items
- Timestamp each significant event

### 1.4 Secrets Validation

**GitHub Actions Secrets Check**:
```bash
# Manually dispatch ops-daily-operations in dry-run mode
# Go to: Actions → Operations · Daily Operations → Run workflow
# Select branch: feature/issue_processing
# Use default inputs (dry_run: true)
# Expected: Success with secret validation steps passing
```

**Required Secrets Confirmed**:
- [x] `GITHUB_TOKEN`
- [x] `GOOGLE_API_KEY`
- [x] `GOOGLE_SEARCH_ENGINE_ID`
- [x] `OPENAI_API_KEY` OR `ANTHROPIC_API_KEY`

**If Secret Validation Fails**: STOP - Do not proceed. Escalate to DevOps immediately.

---

## Section 2: Rehearsal Execution (T=0)

### Phase 1: Workflow Assignment (Live Mode) — 20 minutes

**T+0 min: Initiate Assignment Run**

**Action**:
1. Navigate to: Actions → Operations · Workflow Assignment → Run workflow
2. Configure inputs:
   - Branch: `feature/issue_processing`
   - `limit`: 3
   - `dry_run`: **false** ⚠️ (LIVE MODE)
   - `verbose`: true
   - `statistics_only`: false

3. Click "Run workflow"

**What to Monitor**:
- ✅ Secret validation step passes
- ✅ Discovery guard step identifies target issues
- ✅ AI workflow assignment executes (watch for API calls)
- ✅ Labels applied to issues (`workflow::*`, `specialist::*`)
- ✅ Temporary labels removed (`monitor::triage`)
- ✅ Post-run validation confirms zero triage drift

**Expected Duration**: 3-5 minutes per issue (9-15 minutes total)

**Success Criteria**:
- [ ] All 3 issues processed without errors
- [ ] `monitor::triage` removed from all assigned issues
- [ ] New workflow labels visible on issues
- [ ] Telemetry artifact uploaded (check workflow run artifacts)

**T+15 min: Review Assignment Results**

**Verification Commands**:
```bash
# Check assigned issues (replace XXX with issue numbers)
gh issue view 25 --json labels,body
gh issue view 24 --json labels,body
gh issue view 23 --json labels,body

# Look for:
# - Labels: workflow::*, specialist::*, state::assigned
# - Body sections: ## AI Assessment (should be present)
# - No remaining monitor::triage labels
```

**Checkpoint**: All participants confirm assignment results before proceeding.

---

### Phase 2: Issue Processing (Live Mode) — 30 minutes

**T+20 min: Initiate Processing Run**

**Action**:
1. Navigate to: Actions → Operations · Issue Processing → Run workflow
2. Configure inputs:
   - Branch: `feature/issue_processing`
   - `issue_number`: (leave blank for batch mode)
   - `batch_size`: 2
   - `assignee_filter`: (leave blank)
   - `dry_run`: **false** ⚠️ (LIVE MODE)
   - `verbose`: true

3. Click "Run workflow"

**What to Monitor**:
- ✅ Inventory step counts state::assigned issues
- ✅ Smoke test step executes (dry-run preview)
- ✅ Live processing batch executes
- ✅ Specialist guidance sections added to issue bodies
- ✅ Copilot assignment sections created
- ✅ Issues assigned to @github-copilot[bot]
- ✅ Branch/file scaffolding created (if applicable)
- ✅ Telemetry artifacts uploaded

**Expected Duration**: 5-10 minutes per issue (10-20 minutes total)

**Success Criteria**:
- [ ] 2 issues processed successfully
- [ ] Issue bodies contain ## Specialist Guidance sections
- [ ] Issue bodies contain ## Copilot Assignment sections
- [ ] Issues assigned to github-copilot[bot] with due dates
- [ ] Labels updated: state::copilot (removed state::assigned)
- [ ] No monitor::triage drift detected

**T+45 min: Review Processing Results**

**Verification Commands**:
```bash
# Check processed issues (replace YYY with issue numbers)
gh issue view 27 --json labels,body,assignees
gh issue view 26 --json labels,body,assignees

# Look for:
# - Assignees: github-copilot[bot]
# - Labels: state::copilot (NOT state::assigned)
# - Body sections: ## Specialist Guidance, ## Copilot Assignment
# - Deliverable file paths or branch references
```

**Checkpoint**: Review specialist guidance quality and Copilot assignment clarity.

---

### Phase 3: Daily Operations Confirmation (Dry-Run) — 15 minutes

**T+50 min: Execute Daily Ops Dry-Run**

**Purpose**: Validate guardrail view of system after live changes.

**Action**:
1. Navigate to: Actions → Operations · Daily Operations → Run workflow
2. Configure inputs:
   - Branch: `feature/issue_processing`
   - `assignment_limit`: 10 (default)
   - `processing_batch_size`: 5 (default)

3. Click "Run workflow"

**What to Monitor**:
- ✅ Monitor phase completes (aggregate-only, no new issues)
- ✅ Assignment phase detects recent changes (should find fewer unassigned issues)
- ✅ Processing phase simulates next batch (dry-run)
- ✅ Summary output documents system state
- ✅ Telemetry artifacts captured

**Expected Duration**: 3-5 minutes

**Success Criteria**:
- [ ] Dry-run completes without errors
- [ ] Monitor summary shows consistent state
- [ ] Assignment summary reflects reduced unassigned count
- [ ] Processing summary shows accurate state distribution
- [ ] No unexpected label drift detected

---

## Section 3: Artifact Collection (T+60 min)

### 3.1 Download Telemetry Artifacts

**From Each Workflow Run**:
1. Navigate to completed workflow run
2. Scroll to bottom: "Artifacts" section
3. Download:
   - `workflow-assignment-telemetry` (from Phase 1)
   - `issue-processing-telemetry` (from Phase 2)
   - `daily-operations-dry-run` (from Phase 3)

**Archive Location**: Upload to shared drive or commit to `docs/development/workflow_refactor/artifacts/rehearsal-YYYYMMDD/`

### 3.2 Screenshot Key Outputs

**Capture**:
- GitHub Actions workflow run summaries (all 3 phases)
- Sample issue bodies showing new sections
- Label changes on target issues (before/after)
- Any warnings or errors from logs

### 3.3 Export Issue States

**Commands**:
```bash
# Export current state of all site-monitor issues
gh issue list --label "site-monitor" --state all --json number,title,labels,state,assignees,body --limit 50 > rehearsal-issue-state.json

# Count label distribution
gh issue list --label "site-monitor" --state open --json labels --jq '[.[].labels[].name] | group_by(.) | map({label: .[0], count: length}) | sort_by(-.count)'
```

---

## Section 4: Validation Checklist (T+65 min)

### 4.1 Assignment Phase Validation

**Live Run Results**:
- [ ] **Issue #__ (Assignment 1)**: monitor::triage → removed, workflow labels added, AI Assessment section present
- [ ] **Issue #__ (Assignment 2)**: monitor::triage → removed, workflow labels added, AI Assessment section present
- [ ] **Issue #__ (Assignment 3)**: monitor::triage → removed, workflow labels added, AI Assessment section present

**Telemetry Review**:
- [ ] Assignment mode recorded (ai vs fallback)
- [ ] Confidence scores documented
- [ ] API call counts within limits
- [ ] Duration metrics reasonable

### 4.2 Processing Phase Validation

**Live Run Results**:
- [ ] **Issue #__ (Processing 1)**: state::assigned → state::copilot, Specialist Guidance added, Copilot assigned
- [ ] **Issue #__ (Processing 2)**: state::assigned → state::copilot, Specialist Guidance added, Copilot assigned

**Quality Checks**:
- [ ] Specialist guidance follows template contract (Persona, Inputs, Actions, Deliverables)
- [ ] Copilot assignment includes due date and acceptance criteria
- [ ] No placeholder text or template remnants
- [ ] Branch/file references accurate (if applicable)

**Telemetry Review**:
- [ ] Batch metrics captured (count, duration, success rate)
- [ ] Copilot assignment metadata logged
- [ ] Error handling graceful (if any issues encountered)

### 4.3 System Health Validation

**Daily Ops Dry-Run Results**:
- [ ] Monitor phase executed without creating new issues
- [ ] Assignment phase summary accurate
- [ ] Processing phase preview reflects current state
- [ ] No label drift or state machine violations detected

**API & Rate Limits**:
- [ ] Google Search API calls within quota
- [ ] GitHub API rate limit not exhausted
- [ ] AI provider (OpenAI/Anthropic) within limits
- [ ] No 429 (rate limit) or 403 (permission) errors

---

## Section 5: Observations & Anomalies

**Note-Taker Instructions**: Document anything unexpected, even if it didn't cause failure.

### 5.1 Performance Observations
- Assignment duration per issue: ______
- Processing duration per issue: ______
- Total end-to-end time: ______
- API response times: ______

### 5.2 Quality Observations
- AI assessment accuracy: ______
- Specialist guidance completeness: ______
- Copilot assignment clarity: ______
- Label consistency: ______

### 5.3 Anomalies Encountered
_(Examples: unexpected warnings, slow API calls, unclear error messages, label edge cases)_

**Anomaly 1**:
- Description: ______
- Severity: Low / Medium / High
- Resolution: ______
- Follow-up required: Yes / No

**Anomaly 2**:
- Description: ______
- Severity: Low / Medium / High
- Resolution: ______
- Follow-up required: Yes / No

---

## Section 6: Post-Rehearsal Actions (T+75 min)

### 6.1 Immediate Documentation Updates

**Update Progress Log**:
```bash
# Edit docs/development/workflow_refactor/progress_log.md
# Add new entry: "2025-10-07 — Live Rehearsal Executed"
# Include: results, metrics, anomalies, sign-off status
```

**Update Migration Checklist**:
- Mark rehearsal items complete
- Document any new action items discovered
- Update rollout timeline if needed

### 6.2 Stakeholder Communication

**Summary Email Template**:
```
Subject: Workflow Refactor Rehearsal Complete — [Status]

Team,

The supervised live rehearsal of the unified workflow pipeline was completed on 2025-10-07.

**Scope**:
- Workflow assignment: 3 issues processed
- Issue processing: 2 issues processed  
- Daily operations dry-run: System validation

**Results**:
- Success rate: ___%
- Issues processed: ___ / ___
- Anomalies: ___ (see attached notes)

**Artifacts**:
- Telemetry: [link to shared drive]
- Screenshots: [link]
- Issue state export: [link]

**Next Steps**:
1. Review anomalies and prioritize fixes
2. Update documentation based on observations
3. Schedule production rollout or additional rehearsal

**Sign-Off Status**: [Approved / Needs Iteration / Blocked]

See detailed report: docs/development/workflow_refactor/progress_log.md

[Your Name]
Workflow Modernization Lead
```

### 6.3 Follow-Up Items

**Create GitHub Issues** (if needed):
- [ ] Any bugs or unexpected behavior discovered
- [ ] Documentation improvements identified
- [ ] Feature requests from stakeholders
- [ ] Automation enhancements suggested

**Schedule Follow-Up**:
- [ ] Post-rehearsal retrospective (within 24 hours)
- [ ] Production rollout planning (if approved)
- [ ] Additional rehearsal (if iteration needed)

---

## Section 7: Rollback Procedures

**When to Rollback**:
- Critical errors during execution
- Data corruption or loss
- Permission failures preventing completion
- Stakeholder veto due to unforeseen issues

### 7.1 Immediate Abort

**If Needed During Execution**:
1. **Cancel running workflows**: Click "Cancel workflow" in GitHub Actions
2. **Announce abort**: Post in #wf-modernization Slack channel
3. **Preserve state**: Do NOT manually edit issues until rollback plan confirmed

### 7.2 Label Rollback

**Manual Label Restoration**:
```bash
# Restore monitor::triage to assignment issues
gh issue edit 25 --add-label "monitor::triage" --remove-label "state::assigned"
gh issue edit 24 --add-label "monitor::triage" --remove-label "state::assigned"
gh issue edit 23 --add-label "monitor::triage" --remove-label "state::assigned"

# Restore state::assigned to processing issues
gh issue edit 27 --add-label "state::assigned" --remove-label "state::copilot"
gh issue edit 26 --add-label "state::assigned" --remove-label "state::copilot"

# Remove Copilot assignments
gh issue edit 27 --remove-assignee github-copilot[bot]
gh issue edit 26 --remove-assignee github-copilot[bot]
```

**Issue Body Rollback**:
- Manually remove added sections (## AI Assessment, ## Specialist Guidance, ## Copilot Assignment)
- Or restore from pre-rehearsal backup (if captured)

### 7.3 Incident Logging

**Required Documentation**:
- Timestamp of rollback decision
- Reason for rollback (root cause)
- Issues affected
- Actions taken
- Next steps for resolution

**Template**:
```markdown
## Rehearsal Rollback — 2025-10-07

**Decision Time**: [timestamp]
**Reason**: [description]
**Affected Issues**: #25, #24, #23, #27, #26
**Rollback Actions**: [list steps taken]
**Current State**: [system status after rollback]
**Root Cause Analysis**: [initial findings]
**Next Steps**: [plan for resolution]
```

### 7.4 Emergency Contacts

| Role | Name | Contact | Availability |
|------|------|---------|--------------|
| Workflow Lead | [Name] | [Email/Slack] | Primary |
| DevOps | [Name] | [Email/Slack] | GitHub Actions issues |
| GitHub Admin | [Name] | [Email/Slack] | Permissions/repo issues |
| AI/API | [Name] | [Email/Slack] | OpenAI/Anthropic failures |

---

## Section 8: Success Criteria & Sign-Off

### 8.1 Success Criteria Checklist

**Technical Success**:
- [ ] All workflow runs completed without fatal errors
- [ ] Issues transitioned through expected state machine
- [ ] Labels applied and removed correctly
- [ ] AI Assessment, Specialist Guidance, and Copilot Assignment sections generated
- [ ] Copilot assignments created with due dates
- [ ] Telemetry artifacts captured
- [ ] No API rate limit violations
- [ ] No permission errors

**Quality Success**:
- [ ] AI assessments provide actionable insights
- [ ] Specialist guidance follows template contract
- [ ] Copilot assignments are clear and executable
- [ ] No placeholder or template remnants in output
- [ ] Label taxonomy consistent across all issues

**Operational Success**:
- [ ] Execution completed within planned 90-minute window
- [ ] All stakeholders participated and observed
- [ ] Observations documented by note-taker
- [ ] Artifacts archived for future reference
- [ ] No manual intervention required (beyond planned execution)

### 8.2 Sign-Off Form

**Rehearsal Completion Sign-Off**

| Stakeholder | Role | Approval | Date | Comments |
|-------------|------|----------|------|----------|
| [Name] | Workflow Lead | ☐ Approved ☐ Needs Iteration | ____ | ________ |
| [Name] | Site Monitoring Ops | ☐ Approved ☐ Needs Iteration | ____ | ________ |
| [Name] | Workflow Assignment | ☐ Approved ☐ Needs Iteration | ____ | ________ |
| [Name] | Copilot Operations | ☐ Approved ☐ Needs Iteration | ____ | ________ |
| [Name] | DevOps | ☐ Approved ☐ Needs Iteration | ____ | ________ |

**Overall Recommendation**:
- ☐ **Approved for Production Rollout** — Proceed with scheduled automation
- ☐ **Needs Minor Iteration** — Address identified gaps, re-rehearse subset
- ☐ **Needs Major Iteration** — Significant issues found, full rework required
- ☐ **Blocked** — Critical blocker prevents rollout, escalate immediately

**Next Rehearsal** (if needed): ____________ at ______ UTC

**Production Rollout** (if approved): ____________ at ______ UTC

---

## Appendix A: Quick Command Reference

**Status Check**:
```bash
python main.py status --config config.yaml
```

**List Issues by Label**:
```bash
gh issue list --label "monitor::triage" --state open --json number,title,labels
gh issue list --label "state::assigned" --state open --json number,title,labels
gh issue list --label "state::copilot" --state open --json number,title,assignees
```

**View Issue Details**:
```bash
gh issue view <number> --json title,body,labels,state,assignees,createdAt
```

**Export Issue List**:
```bash
gh issue list --label "site-monitor" --state all --json number,title,labels,state,assignees --limit 100 > issues.json
```

**Check GitHub Actions Status**:
```bash
gh run list --limit 10
gh run view <run-id>
```

---

## Appendix B: Telemetry Sample Validation

**Expected Telemetry Events** (from pre-rehearsal validation):

**Workflow Assignment**:
```json
{
  "event_type": "assignment.complete",
  "timestamp": "2025-10-07T14:15:00Z",
  "cli_command": "assign-workflows",
  "mode": "ai",
  "issue_number": 25,
  "confidence": 0.85,
  "workflow_labels": ["workflow::osint", "specialist::intelligence-analyst"],
  "labels_removed": ["monitor::triage"]
}
```

**Issue Processing**:
```json
{
  "event_type": "batch_processor.summary",
  "timestamp": "2025-10-07T14:35:00Z",
  "cli_command": "process-issues",
  "metrics": {
    "processed_count": 2,
    "success_count": 2,
    "copilot_assignments": {
      "count": 2,
      "next_due_at": "2025-10-09T14:00:00Z"
    }
  },
  "duration": 12.3
}
```

---

**End of Rehearsal Execution Guide**

For questions or updates, contact the Workflow Modernization Lead.
