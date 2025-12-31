# Research Agents: Responsibilities and Testing Guide

**Document Version**: 1.0  
**Date**: December 30, 2025  
**Status**: Ready for QA Review

---

## Executive Summary

This document provides a comprehensive comparison of the **Monitor Agent** and **Crawler Agent**, explaining their distinct responsibilities, interaction patterns, and test coverage. Both agents are feature-complete and deployed to staging.

### Quick Reference

| Agent | Primary Purpose | Trigger | Output |
|-------|----------------|---------|--------|
| **Monitor** | Detect content changes | Scheduled (every 6 hours) | GitHub Issues (acquisition tasks) |
| **Crawler** | Acquire site-wide content | Manual dispatch or scheduled resume | Stored pages + persistent state |

---

## Agent Responsibilities

### Monitor Agent

**Mission**: Lightweight change detection and acquisition queuing

**What it Does**:
- 🔍 **Detects** content changes using tiered bandwidth-efficient strategy
- 📋 **Queues** changed sources by creating GitHub Issues
- ⏱️ **Schedules** checks using intelligent politeness delays
- 🚦 **Tracks** access failures and triggers alerts

**What it Does NOT Do**:
- ❌ Does NOT fetch full page content (except for tier-3 hash comparison)
- ❌ Does NOT store acquired content
- ❌ Does NOT discover new pages via link extraction
- ❌ Does NOT crawl multiple pages per source

**Key Principle**: The Monitor is a **detector**, not an **acquirer**. It answers "Has this changed?" not "What is the content?"

---

### Crawler Agent

**Mission**: Site-wide content acquisition within defined boundaries

**What it Does**:
- 🌐 **Discovers** all pages under a source URL via recursive link extraction
- 🔽 **Acquires** page content with politeness constraints
- 💾 **Stores** content in sharded directory structure
- 📊 **Tracks** crawl progress for multi-session resumption
- 🎯 **Enforces** strict URL scope boundaries (path/host/domain)

**What it Does NOT Do**:
- ❌ Does NOT detect content changes (assumes all discovered pages should be acquired)
- ❌ Does NOT monitor sources on a schedule
- ❌ Does NOT create Issues for individual pages
- ❌ Does NOT operate automatically (requires manual dispatch)

**Key Principle**: The Crawler is an **acquirer**, not a **monitor**. It answers "What content exists?" not "Has it changed?"

---

## Interaction Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                    TYPICAL WORKFLOW                          │
└──────────────────────────────────────────────────────────────┘

1. SOURCE APPROVAL (Source Curator)
   ↓
   User approves source via GitHub Discussion
   Source added to registry with status="active"

2. INITIAL DETECTION (Monitor Agent - Scheduled)
   ↓
   Monitor finds source with last_content_hash=None
   Creates Issue: "Initial Acquisition: {source_name}"
   
3. DECISION POINT: Single Page vs. Site-Wide
   
   ┌─────────────────────────┬─────────────────────────┐
   │  SINGLE PAGE SOURCE     │   MULTI-PAGE SITE       │
   ├─────────────────────────┼─────────────────────────┤
   │  Acquisition Agent      │   Crawler Agent         │
   │  (not in scope)         │   (manual dispatch)     │
   │                         │                         │
   │  Fetches single URL     │   Crawls all pages      │
   │  Stores content         │   Stores all content    │
   │  Sets content_hash      │   Updates source entry  │
   └─────────────────────────┴─────────────────────────┘

4. ONGOING MONITORING (Monitor Agent - Scheduled)
   ↓
   Monitor checks source (tiered detection)
   If changed: Creates Issue "Content Update: {source_name}"
   If failed: Creates Issue "Access Problem: {source_name}"

5. RE-CRAWL (Crawler Agent - Manual)
   ↓
   User dispatches crawler workflow
   Crawler resumes from saved state OR restarts
   Updates existing content, discovers new pages
