# Monitor Agent - Planning Document

## Agent Overview

**Mission:** Queue sources for acquisition by detecting content changes and creating acquisition candidates.

**Status:** ✅ Planning Complete

---

## Responsibilities

- Check registered sources for content changes using lightweight HEAD requests
- Detect changes via HTTP headers (ETag, Last-Modified) and content hash comparison
- Create acquisition candidate Issues for sources with detected changes
- Maintain a changelog of detected updates in source metadata
- Prevent duplicate acquisition requests for unchanged content

## Quality Standards

- Timestamp all checks with source verification metadata
- Distinguish between substantive updates (content hash change) vs. cosmetic changes (timestamp only)
- Avoid duplicate Issues for the same content version
- Respect rate limits and implement polite crawling patterns

---

## Core Concept: Monitor as Queuing Mechanism

The Monitor Agent operates as a **lightweight change detector**, not a content fetcher. Its job is to:

1. **Probe** registered sources using HTTP HEAD requests (minimal bandwidth)
2. **Compare** response headers and hashes against stored state
3. **Queue** changed sources by creating acquisition candidate Issues
4. **Skip** sources whose content hash matches the last acquired version

This design ensures:
- **Efficiency**: Only changed content triggers acquisition
- **No bloat**: Content hashes stored in SourceEntry, not full content history
- **Audit trail**: All change detections visible as GitHub Issues
- **Transparency**: Discussions used for any anomalies or access problems

---

## Two-Mode Operation: Initial vs. Incremental

The Monitor Agent handles two fundamentally different scenarios:

### Mode 1: Initial Acquisition (First-Time Fetch)

**Trigger**: `SourceEntry.last_content_hash` is `None` (source never acquired)

**Characteristics**:
- Source was just approved via Source Curator workflow
- May contain many pages/documents (e.g., 158-page PDF, multi-page website)
- No previous state to compare against
- Full content scope needs acquisition

**Behavior**:
1. Skip tiered change detection (nothing to compare)
2. Create single `initial-acquisition` Issue for the entire source
3. Acquisition Agent handles full fetch and parsing
4. After completion, `last_content_hash` is set from acquired content

**Issue Template** (Initial):
```markdown
## Initial Acquisition: {source_name}

**Source URL**: {url}
**Approved**: {added_at}
**Approved By**: {added_by}
**Approval Discussion**: #{proposal_discussion}

### Source Profile

- **Type**: {source_type} ({content_type})
- **Credibility Score**: {credibility_score}
- **Expected Content**: {content_type_description}
- **Official Domain**: {is_official}

### Acquisition Scope

This is the **first acquisition** of this source. The Acquisition Agent should:
1. Fetch complete content from the source URL
2. Parse all pages/segments using appropriate parser
3. Store in `evidence/` with full provenance
4. Update source registry with content hash and acquisition timestamp

**Labels**: `initial-acquisition`, `{source_type}`

<!-- monitor-initial:{source_url_hash} -->
```

### Mode 2: Update Monitoring (Incremental Changes)

**Trigger**: `SourceEntry.last_content_hash` exists (source previously acquired)

**Characteristics**:
- Source already in `evidence/` with parsed content
- Comparing against known baseline
- Changes are typically incremental (page updates, new sections)
- Most checks result in "no change"

**Behavior**:
1. Use tiered change detection (ETag → Last-Modified → Content Hash)
2. Only create Issue if content actually changed
3. Issue includes diff context (previous vs. current hash)
4. Acquisition Agent fetches updated content, preserves version history

**Issue Template** (Update):
```markdown
## Content Update: {source_name}

**Source URL**: {url}
**Change Detected**: {detected_at}
**Detection Method**: {detection_method}
**Previous Acquisition**: {last_acquired_at}

### Change Summary

| Metric | Previous | Current |
|--------|----------|---------|
| Content Hash | `{previous_hash[:16]}` | `{current_hash[:16]}` |
| ETag | {previous_etag or "N/A"} | {current_etag or "N/A"} |
| Last-Modified | {previous_last_modified or "N/A"} | {current_last_modified or "N/A"} |

### Acquisition Instructions

This is an **incremental update**. The Acquisition Agent should:
1. Fetch current content from the source URL
2. Parse and compare against previous version in `evidence/`
3. Store new version with provenance linking to previous
4. Update source registry with new content hash

**Labels**: `content-update`, `{urgency}-priority`

<!-- monitor-update:{source_url_hash}:{current_hash} -->
```

### Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Source Ready for Check                        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │ last_content_hash is None?  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼ YES                       ▼ NO
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │    INITIAL ACQUISITION    │   │    UPDATE MONITORING      │
    │                           │   │                           │
    │ • Skip change detection   │   │ • Tier 1: Check ETag      │
    │ • Create initial-acq      │   │ • Tier 2: Check Modified  │
    │   Issue immediately       │   │ • Tier 3: Compare hash    │
    │ • Full source scope       │   │ • Create update Issue     │
    │                           │   │   only if changed         │
    └───────────────────────────┘   └───────────────────────────┘
```

### Efficiency Gains

| Scenario | Without Distinction | With Two-Mode Design |
|----------|--------------------|-----------------------|
| New 100-page PDF | 100 Issues (one per page?) | 1 Issue (initial acquisition) |
| Unchanged source | Full hash computation | HEAD request only (fast) |
| Minor update | Same as major update | Tiered detection, minimal I/O |
| Bulk source approval | Overwhelmed queue | Batched initial acquisitions |

### Batch Initial Acquisition

When multiple sources are approved in a short window (e.g., bulk import from Source Curator), the Monitor Agent can optimize:

1. **Group by domain**: Respect rate limits while processing batch
2. **Single workflow run**: Process all pending initial acquisitions together
3. **Priority ordering**: Primary sources before derived sources
4. **Progress tracking**: Update `last_checked` even before acquisition completes

---

## Implementation Plan

### 1. Change Detection Strategy

#### 1.1 Content Hash Tracking (Extend SourceEntry)

Location: `src/knowledge/storage.py`

Extend `SourceEntry` with monitoring metadata:

```python
@dataclass(slots=True)
class SourceEntry:
    # ... existing fields ...
    
    # Monitoring metadata (new fields)
    last_content_hash: str | None = None       # SHA-256 of last acquired content
    last_etag: str | None = None               # HTTP ETag from last check
    last_modified_header: str | None = None    # Last-Modified header value
    last_checked: datetime | None = None       # When source was last probed
    check_failures: int = 0                    # Consecutive check failures
    next_check_after: datetime | None = None   # Backoff: don't check before this
```

**Storage efficiency**: Only store the latest hash per source, not a history. The content hash in `evidence/parsed/manifest.json` provides version history.

#### 1.2 Detection Hierarchy

The agent uses a three-tier detection approach (cheapest first):

| Tier | Method | When Changed | Action |
|------|--------|--------------|--------|
| 1 | HTTP HEAD + ETag comparison | ETag differs from stored | Proceed to Tier 2 |
| 2 | HTTP HEAD + Last-Modified | Header newer than stored | Proceed to Tier 3 |
| 3 | HTTP GET + Content Hash | Hash differs from stored | Queue for acquisition |

If Tier 1 or 2 indicates change, Tier 3 confirms with actual content hash.

#### 1.3 Rate Limiting and Politeness

Implemented in `src/knowledge/monitoring.py`:

```python
@dataclass
class PolitenessPolicy:
    """Rate limiting configuration per domain."""
    
    min_delay_seconds: float = 1.0        # Minimum delay between requests to same domain
    max_delay_seconds: float = 60.0       # Maximum delay (after backoff)
    backoff_factor: float = 2.0           # Multiply delay on failure
    max_failures: int = 5                 # Failures before marking source degraded
    respect_robots_txt: bool = True       # Honor robots.txt crawl-delay
    user_agent: str = "speculum-principum-monitor/1.0"
