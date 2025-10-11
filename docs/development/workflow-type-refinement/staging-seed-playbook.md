# Taxonomy Staging Seed Playbook

This playbook describes the staging issues, labels, and body content needed for the internal rollout pilot.

## Repository Setup
- Target repository: `owner/taxonomy-staging`
- Required labels:
  - `site-monitor`
  - Criminal-law triggers (one per workflow): `evidence`, `precedent`, `compliance`, `coordination`, `lead-development`, `person-profile`, `jurisdiction`, `sentencing`, `statute-review`, `witness`
  - QA helpers: `qa-pilot`, `fallback-test`

## Baseline Issues (10)
Create ten open issues, each tagged with `site-monitor`, `qa-pilot`, and the workflow trigger label from the list above. Suggested titles and highlights:

| # | Workflow | Title | Highlights |
| --- | --- | --- | --- |
| 1 | Asset & Evidence Cataloguing | "Cataloguing seized digital ledger" | Mention custody chain, warrant details |
| 2 | Case Law Precedent Explorer | "Precedent review for NDCA cyber case" | Include citation placeholders |
| 3 | Compliance & Remediation Monitoring | "Compliance remediation tracker" | Note remediation milestones |
| 4 | Inter-Agency Coordination Briefs | "Coordination brief: GAO liaison" | Outline agencies involved |
| 5 | Investigative Lead Development | "Lead backlog: international wires" | List leads and confidence |
| 6 | Person Entity Profiling & Risk Flagging | "Risk profile: key defendants" | Summaries per person |
| 7 | Place Intelligence Mapping | "Venue intelligence: Metro Hall" | Venue notes and events |
| 8 | Sentencing & Mitigation Scenario Planner | "Sentencing scenarios planning" | Baseline vs mitigation |
| 9 | Statutory & Regulatory Research Tracker | "Statute digest for financial regs" | Include directive reference |
| 10 | Witness & Expert Reliability Assessment | "Witness reliability review" | Credibility cues |

Use the structured entity snippets from `tests/integration/test_criminal_law_matrix.py` for inspiration—ensure each body contains:
- Markdown headings (`## Discovery`, `## AI Assessment`)
- Bullet lists with entity or evidence details
- At least one citation reference placeholder (e.g., `18 U.S.C. § 1956`)

## Edge Cases
- **Fallback ambiguity**: Create two issues with overlapping labels (`precedent`, `compliance`, `coordination`) plus `fallback-test` to validate clarification paths.
- **Missing base entities**: One issue intentionally omits person/place references to verify warning surfaces.

## Maintenance
- Refresh issues weekly to avoid stale timestamps.
- Archive generated artifacts in `artifacts/staging/<date>` (automated via `run_taxonomy_staging.sh`).
- Track QA feedback per issue in shared tracker (link TBD).
