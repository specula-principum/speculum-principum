# Current Workflow Inventory & Baseline Assessment

_Last updated: 2025-10-10_

This inventory captures the as-is state of workflow definitions, schema validation, assignment logic, and operational tooling prior to the Criminal Law Workflow Modernization effort. It will serve as the reference baseline for gap analysis and migration planning.

## 1. Workflow Definitions (Active Inventory)
All legacy pre-taxonomy definitions were removed on 2025-10-10. The active inventory now consists exclusively of taxonomy-compliant criminal-law workflows under `docs/workflow/deliverables/criminal-law/`.

| File | Workflow Name | Category | Focus |
| --- | --- | --- | --- |
| `docs/workflow/deliverables/criminal-law/asset-evidence-cataloguing.yaml` | Asset & Evidence Cataloguing | entity-foundation | Evidence ledger, chain-of-custody continuity, admissibility posture |
| `docs/workflow/deliverables/criminal-law/case-law-precedent-explorer.yaml` | Case Law Precedent Explorer | legal-research | Jurisdictional fit, precedent synthesis, argument summaries |
| `docs/workflow/deliverables/criminal-law/compliance-remediation-monitoring.yaml` | Compliance & Remediation Monitoring | operational-coordination | Remediation milestones, compliance alerts, escalation triggers |
| `docs/workflow/deliverables/criminal-law/inter-agency-coordination-briefs.yaml` | Inter-Agency Coordination Briefs | operational-coordination | Contact hierarchies, coordination plans, decision timelines |
| `docs/workflow/deliverables/criminal-law/investigative-lead-development.yaml` | Investigative Lead Development | operational-coordination | Lead ranking, confidence scoring, follow-up tasking |
| `docs/workflow/deliverables/criminal-law/person-entity-profiling.yaml` | Person Entity Profiling & Risk Flagging | entity-foundation | Person dossiers, risk posture scoring, sanctions/conflict checks |
| `docs/workflow/deliverables/criminal-law/place-intelligence-mapping.yaml` | Place Intelligence Mapping | legal-research | Venue analysis, jurisdictional nuances, location risk profiling |
| `docs/workflow/deliverables/criminal-law/sentencing-mitigation-scenario-planner.yaml` | Sentencing & Mitigation Scenario Planner | legal-research | Sentencing models, mitigation levers, comparative scenarios |
| `docs/workflow/deliverables/criminal-law/statutory-regulatory-research-tracker.yaml` | Statutory & Regulatory Research Tracker | legal-research | Statutory aggregation, GAO directive tracking, compliance checkpoints |
| `docs/workflow/deliverables/criminal-law/witness-expert-reliability-assessment.yaml` | Witness & Expert Reliability Assessment | legal-research | Credibility scoring, conflict detection, testimony history |

**Key takeaways**
- Active workflows now align with criminal-law advisory scenarios and embed taxonomy metadata, audit requirements, and confidence thresholds.
- Every workflow shares the modular GAO template stack (`entity_backbone`, core deliverable, compliance appendix) to enforce consistent output structure.
- Follow-up work focuses on instrumentation (metrics, dashboards) and schema evolution rather than workflow conversion.

> _Sections 2–8 retain the initial baseline analysis for historical context and will be revised once post-removal validation completes._

## 2. Schema & Validation Baseline
_Source: `src/workflow/workflow_schemas.py`_
- Current schema requires only `name`, `trigger_labels`, and `deliverables` plus optional `description`, `version`, `processing`, `validation`, `output` fields.
- No concept of hierarchical categories, `required_entities`, `priority`, `confidence_threshold`, or `workflow_version` metadata.
- Validation checks limited to duplicate deliverable names/orders and exclusion of `site-monitor` label.
- Missing mixins for entity foundation or layered modules; workflows can pass validation without defining entity requirements.

**Implications:** We’ll need a schema refactor introducing reusable base entity blocks, taxonomy categories, versioning, and audit metadata while preserving legacy validation until migration completes.

