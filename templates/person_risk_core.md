---
name: "Person Risk Core"
description: "Risk scoring and conflict analysis for individuals involved in the matter."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Overview"
  - "Risk Matrix"
  - "Analytical Notes"
  - "Recommended Next Actions"
  - "Reviewer Checklist"
variables:
  entity_index: "Dictionary of entities keyed by type"
  entity_counts: "Count of entities per type"
  entity_foundation: "Base entity readiness assessment"
  extraction_metadata: "Metadata describing extraction confidence and topics"
---

{% include "confidentiality_banner" %}

# Person Risk Posture & Conflict Review

## Overview
- **Persons Identified**: {{ entity_counts.person }}
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Risk Matrix
{% if entity_index.person %}
| Person | Role | Risk Score | Risk Flags | Conflicts | Confidence |
| --- | --- | --- | --- | --- | --- |
{% for person in entity_index.person %}| {{ person.name }} | {{ person.display_role }} | {{ person.risk_score }} | {{ person.risk_flags }} | {{ person.conflicts }} | {{ person.confidence }} |
{% endfor %}
{% else %}
_No person entities available. Add defendant, witness, or expert records to continue the assessment._
{% endif %}

## Analytical Notes
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Content Type**: {{ extraction_metadata.content_type_display }}

## Recommended Next Actions
1. Validate sanctions, background, and conflict checks against GAO/DOJ repositories.
2. Capture reviewer notes and assign follow-up interviews as required.
3. Document mitigation considerations for each high-risk individual.

### Reviewer Checklist
- [ ] Sanctions list reviewed
- [ ] Conflict log updated
- [ ] Mitigation options recorded
- [ ] GAO liaison briefed on high-risk findings
