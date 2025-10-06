# Site Monitoring Content Enrichment Requirements

## Background
- `SiteMonitorService` currently creates discovery issues via `GitHubIssueCreator.create_individual_result_issue`, which renders a rich template whose only source context is the Google Custom Search snippet (`result.snippet`).
- The AI workflow assignment agent (`AIWorkflowAssignmentAgent`) builds its model prompt from the GitHub issue title, body, and labels, truncating the body to 2,000 characters. Because the issue only contains a search snippet, the AI receives little actionable context when selecting workflows.
- The `DeduplicationManager` persists the discovery URL, title, and associated issue number, but does not retain the fetched page content or any enriched metadata that could feed later automation.

## Goals
1. Produce slimmer, easier-to-skim discovery issues that record only essential metadata (“minimal issues”).
2. Capture the target page content (or a high-quality extract) during site monitoring and make it immediately available for enrichment without long-term storage unless explicitly enabled.
3. Enrich workflow-assignment prompts with the captured content (or an inline excerpt fallback) while preserving token budgets and resilience.
4. Maintain observability, resilience, and configurability across the new data flow.

## Current Behavior Insights
- Issue creation path: `SiteMonitorService._create_individual_issues` → `GitHubIssueCreator.create_individual_result_issue` → `_build_individual_result_body`. The body is static Markdown with a single block quote of the search snippet.
- Issue assignment prompt: `GitHubModelsClient._build_analysis_prompt` interpolates the issue body (first 2,000 chars) verbatim; there is no hook for supplemental context.
- Search results expose `SearchResult.cache_id` but this field is unused. It can serve as a fallback to retrieve Google’s cached page if direct HTTP fetch fails.
- No component currently downloads or stores HTML/text content from discovered URLs.

## Proposed Enhancements

### 1. Minimal Issue Template
- Add a `site_monitor.issue_template` configuration block allowing `"full"` (current) vs `"minimal"` layouts, defaulting to `"minimal"` for new deployments.
- Implement a stripped-down Markdown body generator containing:
  - Discovery header with title, canonical URL, domain, and capture timestamp.
  - Optional excerpt (first sentence of extracted content) wrapped in a `<details>` block to keep the issue brief.
  - Checklist linking to workflow assignment/processing commands.
- Preserve existing labels and metadata to avoid breaking downstream automation.
- Provide a migration CLI flag (e.g., `--issue-template=full`) to maintain backward compatibility during rollout.

### 2. Discovery Content Capture Pipeline
- Introduce a `PageCaptureService` invoked inside `_create_individual_issues` prior to issue creation:
  - Fetch HTML with `requests`, honoring timeouts, retries, and user-agent configuration.
  - Use a content extractor (proposed dependency: `trafilatura` for readability-style article text) to derive cleaned Markdown/text and metadata (author, published date if available).
  - If direct fetch fails, assign the label "needs clarification", and attach the failure.
  - Sanitize output (strip scripts, nav, excessive whitespace) and limit storage size (e.g., 30 KB text cap, fallback to summary when exceeded).
- Return an in-memory capture payload that callers can immediately use for issue templating and AI prompt enrichment. Persisting artifacts to disk is optional and controlled by `site_monitor.page_capture.persist_artifacts` (default: `false`).
- When persistence is enabled, store capture artifacts under `artifacts/discoveries/<content_hash>/`:
  - `content.md` (cleaned text), `metadata.json` (URL, hash, timestamps, fetch status), and optional `raw.html` (behind config flag for debugging).
  - Update `ProcessedEntry` (and on-disk JSON schema) to include `content_hash` + `artifact_path` so downstream services can locate the capture.
- Always expose capture status in telemetry and issue bodies (e.g., a badge stating “Page capture: ✅ excerpt embedded” or corresponding failure reason) so operators understand whether persistence occurred.