## 3. Assignment & Matching Baseline
_Source: `src/agents/ai_workflow_assignment_agent.py`, `src/workflow/workflow_matcher.py`_
- AI agent currently compiles workflow descriptions (name, trigger labels, first three deliverables) for prompt context. No knowledge of entity extraction coverage.
- Scoring relies on GitHub Models output; weighting between entities, statutes, or inter-agency indicators is not implemented.
- Explainability limited to summary/topics; no explicit reason codes or entity evidence logging.
- Fallback matcher uses label heuristics against existing workflow definitions; lacks mapping for future criminal-law taxonomy.

**Implications:** Upgrades must introduce entity-derived features, legal citation detection, and reason-code emission while maintaining backward compatibility during rollout.

## 4. Deliverable Templates & Assets
- Templates referenced in workflows reside under `docs/workflow/deliverables` (e.g., `intelligence_assessment.md`, `technical_overview.md`) but emphasize intelligence/technical content.
- No shared components for entity tables, GAO citation formatting, or confidentiality banners.
- Output metadata typically sets folder/file patterns without legal-compliance structures or audit-trail requirements.

**Implications:** We’ll create modular base templates for entity extraction results and layer criminal-law specific sections per workflow.

## 5. CLI & Telemetry Baseline
_Source: `main.py`, `src/utils/cli_helpers.py`, telemetry utilities_
- `process-issues` command lacks filters for workflow categories or taxonomy adoption metrics; telemetry focuses on assignment outcomes without entity coverage stats.
- No CLI surfacing of confidence distributions or manual review thresholds.
- Existing telemetry publishers capture summaries but not detailed legal/audit context required by GAO stakeholders.

**Implications:** Add CLI flags (e.g., `--workflow-category`, `--show-taxonomy-metrics`) and instrument telemetry for entity coverage, confidence, and audit logs.

## 6. Gap Summary vs. Target State
| Target Requirement | Current State Gap |
| --- | --- |
| Hierarchical taxonomy (Entity Foundation → Legal Research → Operational Coordination) | No taxonomy fields or categorization in YAML/schema. |
| Base entities mandatory before specialized layers | No schema checks or deliverable templates for entity extraction. |
| Criminal-law specific workflows (10 defined scenarios) | Existing workflows are intelligence/technical; none map to GAO advisory needs. |
| AI scoring weight (40% entity coverage) & legal signals | AI agent prompt lacks entity data and legal signal features. |
| Explainability via reason codes + audit trail | No reason code output; limited telemetry logging. |
| Deliverables with GAO formatting and confidentiality banners | Templates absent; current outputs lack legal compliance guidance. |
| CLI/telemetry support for taxonomy adoption metrics | CLI options and telemetry events do not track taxonomy metrics. |

## 7. Criminal Law Workflow Definitions (Draft)
- Authored ten GAO-aligned workflow definitions under `docs/workflow/deliverables/criminal-law/`, each embedding taxonomy metadata, entity prerequisites, and audit requirements.
- Added unit coverage in `tests/unit/workflow/test_criminal_law_workflow_definitions.py` to guarantee schema compliance and catalog completeness.
- Deliverable templates referenced are placeholders pending template modularization in Phase 4; migration guidance will address legacy label mapping.

## 8. Suggested Next Steps
1. **Stakeholder Validation:** Share this inventory with legal/GAO stakeholders to confirm gaps and prioritize migration sequencing.
2. **Schema Drafting:** Prototype new schema structures (base entity mixins, taxonomy enums, metadata) and plan compatibility strategy.
3. **Workflow Authoring Workshop:** Begin drafting criminal-law workflows using inventory lessons to avoid past inconsistencies.
4. **Assignment Feature Design:** Outline scoring inputs (entities, statutes, inter-agency cues) and reason-code taxonomy for AI agent updates.
5. **Template Modularization:** Identify reusable sections (entity tables, GAO citations) to accelerate deliverable redesign.
6. **Telemetry Requirements Doc:** Define event schema capturing entity evidence, model versioning, and manual review hooks for audit trails.
