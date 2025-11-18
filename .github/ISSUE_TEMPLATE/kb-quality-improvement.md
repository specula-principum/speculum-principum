---
name: Knowledge Base Quality Improvement
about: Improve the quality metrics for an existing KB section
title: "Improve quality of {kb_section}"
labels: [kb-quality, ready-for-copilot, automated]
assignees: ''
---

## Task: Improve Knowledge Base Quality

**Target Section:** `{kb_section}`  
**Current Quality Score:** {current_score}  
**Target Quality Score:** {target_score}

### Quality Issues Identified

{quality_issues}

### Improvement Actions

- [ ] Fix incomplete metadata
- [ ] Add missing related links
- [ ] Improve summaries/definitions
- [ ] Validate taxonomy assignments
- [ ] Add source references

### Tools to Use

```bash
# 1. Analyze current quality
python -m main kb quality-report \
  --kb-root knowledge-base/ \
  --output reports/quality-report.json

# 2. Get improvement suggestions and apply fixes
python -m main kb improve \
  --kb-root knowledge-base/ \
  --fix-links \
  --suggest-tags \
  --report reports/improvement-report.json

# 3. Validate improvements
python -m main copilot kb-validate \
  --kb-root knowledge-base/
```

### Success Criteria

- [ ] Quality score improved to ≥ {target_score}
- [ ] All validation errors resolved
- [ ] Documentation updated

### Notes

{additional_instructions}