```

Domain-specific delays tracked in memory during check runs.

#### 1.4 Dynamic Content Handling

For JavaScript-rendered content:
- **Detection**: Content-Type headers indicating HTML + small content size
- **Strategy**: Skip lightweight HEAD check, proceed to full hash comparison
- **Future**: Flag for Acquisition Agent to use browser rendering

Stored in `SourceEntry.content_type`:
- `"webpage"` - Standard HTML
- `"webpage_dynamic"` - JS-rendered (requires full fetch)
- `"pdf"`, `"api"`, `"feed"` - Direct content

---

### 2. Alert Schema (Acquisition Candidate Issues)

#### 2.1 AcquisitionCandidate Data Model

Location: `src/knowledge/monitoring.py`

```python
@dataclass(slots=True)
class ChangeDetection:
    """Represents a detected content change or initial acquisition need."""
    
    source_url: str                    # URL that changed or needs acquisition
    source_name: str                   # Human-readable name
    detected_at: datetime              # When change/need was detected
    
    # Detection context
    detection_method: str              # "initial" | "etag" | "last_modified" | "content_hash"
    change_type: str                   # "initial" | "content" | "metadata"
    
    # Previous state (None for initial acquisition)
    previous_hash: str | None          # Hash before change
    previous_checked: datetime | None  # When previously checked
    
    # Current state
    current_etag: str | None           # New ETag value
    current_last_modified: str | None  # New Last-Modified value
    current_hash: str | None           # New content hash (if full fetch performed)
    
    # Classification
    urgency: str = "normal"            # "high" | "normal" | "low"
    
    @property
    def is_initial(self) -> bool:
        """True if this is an initial acquisition (no previous content)."""
        return self.change_type == "initial"
    
    def to_dict(self) -> dict[str, Any]: ...
```

#### 2.2 Urgency Classification

| Urgency | Criteria | Label |
|---------|----------|-------|
| **high** | Initial acquisition of primary source; official domain content change | `high-priority` |
| **normal** | Initial acquisition of derived source; standard content updates | `normal-priority` |
| **low** | Reference source updates; metadata-only changes; high-frequency updaters | `low-priority` |

**Initial Acquisition Urgency Rules**:
- `primary` source type → `high` urgency (foundational content)
- `derived` source with official domain → `normal` urgency
- `derived` source with non-official domain → `low` urgency
- `reference` source → `low` urgency

**Update Monitoring Urgency Rules**:
- Primary source content change → `high` urgency
- Source added within last 7 days → boost one level
- Derived source routine update → `normal` urgency
- High-frequency source (daily updates) → `low` urgency (batch)

#### 2.3 Issue Templates

Templates are defined in the "Two-Mode Operation" section above:
- **Initial Acquisition**: Uses `initial-acquisition` label, full source scope
- **Content Update**: Uses `content-update` label, includes diff context

Both templates include HTML comment markers for deduplication:
- Initial: `<!-- monitor-initial:{source_url_hash} -->`
- Update: `<!-- monitor-update:{source_url_hash}:{current_hash} -->`

#### 2.4 Deduplication Logic

Before creating an Issue, the agent checks for existing Issues to prevent duplicates:

**For Initial Acquisition**:
1. Search open Issues for marker `<!-- monitor-initial:{url_hash} -->`
2. Check if `SourceEntry.last_content_hash` is now set (acquisition completed)
3. Skip if either condition true

**For Content Updates**:
1. Search open Issues for marker `<!-- monitor-update:{url_hash}:{content_hash} -->`
2. Compare detected hash against `SourceEntry.last_content_hash`
3. Skip if hash matches (content already acquired) or Issue exists

**Deduplication Query** (GitHub Search API):
```
repo:{owner}/{repo} is:issue is:open "<!-- monitor-initial:{url_hash}" in:body
repo:{owner}/{repo} is:issue is:open "<!-- monitor-update:{url_hash}:{hash}" in:body
```

---

### 3. Scheduling Mechanisms

#### 3.1 GitHub Actions Scheduled Workflow

Monitoring runs via scheduled GitHub Actions (no persistent server required):

Location: `.github/workflows/3-op-monitor-sources.yml`

```yaml
name: "Monitor Sources for Changes"

