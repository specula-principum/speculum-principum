# Production Rollout Plan

**Version**: 1.0  
**Status**: Draft — Pending Rehearsal Sign-Off  
**Target Rollout Date**: TBD (Post-rehearsal approval)  
**Owner**: Workflow Modernization Lead

---

## Executive Summary

This document outlines the production rollout strategy for the unified workflow pipeline, transitioning from supervised rehearsal to fully automated operations. The rollout follows a phased approach to minimize risk while enabling the complete monitor → assign → process → Copilot execution path.

**Prerequisites**:
- ✅ Live rehearsal executed successfully
- ✅ Sign-off from all stakeholders
- ✅ Anomalies identified during rehearsal resolved or documented
- ✅ Telemetry validation confirms expected behavior

---

## Phase 1: Scheduled Automation (Week 1)

### 1.1 Enable Workflow Assignment Schedule

**Current State**: Manual dispatch only  
**Target State**: Automated execution every 2 hours

**Action**:
```yaml
# In .github/workflows/ops-workflow-assignment.yml
# CURRENT (disabled):
# schedule:
#   - cron: '0 */2 * * *'  # Every 2 hours

# ENABLE:
schedule:
  - cron: '0 */2 * * *'  # Every 2 hours (uncommented)
```

**Configuration**:
- Limit: 10 issues per run (conservative initial limit)
- Dry-run: false (live mode)
- Verbose: true (capture detailed logs)
- Statistics: true (emit metrics)

**Monitoring Window**: 48 hours with on-call coverage

**Success Criteria**:
- [ ] At least 4 scheduled runs complete successfully
- [ ] No GitHub rate limit violations
- [ ] AI API usage within quota
- [ ] Label transitions follow state machine
- [ ] No monitor::triage drift detected

**Rollback Trigger**: >20% failure rate across 4 runs

---

### 1.2 Enable Issue Processing Schedule

**Current State**: Manual dispatch only  
**Target State**: Automated execution every 4 hours

**Action**:
```yaml
# In .github/workflows/ops-issue-processing.yml
# CURRENT (disabled):
# schedule:
#   - cron: '5 */4 * * *'

# ENABLE:
schedule:
  - cron: '5 */4 * * *'  # Every 4 hours, offset 5 minutes (uncommented)
```

**Configuration**:
- Batch size: 5 issues per run
- Dry-run: false (live mode)
- Verbose: true
- Continue-on-error: true (resilient batch processing)

**Monitoring Window**: 48 hours with on-call coverage

**Success Criteria**:
- [ ] At least 3 scheduled runs complete successfully
- [ ] Specialist guidance quality maintained
- [ ] Copilot assignments created correctly
- [ ] No state::assigned → state::copilot drift
- [ ] Branch/file operations successful

**Rollback Trigger**: >10% failure rate or data quality issues

---

### 1.3 Enable Daily Operations Workflow

**Current State**: Dry-run only  
**Target State**: Live daily execution

**Action**:
```yaml
# In .github/workflows/ops-daily-operations.yml
# UPDATE schedule to run in live mode (currently dry-run only)
# Requires modification to remove --dry-run flags after validating behavior
```

**Phased Approach**:
1. **Week 1**: Keep dry-run mode, validate daily summary output
2. **Week 2**: Enable monitoring phase (live)
3. **Week 3**: Enable assignment phase (live)
4. **Week 4**: Enable processing phase (live) — Full pipeline operational

**Configuration**:
- Assignment limit: 20 issues
- Processing batch size: 10 issues
- Schedule: Daily at 06:30 UTC

**Success Criteria**:
- [ ] Daily summary reports accurate system state
- [ ] No conflicts with individual workflow schedules
- [ ] Telemetry artifacts collected and accessible
- [ ] Execution time within 15-minute window

**Rollback Trigger**: Execution time exceeds 30 minutes or conflicts detected

---

## Phase 2: Capacity Scaling (Week 2)

### 2.1 Increase Assignment Capacity

