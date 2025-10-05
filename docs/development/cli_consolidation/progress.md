# CLI Consolidation Progress

## Summary (as of 2025-10-04)

- **Phase 1 – Monitor Service Helper Extraction**
  - Introduced `src/utils/cli_monitors.py` with `get_monitor_service` and `MonitorServiceError`.
  - Refactored CLI monitor-related commands (`monitor`, `setup`, `status`, `cleanup`) to reuse the helper.
  - Added targeted unit tests in `tests/unit/utils/test_cli_monitors.py`.

- **Phase 2 – Unified Runtime Validation**
  - Added `src/utils/cli_runtime.py` with `ensure_runtime_ready` to centralize config/env checks.
  - Updated `process-issues` and `assign-workflows` handlers to consume the new helper.
  - Added coverage via `tests/unit/utils/test_cli_runtime.py`.

- **Phase 3 – Telemetry Wiring Consolidation**
  - Created `src/utils/telemetry_helpers.py` providing `setup_cli_publishers`, `emit_cli_summary`, and `attach_cli_static_fields`.
  - Rewired telemetry handling in `monitor`, `process-issues`, and `assign-workflows` to use shared helpers; preserved legacy shim for existing tests.
  - Added new unit coverage in `tests/unit/utils/test_telemetry_helpers.py` and refreshed related suites.
- **Phase 4 – Issue Discovery API Alignment (in progress)**
  - Promoted site-monitor discovery to the public `BatchProcessor.find_site_monitor_issues`, returning a structured `SiteMonitorIssueDiscovery` payload.
  - Updated CLI find-issues flow, monitor batch execution, and `SiteMonitorService.process_existing_issues` to reuse the shared discovery helper while preserving agent-activity filtering.
  - Extended unit and e2e suites to validate the new discovery contract, telemetry payloads, and batch-powered discovery fallbacks.
- **Phase 5 – CLI Scaffolding Reuse**
  - Added `CliExecutionContext` and `prepare_cli_execution` helpers to standardize dry-run banners and progress setup across commands.
  - Updated `process-issues`, `assign-workflows`, and `cleanup` handlers to reuse the helper, replacing ad-hoc messaging paths.
  - Expanded `tests/unit/utils/test_cli.py` with coverage for dry-run decorations to guard regression.

## Notes

- Targeted pytest runs remain green (`tests/unit/utils/test_cli_monitors.py`, `tests/unit/utils/test_cli_runtime.py`, `tests/unit/utils/test_telemetry_helpers.py`).
- Remaining opportunities: route `process-issues --from-monitor` through the monitor helper, convert legacy monitor tests to use discovery fixtures, continue consolidating CLI scaffolding per Phase 5.