on:
  schedule:
    # Run every 6 hours
    - cron: "0 */6 * * *"
  workflow_dispatch:
    inputs:
      source_url:
        description: "Optional: Check specific source URL only"
        required: false
      force_check:
        description: "Ignore backoff timers"
        type: boolean
        default: false

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt
      
      - name: Run Monitor Agent
        run: |
          python -m main agent \
            --mission monitor_sources \
            ${{ inputs.source_url && format('--source-url {0}', inputs.source_url) || '' }} \
            ${{ inputs.force_check && '--force-check' || '' }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
      
      - name: Commit source registry updates
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore: update source monitoring metadata"
          file_pattern: "knowledge-graph/sources/*.json"
```

#### 3.2 Polling Frequency by Source Type

| Source Type | Base Frequency | Rationale |
|-------------|----------------|-----------|
| `primary` | Every 6 hours | Foundational sources need frequent checks |
| `derived` | Every 24 hours | Secondary sources checked daily |
| `reference` | Every 7 days | Reference materials rarely change |

Stored in `SourceEntry.update_frequency`:
- `"frequent"` → 6 hours
- `"daily"` → 24 hours  
- `"weekly"` → 7 days
- `"monthly"` → 30 days
- `"unknown"` → 24 hours (default)

#### 3.3 Backoff Strategy for Failures

```python
def calculate_next_check(source: SourceEntry, check_failed: bool) -> datetime:
    """Calculate when to next check a source."""
    base_interval = FREQUENCY_INTERVALS.get(source.update_frequency, timedelta(hours=24))
    
    if not check_failed:
        # Success: reset failures, check after base interval
        return datetime.now(timezone.utc) + base_interval
    
    # Failure: exponential backoff
    backoff_multiplier = min(2 ** source.check_failures, 32)  # Cap at 32x
    backoff_interval = base_interval * backoff_multiplier
    
    # Don't wait more than 7 days between checks
    max_interval = timedelta(days=7)
    return datetime.now(timezone.utc) + min(backoff_interval, max_interval)
```

#### 3.4 Priority Queue (Within Single Run)

When multiple sources need checking in a single workflow run:

1. **Sort by priority**: `primary` > `derived` > `reference`
2. **Within priority**: Sort by `next_check_after` (oldest first)
3. **Apply domain grouping**: Check same-domain sources consecutively to reuse connections
4. **Respect rate limits**: Insert delays between same-domain requests

---

### 4. Tool Requirements

#### 4.1 Existing Tools (Reuse)

| Tool | Module | Purpose |
|------|--------|---------|
| `list_sources` | `toolkit/source_curator.py` | Get sources to monitor |
| `get_source` | `toolkit/source_curator.py` | Retrieve source details |
| `update_source_status` | `toolkit/source_curator.py` | Mark degraded sources |
| `verify_source_accessibility` | `toolkit/source_curator.py` | Basic HTTP check |
| `create_issue` | `toolkit/github.py` | Create GitHub Issue (base) |
| `search_issues` | `toolkit/github.py` | Check for duplicate Issues |
| `add_label` | `toolkit/github.py` | Add priority labels |
| `create_discussion` | `toolkit/discussion_tools.py` | Report access problems |

#### 4.2 New Tools Required

Location: `src/orchestration/toolkit/monitor.py`

| Tool | Description | Risk Level |
|------|-------------|------------|
| `get_sources_pending_initial` | List sources with `last_content_hash=None` | SAFE |
| `get_sources_due_for_check` | List sources whose `next_check_after` has passed | SAFE |
| `check_source_for_changes` | Perform tiered change detection on an existing source | SAFE |
| `update_source_monitoring_metadata` | Update `last_checked`, `last_content_hash`, etc. | REVIEW |
| `create_initial_acquisition_issue` | Create Issue for first-time source acquisition | REVIEW |
| `create_content_update_issue` | Create Issue for content change detection | REVIEW |
| `report_source_access_problem` | Create Discussion for persistent access failures | REVIEW |

#### 4.3 New Module: Source Monitoring

Location: `src/knowledge/monitoring.py`

```python
"""Source change detection and monitoring utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import requests

from src.parsing import utils

from .storage import SourceEntry, SourceRegistry


@dataclass(slots=True)
class CheckResult:
    """Result of checking a source for changes."""
    
    source_url: str
    checked_at: datetime
    status: Literal["unchanged", "changed", "error", "skipped"]
    
    # HTTP response metadata
    http_status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str | None = None
    
    # Change details (if status == "changed")
    detection_method: str | None = None  # "etag" | "last_modified" | "content_hash"
    
    # Error details (if status == "error")
    error_message: str | None = None
    

class SourceMonitor:
    """Monitors sources for content changes."""
    
    def __init__(
        self,
        registry: SourceRegistry,
        timeout: float = 10.0,
        user_agent: str = "speculum-principum-monitor/1.0",
    ) -> None:
        self._registry = registry
        self._timeout = timeout
        self._user_agent = user_agent
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
    
    def check_source(self, source: SourceEntry, force_full: bool = False) -> CheckResult:
        """Check a source for changes using tiered detection."""
        ...
    
    def get_sources_due(self) -> list[SourceEntry]:
        """Return sources that should be checked now."""
        now = datetime.now(timezone.utc)
        return [
            s for s in self._registry.list_sources(status="active")
            if s.next_check_after is None or s.next_check_after <= now
        ]
```

---

### 5. Mission Configuration

Location: `config/missions/monitor_sources.yaml`

```yaml
id: monitor_sources
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-26
  summary_tooling: source-monitoring

goal: |
  Monitor registered sources and queue them for acquisition when needed.
  
  This mission handles TWO distinct modes:
  
  MODE 1 - Initial Acquisition (last_content_hash is None):
  - Source was recently approved but never acquired
  - Skip change detection (nothing to compare)
  - Create `initial-acquisition` Issue for full source fetch
  - Acquisition Agent will set last_content_hash after completion
  
  MODE 2 - Update Monitoring (last_content_hash exists):
  - Source has been previously acquired
  - Perform tiered change detection:
    * Tier 1: Compare HTTP ETag header
    * Tier 2: Compare Last-Modified header  
    * Tier 3: Compare content hash (only if tiers 1-2 indicate change)
  - Create `content-update` Issue only if content actually changed
  
  Common for both modes:
  - Check for duplicate Issues before creation
  - Update source monitoring metadata (last_checked, next_check_after)
  - Report persistent access failures as Discussions
  - Mark sources as degraded after 5 consecutive failures
  
  This mission runs on schedule via GitHub Actions (every 6 hours).

constraints:
  - "For initial acquisition: create single Issue per source, not per page"
  - "For updates: use HEAD requests first to minimize bandwidth"
  - "Respect rate limits: minimum 1 second between requests to same domain"
  - "Do not fetch full content unless change is detected (update mode only)"
  - "Do not create duplicate Issues - check markers before creation"
  - "Update source metadata even when no change detected (last_checked)"
  - "Maximum 5 consecutive failures before marking source degraded"

success_criteria:
  - Sources needing initial acquisition have `initial-acquisition` Issues
  - Changed sources have `content-update` Issues created
  - No duplicate Issues created for same content
  - Source monitoring metadata updated in registry
  - Access problems reported as Discussions

max_steps: 50
allowed_tools:
  - list_sources
  - get_source
  - get_sources_pending_initial
  - get_sources_due_for_check
  - check_source_for_changes
  - update_source_monitoring_metadata
  - search_issues
  - create_initial_acquisition_issue
  - create_content_update_issue
  - create_discussion
  - update_source_status
requires_approval: false
```

---

### 6. Test Cases

Location: `tests/knowledge/test_monitoring.py`

#### 6.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_check_result_dataclass` | CheckResult serialization |
| `test_change_detection_is_initial` | is_initial property for initial acquisitions |
| `test_source_entry_monitoring_fields` | New fields present in SourceEntry |
| `test_sources_pending_initial` | Filters sources with last_content_hash=None |
| `test_sources_due_for_check` | Filters by next_check_after |
| `test_backoff_calculation` | Exponential backoff formula |
| `test_backoff_caps_at_max` | Backoff doesn't exceed 7 days |
| `test_priority_sorting` | Sources sorted by type then due time |
| `test_domain_grouping` | Same-domain sources grouped |
| `test_initial_dedup_marker_format` | `monitor-initial:` marker correct |
| `test_update_dedup_marker_format` | `monitor-update:` marker correct |

#### 6.2 Integration Tests - Initial Acquisition Mode

| Test | Description |
|------|-------------|
| `test_initial_acquisition_detected` | Source with no hash creates initial Issue |
| `test_initial_acquisition_issue_template` | Issue uses initial-acquisition template |
| `test_initial_acquisition_labels` | Issue has `initial-acquisition` label |
| `test_initial_acquisition_skips_tiered_check` | No HEAD request for initial sources |
| `test_initial_acquisition_dedup` | Second run doesn't create duplicate Issue |
| `test_bulk_initial_acquisition` | Multiple new sources batched efficiently |
| `test_initial_acquisition_primary_high_urgency` | Primary sources get high priority |

#### 6.3 Integration Tests - Update Monitoring Mode

| Test | Description |
|------|-------------|
| `test_etag_change_detected` | ETag change triggers detection |
| `test_last_modified_change_detected` | Last-Modified change triggers detection |
| `test_content_hash_change_detected` | Hash change triggers detection |
| `test_unchanged_source_updates_metadata` | last_checked updated even if no change |
| `test_content_update_issue_created` | Change creates Issue with update template |
| `test_content_update_issue_labels` | Issue has `content-update` label |
| `test_duplicate_update_not_created` | Same hash doesn't create second Issue |
| `test_tiered_detection_short_circuits` | ETag match skips deeper checks |

#### 6.4 Integration Tests - Common Behaviors

| Test | Description |
|------|-------------|
| `test_failure_increments_counter` | Failed check increments check_failures |
| `test_success_resets_failures` | Successful check resets check_failures to 0 |
| `test_degraded_after_max_failures` | Source marked degraded after 5 failures |
| `test_access_problem_discussion_created` | Persistent failure creates Discussion |

#### 6.5 Edge Cases

| Test | Description |
|------|-------------|
| `test_no_etag_header` | Handles missing ETag gracefully |
| `test_no_last_modified_header` | Handles missing Last-Modified gracefully |
| `test_redirect_followed` | Final URL used for hash comparison |
| `test_timeout_handling` | Timeout treated as failure |
| `test_ssl_error_handling` | SSL errors reported properly |
| `test_empty_registry` | No sources returns early |
| `test_all_sources_skipped_by_backoff` | All sources in backoff period |
| `test_rate_limit_between_same_domain` | Delay inserted between same-domain requests |
| `test_mixed_initial_and_update` | Run handles both modes in single execution |
| `test_initial_then_update_transition` | After acquisition, source enters update mode |

---

### 7. GitHub Workflow Integration

#### 7.1 Scheduled Monitoring Workflow

Location: `.github/workflows/3-op-monitor-sources.yml`

```yaml
name: "Monitor Sources for Changes"

on:
  schedule:
    - cron: "0 */6 * * *"  # Every 6 hours
  workflow_dispatch:
    inputs:
      source_url:
        description: "Check specific source URL only"
        required: false
        type: string
      force_check:
        description: "Ignore backoff timers"
        type: boolean
        default: false

jobs:
  monitor:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      discussions: write
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      
      - run: pip install -r requirements.txt
      
      - name: Run Monitor Agent
        id: monitor
        run: |
          ARGS="--mission monitor_sources"
          if [ -n "${{ inputs.source_url }}" ]; then
            ARGS="$ARGS --input source_url=${{ inputs.source_url }}"
          fi
          if [ "${{ inputs.force_check }}" = "true" ]; then
            ARGS="$ARGS --input force_check=true"
          fi
          python -m main agent $ARGS
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
      
      - name: Commit monitoring metadata updates
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore(monitor): update source check metadata [skip ci]"
          file_pattern: "knowledge-graph/sources/*.json"
```

#### 7.2 Acquisition Candidate Processing Workflow

Location: `.github/workflows/3-op-acquire-source.yml` (for Acquisition Agent)

This workflow triggers when monitor creates acquisition candidate Issues:

```yaml
name: "Process Acquisition Candidates"

on:
  issues:
    types: [opened, labeled]

jobs:
  acquire:
    if: contains(github.event.issue.labels.*.name, 'acquisition-candidate')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: |
          python -m main agent \
            --mission acquire_source \
            --issue ${{ github.event.issue.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

---

## Storage Efficiency Summary

The Monitor Agent avoids bloat by:

1. **Single hash per source**: Only `last_content_hash` stored, not full history
2. **Header caching**: Store `last_etag` and `last_modified_header` for cheap comparisons
3. **Version history in evidence/**: The `evidence/parsed/manifest.json` tracks all acquired versions
4. **Dedup via Issues**: Acquisition candidates tracked as Issues, not local storage
5. **No content storage**: Monitor only probes, never stores content

---

## Dependencies

- **Upstream**: Source Curator Agent (provides `knowledge-graph/sources/` registry)
- **Downstream**: Acquisition Agent (consumes `acquisition-candidate` Issues)

## Related Modules

- `src/knowledge/storage.py` - SourceEntry with monitoring fields
- `src/knowledge/monitoring.py` - New module for change detection
- `src/orchestration/toolkit/monitor.py` - New toolkit for monitor tools
- `src/integrations/github/issues.py` - Issue creation and search
- `src/parsing/utils.py` - SHA-256 hashing utilities

---

*Last Updated: 2025-12-26*
