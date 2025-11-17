# Modern Governance Extraction Sprint

## Sprint Overview
- **Duration**: 2025-11-18 → 2025-12-02 (10 working days)
- **Primary Goal**: Generalize parsing and extraction pipelines from historical treatises to contemporary state and county governance documents.
- **Success Criteria**: Multi-format corpus parsed with high fidelity, extractor outputs validated on at least six modern governance sources, regression tests updated, and configuration patterns documented for reuse.
- **Constraints**: Maintain backward compatibility with existing Machiavelli fixtures; no schema changes for downstream KB consumers.
- **Dependencies**: Parsing config (`config/kb-processing.yaml`), extraction config (`config/extraction.yaml`), CLI entry (`python -m main`).

## Initial Corpus Candidates
| Tier | Document | Format | Source URL (Suggested) |
| --- | --- | --- | --- |
| State Constitution | Colorado Constitution (2024 update) | PDF | https://leg.colorado.gov/content/constitution-state-colorado |
| State Administrative Code | Texas Administrative Code, Title 1 (Part 1) | HTML | https://texreg.sos.state.tx.us/public/readtac$ext.viewtac |
| County Charter | Miami-Dade Home Rule Charter | PDF | https://www.miamidade.gov/charter/home-rule-charter.asp |
| County Ordinance Compilation | King County Code, Title 2 (Administration) | HTML | https://kingcounty.gov/council/legislation/kc_code |
| Budget Executive Summary | Los Angeles County FY25 Budget Book – Executive Summary | PDF | https://ceo.lacounty.gov/budget/ |
| Intergovernmental Agreement | Denver Regional Council of Governments – Transportation Planning Agreement | PDF | https://drcog.org |

> Replace links with definitive downloads during intake and log any access constraints in the progress log.

## Scope
- **In Scope**: Multi-format parsing (PDF/HTML/DOCX), extractor retuning, taxonomy expansion, metadata normalization across civic documents, regression test authoring.
- **Out of Scope**: Mission runner automation, downstream dashboard changes, internationalization.

## Workstreams & Tasks
### Workstream A – Corpus & Parsing Foundations
- [x] Finalize document list. `prince01mach_1.pdf`, `Agriculture, Water & Natural Resources.htm`, `application_of_the_colorado_common_interest_ownership_act_ccioa_in_hoa_communities_-_colorado_law_summary.pdf`, `fy25-26apprept.pdf`
- [x] Enhance `config/kb-processing.yaml` with format-specific overrides (e.g., HTML selectors, PDF OCR flags).
- [x] Run `python -m main parse --output-root evidence/parsed …` for each source; capture parse logs and warnings in `devops/projects/governance-extraction-progress.md`.
- [x] Annotate `evidence/parsed/README.md` with artifact metadata (format, checksum, section count).

### Workstream B – Segmentation & Structure Generalization
- [x] Update segmentation heuristics to recognize decimal and alphanumeric section markers (`Sec. 1.01`, `Article II`, `§ 2-104`).
- [x] Verify heading extraction on HTML tables of contents and multi-level statutes. *(prince01mach_1 PDF ToC validated; duplicate `CONTENTS`/`PREFACE` headings logged for cleanup backlog)*
- [x] Create fixtures under `tests/extraction/fixtures/governance/` for representative segments.
- [x] Document outstanding structural anomalies (e.g., nested numbering resets) in progress log.

### Workstream C – Entities, Relationships, Taxonomy Expansion
- [x] Extend known locations/demonyms to cover U.S. states, counties, agencies; externalize maps where possible.
- [x] Add relationship keywords for oversight, funding, delegation, emergency powers.
- [x] Introduce taxonomy labels for municipal services, fiscal governance, intergovernmental coordination.
- [x] Run `python -m main extract-benchmark …` across the new corpus and compare metrics versus historical baseline.

### Workstream D – Metadata, Summaries, Linking Adaptation
- [ ] Curate metadata subjects/keywords for civic documents (e.g., “state government”, “county charter”).
- [ ] Enhance auto-summary templates to optionally inject structure insights and highlight fiscal or statutory takeaways.
- [ ] Configure glossary-driven linking maps for modern agencies and statutes; validate outbound references.
- [ ] Update QA reports under `reports/quality-*.md` with side-by-side snapshots.

### Workstream E – Quality Assurance & Regression Harness
- [x] Establish governance-specific regression tests (entities, relationships, metadata, summarization) mirroring existing Machiavelli suites. *(See progress log entry 2025-11-15T03:58Z – fixtures and pytest harness in place.)*
- [x] Track benchmark latencies per document type; flag >20% regressions. *(Profiles `governance-default`/`governance-full` now captured in benchmark YAMLs.)*
- [x] Capture outstanding issues/backlog items in `devops/projects/governance-extraction-progress.md` for hand-off. *(Backlog items logged through 2025-11-15T04:26Z entry.)*
- [x] Prepare enablement notes summarizing configuration deltas for future missions. *(Enablement notes appended beneath Workstream E log section.)*

## Milestones & Cadence
| Date | Milestone | Owner | Notes |
| --- | --- | --- | --- |
| 2025-11-18 | Corpus intake complete | Parsing lead | All source files downloaded and logged |
| 2025-11-22 | Parsing & structure baseline | Segmentation owner | Artifacts signed off for downstream use |
| 2025-11-27 | Extractor retuning complete | Module owners | Entities/relationships/taxonomy validated |
| 2025-12-02 | QA review & retro | Whole team | Tests passing, documentation updated |

- **Daily stand-up**: 10:00 local, 15-minute checkpoint.
- **Async updates**: Post blockers/findings in the governance sprint channel with links to progress log entries.

## Testing & Validation Plan
- Record every parse/extraction run (command, timestamp, outcome) in `reports/quality-*.md`.
- Store raw extractor outputs under `evidence/parsed/<document_slug>/outputs/`.
- Prefer YAML outputs for manual QA; JSON for regression fixtures.
- Maintain benchmark history comparing Machiavelli and governance corpora to detect drift.

## Review & Sign-off Process
- Parsing reviewer certifies corpus fidelity before extractor work proceeds.
- Each extractor owner provides before/after snippets highlighting improvements.
- QA reviewer verifies new regression tests gate the identified fixes.
- Sprint conclusion: demo modern-document pipeline, list remaining gaps, and propose follow-on backlog.

## Risks & Mitigations
- **Document diversity** → Mitigate by selecting multiple formats and numbering schemes; adjust heuristics iteratively.
- **Extractor drift impacting historical corpus** → Run dual regression suites (historical + modern) before merging changes.
- **Glossary maintenance burden** → Store agency/location maps in reusable YAML to simplify future updates.
- **Benchmark regressions** → Capture per-document latency and revert tuning that causes >20% slowdown without quality gain.

## Backlog for Future Sprints
- Automate source ingestion from open-data portals.
- Add support for real-time ordinance updates via mission runner.
- Expand taxonomy to cover public health and emergency management domains.
- Explore lightweight machine-learning classifiers for entity disambiguation once heuristic coverage plateaus.
