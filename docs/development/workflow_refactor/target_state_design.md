# Target State Design

**Goal**: Define the end-to-end experience where every monitored update progresses through workflow assignment, specialist enrichment, and Copilot delivery without redundant pathways.

## 1. End-to-End Flow Overview
1. **Site Monitoring**
   - Detect new or changed web content, capture rich metadata (URL, title, excerpt, retrieval timestamp).
   - Create an issue with a standardized template including a "Discovery" section and initial triage notes.
   - Apply the temporary label `monitor::triage` and set a `workflow.state` field in issue metadata to `"discovery"`.
2. **Workflow Assignment (AI-First)**
   - Retrieve issues tagged `monitor::triage` and not yet marked `workflow.state >= assigned`.
   - Fetch the target page (respecting caching/quotas) and run the GitHub Models classifier.
   - Generate:
     - `workflow.labels`: definitive workflow tags (e.g., `workflow::osint`, `specialist::intelligence-analyst`).
     - `workflow.summary`: 3-5 bullet insights with confidence scores.
   - Remove the temporary discovery label and set `workflow.state = "assigned"`.
   - Persist AI rationale in the issue body under an "AI Assessment" section for specialist consumption.
3. **Issue Processing (Unified Copilot Path)**
   - Single CLI entrypoint `process-issues` handles all processing.
   - Select specialists based on `workflow.labels` and workflow configuration.
   - Generate specialist guidance blocks (structured markdown) and attach deliverable scaffolds.
   - Add a `Copilot Assignment` section with explicit instructions, inputs, and acceptance criteria.
   - Assign the issue to Copilot (or queue via API) and transition `workflow.state = "copilot-assigned"`.
   - Post summary comment referencing files/branches prepared for Copilot.
4. **Copilot Execution**
   - Copilot follows the structured guidance, edits/creates documents in the dedicated branch, and updates status.
   - Upon completion, Copilot or automated checks transition `workflow.state = "completed"` and close/notify as required.

## 2. Data Contracts & Artifacts
| Artifact | Owner | Key Fields | Notes |
| --- | --- | --- | --- |
| Issue Body Template | Site Monitoring | Discovery metadata, raw excerpt | Provides context for AI classifier.
| AI Assessment Block | Workflow Assignment | Summary bullets, label rationale, confidence | Stored under `## AI Assessment`.
| Specialist Guidance Block | Issue Processing | Specialist persona, objective, input artifacts, deliverables | Structured markdown for Copilot.
| Copilot Assignment Block | Issue Processing | Checklist, definition of done, review path | Ensures consistent handoff.
| Labels | All | `monitor::triage`, `workflow::*`, `specialist::*`, `state::*` | Enforces state machine semantics.

## 3. Label & State Machine Harmonization
```
discovery (monitor::triage)
  ↓ AI assignment completed
assigned (workflow::*)
  ↓ Specialist guidance generated
copilot-assigned (state::copilot)
  ↓ Copilot completed work
completed (state::done)
```
- Temporary labels (`monitor::triage`) must be replaced with deterministic workflow labels during assignment.
- State labels (`state::*`) provide a single source for automation to determine progress.

## 4. Unified Issue Processing Contract
- **CLI**: `python main.py process-issues [options]`
- **Modes**:
  - `--from-monitor`: pickup newly assigned issues.
  - `--dry-run`: no external side effects.
  - `--continue-on-error`: resilient batch processing.
- **Outputs**:
  - Updated issue body sections (`## Specialist Guidance`, `## Copilot Assignment`).
  - Optional branch/files scaffolding when deliverables require repository updates.
  - Issue assignment to Copilot with due dates and priority notes.

## 5. Specialist Guidance Template (Required Fields)
```
## Specialist Guidance

### Persona
- **Role**: Intelligence Analyst
- **Objective**: Produce threat assessment for <target>

### Inputs Provided
- URL: <link>
- AI Summary Highlights: <bullets>
- Supporting Artifacts: <files/branches>

### Analytical Focus
1. ...
2. ...

### Deliverables Requested
- [ ] Executive Summary (doc path)
- [ ] Source Vetting Notes

### Quality Checklist
- IC writing standards upheld.
- Cite at least 3 external sources.
```

## 6. Copilot Assignment Template (Required Fields)
```
## Copilot Assignment

**Assignee**: @github-copilot
**Due**: <ISO timestamp>
**Acceptance Criteria**:
1. Update <file> with specialist findings.
2. Create <report> using template <path>.
3. Comment with completion summary and key blockers (if any).

**Validation Steps**:
- Run pytest suite <subset>.
- Review branch <name> for doc updates.
```

## 7. Operational Guardrails
- **Idempotency**: Each workflow must detect when the next state is already achieved and skip gracefully.
- **Concurrency**: Introduce optimistic locking or label checks to prevent double-processing when GitHub Actions overlap with manual runs.
- **Observability**: Emit structured logs with workflow state transitions for dashboards and audits.
- **Testing**: Provide integration fixtures that simulate the entire pipeline with mocked GitHub responses.

## 8. Sunset of Redundant Commands
- ✅ Retire `process-copilot-issues` once the unified processor supports Copilot assignment. *(Completed 2025-09-30; Copilot handoff now lives entirely in `process-issues`.)*
- Update documentation, CLI help, and CI jobs to reference the consolidated entrypoint.
- Add migration script or checklist to remove legacy GitHub Actions referencing the deprecated command.
