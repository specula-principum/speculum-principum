---
title: "Add entity: {entity_name}"
labels:
  - ready-for-copilot
  - kb-entity
  - manual
---

## Task: Add New Entity to Knowledge Base

**Entity:** {entity_name}
**Entity Type:** {entity_type}
**Source Material:** {source_material}

### Requirements

Create a new entity document that covers:

1. **Identity** – Core facts about the entity
2. **Role & Context** – How the entity relates to mission objectives
3. **Relationships** – Key links to concepts, entities, or events
4. **Source References** – Citations with page or section numbers
5. **Insights** – Analyst interpretation or strategic significance

### Document Location

`knowledge-base/entities/{entity_type_slug}/{entity_slug}.md`

### Metadata Requirements

```yaml
title: {entity_name}
kb_id: entities/{entity_type_slug}/{entity_slug}
type: entity
entity_type: {entity_type}
sources:
  - kb_id: sources/{source_slug}
    pages: [...]
related:
  concepts: []
  entities: []
```

### Tools to Use

```bash
# Extract entity information from sources
python -m main extract entities \
  --input {source_path} \
  --focus "{entity_name}" \
  --output-format json

# Create KB entity document
python -m main kb create-entity \
  --name "{entity_name}" \
  --entity-type {entity_type} \
  --sources {source_path} \
  --kb-root knowledge-base/

# Validate the new entity entry
python -m main kb validate \
  --kb-root knowledge-base/ \
  --document entities/{entity_type_slug}/{entity_slug}.md
```

### Success Criteria

- [ ] Entity document created with required metadata
- [ ] Relationships and references populated
- [ ] Validation passes with no errors

### Notes

{additional_instructions}
