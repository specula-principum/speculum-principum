# Workflow Taxonomy Modernization – Implementation Roadmap

## Phase 0 · Discovery & Alignment *(Completed 2025-10-09)*
- **Stakeholder Confirmation:** Held review sessions with the Principal Attorney, GAO Liaison, and Knowledge Management Specialist; secured approval of taxonomy goals, audit fields, and risk tolerances.
- **Current State Inventory:** Catalogued existing workflow YAML definitions, templates, and assignment rules; confirmed migration priorities with stakeholders.
- **Data & Tooling Audit:** Verified entity extraction pipeline health, GitHub Models API quotas, and template rendering capabilities; captured remediation actions for minor telemetry gaps.
- **Success Metrics Baseline:** Recorded pre-modernization metrics (assignment accuracy, reclassification rate, deliverable turnaround) for comparison during rollout.
- **Outcome:** Stakeholder sign-off recorded in `progress-log.md`, unlocking Phase 1 engineering work.

## Phase 1 · Taxonomy Definition & Schema Foundations
- **Hierarchical Model Draft:** Formalize the ten target workflows with parent categories (`Entity Foundation`, `Legal Research Layer`, `Operational Coordination`) and document triggers, inputs, outputs, and success criteria.
- **Metadata Specification:** Define canonical fields (`required_entities`, `priority`, `confidence_threshold`, `workflow_version`, `audit_trail`) and align naming conventions.
- **Schema Refactor:** Extend `workflow_schemas.py` with reusable entity mixins, layered module validation, and enumeration support for categories; include backward-compatibility toggles.
- **Validation Suite:** Author targeted unit tests to lock schema behaviours, including failure cases for missing base entities or invalid metadata.

## Phase 2 · Workflow Definition Migration
- **YAML Updates:** Rewrite or add workflow definitions under `docs/workflow` to match the new taxonomy, including shared base entity blocks and workflow-specific overlays.
- **Label Mapping Matrix:** Create a migration map from legacy labels to new workflows, including confidence thresholds and manual review notes.
- **Version Control Strategy:** Introduce `workflow_version` tracking and document release cadence for schema/definition updates.

## Phase 3 · Assignment Engine Enhancements
- **Signal Feature Engineering:** Update `ai_workflow_assignment_agent.py` to incorporate entity coverage weighting (40%), legal citation detection, inter-agency context, and explainability reason codes.
- **Fallback Alignment:** Refresh `workflow_assignment_agent.py` label heuristics to respect the new taxonomy and leverage the migration map.
- **Confidence Handling:** Implement configurable manual review thresholds and telemetry logging for borderline assignments.
- **Test Coverage:** Expand integration tests to validate scoring outputs, reason codes, and fallback routing.

## Phase 4 · Deliverable & Template Overhaul
- **Template Modularization:** Create shared base components for entity tables, GAO citation blocks, and confidentiality banners; integrate into each workflow template in `docs/workflow/deliverables`.
- **Generator Logic:** Enhance `workflow/deliverable_generator.py` to stack base entity sections before workflow-specific content and honour audit trail requirements.
- **Acceptance Criteria:** Define validation checks ensuring deliverables include mandatory sections and references.

## Phase 5 · CLI & Telemetry Upgrades
- **CLI Filters:** Extend `main.py process-issues` and related CLI helpers to accept `--workflow-category` and display taxonomy adoption metrics.
- **Telemetry Instrumentation:** Emit events capturing entity extraction coverage, workflow confidence distribution, and manual review counts.
- **Operational Dashboards:** Document queries or dashboards (if applicable) for monitoring adoption metrics.

## Phase 6 · Testing, Migration & Rollout
- **Integration Test Matrix:** Ensure end-to-end coverage for at least one scenario per workflow, including mixed batch processing.
- **Regression Safeguards:** Maintain compatibility layer for legacy workflows until migration completes; supply automated migration scripts if needed.
- **Training & Documentation:** Produce quick-reference guides, update README sections, and prepare training materials aligned with GAO compliance expectations.
- **Pilot & Feedback Loop:** Run a controlled pilot with advisory teams, gather feedback, adjust scoring weights, and finalize rollout plan.

---

### Immediate Next Actions
1. Finalize template modularization design (entity backbone, GAO appendix, scenario cores) and wire into the draft criminal-law workflows.
2. Implement Phase 1 schema refinements surfaced during stakeholder sign-off, including documentation of audit field ownership and versioning cadence.
3. Begin pruning legacy workflow definitions/templates to streamline the repository ahead of Phase 2 migration work.
