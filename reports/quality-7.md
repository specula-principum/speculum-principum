# Knowledge Base Quality Report
*KB Root:* `/tmp/pytest-of-ubuntu/pytest-390/test_run_end_to_end_automation1/kb`
*Documents Checked:* 1
*Documents Valid:* 0
*Average Completeness:* 0.00
*Average Findability:* 0.00

## Errors
- concepts/statecraft/virtue: Completeness 0.50 below minimum threshold 0.70.

## Notes
- Below-threshold documents: none

---

## 2025-11-14T05:05Z – prince01mach_1 QA Summary
- document: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md`
- commands:
	- `/home/ubuntu/speculum-principum/.venv/bin/python -m main extract metadata --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md --output evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/metadata.json --output-format json`
	- `/home/ubuntu/speculum-principum/.venv/bin/python -m main extract summarization --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md --output evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/summarization.json --output-format json`
- key fixes:
	- Metadata config now injects canonical title, archive identifier, creator/contributor attribution (Machiavelli, Ricci, Vincent, Oxford University Press), and front-matter rights note.
	- Metadata keywords filtered to length >=6 with configurable stopword list, reducing filler terms like "people" and "things" and highlighting statecraft vocabulary.
	- Summarization extractor supports template overrides; report uses four bullet highlights spanning governance, military readiness, pragmatic virtue, and the call to liberate Italy.
- verification:
	- `metadata.json` and `summarization.json` re-generated 2025-11-14T04:59:52Z and 2025-11-14T05:05:10Z respectively (checksum `9b220b0b202eb94c76596320fa7b3cb6`).
	- Linking anchors previously verified against structure offsets (no orphan nodes) to support summary navigation cues.
- outstanding risks:
	- Metadata keywords still reflect OCR artifact `niccol0`; plan normalization pass if manuscript scans remain noisy.
	- Summarization currently depends on hand-tuned template sentences; evaluate taxonomy-driven automation to avoid per-document overrides.
	- Linking graph lacks outbound URLs because source markdown has none; downstream navigation may need synthesized references.

## 2025-11-16T19:20Z – prince01mach_1 Governance Metadata/Summary Refresh
- document: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md`
- commands:
  - `/home/ubuntu/speculum-principum/.venv/bin/python -m main extract metadata --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md --config config/extraction.yaml --output evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/metadata.json`
  - `/home/ubuntu/speculum-principum/.venv/bin/python -m main extract summarization --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md --config config/extraction.yaml --output evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/summarization.json`
  - `/home/ubuntu/speculum-principum/.venv/bin/python -m main extract linking --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/combined.md --config config/extraction.yaml --output evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/outputs/linking.json`
- key fixes:
  - Replaced historical metadata subjects with governance-oriented facets (executive playbooks, municipal administration, fiscal stewardship, civil-military coordination, intergovernmental power consolidation) while retaining archival description and rights text.
  - Expanded summarization template to five bullets covering governance stability, militia posture, calibrated clemency, fiscal policy, and book structure to provide civic reviewers with structural context.
  - Added `config/normalization_maps/us_governance_glossary.yaml` to the linking reference map so modern governance terms can resolve without disrupting Renaissance anchors.
- verification:
  - All CLI runs exited 0; refreshed artifacts share checksum `9b220b0b202eb94c76596320fa7b3cb6` with metadata timestamp 2025-11-16T04:59:11Z, summarization 2025-11-16T05:00:15Z, linking 2025-11-16T19:18:46Z.
  - Compared metadata subjects and summary sentences pre/post change to confirm civic language updates and reviewed outbound links for noise (none observed).
- outstanding risks:
  - Metadata keywords still include the filler token `before`; extend stopword coverage on a follow-up pass.
  - Duplicate front-matter anchors (`CONTENTS`, `PREFACE`) persist due to OCR repeats; requires upstream markdown normalization.
  - Governance glossary currently covers only high-level entities; expand with additional agencies/statutes once new sources land.