```

---

## Scope Boundaries

### Monitor Agent Scope

**Input**: Single source URL  
**Processing**: 1 HTTP request per check (HEAD or GET)  
**Output**: 1 Issue per detected change

| Mode | Input | Tiered Detection | Output |
|------|-------|------------------|--------|
| Initial | `last_content_hash=None` | ❌ Skipped | Issue: `initial-acquisition` |
| Update | `last_content_hash` exists | ✅ Tier 1→2→3 | Issue: `content-update` (if changed) |

**Example**:
```yaml
Source: https://www.denverbroncos.com/team/roster
Monitor Action: 
  - HEAD request to exact URL
  - Compare ETag or Last-Modified
  - If changed, GET request for hash comparison
  - Create Issue if hash differs
```

---

### Crawler Agent Scope

**Input**: Source URL + Scope constraint  
**Processing**: N HTTP requests (all pages under scope)  
**Output**: N stored pages + crawl state

| Scope Type | Example Source | Valid Pages | Invalid Pages |
|------------|---------------|-------------|---------------|
| `path` | `https://example.com/docs/v2/` | `/docs/v2/guide`<br/>`/docs/v2/api/ref` | `/docs/v1/`<br/>`/blog/` |
| `host` | `https://docs.example.com/` | Any path on `docs.example.com` | `api.example.com`<br/>`www.example.com` |
| `domain` | `https://example.com/` | `docs.example.com`<br/>`api.example.com`<br/>`example.com` | `other-site.com` |

**Example**:
```yaml
Source: https://www.denverbroncos.com/team/roster
Scope: path
Crawler Action:
  - GET /team/roster (start)
  - Extract links: [/team/roster/offense, /team/roster/defense, /news/article]
  - Filter by scope: [/team/roster/offense, /team/roster/defense]  ← /news/article rejected
  - GET /team/roster/offense
  - GET /team/roster/defense
  - Store all 3 pages
```

---

## Data Models Comparison

### Monitor Agent Data

**Primary Model**: `SourceEntry` (in `knowledge-graph/sources/`)

Key monitoring fields:
```python
last_content_hash: str | None      # SHA-256 of last acquired content
last_etag: str | None              # Last ETag header
last_modified_header: str | None   # Last Last-Modified header
last_checked: datetime | None      # When last checked
check_failures: int                # Consecutive failure count
next_check_after: datetime | None  # Earliest next check time
```

**Outputs**: GitHub Issues (no persistent files except source metadata updates)

---

### Crawler Agent Data

**Primary Models**:

1. **CrawlState** (in `knowledge-graph/crawls/{source_hash}/`)
   - Frontier (URLs to visit)
   - Visited hashes (deduplication)
   - Statistics (discovered, in-scope, out-of-scope, failed)
   - Configuration (max_pages, max_depth, scope)

2. **PageRegistry** (in `knowledge-graph/crawls/{source_hash}/pages_*.json`)
   - Batch files (500 pages each)
   - Page metadata (url, status, content_hash, title, links)

3. **Stored Content** (in `evidence/parsed/{domain}/{source_hash}/{shard}/`)
   - Sharded by content hash prefix (0-f)
   - Markdown content files
   - Metadata JSON files

**Outputs**: Persistent crawl state, page registry, stored content files

---

## Testing Coverage

### Monitor Agent Tests

**Total**: 35 unit tests + 21 integration tests = **56 tests**

#### Test Categories

| Category | Test Count | File |
|----------|-----------|------|
| Check Result | 3 | `test_source_monitoring.py` |
| Change Detection | 5 | `test_source_monitoring.py` |
| Politeness Policy | 11 | `test_source_monitoring.py` |
| Source Selection | 5 | `test_source_monitoring.py` |
| Tiered Detection | 6 | `test_source_monitoring.py` |
| Error Handling | 5 | `test_source_monitoring.py` |
| Toolkit Integration | 21 | `test_monitor_toolkit.py`, `test_monitor_integration.py` |

#### Key Test Scenarios

**Change Detection**:
- ✅ Initial source (no hash) returns `initial` status
- ✅ Unchanged ETag returns `unchanged`
- ✅ Changed ETag triggers hash check
- ✅ Unchanged hash returns `unchanged`
- ✅ Changed hash returns `changed`

**Politeness**:
- ✅ Success uses base check interval
- ✅ Failure applies exponential backoff
- ✅ Backoff caps at maximum
- ✅ Primary sources get high priority
- ✅ Recent sources get priority boost

**Error Handling**:
- ✅ Timeout returns error status
- ✅ SSL error returns error status
- ✅ Connection error returns error status

