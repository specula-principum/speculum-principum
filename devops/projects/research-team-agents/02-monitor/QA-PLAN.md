# Monitor Agent - QA Testing Plan

## Overview

**Feature:** Monitor Agent for source change detection and acquisition queuing  
**Version:** 1.0  
**Created:** 2025-12-27  
**Status:** Ready for Implementation

---

## 1. Test Objectives

### Primary Goals
- Verify the Monitor Agent correctly identifies sources requiring initial acquisition
- Validate tiered change detection (ETag → Last-Modified → Content Hash) for existing sources
- Confirm proper GitHub Issue creation with correct templates and labels
- Ensure deduplication prevents redundant Issues
- Validate monitoring metadata persistence in source registry

### Quality Criteria
- Zero duplicate Issues created for same content version
- 100% accuracy in distinguishing initial vs. update modes
- All HTTP edge cases handled gracefully (timeouts, redirects, SSL errors)
- Rate limiting enforced between same-domain requests
- Source degradation triggered after 5 consecutive failures

---

## 2. Test Environment Requirements

### Local Development
| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| pytest | Latest |
| responses/httpretty | HTTP mocking library |
| Test fixtures | Mock source registry, mock GitHub API |

### Integration Testing
| Component | Requirement |
|-----------|-------------|
| GitHub API | Test repository with Issues/Discussions enabled |
| HTTP servers | Mock servers simulating various response scenarios |
| Source registry | Test data in `dev_data/knowledge-graph/sources/` |

### CI Environment
| Component | Requirement |
|-----------|-------------|
| GitHub Actions | Ubuntu runner |
| Secrets | `GH_TOKEN` for API access |
| Artifacts | Test reports, coverage data |

---

## 3. Test Scenarios

### 3.0 Repository Setup Integration

#### TC-RS-001: Primary Source Registered During Setup
| Attribute | Value |
|-----------|-------|
| **Precondition** | New repository initialized with source_url in setup workflow |
| **Action** | Copilot creates source registry entry per setup instructions |
| **Expected Result** | Primary source registered in `knowledge-graph/sources/` |
| **Verification** | Source exists with `source_type = "primary"`, `status = "active"`, `last_content_hash = None` |

#### TC-RS-002: Monitor Detects Setup Source
| Attribute | Value |
|-----------|-------|
| **Precondition** | Repository setup completed with primary source registered |
| **Action** | Run monitor check on workspace |
| **Expected Result** | Primary source detected as needing initial acquisition |
| **Verification** | Source appears in `get_sources_due()` results |

#### TC-RS-003: Setup Instructions Include Source Registry
| Attribute | Value |
|-----------|-------|
| **Precondition** | Setup agent processes valid configuration |
| **Action** | Inspect posted instructions to Copilot |
| **Expected Result** | Instructions include creating source registry entry with correct schema |
| **Verification** | Comment contains `knowledge-graph/sources/` path and required fields |

---

### 3.1 Mode 1: Initial Acquisition

#### TC-IA-001: Detect Source Needing Initial Acquisition
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source exists with `last_content_hash = None` |
| **Action** | Run monitor check on source |
| **Expected Result** | Source identified as needing initial acquisition |
| **Verification** | `is_initial` property returns `True` |

#### TC-IA-002: Create Initial Acquisition Issue
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source needs initial acquisition, no existing Issue |
| **Action** | Monitor creates acquisition Issue |
| **Expected Result** | Issue created with `initial-acquisition` label |
| **Verification** | Issue body contains `<!-- monitor-initial:{url_hash} -->` marker |

#### TC-IA-003: Initial Acquisition Issue Template
| Attribute | Value |
|-----------|-------|
| **Precondition** | Initial acquisition Issue created |
| **Action** | Inspect Issue content |
| **Expected Result** | Issue contains: source URL, approval info, source profile, acquisition scope |
| **Verification** | All template fields populated correctly |

#### TC-IA-004: Skip Tiered Detection for Initial Sources
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `last_content_hash = None` |
| **Action** | Run monitor check |
| **Expected Result** | No HEAD request made for change detection |
| **Verification** | HTTP request log shows no HEAD requests for this source |

#### TC-IA-005: Deduplication for Initial Acquisition
| Attribute | Value |
|-----------|-------|
| **Precondition** | Initial acquisition Issue already exists for source |
| **Action** | Run monitor check again |
| **Expected Result** | No duplicate Issue created |
| **Verification** | Issue count for source remains 1 |

#### TC-IA-006: Bulk Initial Acquisition
| Attribute | Value |
|-----------|-------|
| **Precondition** | 5 sources approved simultaneously, all need initial acquisition |
| **Action** | Run single monitor workflow |
| **Expected Result** | 5 Issues created, domain rate limits respected |
| **Verification** | Timestamps show ≥1s delay between same-domain requests |

