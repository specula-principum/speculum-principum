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
- **Evidence Items Logged**: {{ entity_counts.thing }}
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

{% if entity_index.thing %}
## Evidence Ledger
| Asset / Evidence | Custodian / Context | Confidence | Notes |
| --- | --- | --- | --- |
{% for asset in entity_index.thing %}| {{ asset.name }} | {{ asset.display_role }} | {{ asset.confidence }} | {{ asset.display_notes }} |
{% endfor %}
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
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}

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
