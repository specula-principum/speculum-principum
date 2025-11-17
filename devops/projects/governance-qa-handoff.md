# Governance Extraction QA Hand-off

## Scope & Context
- Focus document: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md` (Machiavelli baseline tuned for governance pilot).
- Latest extractor runs (metadata, summarization, linking) executed with `config/extraction.yaml` on 2025-11-16.
- Objective: confirm governance-oriented metadata subjects, five-bullet summary template, and glossary-backed linking behave as expected without reintroducing noise.

## Key Artifacts
- Metadata: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/metadata.json`
- Summarization: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/summarization.json`
- Linking: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/linking.json`
- Config updates: `config/extraction.yaml`, `config/normalization_maps/us_governance_glossary.yaml`
- QA log entries: `reports/quality-7.md` (latest section dated 2025-11-16T19:20Z)
- Progress log: `devops/projects/kb-extraction-progress.md` (Workstream D entry 2025-11-16T19:30:00Z)

## What Changed
- Replaced metadata subjects with civic-governance framing while leaving title/description/rights intact.
- Added a fifth summary bullet to highlight document structure alongside governance themes.
- Introduced governance glossary to the linking reference map (dual source: renaissance + governance).

## Expected Outcomes
- Metadata subjects list governance topics (executive playbooks, municipal administration, fiscal stewardship, civil-military coordination, intergovernmental coordination).
- Summary bullet list contains five sentences covering governance stability, militia posture, calibrated clemency, fiscal policy, and structural overview.
- Linking outbound references still point to authoritative Renaissance entities (no new U.S. links yet); anchors remain aligned with `structure.json` offsets.

## QA Checklist
1. **Metadata Review**
   - Confirm subjects match governance taxonomy and no legacy historical-only subjects remain.
   - Verify keyword list still excludes stopwords >=6 characters; note residual token `before` (known issue).
2. **Summarization**
   - Ensure bullet count is five and matches configured sentences; highlights should emphasize governance lexicon.
   - Validate no raw OCR fragments leak into summary output.
3. **Linking**
   - Check anchors for duplication beyond known `CONTENTS`/`PREFACE` repeats (expected until markdown cleanup).
   - Confirm outbound links list remains limited to Wikipedia targets in `renaissance_statecraft_glossary.yaml`; ensure new governance glossary entries did not trigger false matches.
4. **Regression Commands**
   - Run: `/home/ubuntu/speculum-principum/.venv/bin/python -m pytest tests/extraction/test_metadata.py tests/extraction/test_summarization.py`
   - Optional spot-check: rerun extractors with commands listed above to confirm deterministic output.

## Known Gaps & Follow-ups
- Metadata keywords still include filler token `before`; next cycle should extend stopword list.
- Duplicate front-matter anchors (`CONTENTS`, `PREFACE`) persist due to OCR; backlog to normalize markdown headings.
- Governance glossary currently contains high-level references only; will expand once additional modern documents are processed.
- Templates/glossary not yet propagated to other governance sources (pending intake/Workstream D kickoff for those files).

## Contact Notes
- Current owner: automation agent (handoff complete; awaiting QA validation).
- For questions on glossary expansion or metadata stopwords, reference Workstream D entry in `devops/projects/kb-extraction-progress.md` (2025-11-16T19:30:00Z).
