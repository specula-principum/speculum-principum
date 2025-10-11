---
name: "Inter-Agency Coordination Brief"
description: "Briefing template for cross-agency coordination and decision timelines."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Overview"
  - "Agency Contact Map"
  - "Decision Timeline"
  - "Coordination Tasks"
variables:
  entity_index: "Dictionary of entities keyed by type"
  event_timeline: "Chronological events derived from extraction"
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Inter-Agency Coordination Brief

## Overview
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

{% if entity_index.organization %}
## Agency Contact Map
| Agency | Role / Context | Confidence | Notes |
| --- | --- | --- | --- |
{% for agency in entity_index.organization %}| {{ agency.name }} | {{ agency.display_role }} | {{ agency.confidence }} | {{ agency.display_notes }} |
{% endfor %}
{% else %}
_No agency entities recorded. Add GAO, DOJ, or partner organizations to continue the brief._
{% endif %}

{% if event_timeline %}
## Decision Timeline
| Timestamp | Event | Entities Involved | Confidence |
| --- | --- | --- | --- |
{% for event in event_timeline %}| {{ event.display_timestamp }} | {{ event.description_display }} | {{ event.entities_display }} | {{ event.confidence }} |
{% endfor %}
{% endif %}

## Coordination Tasks
- Assign briefing owner and next delivery date.
- Identify dependencies requiring GAO liaison approval.
- Document escalation paths for urgent decisions.

```yaml
# Coordination task template
coordination_task:
  description: 
  owning_agency: 
  due_date: 
  status: planned
```
