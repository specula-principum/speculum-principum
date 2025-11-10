---
title: "Improve quality of {kb_section}"
labels:
  - ready-for-copilot
  - kb-quality
  - automated
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
python -m main kb metrics \
  --kb-root knowledge-base/ \
  --section {kb_section} \
  --detailed

# 2. Get improvement suggestions
python -m main kb improve \
  --kb-root knowledge-base/ \
  --section {kb_section} \
  --suggest

# 3. Apply fixes
python -m main kb improve \
  --kb-root knowledge-base/ \
  --section {kb_section} \
  --auto-fix \
  --rebuild-links
```

### Success Criteria

- [ ] Quality score improved to >= {target_score}
- [ ] All validation errors resolved
- [ ] Documentation updated

### Notes

{additional_instructions}
