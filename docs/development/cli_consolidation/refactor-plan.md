# CLI Consolidation Refactor Plan

## Background
`main.py` currently wires every CLI command directly, duplicating configuration checks, site-monitor service creation, telemetry plumbing, and orchestration logic. As new workflows and automation features were added, overlapping responsibilities grew across commands like `monitor`, `cleanup`, `process-issues`, and `assign-workflows`, increasing maintenance cost and the risk of inconsistent behavior.

## Objectives
- Reduce duplication by extracting shared helpers for configuration validation, telemetry setup, and monitor service creation.
- Clarify the ownership boundaries between the site monitor, batch processing orchestrator, and workflow assignment agents.
- Provide a consistent CLI experience (flags, output formatting, error handling) across commands.
- Prepare the codebase for future automation features without multiplying entrypoint complexity.

## Scope
- Refactors within `main.py`, `src/core/site_monitor.py`, `src/core/processing_orchestrator.py`, and supporting utilities.
- New helpers or modules in `src/utils/` to encapsulate shared CLI and telemetry behaviors.
- Tests and documentation updates required to validate and communicate the refactor.

## Out of Scope
- Changing command semantics or user-facing options beyond what is necessary for consolidation.
- Replacing underlying GitHub/GCP client integrations.
- Deeper workflow templating or AI agent changes (unless impacted by the consolidation work).

## Current Pain Points
1. **Monitor service instantiation** is repeated in four commands, each performing the same file-existence checks and service wiring.
2. **Config/environment validation** happens in multiple places with slightly different pathways, risking divergence.
3. **Telemetry setup** is duplicated with only minor variations, making it hard to evolve event payloads consistently.
4. **Issue discovery** logic is split between batch processors and monitor services with overlapping responsibilities.
5. **CLI scaffolding** (progress reporting, dry-run messaging, formatting) must be reimplemented for every new command, slowing feature delivery.

## Proposed Work Plan

### Phase 0 – Preparation & Safety Net
- Inventory existing tests covering CLI commands; add smoke tests if coverage gaps appear (e.g., click-based or argparse-level tests using `pytest` fixtures).
- Capture current CLI help output for regression comparison.

### Phase 1 – Monitor Service Helper Extraction
- Add `get_monitor_service(config_path, github_token, *, telemetry=None)` in a new `src/utils/cli_monitors.py` module.
- Replace inline service construction in `monitor`, `setup`, `status`, and `cleanup` with the helper.
- Include consistent error handling (`FileNotFoundError`, config validation) inside the helper.
- Update unit tests to cover helper behavior (config missing, telemetry passthrough).

### Phase 2 – Unified Runtime Validation
- Introduce `ensure_runtime_ready(config_path)` returning `(config, env)` while managing exits and telemetry emission.
- Use it in both `process-issues` and `assign-workflows` to eliminate redundant validation code.
- Ensure `safe_execute_cli_command` wrappers continue to receive proper `CliResult` objects when validation fails.

### Phase 3 – Telemetry Wiring Consolidation
- Extract telemetry configuration into `src/utils/telemetry_helpers.py` with functions like `setup_cli_publishers(command_name, **static_fields)` and `emit_cli_summary(publishers, event_name, payload)`.
- Update `monitor`, `process-issues`, and `assign-workflows` to use shared helpers.
- Provide regression tests (mocks/spies) ensuring telemetry events still fire with expected payload keys.

### Phase 4 – Issue Discovery API Alignment
- Promote the issue-finding logic inside `BatchProcessor` to a public method accessible by both `process-issues` and the site monitor service (or vice versa).
- Review `process_existing_issues` to ensure it delegates to orchestrator methods instead of reimplementing processing loops.
- Clarify data contracts by documenting return schemas and centralizing status parsing.

### Phase 5 – CLI Scaffolding Reuse
- Move repetitive CLI patterns (progress reporting setup, formatted summaries, dry-run messaging) into helper utilities, potentially extending `src/utils/cli_helpers.py`.
- Standardize `--verbose`, `--dry-run`, and output formatting across commands.
- Update CLI documentation and ensure help text remains accurate.

### Phase 6 – Documentation & Rollout
- Update `README.md` and `docs/development/workflow_refactor` (or create dedicated consolidation notes) to reflect new helper modules and usage patterns.
- Communicate behavior changes in release notes/CHANGELOG.
- Schedule pair reviews for each phase to manage risk.

## Testing Strategy
- Maintain fast CLI regression tests using `pytest` with `subprocess` or `argparse` harness wrappers.
- Verify telemetry helpers using fakes to assert event emission.
- Ensure workflow assignment and issue processing integrations are exercised via existing fixtures (mock GitHub interactions).

## Risks & Mitigations
- **Behavior drift**: Capture baseline outputs before refactor and compare after each phase.
- **Telemetry schema breakage**: Coordinate with analytics consumers; version event schemas if necessary.
- **Hidden coupling**: Add logging/coverage during refactor to reveal unexpected dependencies early.

## Success Criteria
- Duplicate code sections in `main.py` are removed or significantly reduced.
- Commands share consistent validation, telemetry, and progress reporting.
- All existing tests remain green, and new regression tests guard the consolidated helpers.
- Team members have up-to-date documentation explaining the new CLI architecture.
