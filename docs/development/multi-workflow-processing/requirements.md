# Multi-Workflow Processing Requirements

## Background
The current issue processor selects exactly one workflow per issue. When a label set matches more than one workflow, the processor halts with a `needs_clarification` status. This manual gate is acceptable for rare collisions, but it blocks legitimate use cases where a single discovery spans multiple domains (for example, a government announcement that mixes policy guidance, enforcement actions, and compliance deadlines).

## Goals
- Support processing a single issue with more than one workflow when the labels indicate multiple valid matches.
- Preserve deterministic, auditable behavior so automated runs remain predictable and reproducible.
- Avoid regressions to single-workflow issues and keep backward compatibility with existing deliverables, templates, and pipelines.
- Maintain clear user-facing communication in GitHub issues (comments, labels, assignments) when multi-workflow processing occurs.

## Requirements
### Functional
1. Detect and classify multi-workflow candidates instead of forcing `needs_clarification`.
2. Provide a strategy to select, order, and execute multiple workflows in a single processing run.
3. Generate a consolidated processing report (comment + telemetry) that explains which workflows ran, their outputs, and any conflicts.
4. Allow individual workflows within the batch to fail without aborting the entire run when safe to do so, and surface partial completions clearly.
5. Expose configuration toggles to opt into multi-workflow processing per environment (CLI flag and config entry) with sensible defaults.

### Non-Functional
1. The solution must run within existing timeout and resource limits; do not multiply runtime without guardrails.
2. Concurrency decisions must be deterministic (e.g., sorted workflow list, defined tie-breakers).
3. Logging and telemetry should uniquely identify each workflow execution to preserve traceability.
4. Test coverage must include unit, integration, and CLI acceptance tests for multi-workflow scenarios.

## Solution Research
We evaluated three approaches:

1. **Sequential Chaining:** Execute workflows one after another in priority order. Simple to implement and preserves shared state but can be slow. Conflict detection is easier because outputs are inspected after each step. Risk: later workflows may overwrite artifacts from earlier ones without additional safeguards.

2. **Parallel Execution:** Run workflows concurrently using isolated sandboxes, then merge outputs. Attractive for throughput but introduces complex conflict resolution (file collisions, Git branches, shared telemetry). Requires careful locking and branching strategies.

3. **Hybrid Orchestrated Batching (Recommended):** Determine dependency-aware ordering, execute independent workflows in parallel where safe, and serialize those that touch overlapping deliverables or Git branches. Use a staging workspace per workflow and merge results through a deterministic reconciliation step. Balances speed and safety while keeping conflicts manageable.

The hybrid approach provides the best trade-off: it avoids the full complexity of unrestricted parallel processing while still improving throughput over naive sequential runs. It also naturally supports future enhancements such as workflow dependency graphs or priority weighting.

## High-Level Design
1. **Multi-Workflow Matcher Layer**
   - Extend `WorkflowMatcher` to return an ordered list of workflows (with reasons) instead of aborting.
   - Add conflict metadata (shared deliverable paths, git modes) to assist the orchestrator.

2. **Orchestrator Enhancements**
   - Introduce a `WorkflowExecutionPlan` that captures run order, parallelizable groups, and merge strategy.
   - Spool each workflow into an isolated working directory and temporary branch. Record created files and handoff payloads.

3. **Merge & Commenting**
   - Aggregate deliverables, deduplicate conflicting filenames by appending workflow slugs, and produce a combined GitHub comment that summarizes per-workflow outcomes.
   - Update telemetry schemas to track multi-workflow metrics (count, runtime, conflicts resolved).

4. **Error Handling**
   - Implement per-workflow retries. If one workflow fails, continue others unless configured to stop on first failure. Report failures in the final summary and mark the issue with a flag label (`workflow::partial-complete`).

5. **Configuration & CLI**
   - Add `--allow-multi-workflow` CLI option and matching config key (`processing.enable_multi_workflow`).
   - Provide optional overrides for concurrency level and conflict resolution policy.

## Open Questions
- Do we need workflow-defined dependencies or can we infer conflicts from deliverable metadata alone?
- How should Git integration behave when multiple workflows target the same repository branch? Options: single branch with prefixed paths, or one branch per workflow plus a final merge.
- What is the expected UI/UX for Copilot handoff when several workflows produce guidance? Possibly merge sections with workflow headings.

## Next Steps
1. Produce detailed technical design covering execution plan data structures and merge algorithms.
2. Prototype the hybrid orchestrator using two existing workflows to validate branching and output reconciliation.
3. Define automated tests and telemetry updates.
4. Draft migration and rollout plan including documentation and training.
