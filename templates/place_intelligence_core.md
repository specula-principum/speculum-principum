---
name: "Place Intelligence Core"
description: "Geospatial and jurisdictional intelligence for criminal-law matters."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Jurisdiction Snapshot"
  - "Event & Venue Timeline"
  - "Inter-Agency Considerations"
  - "Analyst Notes"
variables:
  entity_index: "Dictionary of entities keyed by type"
  entity_counts: "Count of entities per type"
  event_timeline: "Chronological events derived from extraction"
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Place Intelligence Mapping

## Jurisdiction Snapshot
- **Locations Identified**: {{ entity_counts.place }}
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

{% if entity_index.place %}
| Location | Jurisdiction | Role / Context | Confidence | Notes |
| --- | --- | --- | --- | --- |
{% for place in entity_index.place %}| {{ place.name }} | {{ place.jurisdiction_display }} | {{ place.display_role }} | {{ place.confidence }} | {{ place.display_notes }} |
{% endfor %}
{% else %}
_No place entities available. Capture venue, district, or facility information to continue mapping._
{% endif %}

## Event & Venue Timeline
{% if event_timeline %}
| Timestamp | Event | Entities Involved | Confidence |
| --- | --- | --- | --- |
{% for event in event_timeline %}| {{ event.display_timestamp }} | {{ event.description_display }} | {{ event.entities_display }} | {{ event.confidence }} |
{% endfor %}
{% else %}
_No events captured. Add chronology details or extraction focus to populate the timeline._
{% endif %}

## Inter-Agency Considerations
- Document coordination touchpoints for GAO, DOJ, FBI, and partner agencies.
- Capture venue-specific restrictions (e.g., grand jury schedules, security clearances).
- Outline next briefing milestone for the GAO liaison.

## Analyst Notes
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Content Type**: {{ extraction_metadata.content_type_display }}

```yaml
# Update the coordination record as tasks progress
next_briefing:
  agency: 
  point_of_contact: 
  scheduled_for: 
  decision_deadline: 
```
