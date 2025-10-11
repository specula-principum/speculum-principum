---
name: "Case Law Precedent Explorer"
description: "Framework for analyzing relevant case law precedents by jurisdiction."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Overview"
  - "Precedent Matrix"
  - "Jurisdiction Heatmap Notes"
  - "Argument Development"
  - "Analyst Notes"
variables:
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_index: "Dictionary of entities keyed by type"
  entity_foundation: "Base entity readiness assessment"
  entity_counts: "Count of entities per type"
---

{% include "confidentiality_banner" %}

# Case Law Precedent Explorer

## Overview
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Jurisdictions Identified**: {{ entity_counts.place }}
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Precedent Matrix
| Case Name | Citation | Jurisdiction | Alignment | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## Jurisdiction Heatmap Notes
{% if entity_index.place %}
{% for place in entity_index.place %}- **{{ place.name }}** — {{ place.display_notes }}
{% endfor %}
{% else %}
_No jurisdiction entities recorded. Populate venue data to enable precedent targeting._
{% endif %}

## Argument Development
1. Summarize prosecution and defense positions leveraging top precedents.
2. Highlight distinguishing facts or mitigating circumstances.
3. Capture open questions for GAO legal review.

## Analyst Notes
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Content Type**: {{ extraction_metadata.content_type_display }}

```markdown
### Draft Argument Template
- Issue:
- Governing Rule:
- Application to Facts:
- Conclusion:
```
