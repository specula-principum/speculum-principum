# Internal Rollout Checklist

This checklist supports the taxonomy-staging pilot and should be reviewed before and after each dry-run cycle.

## Environment & Configuration
- [ ] Taxonomy-staging repository created with mirrored labels (`site-monitor`, taxonomy-specific triggers, QA flags).
- [ ] `config.yaml` staged with sanitized tokens (use GitHub fine-grained tokens or automation accounts).
- [ ] Secrets stored in GitHub Actions or local `.env` for dry-run execution.
- [ ] `monitor`, `assign-workflows`, and `process-issues` commands wired to staging repo references.
- [ ] Deliverable output path mapped to shared staging bucket or secure workspace folder.

## Seed Issues & Data Prep
- [ ] Ten baseline issues created (one per criminal-law workflow) with unique trigger labels.
- [ ] Three mixed-label issues covering ambiguous / fallback scenarios.
- [ ] Issue bodies enriched with structured entity snippets (see integration fixtures).
- [ ] Optional: backfill historical issues for regression comparison.

## Dry-Run Execution
- [ ] `python main.py monitor --config config.yaml --no-individual-issues --dry-run` completes without errors.
- [ ] `python main.py assign-workflows --config config.yaml --limit 10 --dry-run --verbose` matches expected workflows.
- [ ] `python main.py process-issues --config config.yaml --dry-run --verbose` produces GAO templates and artifacts.
- [ ] Artifact directories synchronized to staging bucket with date-stamped folders.

## QA Review (Per Run)
- [ ] Workflow selection matches QA expectation sheet.
- [ ] Deliverables contain required sections; no validation warnings logged.
- [ ] Audit metadata fields populated (model version, reason codes, entity counts).
- [ ] Fallback agent only invoked when ambiguous labels persisted.
- [ ] Telemetry payload archived for analytics (if enabled).

## Pilot Feedback Loop
- [ ] QA reviewers log findings in shared tracker.
- [ ] Schema / template gaps triaged and assigned.
- [ ] Exit criteria (accuracy, template completeness, audit readiness) evaluated weekly.

## Post-Pilot Readout
- [ ] Summarize telemetry results and reviewer sentiment.
- [ ] Capture outstanding risks/blockers with owners and timelines.
- [ ] Approve rollout readiness or schedule additional pilot iteration.
