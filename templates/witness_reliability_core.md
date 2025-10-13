---
name: "Witness & Expert Reliability Assessment"
description: "Credibility analysis for witnesses and subject-matter experts."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Overview"
  - "Credibility Index"
  - "Follow-Up Actions"
variables:
  entity_index: "Dictionary of entities keyed by type"
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Witness & Expert Reliability Assessment

## Overview
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Credibility Index
{% if entity_index.person %}
| Name | Role | Credibility Score | Prior Flags | Conflict Notes |
| --- | --- | --- | --- | --- |
{% for person in entity_index.person %}| {{ person.name }} | {{ person.display_role }} | {{ person.risk_score }} | {{ person.risk_flags }} | {{ person.conflicts }} |
{% endfor %}
{% else %}
_No person entities available. Capture witness/expert details to evaluate reliability._
{% endif %}

## Follow-Up Actions
1. Verify testimony history and cross-agency statements.
2. Capture impeachment or bias concerns.
3. Coordinate with GAO liaison for expert validation.

```markdown
### Reliability Notes Template
- Witness / Expert:
- Key Points:
- Concerns:
- Mitigation:
```
