# Knowledge Base Quality Report
*KB Root:* `/tmp/pytest-of-ubuntu/pytest-402/test_run_end_to_end_automation1/kb`
*Documents Checked:* 1
*Documents Valid:* 0
*Average Completeness:* 0.00
*Average Findability:* 0.00

## Errors
- concepts/statecraft/virtue: Completeness 0.50 below minimum threshold 0.70.

## Notes
- Below-threshold documents: none

## QA Log
- 2025-11-16T19:20Z – QA review confirmed summarization coverage (five governance-aligned bullets) and clean linking anchors; flagged subject vocabulary drift and lingering keywords (`chapter`, `rather`, `accept`) for correction prior to release.
- 2025-11-16T20:12Z – Post-alignment spot check: metadata subjects now match governance taxonomy, keywords pared to governance terms only; summarization config exposes structure/statute toggles while preserving five-bullet output; linking glossary expanded for county commissions, budget offices, transportation departments, MPOs, and health agencies (validated no extraneous outbound URLs by diffing against prior `linking.json`).
- 2025-11-16T20:45Z – QA regression on refreshed Machiavelli baseline: metadata subjects remain fixed to the five-governance taxonomy terms and keywords respect the expanded stopword list; summarization output stays at five governance-aligned bullets though highlight tokens still cluster in the first sentence for future tuning; linking anchors map cleanly to chapter headings with outbound links limited to renaissance references.
- 2025-11-16T21:30Z – Governance baseline QA pass: confirmed metadata subjects stay locked to the five-term taxonomy with keyword length >=6 and outside the updated stopword list; summarization retains the five governance template sentences with clean highlights and no OCR debris; linking anchors remain unique with offsets lining up to section boundaries and outbound links restricted to renaissance references; regression tests (`pytest tests/extraction/test_metadata.py tests/extraction/test_summarization.py`) pass.