---

### Crawler Agent Tests

**Total**: 60 unit tests + 21 integration tests = **81 tests**

#### Test Categories

| Category | Test Count | File |
|----------|-----------|------|
| Hashing Utilities | 9 | `test_crawler_toolkit.py` |
| Tool Registration | 2 | `test_crawler_toolkit.py` |
| State Management | 10 | `test_crawler_toolkit.py` |
| Frontier Operations | 6 | `test_crawler_toolkit.py` |
| Scope Filtering | 3 | `test_crawler_toolkit.py` |
| Robots.txt | 4 | `test_crawler_toolkit.py` |
| Link Extraction | 4 | `test_crawler_toolkit.py` |
| Content Storage | 3 | `test_crawler_toolkit.py` |
| Page Registry | 3 | `test_crawler_toolkit.py` |
| Visit Tracking | 4 | `test_crawler_toolkit.py` |
| End-to-End Workflows | 2 | `test_crawler_toolkit.py` |
| URL Scope Validation | 69 | `test_url_scope.py` |
| Link Extraction | 52 | `test_link_extractor.py` |
| Crawl State | 34 | `test_crawl_state.py` |
| Page Registry | 28 | `test_page_registry.py` |
| Integration | 21 | `test_crawler_integration.py` |

#### Key Test Scenarios

**Scope Enforcement**:
- ✅ Path scope: exact match and subpaths
- ✅ Path scope: rejects siblings and parents
- ✅ Host scope: same host only
- ✅ Domain scope: includes subdomains
- ✅ All scopes: reject external domains

**Crawl Workflow**:
- ✅ Single page crawl (path scope)
- ✅ Directory crawl (multiple pages)
- ✅ Host-wide crawl
- ✅ Resume from saved state
- ✅ Respect max_pages limit
- ✅ Respect max_depth limit
- ✅ Deduplication (same URL not fetched twice)
- ✅ Out-of-scope URLs logged but not fetched

**Robots.txt**:
- ✅ Parse Disallow directives
- ✅ Filter disallowed URLs
- ✅ Respect crawl delays
- ✅ Handle missing robots.txt

**Link Extraction**:
- ✅ Absolute URLs extracted correctly
- ✅ Relative URLs resolved to absolute
- ✅ URL fragments stripped
- ✅ JavaScript/mailto links ignored
- ✅ Empty href handled gracefully
- ✅ Anchor text captured

---

## QA Test Plan

### Monitor Agent QA Tests

#### Test 1: Initial Acquisition Detection
**Preconditions**: Source with `status=active`, `last_content_hash=None`

**Steps**:
1. Trigger Monitor workflow (manual dispatch)
2. Check workflow logs for source detection
3. Verify Issue created with label `initial-acquisition`
4. Verify Issue contains source URL and metadata

**Expected Result**: Issue created, no HTTP requests made to source

---

#### Test 2: No Change Detection (ETag)
**Preconditions**: Source with existing `last_etag`

**Steps**:
1. Mock source to return same ETag
2. Trigger Monitor workflow
3. Check workflow logs for "unchanged" status

**Expected Result**: No Issue created, only HEAD request made

---

#### Test 3: Change Detection (ETag + Hash)
**Preconditions**: Source with existing `last_etag`

**Steps**:
1. Mock source to return new ETag
2. Mock source to return new content hash
3. Trigger Monitor workflow
4. Verify Issue created with label `content-update`

**Expected Result**: Issue created, HEAD + GET requests made

---

#### Test 4: Access Failure Handling
**Preconditions**: Source with reachable URL

**Steps**:
1. Mock source to return 500 error
2. Trigger Monitor workflow
3. Check source entry: `check_failures` incremented
4. Repeat 5 times
5. Verify Issue created with label `access-problem`

**Expected Result**: Issue created after 5 failures

---

#### Test 5: Politeness Delays
**Preconditions**: Multiple sources on same domain

**Steps**:
1. Create 3 sources: `example.com/page1`, `example.com/page2`, `example.com/page3`
2. Trigger Monitor workflow
3. Check workflow logs for request timing

**Expected Result**: Minimum 1 second delay between requests to same domain

---

### Crawler Agent QA Tests