### 3. Prompt Enrichment for Workflow Assignment
- Extend `AIWorkflowAssignmentAgent` to load the captured artifact when evaluating an issue:
  - Look up the discovery hash via `DeduplicationManager` using the issue URL (parse from the issue body).
  - When persisted artifacts exist, read `content.md`, summarize if necessary (e.g., top paragraphs + bulletized headings using simple heuristics), and append to the AI prompt under a "Page Extract" section.
  - When no artifact is stored (default behavior), fall back to the inline excerpt embedded in the issue body, ensuring prompts remain enriched without disk access.
  - Enforce token/character budget (configurable, default 1,200 chars) with graceful truncation and ellipsis markers.
- Include structured cues in the prompt, such as:
  - `Primary Content Summary:` (auto-generated short summary using first paragraph or optional lightweight extractive summarizer)
  - `Key Sections:` (top N headings detected in the extract)
- Provide configuration toggles: `ai.prompts.include_page_extract` (bool) and `ai.prompts.page_extract_max_chars`.

### 4. Observability, Resilience, and Operations
- Emit telemetry events for capture success/failure, including reasons (timeout, blocked by robots, extractor failure).
- Cache results to avoid repeated fetches during retries or batch reprocessing (keyed by normalized URL hash).
- Surface capture errors in the issue (e.g., “Page capture failed: HTTP 403”) without blocking issue creation.
- Update CI tests and add unit coverage for:
  - `PageCaptureService` happy path, timeout, cache fallback, and oversized content handling (use `responses` mocking).
  - Prompt builder ensuring inclusion/truncation of page extract.
  - Deduplication persistence schema migration (fixtures verifying backwards compatibility with legacy JSON files).

## Implementation Roadmap
1. **Schema & Config Prep**
  - Extend `MonitorConfig` and `ProcessedEntry` schemas with new fields (content hash, optional artifact path) and supply migration utilities for existing `processed_urls.json`.
  - Introduce `persist_artifacts` flag defaulting to `false` to make storage opt-in.
2. **Page Capture Service**
  - Implement fetch/extract module with retries, caching, and sanitization.
  - Wire into site monitor pipeline with metrics + error handling, returning in-memory captures plus optional persistence.
3. **Minimal Issue Template**
  - Refactor `GitHubIssueCreator` body builder to support template variants; add tests covering both modes and excerpt embedding.
4. **Optional Artifact Storage & Telemetry**
  - When persistence is enabled, write artifacts and update telemetry publishers; otherwise report ephemeral capture status.
5. **Prompt Enrichment**
  - Enhance AI agent prompt composition with captured content or inline excerpts, respecting token limits and new config options.
6. **Testing & Documentation**
  - Add unit/integration tests, update operations docs (`docs/ai-workflow-assignment.md`, `docs/workflow-creation-guide.md`), and record configuration examples.

## Acceptance Criteria
- New configuration toggles documented and defaulted safely (minimal issues + prompt enrichment off until capture succeeds; artifact persistence disabled by default).
- Site-monitoring run records discovery content hashes and exposes excerpts without requiring disk persistence, while still supporting optional artifact storage.
- Generated GitHub issues use the minimal template, remaining under 20 lines unless the optional excerpt is expanded.
- AI workflow assignment prompt includes page extract when available, falling back cleanly to inline issue excerpts when capture is non-persistent.
- Test suite exercises capture, storage (when enabled), and prompt enrichment logic.
- Telemetry/log output surfaces capture success/failure counts per run and clarifies whether artifacts were persisted.

## Risks & Mitigations
- **Robots/blocked content**: Provide configurable user-agent and obey robots.txt (future enhancement), log failures without halting monitoring.
- **Token overflow**: Strict max character budget and summarization keep prompts within GitHub Models limits.
- **Storage growth**: Default behavior keeps captures ephemeral; when persistence is enabled, rotate or prune artifacts using existing retention logic (reuse `retention_days`) and optionally compress archived extracts.
- **Backward compatibility**: Maintain ability to render legacy “full” issue template via config to avoid surprising existing workflows.

## Open Questions
- Should we persist raw HTML for future reprocessing, or is sanitized Markdown sufficient?
- Do we need to redact PII or sensitive data from captured pages before storage/prompting?
- Would a lightweight summarization model (e.g., `sumy`, `nltk`) improve extract quality, or is heuristic trimming adequate for now?
- How should we expose artifact locations to human reviewers (issue comment vs. repository artifact listing)?
