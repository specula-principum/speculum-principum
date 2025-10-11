---
name: "Entity Backbone"
description: "Shared entity backbone for GAO-aligned criminal law workflows."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Entity Backbone Summary"
  - "Standardized Entity Tables"
  - "Relationship Overview"
  - "Event Timeline"
  - "Extraction Highlights"
variables:
  issue: "Normalized issue metadata including number, title, labels"
  workflow: "WorkflowInfo describing the active workflow"
  extraction_metadata: "Metadata about the entity extraction process"
  entity_groups: "List of grouped entity records with normalized fields"
  entity_summary: "Aggregate summary of entity coverage"
  entity_foundation: "Base entity readiness assessment"
  relationship_summary: "List of extracted relationships"
  event_timeline: "Chronological events related to the matter"
---

{% include "confidentiality_banner" %}

# Entity Backbone Summary

- **Issue**: #{{ issue.number }} — {{ issue.title }}
- **Workflow**: {{ workflow.name }}
- **Generated**: {{ timestamp.strftime('%Y-%m-%d %H:%M UTC') }}
- **Entity Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Entity Foundation Ready**: {% if entity_foundation.ready %}Yes{% else %}No{% endif %}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

{% include "shared_entity_tables" %}
