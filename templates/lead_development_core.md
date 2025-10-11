---
name: "Investigative Lead Development"
description: "Backlog and prioritization framework for investigative leads."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Summary"
  - "Lead Backlog"
  - "Source Confidence & Tasking Plan"
variables:
  entity_index: "Dictionary of entities keyed by type"
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Investigative Lead Development

## Summary
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

{% if entity_index.lead %}
## Lead Backlog
| Lead | Context | Confidence | Notes |
| --- | --- | --- | --- |
{% for lead in entity_index.lead %}| {{ lead.name }} | {{ lead.display_role }} | {{ lead.confidence }} | {{ lead.display_notes }} |
{% endfor %}
{% else %}
_No lead entities were extracted. Capture investigative tasks or intelligence gaps to seed the backlog._
{% endif %}

## Source Confidence & Tasking Plan
- Rate source reliability and corroborate with GAO/DOJ partners.
- Assign follow-up owners and due dates.
- Document inter-agency touchpoints for each high-priority lead.

```yaml
# Example tasking entry
lead_task:
  lead: 
  assigned_to: 
  due_date: 
  confidence: 
  next_step: 
```
