# Workflow Intake: Emerging Threat Briefing

## Discovery

- **Site**: Example Threat Feed
- **Title**: Coordinated Spearphishing Campaign Targets Legal Sector
- **URL**: https://intel.example.com/legal-spearphish
- **Source**: intel.example.com
- **Detected**: 2025-10-03 13:03 UTC

> Automated monitoring detected recurring delivery of high-fidelity spearphishing lures leveraging compromised vendor accounts.

## AI Assessment

**Summary**
- Pattern consistent with credential harvesting runbook observed in Q2.
- Targets feature executive assistants and legal operations staff.
- Indicators suggest lateral movement staging via collaboration tools.

**Recommended Workflows**
- ai-content-extraction-demo — Confidence: 0.87 — Rationale: Match on sector keywords and phishing indicators.

**Key Topics**
- Legal sector threat activity
- Spearphishing lures
- Vendor account compromise

**Indicators**
- Sender: counsel-updates@vendor.example
- SHA256 Attachment Hash: 12ab56ff9c0d...
- Lure Subject: "DocuSign Signature Required"

**Classification**
- Urgency: High
- Content Type: Threat Actor Campaign

## Specialist Guidance

### Persona: Intelligence Analyst
- **Role**: You are a senior intelligence analyst with 15+ years of experience in threat assessment, geopolitical analysis, and strategic intelligence
- **Objective**: Demonstration workflow for AI content extraction integration

### Key Insights from AI Assessment
- Issue focus: 📄 Coordinated Spearphishing Campaign Targets Legal Sector
- Summary: Pattern consistent with credential harvesting runbook observed in Q2. Targets feature executive assistants and legal operations staff. Indicators suggest lateral movement staging via collaboration tools.
- Recommended workflow: ai-content-extraction-demo — Confidence: 0.87 — Rationale: Match on sector keywords and phishing indicators.
- Key topics: Legal sector threat activity, Spearphishing lures, Vendor account compromise
- Indicators: Sender: counsel-updates@vendor.example, SHA256 Attachment Hash: 12ab56ff9c0d..., Lure Subject: "DocuSign Signature Required"
- Urgency: High
- Content type: Threat Actor Campaign
- Primary source: https://intel.example.com/legal-spearphish
- Detection timestamp: 2025-10-03 13:03 UTC

### Required Actions
1. Review the discovery context and AI assessment to confirm scope.
2. Prioritize workflow objectives using the specialist guidance template.
3. Develop deliverables: AI-Enhanced Intelligence Summary, Technical Analysis Report.
4. Validate generated files: study/intel/legal-spearphishing.md.
5. Document source citations and note confidence levels.

### Deliverables
- [ ] AI-Enhanced Intelligence Summary — Target: `ai_enhanced_summary` — Intelligence summary enhanced with AI-extracted content
- [ ] Technical Analysis Report — Target: `technical_analysis` — Technical analysis incorporating extracted indicators
- [ ] Verify output stored at `study/intel/legal-spearphishing.md`

### Collaboration Notes
- Reference branch `feature/workflow-refactor-sample` for in-progress commits.
- Coordinate with Workflow Assignment if label adjustments are needed.
- Escalation if blocked: Workflow Modernization Lead.

## Copilot Assignment

**Assignee**: @github-copilot[bot]
**Due**: 2025-10-05T13:03:17+00:00

**Summary**: Pattern consistent with credential harvesting runbook observed in Q2. Targets feature executive assistants and legal operations staff. Indicators suggest lateral movement staging via collaboration tools.

**Acceptance Criteria**:
1. Produce: AI-Enhanced Intelligence Summary, Technical Analysis Report
1. Deliver all specialist-requested artifacts with the updated analysis.
2. Reflect specialist guidance directly in the committed files.
3. Confirm files are updated: study/intel/legal-spearphishing.md

**Validation Steps**:
- Checkout branch `feature/workflow-refactor-sample` for updates.
- Review updated files: study/intel/legal-spearphishing.md
- Run project linters and pytest critical suites.
- Post completion summary with any blockers or open questions.

**Notes**: Collaborate with Intelligence Analyst if scope changes or additional sources are required.

