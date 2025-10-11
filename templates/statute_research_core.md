---
name: "Statutory & Regulatory Research Core"
description: "Digest of applicable statutes, GAO directives, and compliance obligations."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Summary"
  - "Statute Digest"
  - "GAO Directive Alignment"
  - "Compliance Checklist"
  - "Referenced Indicators"
variables:
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Statutory & Regulatory Research Tracker

## Summary
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Statute Digest
| Citation | Jurisdiction | Relevance | Action Required |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

## GAO Directive Alignment
| Directive | Compliance Area | Status | Owner |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |

## Compliance Checklist
- [ ] Assign owner for statute monitoring updates.
- [ ] Record next review date for regulatory changes.
- [ ] Capture GAO liaison confirmation of compliance approach.

{% if extraction_metadata.indicators %}
## Referenced Indicators
| Type | Value | Confidence | Description |
| --- | --- | --- | --- |
{% for indicator in extraction_metadata.indicators %}| {{ indicator.type }} | {{ indicator.value }} | {{ indicator.confidence }} | {{ indicator.description }} |
{% endfor %}
{% endif %}

```yaml
# Schedule automated monitoring for critical citations
statute_monitoring:
  citation: 
  refresh_interval_days: 30
  next_review: 
  responsible_owner: 
```