**Current Limits**: 10 issues per run (every 2 hours) = ~120 issues/day  
**Target Limits**: 20 issues per run = ~240 issues/day

**Justification**: Based on observed performance and API quotas from Phase 1

**Prerequisite Validation**:
- [ ] Average assignment duration <30 seconds per issue
- [ ] AI API usage <50% of daily quota during Phase 1
- [ ] GitHub API rate limit comfortably below limits
- [ ] Zero critical errors in Phase 1 runs

**Gradual Increase**:
- Day 1-2: 15 issues per run
- Day 3-5: 18 issues per run
- Day 6-7: 20 issues per run

**Monitoring**: Watch for API rate limit warnings, execution time increases

---

### 2.2 Increase Processing Capacity

**Current Limits**: 5 issues per run (every 4 hours) = ~30 issues/day  
**Target Limits**: 10 issues per run = ~60 issues/day

**Justification**: Match assignment throughput while maintaining quality

**Prerequisite Validation**:
- [ ] Average processing duration <2 minutes per issue
- [ ] Specialist guidance quality score >90% (manual review sample)
- [ ] Copilot completion rate >80% within 48 hours
- [ ] Zero data corruption or merge conflicts

**Gradual Increase**:
- Day 1-2: 7 issues per run
- Day 3-5: 9 issues per run
- Day 6-7: 10 issues per run

**Monitoring**: Track Copilot backlog, specialist guidance completeness

---

### 2.3 Optimize Schedule Coordination

**Current State**: Independent schedules with potential overlap  
**Target State**: Coordinated schedule to prevent conflicts

**Proposed Schedule**:
```
00:00 UTC - Daily Operations (monitoring phase)
02:00 UTC - Workflow Assignment
04:00 UTC - Issue Processing
06:00 UTC - Workflow Assignment
06:30 UTC - Daily Operations (full pipeline dry-run)
08:00 UTC - Issue Processing
10:00 UTC - Workflow Assignment
12:00 UTC - Issue Processing
14:00 UTC - Workflow Assignment
16:00 UTC - Issue Processing
18:00 UTC - Workflow Assignment
20:00 UTC - Issue Processing
22:00 UTC - Workflow Assignment
```

**Rationale**: Assignment before processing ensures fresh state::assigned issues available

**Concurrency Controls**: Existing workflow concurrency groups prevent overlaps within same workflow

---

## Phase 3: Quality Assurance (Week 3)

### 3.1 Automated Quality Checks

**Implement Validation Workflow**:
Create `.github/workflows/ops-quality-validation.yml` to run hourly:

**Checks**:
- [ ] Label drift detection (monitor::triage on state::assigned issues)
- [ ] Orphaned Copilot assignments (no specialist guidance)
- [ ] Stale assignments (state::copilot >7 days without completion)
- [ ] Template remnants in issue bodies (placeholder text)
- [ ] Broken branch/file references

**Alert Triggers**:
- Slack notification for any validation failure
- GitHub issue created for persistent problems
- Email to Workflow Lead for critical issues

---

### 3.2 Copilot Completion Tracking

**Metrics to Monitor**:
- Time-to-completion distribution
- Completion rate by workflow type
- Blocker frequency and categories
- Feedback quality from Copilot

**Target SLAs**:
- 80% completion within 48 hours
- 95% completion within 7 days
- <5% blocked requiring manual intervention

**Escalation Path**:
- Day 3 overdue: Automated reminder comment
- Day 7 overdue: Copilot Operations notified
- Day 14 overdue: Manual review required

---

### 3.3 Specialist Guidance Quality Review

**Sampling Strategy**:
- Random sample of 10 issues per week
- Review specialist guidance completeness
- Validate Copilot assignment clarity
- Check AI assessment accuracy

**Quality Rubric**:
| Criterion | Weight | Target Score |
|-----------|--------|--------------|
| Persona appropriateness | 20% | >90% |
| Actionable objectives | 25% | >95% |
| Input completeness | 20% | >90% |
| Deliverable clarity | 25% | >95% |
| Acceptance criteria specificity | 10% | >85% |

