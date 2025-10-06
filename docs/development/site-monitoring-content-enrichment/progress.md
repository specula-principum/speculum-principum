# Site Monitoring Content Enrichment — Engineering Log

## Session: 2025-10-05

### Objectives
- Implement minimal issue template option
- Capture discovery page content for immediate enrichment without long-term storage by default
- Enrich AI workflow assignment prompts with captured content or inline excerpts
- Maintain observability and configurability across the flow

### Current Status
- Configuration layer now exposes `IssueTemplateConfig`, `PageCaptureConfig`, `SiteMonitorSettings`, and `AIPromptConfig` for runtime toggles, including the new `persist_artifacts` flag (default `false`).
- `PageCaptureService` downloads pages, extracts readable text via `trafilatura`, and returns enriched payloads for inline issue excerpts; persistence is optional and only triggered when explicitly enabled.
- `GitHubIssueCreator` renders a concise “Discovery Intake” template with capture badges, excerpts, and quick actions; CLI override wiring is in place.
- Site monitor workflow integrates capture, writes issue excerpts, and records capture status while skipping artifact writes unless persistence is requested.
- AI workflow assignment agent consumes stored extracts when available and otherwise falls back to the issue’s embedded preview excerpt; unit tests now cover both artifact-backed and ephemeral paths (including hash-only entries).
- Dependency set updated (`trafilatura` + friends) and pytest suite passing after fixture corrections and prompt enrichment safeguards.
- Documentation refreshed (`docs/ai-workflow-assignment.md`, `docs/workflow-assignment-agent.md`) to highlight minimal issues, optional page capture persistence, and prompt enrichment controls.
- Integration coverage added for capture → issue creation → prompt enrichment, exercising ephemeral captures with patched GitHub/search clients.
- Telemetry assertions now verify capture success/failure events and report whether artifacts were persisted or handled ephemerally; dedup retention no longer assumes artifact directories exist.
- CLI `status` command now surfaces aggregated page-capture success/error counters (pulling from dedup telemetry) so operators can verify capture health quickly.

### Next Planned Steps
1. Investigate lightweight summarization/heading extraction refinements to improve prompt excerpts without increasing token cost.
2. Prototype optional artifact persistence paths (compression/archival) for teams that choose to enable storage while keeping the default ephemeral.
3. Explore surfacing recent capture telemetry (last run timestamps, failure reasons) in CLI status for even richer operator context.

### Open Questions & Notes
- Decide whether to relax `IssueTemplateConfig` validation for mocked configs or update fixtures across the suite.
- Confirm final byte budget + ellipsis behavior for stored excerpts so tests and expectations match real truncation.
- Evaluate need for raw HTML retention toggle defaults; currently off, revisit after telemetry review.
