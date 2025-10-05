# Specialist Alignment & Copilot Handoff

**Objective**: Ensure specialist insights are captured consistently and handed to Copilot with clear, actionable guidance.

## 1. Specialist Personas in Scope
| Specialist | Primary Focus | Typical Deliverables | Key Data Inputs |
| --- | --- | --- | --- |
| Intelligence Analyst | Threat landscape, geopolitical impact | Executive threat brief, risk matrix | AI assessment summary, source dossier, historical incidents |
| OSINT Researcher | Source verification, digital footprint | Source credibility worksheet, intelligence annex | Raw URLs, social/data footprints, verification status |
| Target Profiler | Organizational mapping, stakeholder analysis | Stakeholder map, influence report | Company registry data, org structure, relationship notes |

## 2. Guidance Block Contract
Every issue processed must include a structured `## Specialist Guidance` block adhering to the template below:
```
## Specialist Guidance

### Persona: <Specialist Name>
- **Role**: <Domain expertise>
- **Objective**: <Clear outcome statement>

### Key Insights from AI Assessment
- Insight 1 (Confidence %)
- Insight 2 (Confidence %)
- Insight 3 (Confidence %)

### Required Actions
1. ...
2. ...

### Deliverables
- [ ] <Deliverable Name> — Stored at `<path>`
- [ ] ...

### Collaboration Notes
- Coordinate with: <other specialists / teams>
- Escalation if blocked: <contact>
```

## 3. Copilot Assignment Expectations
- **Assignee**: `@github-copilot` (or designated automation account).
- **Due Date**: Default 48 hours from assignment; configurable per workflow.
- **Acceptance Criteria**: Mirror the specialist deliverables, plus any technical validation (tests, formatting, compliance checks).
- **Completion Signal**: Copilot must comment with summary + checkboxes indicating completion status; automation monitors for response.

## 4. Workflow Configuration Updates
- Update `docs/workflow/deliverables/*.yaml` to map each `workflow::` label to the corresponding specialist personas.
- Ensure `specialist_workflow_config.py` includes the new guidance contract fields and enforces validation.
- Introduce a helper in `ai_prompt_builder.py` to merge AI assessment highlights with specialist-specific prompts.

## 5. Operational Playbook
1. **Before Processing**
   - Verify issue contains `## AI Assessment` from the assignment workflow.
   - Confirm `state::assigned` label present and no conflicting `state::*` labels.
2. **During Processing**
   - Generate specialist guidance blocks using updated templates.
   - Attach or reference any pre-created branch/files for Copilot.
   - Apply `state::copilot` label and remove `state::assigned`.
3. **After Processing**
   - Assign issue to Copilot with due date.
   - Post comment summarizing deliverables, branch name, and validation steps.
   - Log processing metadata (duration, specialists invoked) for metrics collection.

## 6. Training & Documentation
- Host a knowledge-share session with specialists to walk through the new template and expectations.
- Update `docs/issue-processor.md` and related runbooks to reference the unified workflow.
- Provide sample issues demonstrating the end-to-end flow, stored under `examples/refactor-scenarios/` (to be created in implementation phase).

## 7. Deprecation Guidance
- Remove references to the legacy "basic issue-processing" path in documentation and scripts.
- ✅ Archive historical notes about `process-copilot-issues`; redirect readers to the unified processor (completed 2025-09-30).
- Ensure automation scripts do not attempt to run both commands; add safeguard tests where necessary.
