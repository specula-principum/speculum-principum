---
name: "Shared Entity Tables"
description: "Reusable GAO-aligned entity, relationship, and timeline sections."
type: "section"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Standardized Entity Tables"
  - "Relationship Overview"
  - "Event Timeline"
  - "Extraction Highlights"
variables:
  entity_groups: "List of grouped entity records with normalized fields"
  relationship_summary: "Summaries of extracted relationships between entities"
  event_timeline: "Chronological events derived from structured extraction"
  extraction_metadata: "Metadata describing extraction confidence and topics"
---

## Standardized Entity Tables
{% if entity_groups %}
{% for group in entity_groups %}
### {{ group.label }} ({{ group.count }})

| Entity | Role / Context | Confidence | Notes |
| --- | --- | --- | --- |
{% if group.items %}{% for entity in group.items %}| {{ entity.name }} | {{ entity.display_role }} | {{ entity.confidence }} | {{ entity.display_notes }} |
{% endfor %}{% else %}| _No entities captured_ |  |  |  |
{% endif %}

{% endfor %}
{% else %}
_No entity records were extracted. Capture person, place, and evidence entities before proceeding._
{% endif %}

## Relationship Overview
{% if relationship_summary %}

| Source | Relationship | Target | Confidence | Notes |
| --- | --- | --- | --- | --- |
{% for rel in relationship_summary %}| {{ rel.source }} | {{ rel.relationship }} | {{ rel.target }} | {{ rel.confidence }} | {{ rel.context_display }} |
{% endfor %}
{% else %}
_No relationships documented. Capture connections between entities to populate this section._
{% endif %}

## Event Timeline
{% if event_timeline %}

| Timestamp | Event | Entities Involved | Confidence |
| --- | --- | --- | --- |
{% for event in event_timeline %}| {{ event.display_timestamp }} | {{ event.description_display }} | {{ event.entities_display }} | {{ event.confidence }} |
{% endfor %}
{% else %}
_No events captured. Add chronology details or extraction focus to populate the timeline._
{% endif %}

## Extraction Highlights
{% if extraction_metadata %}
{% if extraction_metadata.key_topics %}

- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Content Type**: {{ extraction_metadata.content_type_display }}
- **Entity Total**: {{ extraction_metadata.entity_total }}

{% else %}
_Extraction metadata unavailable. Enable AI extraction or provide analyst highlights manually._
{% endif %}
{% else %}
_Extraction metadata unavailable. Enable AI extraction or provide analyst highlights manually._
{% endif %}
