---
name: "Asset & Evidence Catalog Core"
description: "Catalog of tangible and intangible evidence with custody assessment."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Summary"
  - "Evidence Ledger"
  - "Chain-of-Custody Checklist"
  - "Admissibility Assessment"
  - "Analyst Notes"
variables:
  entity_index: "Dictionary of entities keyed by type"
  entity_counts: "Count of entities per type"
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Asset & Evidence Cataloguing

## Summary
- **Evidence Items Logged**: {% if entity_counts %}{% if entity_counts.thing %}{{ entity_counts.thing }}{% else %}0{% endif %}{% else %}0{% endif %}
- **Extraction Confidence**: {% if extraction_metadata %}{{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }}){% else %}Unavailable{% endif %}
- **Missing Base Entities**: {% if entity_foundation %}{% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}{% else %}None{% endif %}

## Evidence Ledger
{% if entity_index %}
{% if entity_index.thing %}
| Asset / Evidence | Custodian / Context | Confidence | Notes |
| --- | --- | --- | --- |
{% for asset in entity_index.thing %}| {{ asset.name }} | {{ asset.display_role }} | {{ asset.confidence }} | {{ asset.display_notes }} |
{% endfor %}
{% else %}
_No evidence entities documented. Capture exhibits, digital artifacts, or physical items before proceeding._
{% endif %}
{% else %}
_No evidence entities documented. Capture exhibits, digital artifacts, or physical items before proceeding._
{% endif %}

## Chain-of-Custody Checklist
- Record acquisition source and date.
- Identify current custodian and location controls.
- Note admissibility issues or remediation steps.

## Admissibility Assessment
1. Highlight authenticity and integrity considerations.
2. Document applicable Federal Rules of Evidence citations.
3. Flag mitigation or remediation tasks for questionable items.

## Analyst Notes
- **Key Topics**: {% if extraction_metadata %}{{ extraction_metadata.key_topics_display }}{% else %}Unavailable{% endif %}
- **Urgency Level**: {% if extraction_metadata %}{{ extraction_metadata.urgency_level_display }}{% else %}Unavailable{% endif %}

```yaml
# Sample custody log entry
custody_log:
  asset: 
  acquired_from: 
  acquisition_timestamp: 
  current_custodian: 
  admissibility_notes: 
  follow_up_tasks:
    - description: 
      owner: 
      due_date: 
```
