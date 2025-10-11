---
name: "Compliance & Remediation Monitoring"
description: "Scorecard for monitoring remediation commitments and compliance milestones."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Summary"
  - "Compliance Scorecard"
  - "Remediation Timeline"
  - "Alert Thresholds"
variables:
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
---

{% include "confidentiality_banner" %}

# Compliance & Remediation Monitoring

## Summary
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Urgency Level**: {{ extraction_metadata.urgency_level_display }}
- **Missing Base Entities**: {% if entity_foundation.missing_display %}{{ entity_foundation.missing_display }}{% else %}None{% endif %}

## Compliance Scorecard
| Control Area | Target State | Current Status | Owner | Next Review |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  |  |  |  |  |

## Remediation Timeline
| Milestone | Due Date | Status | Notes |
| --- | --- | --- | --- |
|  |  |  |  |
|  |  |  |  |

## Alert Thresholds
- Define triggers for GAO escalation (e.g., missed deadlines, control failures).
- Record notification recipients and channels.

```yaml
# Example alert configuration
alerts:
  threshold: high
  condition: "missed_deadline"
  notify:
    - gaoliaisons@example.gov
    - lead_counsel@example.com
```
