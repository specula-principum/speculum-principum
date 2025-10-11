# Criminal Law Workflow Taxonomy Draft

_Last updated: 2025-10-06_

This draft captures the proposed hierarchical taxonomy for the ten criminal-law advisory workflows. It introduces shared foundations (entity extraction), layered legal research modules, and operational coordination dimensions specific to GAO-aligned engagements.

---

## 1. Hierarchical Structure
- **Layer 0 – Entity Foundation:** Mandatory parsing and validation of `Person`, `Place`, and `Thing` entities. Each entity must include identifiers, role classification, jurisdiction, and confidence rating.
- **Layer 1 – Legal Research Modules:** Scenario-specific legal analysis components (statutory lookups, precedent aggregation, sentencing matrices, etc.).
- **Layer 2 – Operational Coordination Modules:** Briefings, inter-agency guidance, remediation monitoring, and audit logging tailored to GAO collaboration.

Each workflow references the base layer and one or more Layer 1/Layer 2 modules. Validation ensures base entities are present before downstream processing.

### Global Metadata
All workflows must define the following metadata keys:
| Field | Description |
| --- | --- |
| `workflow_version` | Semantic version of the workflow definition. |
| `category` | One of `entity-foundation`, `legal-research`, `operational-coordination`. |
| `priority` | Relative urgency (`low`, `medium`, `high`, `critical`). |
| `confidence_threshold` | Minimum score required for auto-assignment. |
| `required_entities` | List of entity types (`person`, `place`, `asset`, `evidence`, etc.) and the minimum confidence per entity. |
| `audit_trail.required` | Boolean indicating whether detailed logging is required. |
| `audit_trail.fields` | Keys that must be captured (model version, entity evidence, citations, reviewers). |
| `deliverable_templates` | Ordered list of template IDs stacked after the base entity section. |

---

## 2. Workflow Definitions
The table below summarizes trigger criteria, required entities, legal research modules, and key outputs for each workflow. Detailed schema objects will be captured in the YAML rewrite during Phase 2.

| # | Workflow | Category | Trigger Signals | Required Entities | Layered Modules | Key Deliverables | Success Criteria |
|---|----------|----------|-----------------|-------------------|-----------------|------------------|------------------|
| 1 | **Person Entity Profiling & Risk Flagging** | entity-foundation | Labels: `person-profile`, `risk-flag`; Content: references to individuals, aliases, criminal history | `person` (>= 0.7 confidence); optional `organization` links | Risk scoring, conflict checks, sanctions lookups | Entity dossier, risk matrix, conflict summary | All persons classified, risk score assigned, conflicts catalogued with citations. |
| 2 | **Place Intelligence Mapping** | legal-research | Labels: `jurisdiction`, `venue-analysis`; Content: locations, courts, districts | `place` (>= 0.65); optional `event` | Jurisdictional rules, venue precedence, inter-agency response map | Geospatial brief, jurisdiction flags, inter-agency notes | Primary venue confirmed, jurisdictional nuances documented, map generated. |
| 3 | **Asset & Evidence Cataloguing** | entity-foundation | Labels: `evidence`, `asset-trace`; Content: exhibits, chain-of-custody terms | `thing` (>= 0.7), `evidence` subtype; optional `person` custodians | Chain-of-custody ledger, admissibility checks | Evidence ledger, admissibility assessment, custody gaps | All items tagged with custody trail, admissibility risk scored. |
| 4 | **Statutory & Regulatory Research Tracker** | legal-research | Labels: `statute-review`, `gao-directive`; metadata references to CFR, USC, GAO reports | `person` or `organization` (context holder) | Statute digest, GAO directive matcher, compliance checklist | Statute digest, compliance checklist, update monitor | Applicable statutes identified, compliance tasks queued, update cadence set. |
| 5 | **Case Law Precedent Explorer** | legal-research | Labels: `precedent`, `case-law`; references to court cases or citations | `person` (roles), `place` (jurisdiction) | Precedent matrix, jurisdiction heatmap, argument builder | Precedent matrix, heatmap, argument summary | Relevant precedents prioritized with jurisdiction fit and argument notes. |
| 6 | **Investigative Lead Development** | operational-coordination | Labels: `lead-development`, `intel-gap`; Content indicates missing intel | `person` or `organization`, `lead` placeholders | Lead backlog management, source confidence scoring, tasking planner | Lead backlog, confidence scoring table, tasking plan | Leads categorized, gaps highlighted, follow-up tasks scheduled. |
| 7 | **Witness & Expert Reliability Assessment** | legal-research | Labels: `witness`, `expert`; references to testimony, credibility | `person` (role = witness/expert) | Credibility scoring, prior testimony lookup, conflict analysis | Witness dossier, credibility index, conflict log | Each witness/expert scored with supporting evidence and conflict status. |
| 8 | **Sentencing & Mitigation Scenario Planner** | legal-research | Labels: `sentencing`, `mitigation`; references to guidelines, mitigation | `person` (defendant), `case` references | Sentencing guideline calculator, mitigation lever analysis, scenario modeling | Sentencing projections, mitigation levers chart, comparative scenarios | Sentencing ranges charted; proposed mitigation steps tied to precedents/statutes. |
| 9 | **Inter-Agency Coordination Briefs** | operational-coordination | Labels: `coordination`, `gao-brief`; content citing agencies | `organization`, `person` (liaison/POC) | Agency contact mapping, decision timeline builder, briefing generator | Briefing memo, contact map, decision timeline | Key agencies mapped, next steps scheduled, GAO liaison brief produced. |
| 10 | **Compliance & Remediation Monitoring** | operational-coordination | Labels: `compliance`, `remediation`; references to post-judgment actions | `organization`, `person` (compliance officer), `plan` entities | Compliance scorecard, remediation timeline, alerting thresholds | Compliance scorecard, remediation timeline, alert thresholds | Compliance metrics tracked over time, alerts configured, remediation milestones recorded. |