**Review Team**: Rotating weekly among Workflow Assignment, Site Monitoring, Copilot Ops

**Feedback Loop**: Identify template improvements, edge cases for documentation

---

## Phase 4: Full Automation (Week 4)

### 4.1 Enable Complete Pipeline

**Daily Operations Workflow**: Transition to live mode

**Steps**:
1. Remove --dry-run flags from monitoring, assignment, and processing commands
2. Update schedule to execute full pipeline once daily
3. Retain individual workflow schedules for higher frequency

**Validation**:
- [ ] End-to-end execution completes without manual intervention
- [ ] Telemetry shows continuous flow from discovery to Copilot assignment
- [ ] No backlog accumulation (processing keeps pace with monitoring)
- [ ] Quality metrics remain stable

---

### 4.2 Archive Legacy Workflows

**Workflows to Archive** (move to .github/workflows/archive/):
- Any manual-only dispatch workflows no longer needed
- Deprecated testing workflows superseded by new automation

**Documentation Updates**:
- Update README.md to reflect active workflows only
- Archive old runbooks in docs/legacy/
- Create migration guide for users of deprecated workflows

---

### 4.3 Enable Observability Dashboard

**Grafana/Datadog Integration** (if available):
- Ingest telemetry JSONL files
- Create dashboards for:
  - Issue flow (monitoring → assignment → processing → completion)
  - Label distribution over time
  - Specialist workload distribution
  - Copilot completion metrics
  - API usage and rate limits
  - Error rates and categories

**Alternative** (if no dashboard tooling):
- Weekly automated reports via GitHub Actions
- Email summaries of key metrics
- Markdown reports committed to docs/metrics/

---

## Rollback Strategy

### Trigger Conditions

**Automated Rollback** (immediate):
- GitHub API rate limit exhausted
- >50% failure rate in any workflow over 6 hours
- Data corruption detected (conflicting issue states)
- Security alert related to workflow execution

**Manual Rollback** (stakeholder decision):
- Copilot completion rate <50% for 3 consecutive days
- Quality degradation (multiple complaints from users)
- Operational impact (excessive manual intervention required)
- Strategic pivot (business priorities change)

---

### Rollback Procedures

**Disable Scheduled Workflows**:
```yaml
# Comment out schedule triggers in:
# - ops-workflow-assignment.yml
# - ops-issue-processing.yml
# - ops-daily-operations.yml

# schedule:
#   - cron: '...'
```

**Revert to Manual Dispatch**:
- Announce rollback in #wf-modernization
- Document rollback reason in progress log
- Create incident report with root cause analysis

**Data Cleanup**:
- Review issues in intermediate states (state::assigned, state::copilot)
- Manually triage and reassign or complete as needed
- Export issue states for post-mortem analysis

**Communication**:
- Email to all stakeholders with rollback summary
- Post-mortem meeting within 48 hours
- Action plan for resolution or iteration

---

## Post-Rollout Review (Week 5)

### Success Metrics

**Quantitative**:
- [ ] >95% workflow flow-through (discovery → Copilot without manual intervention)
- [ ] Label quality: 100% of assigned issues have matching workflow schemas
- [ ] Specialist signal: 100% of processed issues have specialist guidance
- [ ] Copilot completion: >80% within 48 hours

**Qualitative**:
- [ ] Stakeholder satisfaction survey (5-point scale, target >4.0)
- [ ] Copilot feedback on guidance quality (qualitative themes)
- [ ] Operational burden assessment (time saved vs. manual processes)

---

### Lessons Learned Session

**Attendees**: All stakeholders from rehearsal + broader engineering team

**Agenda**:
1. Review rollout timeline and milestones
2. Discuss challenges and how they were addressed
3. Identify process improvements for future rollouts
4. Celebrate successes and recognize contributions

