# Workflow Definitions Documentation

This directory contains workflow definitions for the automated issue processing agent. Each workflow defines how GitHub issues with specific labels should be processed and what deliverables should be generated.

As of October 2025 the repository only includes taxonomy-compliant criminal-law workflows under `criminal-law/`.

## Workflow File Format

Workflow definitions are YAML files that specify:

- **Trigger conditions** - What labels activate this workflow
- **Output structure** - Where and how files are organized
- **Deliverable specifications** - What documents to generate
- **Processing configuration** - Timeouts, validation rules, etc.

## Workflow Schema

```yaml
name: "Workflow Name"
description: "Brief description of workflow purpose"
workflow_version: "1.0.0"
category: "entity-foundation" | "legal-research" | "operational-coordination"
priority: "low" | "medium" | "high" | "critical"
confidence_threshold: 0.75

trigger_labels:
  - "label1"
  - "label2"

required_entities:
  - entity_type: "person"
    min_count: 1
    min_confidence: 0.7

deliverable_templates:
  - "entity_backbone"
  - "workflow_core_component"
  - "gao_compliance_appendix"

deliverables:
  - name: "deliverable-name"
    title: "Human Readable Title"
    description: "What this deliverable contains"
    template: "template_file.md"
    required: true
    order: 1

audit_trail:
  required: true
  fields:
    - "model_version"
    - "reason_codes"
    - "entity_evidence"

processing:
  timeout: 150  # seconds
  max_retries: 1

validation:
  min_word_count: 250
  required_sections:
    - "Executive Summary"
    - "GAO Compliance"
```

## Label and State Model

| Label Family | Prefix | Purpose |
| --- | --- | --- |
| Temporary discovery | `monitor::triage` | Applied by site monitoring to mark newly created issues that still require workflow assignment. Removed automatically once an assignment is made. |
| Workflow state | `state::` | Tracks pipeline progress. Valid values: `state::discovery`, `state::assigned`, `state::copilot`, `state::done`. Only one state label should exist on an issue at any time. |
| Workflow selection | `workflow::` | Identifies the canonical workflow that governs specialist guidance and deliverables. Set by assignment agents. |
| Specialist alignment | `specialist::` | Declares which specialist persona owns the guidance for the issue (e.g., `specialist::intelligence-analyst`). |

Agents rely on the state machine below when advancing issues:

```
state::discovery  →  state::assigned  →  state::copilot  →  state::done
```

- **Site monitoring** initializes `monitor::triage` and `state::discovery`.
- **Workflow assignment (AI-first, fallback supported)** removes the discovery label, applies `workflow::`/`specialist::` labels, and transitions to `state::assigned`.
- **Issue processing** generates specialist guidance, assigns Copilot, and advances the issue to `state::copilot`.
- **Copilot completion** (automated or manual) clears in-progress labels and marks the issue `state::done`.

All tooling must treat the labels as case-insensitive and de-duplicate before applying changes.

## Required Issue Sections

Every workflow-compatible issue body contains the following sections:

- `## Discovery` — Populated by site monitoring with source metadata and retrieval timestamp.
- `## AI Assessment` — Written by the workflow assignment agents. Includes recommended workflows, rationale, and signal metadata.
- `## Specialist Guidance` — Generated during issue processing. Provides persona context, required actions, deliverables, and collaboration notes.
- `## Copilot Assignment` — Defines due dates, acceptance criteria, and validation steps for the Copilot handoff.

Processing or assignment agents should update these sections in-place via Markdown section upserts to keep history and comments clean.

## Available Variables

The following variables can be used in patterns:

- `{issue_number}` - GitHub issue number
- `{title_slug}` - Issue title converted to URL-friendly slug
- `{date}` - Current date in YYYY-MM-DD format
- `{deliverable_name}` - Name of the specific deliverable
- `{workflow_name}` - Name of the workflow being executed

## Trigger Label Logic

1. All workflows still require the `site-monitor` label for discovery origins.
2. Assignment agents consider workflow `trigger_labels` alongside the existing label set to resolve a single `workflow::` target.
3. If multiple workflows match, the agent requests clarification and keeps the issue in `state::discovery` until resolved.
4. If no workflow matches (only discovery labels remain), the agent lists recommended options and applies `needs clarification` guidance.

## Deliverable Templates

Templates referenced in the `template` field should be placed in the `templates/` directory at the project root. Templates use Markdown format with variable substitution.

## Processing Flow

1. **Issue Detection** – Site monitor or manual intake ensures discovery metadata and discovery-state labels are present.
2. **Workflow Assignment** – AI-first agent (with fallback support) selects and applies a single workflow, removes `monitor::triage`, and transitions the issue to `state::assigned`.
3. **Specialist Guidance Generation** – `process-issues` uses workflow configuration to populate `## Specialist Guidance` and update assignment metadata.
4. **Copilot Handoff** – The processor assigns Copilot, writes the `## Copilot Assignment` block, updates labels to `state::copilot`, and emits telemetry artifacts.
5. **Copilot Execution** – Copilot or automation completes deliverables, transitions the issue to `state::done`, and posts completion summary.

## Example Workflows

### Person Entity Profiling & Risk Flagging
- **Triggers**: `person-profile`, `risk-flag`, `criminal-law`
- **Purpose**: Build structured dossiers with conflict and sanctions analysis
- **Deliverables**: Entity backbone, risk posture core, GAO compliance appendix

### Statutory & Regulatory Research Tracker
- **Triggers**: `statute-review`, `gao-directive`
- **Purpose**: Curate applicable statutes, directives, and compliance checks
- **Deliverables**: Entity backbone, statutory digest core, GAO compliance appendix

### Inter-Agency Coordination Briefs
- **Triggers**: `coordination`, `gao-brief`
- **Purpose**: Map agency touchpoints, task decision timelines, and communication plans
- **Deliverables**: Entity backbone, coordination brief core, GAO compliance appendix

## Creating New Workflows

1. Create a new YAML file in this directory
2. Follow the schema documented above
3. Define unique trigger labels to avoid conflicts
4. Specify required deliverables with clear descriptions
5. Set appropriate processing timeouts and validation rules
6. Test with a sample issue before deploying

## Best Practices

- Use descriptive trigger labels that clearly indicate workflow purpose.
- Keep deliverable names URL-friendly (lowercase, hyphens, no spaces).
- Set realistic timeouts based on workflow complexity.
- Include validation rules to ensure quality output.
- Document any special requirements in the workflow description.
- Validate that workflow metadata declares the appropriate `specialist::` label so state transitions remain deterministic.

## Troubleshooting

- **Multiple workflows match**: Add more specific labels to disambiguate
- **No workflow matches**: Ensure `site-monitor` label is present and check trigger labels
- **Validation failures**: Review min_word_count and required_sections settings
- **Timeout issues**: Increase processing timeout or simplify deliverables

## Integration

These workflows integrate with:
- `src/workflow_matcher.py` - Workflow discovery and matching
- `src/issue_processor.py` - Issue processing orchestration
- `src/deliverable_generator.py` - Document generation
- `main.py process-issues` - Command-line interface