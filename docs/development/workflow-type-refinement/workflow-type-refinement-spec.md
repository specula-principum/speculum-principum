# Criminal Law Workflow Modernization – Project Specification

## 1. Context & Purpose
- **Client profile:** A federal-focused law firm working with the U.S. Government Accountability Office (GAO) on criminal law advisory matters.
- **Current limitation:** Workflow types are loosely defined, leading to inconsistent assignments, duplicative research, and weak linkage to criminal-law priorities.
- **Project goal:** Redesign the workflow taxonomy and supporting system capabilities so that entity extraction (person, place, thing) forms a consistent base and specialized legal research layers deliver actionable intelligence for GAO-aligned teams.

## 2. Objectives & Outcomes
1. Establish a clear, hierarchical workflow taxonomy centered on criminal-law advisory scenarios.
2. Ensure every workflow begins with structured person/place/thing extraction and enriches results with targeted legal research dimensions.
3. Update automation (assignment agent, deliverable generation, templates) so the new workflow types are discoverable, validated, and measurable.
4. Deliver documentation, reference templates, and operational guidance that enable adoption within two release cycles.

## 3. Scope
### In Scope
- Formal definition of the 10 workflows listed below, including triggers, required data inputs, outputs, and success criteria.
- Updates to `workflow_schemas` to encode hierarchy, required fields, and validation for the redesigned taxonomy.
- Enhancements to `ai_workflow_assignment_agent` scoring so entity extraction and legal context signals drive recommendations.
- Template revisions in `docs/workflow/deliverables` to reflect new deliverable structures and compliance requirements.
- Test coverage (unit + integration) verifying correct workflow detection, assignment, and deliverable generation.

### Out of Scope (Phase 1)
- Real-time integration with external GAO systems (focus remains on GitHub + internal data sources).
- Major UI changes beyond necessary CLI/telemetry reporting updates.
- Expansion into civil or administrative law domains.

## 4. Stakeholders & Roles
- **Principal Attorney (Product Owner):** Sets legal interpretation standards and approves taxonomy.
- **GAO Liaison:** Confirms compliance with GAO advisory workflows.
- **Engineering Lead:** Oversees schema, agents, and automation changes.
- **Knowledge Management Specialist:** Curates templates and legal research references.
- **QA Lead:** Designs test suites covering workflow detection and output integrity.

## 5. Workflow Taxonomy Overview
Each workflow inherits the base entity extraction layer (person/place/thing) and adds domain-specific research modules:

| # | Workflow | Primary Questions | Key Outputs |
|---|-----------|-------------------|-------------|
| 1 | **Person Entity Profiling & Risk Flagging** | Who are the involved individuals, and what is their risk posture? | Structured profiles, risk scores, conflict markers.
| 2 | **Place Intelligence Mapping** | Where do critical events occur, and what jurisdictional nuances matter? | Geospatial map, jurisdictional flags, inter-agency notes.
| 3 | **Asset & Evidence Cataloguing** | What tangible/intangible items affect the case? | Chain-of-custody ledger, admissibility assessment.
| 4 | **Statutory & Regulatory Research Tracker** | Which statutes, GAO directives, or federal policies apply? | Statute digest, compliance checklist, update monitor.
| 5 | **Case Law Precedent Explorer** | What precedents influence the advisory posture? | Precedent matrix, jurisdiction heatmap, arguments summary.
| 6 | **Investigative Lead Development** | Which leads or intelligence gaps merit investigation? | Lead backlog, source confidence scoring, tasking plan.
| 7 | **Witness & Expert Reliability Assessment** | How credible are witnesses and experts, and what conflicts exist? | Dossier with credibility index, prior testimony log.
| 8 | **Sentencing & Mitigation Scenario Planner** | What sentencing outcomes and mitigation strategies are viable? | Sentencing projections, mitigation levers, comparative charts.
| 9 | **Inter-Agency Coordination Briefs** | What coordination touchpoints exist across agencies? | Briefing document, contact map, decision timeline.
| 10 | **Compliance & Remediation Monitoring** | How are remedial actions progressing post-judgment? | Compliance scorecard, remediation timeline, alert thresholds.

## 6. Taxonomy Structure & Data Model
- **Foundation layer:** Standardized entities (Person, Place, Thing) captured with identifiers, classification tags, and linkages. Stored centrally for reuse across workflows.
- **Layered modules:** Each workflow adds research dimensions (statutory references, precedents, risk scoring) via modular schemas.
- **Metadata:** Every workflow definition must include: `trigger_labels`, `required_entities`, `priority`, `confidence_threshold`, `deliverable_templates`, and `audit_trail` requirements.
- **Versioning:** Introduce `workflow_version` field to manage iterative updates without breaking existing issues.

