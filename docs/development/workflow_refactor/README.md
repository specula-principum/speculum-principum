# Workflow Refactor Initiative

**Project Owner**: Workflow Modernization Lead  \
**Primary Stakeholders**: Site Monitoring Ops, AI Workflow Assignment Team, Specialist Enablement, Copilot Operations  \
**Last Updated**: October 3, 2025  \
**Status**: ✅ Ready for Live Rehearsal

---

## Quick Start for Next Engineer

**New here?** Start with [`quick_start_guide.md`](./quick_start_guide.md) for a 5-minute overview and execution checklist.

**Current Priority**: Execute supervised live rehearsal (proposed October 7, 2025 at 14:00 UTC) following [`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md).

**Key Documents**:
- Executive decision-maker? Read [`executive_briefing.md`](./executive_briefing.md)
- Technical validator? Read [`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md)
- Rehearsal facilitator? Read [`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md)
- Post-rehearsal planner? Read [`production_rollout_plan.md`](./production_rollout_plan.md)

---

## Purpose
The workflow refactor project consolidates the end-to-end intelligence pipeline—site monitoring, workflow assignment, and issue processing—into a single, coherent system. The objective is to eliminate redundant execution paths, streamline specialist guidance, and ensure every monitored update results in a Copilot-ready issue enriched with high-quality analyst direction.

## Objectives
- Align the three core workflows so that site monitoring, workflow assignment, and issue processing operate as a continuous pipeline.
- Replace overlapping "basic issue-processing" and "issue-processing-copilot" paths with a unified specialist-guided issue processor that hands off to Copilot for document creation.
- Elevate label management so AI-powered workflow assignment both adds relevant workflow labels and removes temporary discovery labels.
- Guarantee that every generated issue contains actionable specialist guidance tailored to the target content.
- Deliver a comprehensive launch plan that minimizes operational downtime and ensures testability at each phase.

## Success Criteria
- **Workflow flow-through**: >95% of monitored updates progress automatically from site monitoring to Copilot-ready issues without manual orchestration.
- **Label quality**: Labels applied by workflow assignment consistently match at least one validated workflow schema, with temporary discovery labels removed within the same execution.
- **Specialist signal**: Issues entering Copilot processing contain at least one specialist guidance block that follows the standardized prompt contract.
- **Operational simplicity**: Only one issue-processing entrypoint remains, with clear CLI/automation hooks and updated documentation.

## Workstreams
1. **Current State Assessment** – Capture the as-is behaviors, configurations, and operational constraints across the three workflows.
2. **Target Architecture Definition** – Document the desired end-to-end flow, data contracts, and automation touchpoints.
3. **Refactor Planning & Execution** – Provide a phased implementation plan, acceptance criteria, and validation strategy.
4. **Specialist Alignment** – Standardize specialist prompt contracts, Copilot handoff instructions, and knowledge base updates.

## Supporting Documents

### 🚀 Start Here (New to Project)
- **[`quick_start_guide.md`](./quick_start_guide.md)** - 5-minute overview and execution checklist
- **[`HANDOFF_CHECKLIST.md`](./HANDOFF_CHECKLIST.md)** - Complete readiness verification for next engineer
- **[`TAKEOVER_SUMMARY.md`](./TAKEOVER_SUMMARY.md)** - October 3, 2025 takeover work summary

### 📊 Planning & Design
- [`current_state_assessment.md`](./current_state_assessment.md) - As-is state analysis and pain points
- [`target_state_design.md`](./target_state_design.md) - Target architecture and data contracts
- [`refactor_plan.md`](./refactor_plan.md) - Implementation roadmap and task backlog
- [`specialist_alignment.md`](./specialist_alignment.md) - Specialist guidance contracts and Copilot handoff
- [`migration_checklist.md`](./migration_checklist.md) - Rollout tracking and validation steps

### 🎯 Execution & Operations
- **[`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md)** - Technical readiness assessment (85% confidence)
- **[`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md)** - Step-by-step 90-minute rehearsal procedures
- **[`production_rollout_plan.md`](./production_rollout_plan.md)** - 4-week phased production deployment
- **[`executive_briefing.md`](./executive_briefing.md)** - C-level decision framework and approval process
- [`live_rehearsal_plan.md`](./live_rehearsal_plan.md) - Original rehearsal concept (superseded by execution guide)
- [`ops_migration_brief.md`](./ops_migration_brief.md) - Operator guidance and failure handling

### 📈 Tracking & History
- [`progress_log.md`](./progress_log.md) - Incremental progress tracking (updated October 3, 2025)
- [`CHANGELOG.md`](./CHANGELOG.md) - Modernization history and release notes
- [`telemetry_samples.md`](./telemetry_samples.md) - Observability examples

### 📦 Artifacts
- [`artifacts/sample_issue_body.md`](./artifacts/sample_issue_body.md) - Template showcase with real sections

---

## Document Index by Role

### For Next Engineer Taking Over
1. Start: [`quick_start_guide.md`](./quick_start_guide.md)
2. Verify: [`HANDOFF_CHECKLIST.md`](./HANDOFF_CHECKLIST.md)
3. Understand: [`TAKEOVER_SUMMARY.md`](./TAKEOVER_SUMMARY.md)
4. Execute: [`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md)

