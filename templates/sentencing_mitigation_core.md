---
name: "Sentencing & Mitigation Scenario Planner"
description: "Scenario analysis for sentencing outcomes and mitigation strategies."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Overview"
  - "Sentencing Scenarios"
  - "Defendant Snapshot"
  - "Action Register"
variables:
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
  entity_index: "Dictionary of entities keyed by type"
---

{% include "confidentiality_banner" %}

# Sentencing & Mitigation Scenario Planner

## Overview
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Sentencing Scenarios
| Scenario | Guideline Range | Mitigation Levers | Notes |
| --- | --- | --- | --- |
| Baseline |  |  |  |
| Mitigation A |  |  |  |
| Mitigation B |  |  |  |

## Defendant Snapshot
{% if entity_index.person %}
| Name | Role | Risk Score | Key Mitigation Notes |
| --- | --- | --- | --- |
{% for person in entity_index.person %}| {{ person.name }} | {{ person.display_role }} | {{ person.risk_score }} | {{ person.display_notes }} |
{% endfor %}
{% else %}
_No defendant entities available. Capture person entities to enable sentencing analysis._
{% endif %}

## Action Register
1. Confirm applicable Federal Sentencing Guidelines sections.
2. Document mitigation evidence and supporting citations.
3. Coordinate with GAO liaison for policy implications.

```yaml
# Mitigation task tracker
mitigation_task:
  description: 
  owner: 
  due_date: 
  status: pending
```