#### TC-IA-007: Primary Source High Urgency
| Attribute | Value |
|-----------|-------|
| **Precondition** | Primary source needs initial acquisition |
| **Action** | Create acquisition Issue |
| **Expected Result** | Issue has `high-priority` label |
| **Verification** | Label set correctly based on source type |

---

### 3.2 Mode 2: Update Monitoring

#### TC-UM-001: ETag Change Detection
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has stored ETag, server returns different ETag |
| **Action** | Run tiered change detection |
| **Expected Result** | Change detected at Tier 1 |
| **Verification** | `detection_method = "etag"` in CheckResult |

#### TC-UM-002: Last-Modified Change Detection
| Attribute | Value |
|-----------|-------|
| **Precondition** | ETag matches, Last-Modified header is newer |
| **Action** | Run tiered change detection |
| **Expected Result** | Change detected at Tier 2 |
| **Verification** | `detection_method = "last_modified"` in CheckResult |

#### TC-UM-003: Content Hash Change Detection
| Attribute | Value |
|-----------|-------|
| **Precondition** | Headers unchanged, content hash differs |
| **Action** | Run tiered change detection (force Tier 3) |
| **Expected Result** | Change detected at Tier 3 |
| **Verification** | `detection_method = "content_hash"` in CheckResult |

#### TC-UM-004: Unchanged Source - Metadata Update
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source content unchanged |
| **Action** | Run monitor check |
| **Expected Result** | `last_checked` updated, no Issue created |
| **Verification** | Source registry shows updated timestamp |

#### TC-UM-005: Create Content Update Issue
| Attribute | Value |
|-----------|-------|
| **Precondition** | Content change detected |
| **Action** | Create update Issue |
| **Expected Result** | Issue has `content-update` label and change summary table |
| **Verification** | Issue body contains `<!-- monitor-update:{url_hash}:{content_hash} -->` |

#### TC-UM-006: Tiered Detection Short-Circuit
| Attribute | Value |
|-----------|-------|
| **Precondition** | ETag matches stored value |
| **Action** | Run check |
| **Expected Result** | Skip Tier 2 and Tier 3 checks |
| **Verification** | No GET request made, only HEAD |

#### TC-UM-007: Duplicate Update Prevention
| Attribute | Value |
|-----------|-------|
| **Precondition** | Update Issue exists for current content hash |
| **Action** | Run monitor check again |
| **Expected Result** | No duplicate Issue created |
| **Verification** | Search for marker returns existing Issue |

---

### 3.3 Failure Handling

#### TC-FH-001: Increment Failure Counter
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `check_failures = 2` |
| **Action** | HTTP request fails (timeout) |
| **Expected Result** | `check_failures` incremented to 3 |
| **Verification** | Source registry reflects new count |

#### TC-FH-002: Reset Failure Counter on Success
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `check_failures = 3` |
| **Action** | HTTP request succeeds |
| **Expected Result** | `check_failures` reset to 0 |
| **Verification** | Source registry shows 0 failures |

#### TC-FH-003: Mark Degraded After Max Failures
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `check_failures = 4` |
| **Action** | 5th consecutive failure occurs |
| **Expected Result** | Source status changed to `degraded` |
| **Verification** | `status = "degraded"` in registry |

#### TC-FH-004: Create Access Problem Discussion
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source reaches degraded status |
| **Action** | Report access problem |
| **Expected Result** | GitHub Discussion created in appropriate category |
| **Verification** | Discussion contains source details and failure history |

---

### 3.4 Backoff and Scheduling

#### TC-BS-001: Exponential Backoff Calculation
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `check_failures = 3` |
| **Action** | Calculate next check time |
| **Expected Result** | `next_check_after = now + (base_interval * 2^3)` |
| **Verification** | Backoff multiplier is 8x |

#### TC-BS-002: Backoff Cap at Maximum
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has `check_failures = 10` |
| **Action** | Calculate next check time |
| **Expected Result** | Backoff capped at 7 days maximum |
| **Verification** | `next_check_after` ≤ now + 7 days |

#### TC-BS-003: Sources Due for Check
| Attribute | Value |
|-----------|-------|
| **Precondition** | 3 sources with `next_check_after` in past, 2 in future |
| **Action** | Call `get_sources_due()` |
| **Expected Result** | Returns only 3 sources due |
| **Verification** | List length = 3, all have past timestamps |

#### TC-BS-004: Priority Sorting
| Attribute | Value |
|-----------|-------|
| **Precondition** | Mixed sources: 1 primary, 2 derived, 1 reference |
| **Action** | Sort for processing |
| **Expected Result** | Order: primary → derived → reference |
| **Verification** | List ordered by source_type priority |