#### Test 6: Path Scope Enforcement
**Preconditions**: Source `https://example.com/docs/`

**Steps**:
1. Mock pages:
   - `/docs/` contains links: [/docs/guide, /docs/api, /blog/post]
   - `/docs/guide` exists
   - `/docs/api` exists
   - `/blog/post` exists
2. Trigger Crawler with `scope=path`
3. Check crawl state statistics

**Expected Result**:
- `visited_count = 3` (/, /guide, /api)
- `out_of_scope_count = 1` (/blog/post)
- `/blog/post` NOT fetched

---

#### Test 7: Host Scope Enforcement
**Preconditions**: Source `https://docs.example.com/`

**Steps**:
1. Mock pages:
   - `/` contains links: [/guide, https://api.example.com/ref, https://external.com/link]
   - `/guide` exists
2. Trigger Crawler with `scope=host`
3. Check crawl state statistics

**Expected Result**:
- `visited_count = 2` (/, /guide)
- `out_of_scope_count = 2` (api.example.com, external.com)

---

#### Test 8: Domain Scope Enforcement
**Preconditions**: Source `https://example.com/`

**Steps**:
1. Mock pages:
   - `/` contains links: [/page, https://docs.example.com/, https://api.example.com/, https://other.com/]
2. Trigger Crawler with `scope=domain`
3. Check crawl state statistics

**Expected Result**:
- `visited_count = 4` (www, docs, api subdomains)
- `out_of_scope_count = 1` (other.com)

---

#### Test 9: Robots.txt Compliance
**Preconditions**: Source with `robots.txt` containing `Disallow: /admin`

**Steps**:
1. Mock source with `/admin` link on homepage
2. Trigger Crawler
3. Check crawl state and page registry

**Expected Result**:
- `/admin` marked as `skipped` (not `fetched` or `failed`)
- `skipped_count = 1`

---

#### Test 10: Crawl Resumption
**Preconditions**: Crawl with 100 pages discovered, `max_pages_per_run=50`

**Steps**:
1. Trigger Crawler (Run 1)
2. Verify `visited_count = 50`, `frontier` has 50 URLs
3. Trigger Crawler (Run 2)
4. Verify `visited_count = 100`, `frontier` empty

**Expected Result**: Crawl completes across 2 runs, no duplicate fetches

---

#### Test 11: Max Depth Limit
**Preconditions**: Source with 15-level deep link chain

**Steps**:
1. Mock pages: / → /l1 → /l2 → ... → /l15
2. Trigger Crawler with `max_depth=10`
3. Check crawl state

**Expected Result**:
- `visited_count = 11` (depth 0-10)
- Pages at depth 11+ not added to frontier

---

#### Test 12: Deduplication
**Preconditions**: Source with multiple pages linking to same URL

**Steps**:
1. Mock pages:
   - `/page1` links to `/shared`
   - `/page2` links to `/shared`
   - `/page3` links to `/shared`
2. Trigger Crawler
3. Check HTTP request logs

**Expected Result**:
- `/shared` fetched exactly once
- All 4 pages in page registry

---

#### Test 13: Sharded Storage
**Preconditions**: Crawl with 200 pages

**Steps**:
1. Trigger Crawler
2. Check storage directory structure

**Expected Result**:
- Files distributed across shards `0/` to `f/`
- No shard directory exceeds 100 files
- All pages have `content.md` and `metadata.json`

---

#### Test 14: Frontier Overflow
**Preconditions**: Source with >1000 discovered URLs

**Steps**:
1. Mock source with 1500 links
2. Trigger Crawler
3. Check crawl state file and overflow file

**Expected Result**:
- `frontier` array has max 1000 URLs
- `frontier_overflow_count = 500`
- `frontier_overflow.jsonl` exists with 500 URLs

---

#### Test 15: Politeness Delay
**Preconditions**: Source with 10 pages

**Steps**:
1. Trigger Crawler
2. Measure time between requests

**Expected Result**:
- Minimum 1.0 second delay between consecutive requests
- Total runtime ≥ 9 seconds (for 10 pages)

---

## Agent Interaction Test

#### Test 16: Monitor → Crawler Handoff
**Preconditions**: New multi-page source approved

**Steps**:
1. Approve source via Source Curator
2. Wait for Monitor scheduled run (or trigger manually)
3. Verify Monitor creates `initial-acquisition` Issue
4. Manually dispatch Crawler with source URL
5. Verify Crawler completes crawl
6. Verify source entry updated with:
   - `last_content_hash` set
   - `total_pages_acquired` > 0
7. Wait for next Monitor scheduled run
8. Verify Monitor performs tiered detection (not initial)

**Expected Result**: Complete handoff from initial detection → crawl → ongoing monitoring

---

## Performance Benchmarks

### Monitor Agent

| Metric | Target | Notes |
|--------|--------|-------|
| Check latency (tier 1) | < 2s | HEAD request only |
| Check latency (tier 3) | < 10s | Full GET + hash |
| Throughput | 100+ sources/run | Parallel checks |
| Failure rate | < 1% | Network errors |

### Crawler Agent

| Metric | Target | Notes |
|--------|--------|-------|
| Fetch rate | 60 pages/min | 1s politeness delay |
| Deduplication rate | 100% | No duplicate fetches |
| Scope accuracy | 100% | No out-of-scope fetches |
| State persistence | 100% | All crawls resumable |
| Storage efficiency | < 1MB/page | Markdown format |

---

## Known Limitations

### Monitor Agent
- Does not validate link integrity (assumes source URL is valid)
- Does not follow redirects (treats redirect as access problem after 5 failures)
- Does not handle authentication (requires public sources)
- Tier-3 hash check downloads full content (can be bandwidth-heavy for large files)

### Crawler Agent
- Does not execute JavaScript (static HTML only)
- Does not handle dynamic content (AJAX, infinite scroll)
- Does not extract content from PDFs linked on pages (requires separate acquisition)
- Does not crawl password-protected areas
- Maximum 16 shards (0-f) may still hit file limits for very large crawls

---

## Troubleshooting Guide

### Monitor Agent Issues

**Issue**: No Issues created despite source changes  
**Check**:
1. Source `status` is `active` (not `pending_review`)
2. Source `next_check_after` is past (or null)
3. Workflow logs show source in `get_sources_due_for_check()` output

**Issue**: Duplicate `initial-acquisition` Issues  
**Check**:
1. Source `last_content_hash` should be set after first acquisition
2. Acquisition workflow must update source entry

---

### Crawler Agent Issues

**Issue**: Out-of-scope pages fetched  
**Check**:
1. Crawl state `scope` field matches input
2. URL normalization removing trailing slashes
3. Review `filter_urls_by_scope` tool calls in logs

**Issue**: Crawl not resuming across runs  
**Check**:
1. Crawl state file exists: `knowledge-graph/crawls/{source_hash}/state.yaml`
2. `force_restart=false` in workflow input
3. Workflow committed state changes before exit

**Issue**: Missing pages in registry  
**Check**:
1. Page added to `visited_hashes` set
2. `update_page_registry` tool called for URL
3. Batch file committed to git

---

## Approval Checklist

### For Product Manager

- [ ] Understand distinction between Monitor (detector) and Crawler (acquirer)
- [ ] Review interaction pattern and handoff workflow
- [ ] Confirm scope boundaries align with product requirements
- [ ] Validate politeness delays meet ethical crawling standards
- [ ] Review known limitations and confirm acceptable for MVP

### For QA Engineer

- [ ] Execute all 16 QA test cases in staging environment
- [ ] Verify test coverage percentages (Monitor: 95%+, Crawler: 97%+)
- [ ] Run performance benchmarks and compare to targets
- [ ] Test failure scenarios (network errors, invalid URLs, timeouts)
- [ ] Validate data persistence across workflow runs

---

## Deployment Status

| Component | Status | Version | Environment |
|-----------|--------|---------|-------------|
| Monitor Agent | ✅ Deployed | 1.0 | Staging |
| Crawler Agent | ✅ Deployed | 1.0 | Staging |
| Monitor Workflow | ✅ Active | `3-op-monitor-sources.yml` | Staging |
| Crawler Workflow | ✅ Active | `4-op-crawl-source.yml` | Staging |

**Next Steps**: Production deployment pending QA sign-off

---

*Document prepared for QA review cycle - December 30, 2025*
