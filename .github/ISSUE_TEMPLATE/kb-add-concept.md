---
name: Knowledge Base Concept Addition
about: Add a new concept document to the knowledge base
title: "Add concept: {concept_name}"
labels: [kb-concept, ready-for-copilot, manual]
assignees: ''
---

## Task: Add New Concept to Knowledge Base

**Concept:** {concept_name}  
**Primary Topic:** {primary_topic}  
**Source Material:** {source_material}

### Requirements

Create a new concept document with:

1. **Clear definition** – What is this concept?
2. **Context** – Where does it appear in sources?
3. **Related concepts** – What other concepts connect to it?
4. **Source references** – Direct quotes and citations
5. **Analysis** – Interpretation and significance

### Document Location

`knowledge-base/concepts/{topic_path}/{concept_slug}.md`

### Metadata Requirements

```yaml
title: {concept_name}
kb_id: concepts/{topic_path}/{concept_slug}
type: concept
primary_topic: {primary_topic}
sources:
  - kb_id: sources/{source_slug}
    pages: [...]
```

### Tools to Use

```bash
# Extract concept information from sources
python -m main extract concepts \
  --input {source_path} \
  --focus "{concept_name}" \
  --output-format json

# Create KB document
python -m main kb create-concept \
  --name "{concept_name}" \
  --topic {primary_topic} \
  --sources {source_path} \
  --kb-root knowledge-base/

# Validate
python -m main kb validate \
  --kb-root knowledge-base/ \
  --document concepts/{topic_path}/{concept_slug}.md
```

### Success Criteria

- [ ] Concept document created with required metadata
- [ ] Related links and references added
- [ ] Validation passes with no errors

### Notes

{additional_instructions}