#### TC-BS-005: Skip Sources in Backoff
| Attribute | Value |
|-----------|-------|
| **Precondition** | All sources have `next_check_after` in future |
| **Action** | Run monitor workflow |
| **Expected Result** | Exit early with "no sources due" message |
| **Verification** | No HTTP requests made |

---

### 3.5 Rate Limiting

#### TC-RL-001: Same-Domain Delay
| Attribute | Value |
|-----------|-------|
| **Precondition** | 3 sources from same domain queued |
| **Action** | Process all sources |
| **Expected Result** | ≥1 second delay between requests |
| **Verification** | Request timestamps differ by ≥1s |

#### TC-RL-002: Cross-Domain Parallel
| Attribute | Value |
|-----------|-------|
| **Precondition** | Sources from 3 different domains |
| **Action** | Process sources |
| **Expected Result** | No artificial delay required between domains |
| **Verification** | Can process at normal speed |

#### TC-RL-003: Domain Grouping
| Attribute | Value |
|-----------|-------|
| **Precondition** | 6 sources: 2 from A.com, 2 from B.org, 2 from C.gov |
| **Action** | Sort for processing |
| **Expected Result** | Same-domain sources grouped consecutively |
| **Verification** | Processing order groups domains together |

---

### 3.6 Edge Cases

#### TC-EC-001: Missing ETag Header
| Attribute | Value |
|-----------|-------|
| **Precondition** | Server doesn't return ETag |
| **Action** | Run tiered detection |
| **Expected Result** | Skip Tier 1, proceed to Tier 2 |
| **Verification** | No error, detection continues |

#### TC-EC-002: Missing Last-Modified Header
| Attribute | Value |
|-----------|-------|
| **Precondition** | Server returns neither ETag nor Last-Modified |
| **Action** | Run tiered detection |
| **Expected Result** | Skip to Tier 3 (content hash) |
| **Verification** | Full GET request made for hash |

#### TC-EC-003: HTTP Redirect Handling
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source URL returns 301/302 redirect |
| **Action** | Run check |
| **Expected Result** | Follow redirect, use final URL for comparison |
| **Verification** | Content hash computed from final URL content |

#### TC-EC-004: Timeout Handling
| Attribute | Value |
|-----------|-------|
| **Precondition** | Server takes >10s to respond |
| **Action** | Run check |
| **Expected Result** | CheckResult status = "error", failure incremented |
| **Verification** | No crash, graceful error handling |

#### TC-EC-005: SSL Certificate Error
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source has invalid SSL certificate |
| **Action** | Run check |
| **Expected Result** | Error captured, source marked for review |
| **Verification** | Error message indicates SSL issue |

#### TC-EC-006: Empty Source Registry
| Attribute | Value |
|-----------|-------|
| **Precondition** | No sources in registry |
| **Action** | Run monitor workflow |
| **Expected Result** | Exit gracefully with informative message |
| **Verification** | No errors, workflow completes successfully |

#### TC-EC-007: Mixed Initial and Update Sources
| Attribute | Value |
|-----------|-------|
| **Precondition** | 2 sources need initial, 3 sources need update check |
| **Action** | Run single workflow |
| **Expected Result** | Both modes processed correctly in one run |
| **Verification** | Initial Issues + Update Issues created as needed |

#### TC-EC-008: Transition from Initial to Update Mode
| Attribute | Value |
|-----------|-------|
| **Precondition** | Source just acquired, `last_content_hash` now set |
| **Action** | Run next monitor check |
| **Expected Result** | Source enters update mode, tiered detection used |
| **Verification** | HEAD request made instead of immediate Issue |

---

## 4. Integration Test Scenarios

### 4.1 End-to-End Workflow: New Source

```
1. Source Curator approves new source
2. Source added to registry with last_content_hash = None
3. Monitor Agent runs (scheduled or manual)
4. Monitor detects source needs initial acquisition
5. Monitor creates GitHub Issue with initial-acquisition template
6. Issue has correct labels and dedup marker
7. Source registry updated with last_checked timestamp
```

**Verification Points:**
- [ ] Issue appears in repository
- [ ] Issue body matches template
- [ ] Labels: `initial-acquisition`, `{urgency}-priority`
- [ ] Marker: `<!-- monitor-initial:{hash} -->`
- [ ] Registry: `last_checked` set

### 4.2 End-to-End Workflow: Content Update

```
1. Source exists with previous acquisition (last_content_hash set)
2. External source content changes
3. Monitor Agent runs
4. Tier 1: ETag differs → proceed
5. Tier 2: Last-Modified newer → proceed  
6. Tier 3: Content hash differs → confirmed change
7. Monitor creates GitHub Issue with content-update template
8. Source registry updated with new hash and timestamp
```