### Entity Foundation Module Specification
| Attribute | Description |
| --- | --- |
| `entity_type` | `person`, `place`, `thing`, `organization`, `case`, `plan`, etc. |
| `identifier` | Structured ID (e.g., SSN hash, docket number, GAO reference) with confidentiality level. |
| `role` | Contextual role (`defendant`, `witness`, `agency`, `evidence`, etc.). |
| `jurisdiction` | Applicable jurisdiction metadata for persons/places/cases. |
| `confidence` | Float 0–1 representing extraction certainty; must exceed workflow-specific threshold. |
| `relationships` | Links between entities with type (`involved_with`, `custodian_of`, `located_in`). |

---

## 3. Scoring & Assignment Signals
To align AI assignment with the taxonomy, introduce weighted signals:
- **Entity Coverage (40%)**: Proportion of required entities extracted with confidence above threshold.
- **Legal Citations (20%)**: Presence of statutory references (`18 U.S.C.`, GAO directives), case citations, or guideline numbers.
- **Contextual Keywords (20%)**: Scenario keywords (e.g., "sentencing guideline", "chain of custody", "mitigation").
- **Inter-Agency Indicators (10%)**: Mentions of GAO, DOJ, FBI, or coordination verbs.
- **Historical Outcomes (10%)**: Past successful assignments for similar issues.

**Reason Codes** (examples to expose via AI agent output):
- `entity-gap` – missing required entity or confidence below threshold.
- `statute-match` – strong statutory citation alignment.
- `precedent-match` – high overlap with precedent keywords. 
- `mitigation-focus` – mitigation terminology detected. 
- `coordination-required` – inter-agency language present.

---

## 4. Deliverable Template Stack
Every workflow will produce deliverables in the following order:
1. **Entity Backbone:** Shared template containing entity tables, relationship graph, confidentiality banner.
2. **Workflow Core Section:** Scenario-specific template referenced in `deliverable_templates`.
3. **GAO Compliance Appendix:** Citations, decision logs, audit metadata.

Deliverable metadata will reference reusable blocks:
- `entity_table_component`
- `gao_citation_block`
- `confidentiality_banner`
- `audit_log appendix`

---

## 5. Validation & Audit Requirements
- **Schema Enforcement:** `workflow_schemas.py` must ensure `required_entities` list is non-empty and each entry specifies `entity_type`, `min_count`, `min_confidence`.
- **Audit Logging:** Workflows with `audit_trail.required = true` must write model version, reason codes, and entity evidence to telemetry.
- **Legacy Compatibility:** During migration, maintain ability to load legacy workflows via `legacy_mode` flag until all issues transition.

---

## 6. Next Steps
1. Translate this taxonomy into updated YAML schema definitions (Phase 1/2).
2. Draft per-workflow YAML templates incorporating metadata, triggers, and deliverable stacks.
3. Update AI assignment logic to emit reason codes and leverage the scoring weights above.
4. Socialize taxonomy with legal stakeholders for approval before implementation.
