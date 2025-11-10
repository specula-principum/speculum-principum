---
title: "Extract knowledge from {source_name}"
labels:
  - ready-for-copilot
  - kb-extraction
  - automated
---

## Task: Extract Knowledge from Source Material

**Source Path:** `{source_path}`
**Source Type:** {source_type}  
**Processing Date:** {date}

### Extraction Requirements

- [ ] Extract concepts (min frequency: {min_concept_freq})
- [ ] Extract entities (people, places, organizations)
- [ ] Build relationship graph
- [ ] Generate source document with references

### Output Requirements

**Target KB Root:** `knowledge-base/`

**Expected Artifacts:**
- Concept documents in `knowledge-base/concepts/`
- Entity documents in `knowledge-base/entities/`
- Source document in `knowledge-base/sources/{source_slug}/`
- Updated indexes and navigation
- Quality report with metrics

### Quality Standards

- Minimum completeness: {min_completeness}
- Minimum findability: {min_findability}
- All documents must validate against IA schema
- All links must resolve

### Tools to Use

```bash
# 1. Process source material
python -m main kb process \
  --source {source_path} \
  --kb-root knowledge-base/ \
  --mission config/mission.yaml \
  --extract concepts entities relationships structure \
  --validate

# 2. Check quality metrics
python -m main kb metrics \
  --kb-root knowledge-base/ \
  --output reports/quality-{issue_number}.json

# 3. Fix any validation issues
python -m main kb validate \
  --kb-root knowledge-base/ \
  --check-links \
  --check-metadata \
  --auto-fix
```

### Success Criteria

- [ ] All extraction tools completed successfully
- [ ] Quality metrics meet thresholds
- [ ] Validation passes with no errors
- [ ] Quality report generated
- [ ] Changes committed to branch `kb-extract-{issue_number}`

### Notes

{additional_instructions}
