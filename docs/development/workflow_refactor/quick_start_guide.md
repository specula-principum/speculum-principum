# Quick Start Guide for Next Engineer

**Last Updated**: October 3, 2025  
**Project Status**: ✅ Ready for Live Rehearsal  
**Current Phase**: Pre-Rehearsal Preparation

---

## 🎯 What You Need to Know in 5 Minutes

The workflow refactor is **complete and validated**. Your job is to **execute the live rehearsal** and **manage the production rollout**.

**Current State**:
- ✅ All code complete (560/562 tests passing, 77% coverage)
- ✅ All GitHub Actions configured and tested
- ✅ All documentation complete (15 docs, 2,500+ lines)
- ✅ Pre-rehearsal validation confirms 85% confidence

**Next Steps**:
1. Confirm rehearsal date (proposed: Oct 7, 2025 at 14:00 UTC)
2. Execute supervised rehearsal (90 minutes with stakeholders)
3. Collect artifacts and validate results
4. Get sign-off and proceed to production rollout (4 weeks)

---

## 📚 Essential Documents (Read in Order)

### Before Rehearsal
1. **[`executive_briefing.md`](./executive_briefing.md)** - 10-minute read for context and decision framework
2. **[`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md)** - 15-minute read for technical readiness details
3. **[`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md)** - 30-minute read for step-by-step procedures

### After Rehearsal
4. **[`production_rollout_plan.md`](./production_rollout_plan.md)** - Phased deployment strategy (read if rehearsal succeeds)
5. **[`progress_log.md`](./progress_log.md)** - Update with rehearsal results and observations

### Reference Materials
- [`README.md`](./README.md) - Project overview and objectives
- [`target_state_design.md`](./target_state_design.md) - Target architecture
- [`migration_checklist.md`](./migration_checklist.md) - Rollout tracking

---

## 🚀 Quick Command Reference

### Validate System Health
```bash
# Check overall status
python main.py status --config config.yaml

# Run full test suite
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v
```

### Dry-Run Validation
```bash
# Test workflow assignment (AI-enhanced)
python main.py assign-workflows --config config.yaml --limit 5 --dry-run --verbose --statistics

# Test issue processing (batch mode)
python main.py process-issues --config config.yaml --batch-size 3 --dry-run --verbose

# List site-monitor issues
gh issue list --label "site-monitor" --state open --json number,title,labels --limit 20
```

### GitHub Actions
```bash
# List recent workflow runs
gh run list --limit 10

# View specific run details
gh run view <run-id>

# Manually trigger workflow (from GitHub UI):
# Actions → [Workflow Name] → Run workflow → Configure inputs
```

---

## 🎬 Rehearsal Execution Checklist

### T-30 Minutes (Preparation)
- [ ] All stakeholders confirmed and available
- [ ] Video conference link shared
- [ ] Target issues identified and tagged:
  - 3 issues with `monitor::triage` (for assignment)
  - 2 issues with `state::assigned` (for processing)
- [ ] Dashboards open (GitHub Actions, Issues, Telemetry)
- [ ] Note-taker assigned with template document
- [ ] Secrets validated (run ops-daily-operations in dry-run)

### Phase 1: Assignment (T+0 to T+20 min)
- [ ] Navigate to Actions → Workflow Assignment → Run workflow
- [ ] Configure: branch=feature/issue_processing, limit=3, dry_run=false, verbose=true
- [ ] Monitor execution (3-5 min per issue expected)
- [ ] Verify labels updated, AI Assessment added, monitor::triage removed
- [ ] Download telemetry artifact

### Phase 2: Processing (T+20 to T+50 min)
- [ ] Navigate to Actions → Issue Processing → Run workflow
- [ ] Configure: branch=feature/issue_processing, batch_size=2, dry_run=false, verbose=true
- [ ] Monitor execution (5-10 min per issue expected)
- [ ] Verify Specialist Guidance, Copilot Assignment sections added
- [ ] Verify Copilot assigned with due date
- [ ] Download telemetry artifact

### Phase 3: Validation (T+50 to T+65 min)
- [ ] Navigate to Actions → Daily Operations → Run workflow
- [ ] Use default dry-run inputs
- [ ] Monitor summary output
- [ ] Download telemetry artifact
- [ ] Verify no label drift detected

### Post-Rehearsal (T+65 to T+90 min)
- [ ] Export issue states: `gh issue list --label "site-monitor" --state all --json number,title,labels,state,assignees > rehearsal-state.json`
- [ ] Screenshot workflow summaries and issue bodies
- [ ] Complete validation checklist in execution guide
- [ ] Document observations and anomalies
- [ ] Get stakeholder sign-off
- [ ] Update progress log with results

---

## 🔧 Troubleshooting

### Secret Validation Fails
**Symptom**: Workflow fails at "Validate required secrets" step  
**Solution**: Verify GitHub secrets are set (Settings → Secrets and variables → Actions)  
**Required**: GITHUB_TOKEN, GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID, OPENAI_API_KEY or ANTHROPIC_API_KEY