**Verification Points:**
- [ ] HEAD request made first
- [ ] GET request made only after change indicated
- [ ] Issue created with change summary table
- [ ] Labels: `content-update`, `{urgency}-priority`
- [ ] Marker: `<!-- monitor-update:{url_hash}:{content_hash} -->`

### 4.3 End-to-End Workflow: No Change

```
1. Source exists with previous acquisition
2. External source content unchanged
3. Monitor Agent runs
4. Tier 1: ETag matches → short-circuit
5. No Issue created
6. Source registry: last_checked updated, next_check_after set
```

**Verification Points:**
- [ ] Only HEAD request made
- [ ] No Issue created
- [ ] `last_checked` updated
- [ ] `next_check_after` = now + base_interval

### 4.4 End-to-End Workflow: Persistent Failure

```
1. Source becomes inaccessible (server down)
2. Monitor runs 5 times over period
3. Each run: check fails, check_failures increments
4. On 5th failure: source marked degraded
5. Discussion created for access problem
6. Future checks use longer backoff
```

**Verification Points:**
- [ ] `check_failures` increments each run
- [ ] After 5: `status = "degraded"`
- [ ] Discussion created in repo
- [ ] Backoff interval increases exponentially

---

## 5. Performance Testing

### 5.1 Scalability Tests

| Test | Sources | Expected Time | Threshold |
|------|---------|---------------|-----------|
| Small batch | 10 sources | <30s | Pass if <30s |
| Medium batch | 50 sources | <3m | Pass if <3m |
| Large batch | 200 sources | <15m | Pass if <15m |

### 5.2 Rate Limit Compliance

| Test | Scenario | Expected Behavior |
|------|----------|-------------------|
| Same domain | 10 sources from one domain | ~10s total (1s/request) |
| Mixed domains | 10 sources, 5 domains | ~5s total (parallel domains) |

### 5.3 Memory Usage

| Metric | Threshold |
|--------|-----------|
| Peak memory | <256MB for 200 sources |
| Registry load | <50MB for 1000 sources |

---

## 6. Acceptance Criteria

### Functional Requirements

- [ ] Initial acquisition mode correctly identifies sources with no prior content hash
- [ ] Update monitoring mode uses tiered detection hierarchy
- [ ] GitHub Issues created with correct templates for both modes
- [ ] Deduplication prevents duplicate Issues via marker search
- [ ] Source metadata updated after every check (success or failure)
- [ ] Failure counter tracks consecutive failures accurately
- [ ] Sources marked degraded after 5 consecutive failures
- [ ] Access problems reported as Discussions
- [ ] Rate limiting enforced for same-domain requests
- [ ] Backoff calculation follows exponential formula with cap

### Non-Functional Requirements

- [ ] Workflow completes within GitHub Actions timeout (6 hours)
- [ ] No unhandled exceptions during normal operation
- [ ] Graceful degradation when GitHub API rate limited
- [ ] Logging provides sufficient detail for debugging
- [ ] All HTTP errors handled without crashes

### Documentation Requirements

- [ ] Mission YAML documented in `config/missions/`
- [ ] Tool docstrings complete and accurate
- [ ] Workflow YAML includes inline documentation
- [ ] Test coverage report available

---

## 7. Test Data Requirements

### Mock Source Registry

```json
{
  "sources": [
    {
      "url": "https://example.gov/reports",
      "name": "Example Reports",
      "source_type": "primary",
      "last_content_hash": null,
      "status": "active"
    },
    {
      "url": "https://news.example.org/feed",
      "name": "Example News",
      "source_type": "derived", 
      "last_content_hash": "abc123...",
      "last_etag": "W/\"etag-value\"",
      "status": "active"
    }
  ]
}
```

### Mock HTTP Responses

| Scenario | Status | Headers | Body |
|----------|--------|---------|------|
| Unchanged | 200 | ETag matches | Same content |
| ETag changed | 200 | New ETag | Same content |
| Content changed | 200 | New ETag + Last-Modified | Different content |
| Server error | 500 | - | Error page |
| Timeout | - | - | No response |
| Redirect | 301 | Location header | - |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GitHub API rate limiting | Medium | High | Implement caching, batch requests |
| Source servers blocking | Low | Medium | Rotate user agents, respect robots.txt |
| Duplicate Issues | Low | High | Marker-based deduplication tested thoroughly |
| Missed content changes | Low | High | Content hash as final verification tier |
| Long-running workflow timeout | Low | Medium | Batch processing, checkpointing |

---

## 9. Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| QA Lead | | | |
| Product Owner | | | |

---

*Document Version: 1.0*  
*Last Updated: 2025-12-27*