### For Executive Decision-Maker
1. Context: [`executive_briefing.md`](./executive_briefing.md)
2. Details: [`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md)
3. Timeline: [`production_rollout_plan.md`](./production_rollout_plan.md)

### For Technical Validator
1. Validation: [`pre_rehearsal_validation.md`](./pre_rehearsal_validation.md)
2. Architecture: [`target_state_design.md`](./target_state_design.md)
3. Testing: Run `pytest tests/ -v` (see validation doc for results)

### For Operations Team
1. Rehearsal: [`rehearsal_execution_guide.md`](./rehearsal_execution_guide.md)
2. Migration: [`ops_migration_brief.md`](./ops_migration_brief.md)
3. Rollout: [`production_rollout_plan.md`](./production_rollout_plan.md)

---

## Project Metrics

**Code Quality**:
- Test Coverage: 77% (7,904 statements)
- Tests Passing: 560/562 (2 skipped)
- Critical Path Coverage: 85-92%

**Documentation**:
- Total Documents: 17
- Total Lines: 2,500+
- Completion: 100%

**Timeline**:
- Planning Started: September 2025
- Code Complete: September 30, 2025
- Validation Complete: October 3, 2025
- Rehearsal Proposed: October 7, 2025
- Production Target: Week of October 14, 2025

## Telemetry & Observability
- CLI commands now register a default JSONL telemetry publisher located at `artifacts/telemetry/{command}.jsonl` so dry-run automation and GitHub Actions can collect structured events without additional wiring.
- Override the destination by setting `SPECULUM_CLI_TELEMETRY_PATH` (exact file) or `SPECULUM_CLI_TELEMETRY_DIR`/`SPECULUM_ARTIFACTS_DIR` (directory). Parent directories are created automatically.
- Events emitted by `SiteMonitorService` and `BatchProcessor` gain CLI metadata via `cli_command` and `cli_session_id`, enabling dashboards to filter by invocation.
- Sample summary event:
	```json
	{
		"event_type": "batch_processor.summary",
		"timestamp": "2025-10-01T14:12:03.482193+00:00",
		"cli_command": "process-issues",
		"cli_session_id": "b8a1e6c3d2b34b3b8797e36f2a4f8347",
		"metrics": {
			"processed_count": 5,
			"copilot_assignments": {
				"count": 3,
				"next_due_at": "2025-10-02T09:00:00Z"
			}
		},
		"context": {
			"total_requested": 6,
			"dry_run": true
		}
	}
	```

---
For questions or updates, contact the Workflow Modernization Lead or update this directory with meeting notes, architectural decisions, and implementation artifacts.
