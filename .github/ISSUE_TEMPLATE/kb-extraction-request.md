---
name: Knowledge Base Extraction Request
about: Request automated knowledge extraction from a source document
title: "Extract knowledge from {source_name}"
labels: [kb-extraction, ready-for-copilot, automated]
assignees: ''
---

## Task: Extract Knowledge from Source Material

**Source Path:** `{source_path}`  
**Source Type:** {source_type}  
**Processing Date:** {date}

### Extraction Requirements

- [ ] Extract concepts (minimum frequency: {min_concept_freq})
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
# Option 1: Run the full automated workflow (recommended)
python -m main copilot kb-automation \
  --source {source_path} \
  --kb-root knowledge-base/ \
  --mission config/mission.yaml \
  --extract concepts entities relationships structure \
  --issue {issue_number} \
  --metrics-output reports/quality-{issue_number}.json

# Option 2: Run steps individually for more control

# Step 1: Process source material
python -m main kb process \
  --source {source_path} \
  --kb-root knowledge-base/ \
  --mission config/mission.yaml \
  --extract concepts entities relationships structure \
  --validate

# Step 2: Generate quality metrics report
python -m main kb quality-report \
  --kb-root knowledge-base/ \
  --output reports/quality-{issue_number}.json

# Step 3: Validate knowledge base
python -m main copilot kb-validate \
  --kb-root knowledge-base/
```

### Success Criteria

- [ ] All extraction tools completed successfully
- [ ] Quality metrics meet thresholds
- [ ] Validation passes with no errors
- [ ] Quality report generated
- [ ] Changes committed to branch `kb-extract-{issue_number}`

### Notes

{additional_instructions}