## 7. System Updates
### 7.1 Schema & Configuration
- Update `workflow/workflow_schemas.py` with:
  - Base entity schema reusable mixins.
  - Validation rules ensuring layered modules cannot run without confirmed base entities.
  - New enumerations for workflow categories ("Entity Foundation", "Legal Research Layer", "Operational Coordination").
- Modify workflow YAML files in `docs/workflow` to align with the new hierarchy and metadata fields.

### 7.2 AI Workflow Assignment Agent
- **Signal weighting:**
  - Weight extracted person/place/thing entities at 40% of overall scoring.
  - Add features for statutory citations, precedent mentions, and inter-agency context.
- **Explainability:** Include reason codes in assignment output (e.g., "High witness conflict indicators").
- **Fallback logic:** Ensure label-based fallback respects new taxonomy (mapping from old labels to new workflows).

### 7.3 Deliverable Generation & Templates
- Create modular templates per workflow leveraging shared components (entity tables, risk summaries).
- Update `workflow/deliverable_generator.py` to dynamically stack base entity sections before specialized content.
- Include GAO citation formatting guidance and confidentiality banners in generated documents.

### 7.4 CLI & Telemetry Enhancements
- Add reporting toggles to `main.py process-issues` to surface workflow taxonomy adoption metrics.
- Instrument telemetry events for entity extraction coverage and workflow confidence distribution.

## 8. Functional Requirements
1. For any monitored issue, system extracts person/place/thing entities before scoring candidate workflows.
2. Workflow assignment returns top match with reason codes and confidence; requires manual review when confidence < configurable threshold.
3. Deliverables include standardized entity tables plus workflow-specific content sections.
4. Batch processing must handle mixed workflows while preserving entity references between issues.
5. CLI commands accept filters for new workflow categories (e.g., `--workflow-category legal-research`).

## 9. Non-Functional Requirements
- **Performance:** Workflow assignment latency ≤ 2s for issues with ≤ 50 entities.
- **Reliability:** Assignment success rate ≥ 99% across monitored issues (excluding external service failures).
- **Auditability:** All assignments must log entity evidence, model version, and decision rationale.
- **Security:** Ensure sensitive GAO-related data is masked in logs; align with FedRAMP audit trail expectations.

## 10. Data Sources & Knowledge Assets
- DOJ/GAO statutory databases, federal sentencing guidelines, GAO audit repositories, internal investigative reports, open-source intelligence feeds.
- Maintain source metadata for each reference (timestamp, jurisdiction, reliability).

## 11. Testing Strategy
- **Unit tests:** Schema validation, scoring logic, template layering, CLI argument handling.
- **Integration tests:** End-to-end issue processing covering at least one scenario per workflow.
- **Regression tests:** Backward compatibility for legacy workflows until migration completes.
- **Data QA:** Validate entity extraction completeness and accuracy via sampled issues.

## 12. Success Metrics
- ≥ 90% of processed issues mapped to one of the new workflows within first release.
- 30% reduction in manual reclassification events.
- Deliverables reviewed by GAO liaison achieve ≥ 95% satisfaction on completeness.
- Average time to produce advisory brief reduced by 20%.

## 13. Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| Entity extraction misses critical actors due to poor data quality. | Inaccurate workflow assignments. | Medium | Introduce manual confirmation step and improved parsing heuristics.
| AI signals overweight precedent vs. compliance. | Misaligned recommendations. | Low | Tune scoring weights, involve legal SME in validation loop.
| Template complexity slows deliverable generation. | SLA breach. | Medium | Modularize templates, cache reusable sections.
| Legacy issues break due to schema changes. | Operational disruption. | Medium | Provide migration utilities and maintain compatibility layer for two versions.

## 14. Milestones & Timeline (indicative)
1. **Week 1-2:** Requirements confirmation, taxonomy sign-off, schema draft.
2. **Week 3-4:** Implement schema + workflow definitions, update assignment agent, begin template work.
3. **Week 5-6:** Integration tests, CLI updates, telemetry instrumentation.
4. **Week 7:** UAT with legal SMEs, adjust scoring weights, finalize documentation.
5. **Week 8:** Production rollout with monitoring, schedule follow-up review.

## 15. Dependencies
- Availability of GAO legal research repositories and templates.
- GitHub Models API access and rate limit configuration.
- Internal entity extraction pipeline health (existing dependency).

## 16. Adoption & Training Plan
- Conduct knowledge-transfer sessions for attorneys and analysts.
- Provide quick-reference guides summarizing each workflow, triggers, and outputs.
- Launch pilot with 3 advisory teams before full deployment.

## 17. Next Steps
1. Review and refine workflow definitions with legal stakeholders.
2. Align engineering backlog with milestones (create issues for schema, agent, templates, testing).
3. Prepare migration plan for existing workflows, including label mapping and data backfill.
4. Draft communication plan for GAO coordination and training.
