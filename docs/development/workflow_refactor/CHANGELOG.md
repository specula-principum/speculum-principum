# Workflow Refactor Changelog

> Canonical history of cross-team changes as the workflow modernization program moves toward production launch.

## 2025-10-03 — Guardrails & Rollout Enablement
- Deprecated the legacy Copilot-only automation path, consolidating GitHub Actions on the unified monitor → assign → process pipeline.
- Hardened assignment and processing workflows with discovery-state gating, secret validation, and telemetry artifact archiving.
- Captured production-derived sample issue bodies and telemetry JSONL events to ground rollout reviews in canonical artifacts.

## 2025-10-02 — Telemetry & CLI Contract Enhancements
- Standardized workflow stage metadata across monitor, assignment, and processing commands and surfaced assignment mode in CLI output.
- Expanded end-to-end dry runs (`assign-workflows`, `process-issues`) to assert on Markdown guidance blocks and fallback flows.
- Published updated deliverable templates and label/state documentation to keep specialist enablement aligned with the new contracts.
