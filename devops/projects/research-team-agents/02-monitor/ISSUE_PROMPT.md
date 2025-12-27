# Implement Monitor Agent

## Overview

Implement the Monitor Agent as defined in the [planning document](./PLAN.md). This agent detects content changes in registered sources and queues them for acquisition by creating GitHub Issues.

## Context

- **Upstream Dependency**: Source Curator Agent (provides `knowledge-graph/sources/` registry)
- **Downstream Consumer**: Acquisition Agent (consumes `initial-acquisition` and `content-update` Issues)
- **Execution Model**: Scheduled GitHub Actions workflow (every 6 hours)

## Two-Mode Operation

The Monitor Agent operates in two distinct modes based on whether a source has been previously acquired:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Initial Acquisition** | `last_content_hash` is `None` | Create `initial-acquisition` Issue immediately |
| **Update Monitoring** | `last_content_hash` exists | Use tiered detection, create `content-update` Issue only if changed |

## Implementation Tasks

### 1. Extend SourceEntry Model
Add monitoring fields (`last_content_hash`, `last_etag`, `last_checked`, `check_failures`, `next_check_after`) to `src/knowledge/storage.py`.

### 2. Create Monitoring Module  
New file `src/knowledge/monitoring.py` with `SourceMonitor` class, `CheckResult` and `ChangeDetection` dataclasses.

### 3. Create Monitor Toolkit
New file `src/orchestration/toolkit/monitor.py` with tools for change detection and Issue creation.

### 4. Create Mission Configuration
New file `config/missions/monitor_sources.yaml` defining the agent mission.

### 5. Create GitHub Workflow
New file `.github/workflows/3-op-monitor-sources.yml` for scheduled execution.

### 6. Add Test Coverage
Unit and integration tests in `tests/knowledge/` and `tests/orchestration/`.

## Acceptance Criteria

- [ ] Sources with no prior acquisition create `initial-acquisition` Issues
- [ ] Sources with detected changes create `content-update` Issues  
- [ ] Unchanged sources are skipped (no Issue created)
- [ ] Duplicate Issues are prevented via HTML marker deduplication
- [ ] Failed checks increment `check_failures` and apply backoff
- [ ] Sources marked `degraded` after 5 consecutive failures
- [ ] All tests pass: `pytest tests/knowledge/test_monitoring.py tests/orchestration/test_monitor_toolkit.py -v`

## Progress Tracking

Track detailed progress in [IMPLEMENTATION.md](./IMPLEMENTATION.md). Update checkboxes as tasks complete.

## Instructions for Agent

1. Read [PLAN.md](./PLAN.md) for complete design specifications
2. Read [IMPLEMENTATION.md](./IMPLEMENTATION.md) for current progress and next steps
3. Follow the phase order defined in IMPLEMENTATION.md
4. After completing work, update the "Session Handoff Notes" section in IMPLEMENTATION.md
5. Run tests after each phase to verify correctness
6. Commit changes with descriptive messages following project conventions

## Labels

`agent-implementation`, `monitor-agent`, `phase-1-foundation`

---

<!-- implementation-tracker:monitor-agent -->