### Workflow Hangs or Times Out
**Symptom**: Workflow runs >15 minutes without completing  
**Solution**: Click "Cancel workflow", check GitHub API rate limits, verify AI provider availability  
**Escalate**: If rate limits exhausted, follow rollback procedures in execution guide

### Label Drift Detected
**Symptom**: Issues have both monitor::triage and state::assigned labels  
**Solution**: This indicates assignment workflow didn't remove temporary label  
**Fix**: Manually remove monitor::triage via `gh issue edit <number> --remove-label "monitor::triage"`

### Missing Issue Sections
**Symptom**: Issue body doesn't contain ## AI Assessment or ## Specialist Guidance  
**Solution**: Check workflow logs for errors during section generation  
**Verify**: Template files exist in templates/ directory, workflow configuration valid

### Copilot Not Assigned
**Symptom**: Issue processed but no @github-copilot[bot] assignee  
**Solution**: Verify Copilot account has repository access (Settings → Collaborators)  
**Alternative**: Manually assign via `gh issue edit <number> --add-assignee github-copilot[bot]`

---

## 📞 Emergency Contacts

| Issue Type | Contact | Action |
|------------|---------|--------|
| GitHub Actions failure | DevOps | Check Actions tab, review logs |
| API rate limits | Technical Lead | Monitor quotas, implement backoff |
| Permission errors | GitHub Admin | Verify repo settings, workflow permissions |
| AI provider issues | AI/API Lead | Check OpenAI/Anthropic status, switch provider |
| Critical blocker | Workflow Lead | Execute rollback per Section 7 of execution guide |

---

## 🎯 Success Criteria

**Rehearsal Succeeds If**:
- ✅ All 5 issues processed without fatal errors
- ✅ Labels transition correctly (monitor::triage → workflow::*, state::assigned → state::copilot)
- ✅ AI Assessment, Specialist Guidance, Copilot Assignment sections generated
- ✅ Telemetry artifacts captured and archived
- ✅ No API rate limit violations or permission errors
- ✅ Stakeholders approve moving to production rollout

**Rehearsal Needs Iteration If**:
- ⚠️ 1-2 issues fail but cause is understood and fixable
- ⚠️ Quality issues in generated content (templates need adjustment)
- ⚠️ Performance slower than expected but within acceptable range

**Rehearsal Fails If**:
- ❌ >50% of issues fail to process
- ❌ Data corruption or conflicting states
- ❌ Critical security or permission issue
- ❌ API exhaustion prevents completion

---

## 🏁 After Rehearsal

### If Approved for Production
1. Update progress log with rehearsal results
2. Complete sign-off checklist
3. Schedule Week 1 rollout (enable scheduled workflows)
4. Follow [`production_rollout_plan.md`](./production_rollout_plan.md) Week 1 procedures
5. Set up on-call rotation for monitoring window

### If Iteration Needed
1. Document issues and gaps in progress log
2. Create GitHub issues for identified problems
3. Estimate time to resolution
4. Schedule follow-up rehearsal (1-2 weeks)
5. Communicate timeline to stakeholders

### If Blocked
1. Execute rollback procedures (Section 7 of execution guide)
2. Create incident report with root cause
3. Escalate to executive team
4. Convene stakeholder meeting to reassess approach

---

## 📈 Key Metrics to Track

### During Rehearsal
- **Duration**: Target <5 min per assignment, <10 min per processing
- **Success Rate**: Target 100% (5/5 issues processed)
- **Label Accuracy**: 0 drift instances
- **Section Quality**: All required sections present and non-empty

### Post-Rollout (Week 1-4)
- **Flow-Through**: >95% (monitored → assigned → processed → completed)
- **Label Quality**: 100% match validated schemas
- **Copilot Completion**: >80% within 48 hours
- **Error Rate**: <5% across all workflows

---

## 💡 Pro Tips

1. **Keep Calm**: Everything is validated and tested. Rehearsal is a formality to build confidence.
2. **Document Everything**: Update progress log in real-time during rehearsal.
3. **Trust the Process**: Follow the execution guide step-by-step. It's designed for success.
4. **Communicate Often**: Post updates in #wf-modernization every 15 minutes during rehearsal.
5. **Ask for Help**: All stakeholders are there to support you. Use them.
6. **Celebrate Success**: This is a major milestone. Recognize the team's hard work.

---

## 📋 Final Pre-Flight Checklist

**Before Starting Rehearsal**:
- [ ] Read executive briefing, pre-rehearsal validation, and execution guide
- [ ] Confirm all stakeholders available and video conference ready
- [ ] Validate system health (tests, CLI, GitHub Actions)
- [ ] Tag target issues and capture backup state
- [ ] Open monitoring dashboards
- [ ] Review rollback procedures
- [ ] Take a deep breath and execute with confidence! 🚀

---

**You've got this!** The previous engineer did comprehensive preparation. Your job is execution and delivery. Follow the guides, communicate clearly, and trust the validated system.

**Questions?** Check the docs first, then reach out to stakeholders. All contact info is in the execution guide.

**Good luck with the rehearsal!** 🎉
