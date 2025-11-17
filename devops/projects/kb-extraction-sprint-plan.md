# KB Extraction Sprint – prince01mach_1.pdf

## Sprint Overview
- **Duration**: 2025-11-12 → 2025-11-25 (10 working days)
- **Primary Goal**: Validate and refine the end-to-end knowledge-base extraction pipeline using `evidence/prince01mach_1.pdf` as the reference document.
- **Success Criteria**: Parsed Markdown artifact reviewed and approved, all major extractor outputs (segments, structure, entities, relationships, taxonomy, summarization) baseline-tested, remediation backlog logged, and refinement patches merged or queued.
- **Constraints**: Maintain existing extractor interfaces, no schema changes to downstream KB consumers.
- **Dependencies**: Parsing config (`config/kb-processing.yaml`), extraction config (`config/extraction.yaml`), CLI entry (`python -m main`).

## Scope
- **In Scope**: PDF parsing, extractor benchmarking, manual review of outputs, configuration tuning, documentation of findings, regression tests for improved modules.
- **Out of Scope**: Automation of approval workflows, changes to orchestrator agents, deployment automation.

## Workstreams & Tasks
### Workstream A – Parsing & Data Readiness
- [x] Verify parsing configuration covers PDFs and update `config/kb-processing.yaml` if gaps exist.
- [x] Parse source: `python -m main parsing --output-root evidence/parsed pdf evidence/prince01mach_1.pdf`.
- [x] Catalog generated artifact path in `evidence/parsed/README.md` (include checksum, page count, parser warnings).
- [x] Spot-check Markdown for layout fidelity (figures, headings, footnotes) and record issues in sprint notes.

### Workstream B – Segmentation & Structural Analysis
- [x] Run segment extractor on parsed artifact: `python -m main extraction extract segments --input <parsed_markdown>`.
- [x] Compare segment boundaries against original PDF sections; flag misaligned headers or paragraph merges.
- [x] Execute structure analyzer: `python -m main extraction extract structure --input <parsed_markdown>` and review hierarchy depth against Table of Contents.
- [x] File configuration or parser tweaks required to correct structural drift.

### Workstream C – Entities, Relationships, Taxonomy
- [x] Benchmark `entities`, `relationships`, and `taxonomy` extractors via `python -m main extraction extract-benchmark --input <parsed_markdown> entities relationships taxonomy` (3 iterations default).
- [x] Inspect JSON outputs for terminology coverage (characters, locations, political entities); capture false positives/negatives.
- [x] Adjust extractor prompts/config tuning in `config/extraction.yaml`, re-run, and document deltas (externalize normalization maps so domains can swap profiles without code edits).
- [x] Generate linking output (`linking` extractor) and validate graph consistency (no orphan nodes, consistent IDs).

### Workstream D – Summaries, Metadata, Quality Loop
- [x] Produce metadata (`python -m main extraction extract metadata ...`) and ensure citation info pulls from PDF front matter.
- [x] Run summarization module, review thematic accuracy, and iterate prompt/templates if drift detected.
- [x] Compile consolidated QA report summarizing issues, fixes, and outstanding risks (store under `reports/quality-*.md`).
- [x] Capture regression tests: add fixtures under `tests/extraction/fixtures/prince01mach_1/` and write PyTest cases covering fixed defects.

### Workstream E – Follow-On Quality Extensions
- [x] Normalize OCR artifacts that leak into metadata keywords and entities (e.g., convert `niccol0` to `niccolo`) via post-processing filters.
- [x] Design outbound linking heuristics so `linking` extractor emits references when the source lacks explicit URLs (consider structural anchors or curated glossaries).
- [x] Prototype automated summary template generation using taxonomy or structural analytics to reduce manual config maintenance.
- [x] Evaluate metadata keyword stopword lists for reuse across missions and upstream them into shared normalization maps.

## Milestones & Cadence
| Date | Milestone | Owner | Notes |
| --- | --- | --- | --- |
| 2025-11-12 | Kickoff sync & parsing readiness | Core extraction team | Confirm tooling access, assign reviewers |
| 2025-11-14 | Parsed artifact sign-off | Parsing lead | Markdown artifact approved for downstream tasks |
| 2025-11-18 | Extractor baseline complete | Module owners | Segment/structure/entity outputs reviewed |
| 2025-11-21 | Refinement patches merged | Dev owners | Config/code updates landed, tests passing |
| 2025-11-25 | Sprint review & retro | Whole team | Present QA report, finalize backlog |

- **Daily stand-up**: 10:00 local, 15-minute checkpoint.
- **Async updates**: Post blockers and findings in project channel, link to issue tracker entries.

## Testing & Validation Plan
- Maintain a shared checklist in `reports/quality-7.md` to log validation runs (command, timestamp, outcome).
- Store raw extractor outputs in `evidence/parsed/prince01mach_1/outputs/<extractor>.json` for reproducibility.
- Use `--output-format yaml` for human review, JSON for fixtures.
- Record benchmark statistics (mean/median latency) to monitor regressions.
- Track defects in GitHub issues labeled `kb-extraction`, referencing command output and config hash.

## Review & Sign-off Process
- Parsing lead signs off on Markdown fidelity before extractor work begins.
- Each extractor owner submits a short findings summary with before/after snippets.
- QA reviewer verifies regression tests cover addressed defects prior to merge.
- Sprint review demo: walk through final outputs, highlight remaining gaps, capture next sprint candidates.

## Risks & Mitigations
- **PDF parsing anomalies** → Mitigate by keeping original PDF alongside Markdown and using dual-review sign-off.
- **Extractor drift due to prompt changes** → Version prompts in config and pin revisions in sprint notes.
- **Latency regressions** → Benchmark after each refinement; rollback if >25% slowdown without accuracy gain.
- **Missing entities in historical texts** → Enrich evaluation set with manual annotations from domain expert for calibration.

## Backlog for Future Sprints
- Automate parse-to-extraction pipeline with mission runner.
- Expand fixture set with additional chapters or related PDFs.
- Integrate confidence scoring to auto-flag uncertain entities.
- Add visualization tooling for relationship graphs.
