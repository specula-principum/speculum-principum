---
name: "GAO Compliance Appendix"
description: "Audit-ready appendix capturing citations, evidence, and decision logs."
type: "document"
version: "1.0"
author: "Workflow Modernization Team"
sections:
  - "Audit Snapshot"
  - "Citations & Authorities"
  - "Evidence & Audit Trail"
  - "Decision Log"
  - "Review Sign-Off"
variables:
  extraction_metadata: "Metadata describing extraction confidence and topics"
  entity_foundation: "Base entity readiness assessment"
  issue: "Normalized issue metadata including number and title"
  workflow: "WorkflowInfo describing the active workflow"
---

{% include "confidentiality_banner" %}

# GAO Compliance Appendix

## Audit Snapshot
- **Issue Reference**: #{{ issue.number }}
- **Extraction Confidence**: {{ extraction_metadata.confidence }} ({{ extraction_metadata.confidence_percent }})
- **Key Topics**: {{ extraction_metadata.key_topics_display }}
- **Base Entities Ready**: {% if entity_foundation.ready %}Yes{% else %}No — Missing {{ entity_foundation.missing_display }}{% endif %}

{% include "shared_gao_citation_block" %}

## Review Sign-Off
- Principal Attorney: ______________________________
- GAO Liaison: _____________________________________
- Review Date: _____________________________________

```yaml
# Optional metadata for automated audit storage
compliance_record:
  issue_number: {{ issue.number }}
  workflow: {{ workflow.name }}
  extraction_confidence: {{ extraction_metadata.confidence }}
  entity_foundation_ready: {{ entity_foundation.ready }}
```
