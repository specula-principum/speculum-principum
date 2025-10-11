# Legacy Workflow Migration Plan

_Date: 2025-10-10_

All pre-taxonomy workflow definitions (legacy intelligence, OSINT, research, profiling, and technical review workflows) were removed from the repository on 2025-10-10. The archive directory and deliverable stubs no longer exist; only taxonomy-compliant criminal-law workflows remain under `docs/workflow/deliverables/criminal-law/`.

## Current Objectives
- Confirm no automation, documentation, or telemetry pipelines reference the retired workflow IDs.
- Provide clear communications to stakeholders highlighting the removal and the new taxonomy-only baseline.
- Establish guard rails (linting/tests/CI checklists) that prevent legacy workflows from re-entering the repository.

## Validation Checklist
1. **Automation & Agents**
   - [ ] Re-scan assignment agents, CLI options, and specialist registries for deprecated workflow names.
   - [ ] Update any fallback prompts or help text (e.g., AI clarification comments) that still list the legacy options.
2. **Telemetry & Reporting**
   - [ ] Confirm telemetry schemas and dashboards exclude the retired identifiers.
   - [ ] Purge or annotate historical telemetry artifacts that still reference legacy workflows.
3. **Documentation & Onboarding**
   - [ ] Refresh onboarding collateral, FAQs, and SOPs to remove legacy workflow references.
   - [ ] Publish a changelog entry summarizing the removal for legal and operations stakeholders.

## Follow-Up Actions
- Backfill automated tests that assert only taxonomy workflows load during matcher initialization.
- Add a repository guideline stating that future non-taxonomy experiments live in feature branches or external sandboxes until vetted.
- Schedule a 30-day review to verify no issues or telemetry entries contain the deprecated workflow IDs.

## Risks & Mitigations
- **Residual references in automation:** Mitigation: CI guard + targeted code search before release.
- **Stakeholder confusion about missing workflows:** Mitigation: Update onboarding packets and provide crosswalk from legacy names to their criminal-law counterparts where applicable.
- **Historical telemetry drift:** Mitigation: Tag archived events and ensure dashboards apply filters by schema version.