**Deliverables**:
- Updated runbooks with real-world learnings
- Template updates based on production data
- Recommendations for next-generation features
- Post-mortem report published in docs/

---

### Continuous Improvement Backlog

**Potential Enhancements**:
- [ ] AI model fine-tuning based on assignment accuracy
- [ ] Specialist persona expansion (new domains)
- [ ] Workflow branching (conditional processing paths)
- [ ] Multi-language support for international content
- [ ] Integration with external intelligence feeds
- [ ] Automated quality scoring for deliverables
- [ ] Self-healing workflows (automatic retry/recovery)

**Prioritization Criteria**:
- User impact (stakeholder requests)
- Technical debt reduction
- Operational efficiency gains
- Strategic alignment with roadmap

---

## Appendix A: Rollout Timeline

| Week | Phase | Key Milestones | Go/No-Go Decision |
|------|-------|----------------|-------------------|
| Pre-rollout | Rehearsal | Live rehearsal, sign-off | Day -1: Proceed to Week 1 |
| 1 | Scheduled Automation | Enable assignment & processing schedules | Day 7: Proceed to Week 2 or iterate |
| 2 | Capacity Scaling | Increase limits, optimize schedules | Day 14: Proceed to Week 3 or hold |
| 3 | Quality Assurance | Validation workflows, tracking | Day 21: Proceed to Week 4 or hold |
| 4 | Full Automation | Complete pipeline live | Day 28: Declare success or rollback |
| 5 | Post-Rollout Review | Metrics, retrospective, backlog | Day 35: Close rollout, plan next phase |

---

## Appendix B: Contact Matrix

| Role | Responsibility | Primary Contact | Backup |
|------|----------------|-----------------|--------|
| Rollout Lead | Overall coordination | [Name] | [Name] |
| DevOps | GitHub Actions, infrastructure | [Name] | [Name] |
| Site Monitoring | Content discovery | [Name] | [Name] |
| Workflow Assignment | AI classification | [Name] | [Name] |
| Issue Processing | Specialist guidance | [Name] | [Name] |
| Copilot Operations | Assignment execution | [Name] | [Name] |
| On-Call Engineer | Incident response | [Rotation] | [Escalation] |

---

## Appendix C: Communication Templates

### Week 1 Launch Announcement

```
Subject: Unified Workflow Pipeline — Production Rollout (Phase 1)

Team,

The unified workflow pipeline is entering production this week following a successful live rehearsal on [date].

**What's Changing**:
- Workflow assignment will run automatically every 2 hours
- Issue processing will run automatically every 4 hours
- Issues will flow from discovery → assignment → processing → Copilot with minimal manual intervention

**What to Expect**:
- More consistent labeling and specialist guidance on site-monitor issues
- Faster turnaround from content discovery to Copilot-ready assignments
- Detailed telemetry for monitoring pipeline health

**What You Can Do**:
- Monitor the #wf-modernization channel for status updates
- Report any anomalies or unexpected behavior immediately
- Provide feedback on specialist guidance quality

**Monitoring Window**: 48 hours with on-call coverage

See full rollout plan: docs/development/workflow_refactor/production_rollout_plan.md

Thanks for your partnership on this modernization effort!

[Rollout Lead]
```

---

### Weekly Status Update Template

```
Subject: Workflow Pipeline — Week [N] Status

Team,

**Week [N] Summary** ([Date Range])

**Metrics**:
- Issues monitored: ___
- Workflow assignments: ___
- Processing completed: ___
- Copilot assignments: ___
- Success rate: ___%

**Highlights**:
- [Achievement 1]
- [Achievement 2]

**Issues**:
- [Issue 1 and resolution]
- [Issue 2 and status]

**Next Week**:
- [Planned milestone]
- [Expected changes]

**Feedback Welcome**: Reply to this email or post in #wf-modernization

Dashboard: [link to telemetry/metrics]

[Rollout Lead]
```

---

**End of Production Rollout Plan**

This document will be updated based on rehearsal findings and stakeholder feedback.
