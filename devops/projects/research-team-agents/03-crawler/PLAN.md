# Site Crawler Agent - Planning Document

## Agent Overview

**Mission:** Traverse all accessible pages under a source URL and acquire content for the knowledge graph.

**Status:** ✅ Complete

**Prerequisite:** Monitor Agent (02-monitor) - provides source registry and change detection

---

## Implementation Progress

> **Last Updated:** 2025-12-30

### Phase 1: Core Data Models ✅ COMPLETE

| Deliverable | Status | Notes |
|-------------|--------|-------|
| `src/knowledge/crawl_state.py` | ✅ Done | CrawlState dataclass with persistence |
| `src/knowledge/page_registry.py` | ✅ Done | PageEntry with batch storage |
| `src/knowledge/storage.py` extensions | ✅ Done | SourceEntry crawl fields added |
| `tests/knowledge/test_crawl_state.py` | ✅ Done | 34 tests passing |
| `tests/knowledge/test_page_registry.py` | ✅ Done | 28 tests passing |

**Test Results:** 62 new tests, all passing

### Phase 2: URL Scope & Link Extraction ✅ COMPLETE

| Deliverable | Status | Notes |
|-------------|--------|-------|
| `src/parsing/url_scope.py` | ✅ Done | Scope validation for path/host/domain |
| `src/parsing/link_extractor.py` | ✅ Done | HTML link extraction with normalization |
| `src/parsing/robots.py` | ✅ Done | Robots.txt parsing and compliance |
| `tests/parsing/test_url_scope.py` | ✅ Done | 69 tests passing |
| `tests/parsing/test_link_extractor.py` | ✅ Done | 52 tests passing |

**Test Results:** 121 new tests, all passing

### Phase 3: Crawler Toolkit ✅ COMPLETE

| Deliverable | Status | Notes |
|-------------|--------|-------|
| `src/orchestration/toolkit/crawler.py` | ✅ Done | 12 tools registered |
| `tests/orchestration/test_crawler_toolkit.py` | ✅ Done | 60 tests passing |
| `src/parsing/url_scope.py` extensions | ✅ Done | Added filter_urls_by_scope() |

**Test Results:** 60 new tests, all passing

**Tools Implemented:**
- State Management: `load_crawl_state`, `save_crawl_state`, `get_crawl_statistics`
- Frontier: `get_frontier_urls`, `add_to_frontier`, `filter_urls_by_scope`
- Fetch/Extract: `check_robots_txt`, `extract_links`, `fetch_page`
- Storage: `store_page_content`, `update_page_registry`, `mark_url_visited`

### Phase 4: Mission & Workflow ✅ COMPLETE

| Deliverable | Status | Notes |
|-------------|--------|-------|
| `config/missions/crawl_source.yaml` | ✅ Done | Full mission with algorithm |
| `.github/workflows/4-op-crawl-source.yml` | ✅ Done | Manual dispatch with inputs |

### Phase 5: Integration & Testing ✅ COMPLETE

| Deliverable | Status | Notes |
|-------------|--------|-------|
| End-to-end tests | ✅ Done | 21 integration tests |
| Documentation | ✅ Done | docs/guides/crawler-agent.md |

**Test Results:** 21 integration tests, all passing

**Final Test Count:** 961 tests total, all passing

---

## Core Principle: URL Scope Constraint

> **All valid pages to crawl MUST be under the given source URL.**

The source URL defines the crawl boundary. This is a **strict containment rule**:

### Scope Examples

| Source URL | Valid Pages | Invalid Pages |
|------------|-------------|---------------|
| `https://www.denverbroncos.com` | `/team/roster`, `/news/article-1` | `https://nfl.com/...` |
| `https://www.denverbroncos.com/team/` | `/team/roster`, `/team/coaches` | `/news/...`, `/schedule/...` |
| `https://docs.example.com` | Any page on `docs.example.com` | `https://www.example.com/...` |
| `https://example.com/docs/v2/` | `/docs/v2/guide`, `/docs/v2/api/` | `/docs/v1/...`, `/blog/...` |

### Scope Types

```
┌─────────────────────────────────────────────────────────────────┐
│                     CRAWL SCOPE HIERARCHY                       │
└─────────────────────────────────────────────────────────────────┘

Source URL: https://www.denverbroncos.com/team/roster

┌─────────────────────────────────────────────────────────────────┐
│  SCOPE: "path" (DEFAULT - Most Restrictive)                    │
│                                                                 │
│  ✅ https://www.denverbroncos.com/team/roster                  │
│  ✅ https://www.denverbroncos.com/team/roster/offense          │
│  ✅ https://www.denverbroncos.com/team/roster/defense          │
│  ❌ https://www.denverbroncos.com/team/coaches                 │
│  ❌ https://www.denverbroncos.com/news/                        │
│  ❌ https://shop.denverbroncos.com/                            │
└─────────────────────────────────────────────────────────────────┘

Source URL: https://www.denverbroncos.com

┌─────────────────────────────────────────────────────────────────┐
│  SCOPE: "host" (Single Host)                                   │
│                                                                 │
│  ✅ https://www.denverbroncos.com/team/roster                  │
│  ✅ https://www.denverbroncos.com/news/article-1               │
│  ✅ https://www.denverbroncos.com/schedule                     │
│  ❌ https://shop.denverbroncos.com/                            │
│  ❌ https://denverbroncos.com/ (different host, no www)        │
└─────────────────────────────────────────────────────────────────┘

Source URL: https://www.denverbroncos.com

┌─────────────────────────────────────────────────────────────────┐
│  SCOPE: "domain" (All Subdomains - Least Restrictive)          │
│                                                                 │
│  ✅ https://www.denverbroncos.com/team/roster                  │
│  ✅ https://shop.denverbroncos.com/jerseys                     │
│  ✅ https://tickets.denverbroncos.com/                         │
│  ✅ https://denverbroncos.com/                                 │
│  ❌ https://nfl.com/teams/broncos                              │
└─────────────────────────────────────────────────────────────────┘
```

### Scope Validation Logic

```python
def is_url_under_source(url: str, source_url: str, scope: str) -> bool:
    """
    Determine if a URL is within the crawl boundary of the source URL.
    
    This is the CORE constraint of the crawler - no URL outside the
    source boundary should ever be fetched.
    """
    source = urlparse(source_url)
    target = urlparse(url)
    
    # Must be same scheme (http/https)
    if target.scheme != source.scheme:
        return False
    
    if scope == "path":
        # Most restrictive: same host AND path starts with source path
        if target.netloc != source.netloc:
            return False
        source_path = source.path.rstrip("/")
        target_path = target.path.rstrip("/")
        return target_path == source_path or target_path.startswith(source_path + "/")
    
    elif scope == "host":
        # Single host: exact hostname match
        return target.netloc == source.netloc
    
    elif scope == "domain":
        # All subdomains: base domain must match
        source_domain = extract_base_domain(source.netloc)
        target_domain = extract_base_domain(target.netloc)
        return target_domain == source_domain
    
    return False
```

---

## Responsibilities

1. **Discover** all pages accessible from the source URL via link extraction
2. **Filter** discovered URLs to only those within the source URL scope
3. **Fetch** page content respecting politeness constraints
4. **Store** content using sharded directory structure
5. **Track** crawl progress in resumable state
6. **Report** progress via GitHub Issues

## Quality Standards

- **Strict scope enforcement** - Never fetch URLs outside the source boundary
- **Politeness** - Minimum 1 second delay between requests to same host
- **Robots.txt compliance** - Respect crawl restrictions
- **Deduplication** - Never fetch the same URL twice
- **Resumability** - Crawl state persisted for workflow resume
- **Auditability** - All discovered/skipped/failed URLs logged

---

## Data Models

### 1. CrawlState

Tracks the state of a site-wide crawl across workflow runs:

```python
@dataclass
class CrawlState:
    """Persistent state for a site-wide crawl."""
    
    source_url: str                    # The source URL (crawl boundary root)
    source_hash: str                   # SHA-256 of source URL
    scope: str                         # "path" | "host" | "domain"
    
    # Status
    status: str                        # "pending" | "crawling" | "paused" | "completed"
    started_at: datetime | None
    last_activity: datetime | None
    completed_at: datetime | None
    
    # URL Frontier (URLs to visit)
    frontier: list[str]                # Active queue (kept in memory, max 1000)
    frontier_overflow_count: int       # Count of URLs in overflow file
    
    # Visited tracking
    visited_count: int                 # Total pages successfully fetched
    visited_hashes: set[str]           # URL hashes for deduplication
    
    # Statistics
    discovered_count: int              # Total URLs found via link extraction
    in_scope_count: int                # URLs that passed scope filter
    out_of_scope_count: int            # URLs rejected by scope filter
    skipped_count: int                 # URLs skipped (robots.txt, patterns)
    failed_count: int                  # Failed fetches
    
    # Configuration
    max_pages: int                     # Safety limit (default: 10000)
    max_depth: int                     # Max link depth from source (default: 10)
    exclude_patterns: list[str]        # fnmatch patterns to exclude
    
    # Storage
    content_root: str                  # Path to content storage
    registry_path: str                 # Path to page registry
```

### 2. PageEntry

Metadata for each discovered/fetched page:

```python
@dataclass
class PageEntry:
    """Metadata for a single crawled page."""
    
    url: str                           # Full URL
    url_hash: str                      # SHA-256 of URL (for dedup/filename)
    
    # Relationship to source
    source_url: str                    # The source URL this belongs to
    discovered_from: str | None        # URL that linked to this page
    link_depth: int                    # Hops from source URL
    
    # Status
    status: str                        # "pending" | "fetched" | "failed" | "skipped"
    discovered_at: datetime
    fetched_at: datetime | None
    
    # Fetch details
    http_status: int | None
    content_type: str | None
    error_message: str | None
    
    # Content (if fetched)
    content_hash: str | None           # SHA-256 of content
    content_path: str | None           # Relative path to stored content
    content_size: int | None           # Bytes
    extracted_chars: int | None        # Characters extracted
    
    # Page metadata
    title: str | None
    outgoing_links_count: int | None   # Links found on this page
    outgoing_links_in_scope: int | None  # Links within scope
```

### 3. SourceEntry Extensions

Add to existing `SourceEntry` in `src/knowledge/storage.py`:

```python
# Site-wide crawl configuration
is_crawlable: bool = False             # Enable site-wide crawling
crawl_scope: str = "path"              # "path" | "host" | "domain"
crawl_max_pages: int = 10000           # Max pages to acquire
crawl_max_depth: int = 10              # Max link depth

# Crawl state reference
crawl_state_path: str | None = None    # Path to CrawlState file

# Crawl statistics
total_pages_discovered: int = 0
total_pages_acquired: int = 0
last_crawl_started: datetime | None = None
last_crawl_completed: datetime | None = None
```

---

## Storage Layout

### Sharded Content Storage

To stay under GitHub's 1,000 files per directory limit:

```
evidence/
└── parsed/
    └── {domain}/                       # e.g., denverbroncos.com
        └── {source_path_hash}/         # Hash of source URL path
            ├── manifest.json           # Crawl manifest
            ├── 0/                      # Hash prefix shard (0-f)
            │   └── {content_hash}/
            │       ├── content.md
            │       └── metadata.json
            ├── 1/
            │   └── ...
            └── f/                      # 16 shards total
```

### Page Registry (Batched)

```
knowledge-graph/
└── crawls/
    └── {source_hash}/                  # Per-source crawl data
        ├── crawl_state.json            # CrawlState
        ├── frontier_overflow.jsonl     # Overflow URLs (if >1000)
        ├── registry.json               # Index of batch files
        ├── pages_0000.json             # Pages 0-499
        ├── pages_0001.json             # Pages 500-999
        └── ...
```

---

## Workflow Design

### Crawl Mission Configuration

`config/missions/crawl_source.yaml`:

```yaml
id: crawl_source
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-30
  summary_tooling: site-crawler

goal: |
  Crawl all accessible pages under the given source URL and store their content.
  
  CRITICAL CONSTRAINT: Only crawl URLs that are UNDER the source URL.
  - If source is a directory path, only crawl pages under that path
  - If source is a host, only crawl pages on that exact host
  - If source is a domain, only crawl pages on that domain (including subdomains)
  
  The `crawl_scope` parameter controls this behavior:
  - "path": Only URLs under the source path (DEFAULT, most restrictive)
  - "host": Only URLs on the same host
  - "domain": URLs on any subdomain of the base domain
  
  This mission is designed for resumable execution:
  1. Load or create CrawlState for the source
  2. Process URLs from the frontier (up to max_pages_per_run)
  3. For each URL: fetch, extract links, filter by scope, store content
  4. Save state and exit (next run continues from saved state)

constraints:
  - "NEVER fetch URLs outside the source URL scope"
  - "Validate every discovered URL against scope before adding to frontier"
  - "Respect robots.txt crawl restrictions"
  - "Minimum 1 second delay between requests to same host"
  - "Maximum 1000 pages per workflow run (for chunking)"
  - "Commit progress every 100 pages"
  - "Always save CrawlState before workflow exit"

success_criteria:
  - All in-scope pages discovered and fetched
  - Content stored in sharded directory structure
  - Page registry updated with all entries
  - CrawlState reflects accurate progress
  - No out-of-scope URLs fetched

inputs:
  source_url:
    description: "The source URL defining the crawl boundary"
    required: true
  crawl_scope:
    description: "Scope constraint: path, host, or domain"
    required: false
    default: "path"
  max_pages_per_run:
    description: "Maximum pages to process this run"
    required: false
    default: 1000
  force_restart:
    description: "Restart crawl from scratch (discard existing state)"
    required: false
    default: false

max_steps: 100
allowed_tools:
  - load_crawl_state
  - save_crawl_state
  - get_frontier_urls
  - add_to_frontier
  - fetch_page
  - extract_links
  - filter_urls_by_scope
  - store_page_content
  - update_page_registry
  - check_robots_txt
  - update_crawl_tracking_issue
  - get_source
  - update_source
requires_approval: false
```

### GitHub Actions Workflow

`.github/workflows/4-op-crawl-source.yml`:

```yaml
name: "Crawl Source Site"

on:
  workflow_dispatch:
    inputs:
      source_url:
        description: "Source URL to crawl (defines crawl boundary)"
        required: true
        type: string
      crawl_scope:
        description: "Crawl scope constraint"
        required: false
        type: choice
        options:
          - path
          - host
          - domain
        default: path
      max_pages_per_run:
        description: "Max pages this run (for chunking)"
        required: false
        type: number
        default: 1000
      force_restart:
        description: "Restart crawl from scratch"
        required: false
        type: boolean
        default: false

  # Auto-resume paused crawls every 4 hours
  schedule:
    - cron: "0 */4 * * *"

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 300  # 5 hours max
    
    permissions:
      contents: write
      issues: write
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      
      - run: pip install -r requirements.txt
      
      - name: Run Crawler Agent
        run: |
          python -m main agent \
            --mission crawl_source \
            --input source_url="${{ inputs.source_url || '' }}" \
            --input crawl_scope="${{ inputs.crawl_scope || 'path' }}" \
            --input max_pages_per_run=${{ inputs.max_pages_per_run || 1000 }} \
            --input force_restart=${{ inputs.force_restart || false }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
      
      - name: Commit crawl progress
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore(crawl): update crawl state and content [skip ci]"
          file_pattern: |
            evidence/parsed/**
            knowledge-graph/crawls/**
```

---

## Tool Requirements

### New Tools

| Tool | Description | Risk Level |
|------|-------------|------------|
| `load_crawl_state` | Load or create CrawlState for source | SAFE |
| `save_crawl_state` | Persist CrawlState to storage | SAFE |
| `get_frontier_urls` | Get next N URLs from frontier | SAFE |
| `add_to_frontier` | Add URLs to frontier (with scope check) | SAFE |
| `fetch_page` | Fetch single page content | SAFE |
| `extract_links` | Extract links from HTML | SAFE |
| `filter_urls_by_scope` | Filter URLs by source scope | SAFE |
| `store_page_content` | Store content in sharded structure | REVIEW |
| `update_page_registry` | Update page batch file | REVIEW |
| `check_robots_txt` | Check if URL is allowed by robots.txt | SAFE |
| `update_crawl_tracking_issue` | Update progress Issue | REVIEW |

### Existing Tools (Reuse)

| Tool | Module |
|------|--------|
| `get_source` | `toolkit/source_curator.py` |
| `update_source` | `toolkit/source_curator.py` |
| `create_issue` | `toolkit/github.py` |
| `add_comment` | `toolkit/github.py` |

---

## Implementation Modules

### New Modules

| Module | Purpose |
|--------|---------|
| `src/knowledge/crawl_state.py` | CrawlState dataclass and persistence |
| `src/knowledge/page_registry.py` | PageEntry and batch storage |
| `src/parsing/link_extractor.py` | Link extraction from HTML |
| `src/parsing/url_scope.py` | URL scope validation |
| `src/parsing/robots.py` | Robots.txt parsing and checking |
| `src/orchestration/toolkit/crawler.py` | Crawler agent tools |

### Modified Modules

| Module | Changes |
|--------|---------|
| `src/knowledge/storage.py` | Add SourceEntry crawl fields |
| `src/integrations/github/storage.py` | Add batch commit support |

---

## Test Cases

### Unit Tests

| Test | Description |
|------|-------------|
| `test_scope_path_exact_match` | Source URL matches itself |
| `test_scope_path_subpath` | URLs under source path accepted |
| `test_scope_path_sibling_rejected` | Sibling paths rejected |
| `test_scope_path_parent_rejected` | Parent paths rejected |
| `test_scope_host_same_host` | Same host accepted |
| `test_scope_host_subdomain_rejected` | Subdomains rejected for host scope |
| `test_scope_domain_subdomain_accepted` | Subdomains accepted for domain scope |
| `test_scope_different_domain_rejected` | External domains always rejected |
| `test_crawl_state_serialization` | State serializes/deserializes correctly |
| `test_frontier_overflow` | Frontier overflow to file works |
| `test_page_registry_batching` | Pages batched correctly |
| `test_link_extraction_relative_urls` | Relative URLs resolved correctly |
| `test_link_extraction_fragments_removed` | URL fragments stripped |
| `test_robots_txt_parsing` | Robots.txt rules parsed |
| `test_robots_txt_disallow` | Disallowed URLs filtered |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_crawl_single_page_scope` | Path scope with single page |
| `test_crawl_directory_scope` | Path scope with directory |
| `test_crawl_host_scope` | Host scope crawl |
| `test_crawl_resume_from_state` | Resumption from saved state |
| `test_crawl_respects_max_pages` | Stops at max_pages limit |
| `test_crawl_respects_max_depth` | Stops at max_depth limit |
| `test_crawl_deduplication` | Same URL not fetched twice |
| `test_crawl_out_of_scope_logged` | Out-of-scope URLs logged but not fetched |

### Edge Cases

| Test | Description |
|------|-------------|
| `test_trailing_slash_normalization` | `/path` and `/path/` treated same |
| `test_www_vs_no_www` | Handle www prefix correctly |
| `test_case_insensitive_host` | Host comparison case-insensitive |
| `test_query_params_preserved` | Query params kept in URLs |
| `test_redirect_within_scope` | Redirects to in-scope URL followed |
| `test_redirect_out_of_scope` | Redirects to out-of-scope URL rejected |
| `test_javascript_links_ignored` | `javascript:` URLs ignored |
| `test_mailto_links_ignored` | `mailto:` URLs ignored |
| `test_empty_href_ignored` | Empty href handled |

---

## Crawl Algorithm

```
FUNCTION crawl_source(source_url, scope, max_pages_per_run):
    
    # 1. Initialize or load state
    state = load_crawl_state(source_url)
    IF state is None:
        state = create_crawl_state(source_url, scope)
        state.frontier.append(source_url)
        create_tracking_issue(state)
    
    # 2. Load robots.txt
    robots = fetch_robots_txt(source_url)
    
    # 3. Process frontier
    pages_processed = 0
    WHILE state.frontier AND pages_processed < max_pages_per_run:
        
        url = state.frontier.pop(0)
        url_hash = sha256(url)
        
        # Skip if already visited
        IF url_hash IN state.visited_hashes:
            CONTINUE
        
        # Check robots.txt
        IF NOT robots.can_fetch(url):
            log_skipped(url, "robots.txt")
            state.skipped_count += 1
            CONTINUE
        
        # Apply politeness delay
        wait(1.0 seconds)
        
        # Fetch page
        TRY:
            response = fetch(url)
            content = extract_content(response)
            
            # Store content
            content_path = store_content(content, state)
            
            # Create page entry
            page = PageEntry(
                url=url,
                status="fetched",
                content_hash=sha256(content),
                content_path=content_path,
                ...
            )
            update_page_registry(page, state)
            
            # Extract and filter links
            links = extract_links(response.html, url)
            FOR link IN links:
                state.discovered_count += 1
                
                IF is_url_under_source(link, source_url, scope):
                    state.in_scope_count += 1
                    link_hash = sha256(link)
                    IF link_hash NOT IN state.visited_hashes:
                        state.frontier.append(link)
                ELSE:
                    state.out_of_scope_count += 1
                    log_out_of_scope(link, source_url)
            
            # Mark visited
            state.visited_hashes.add(url_hash)
            state.visited_count += 1
            
        EXCEPT FetchError as e:
            log_failed(url, e)
            state.failed_count += 1
        
        pages_processed += 1
        
        # Checkpoint every 100 pages
        IF pages_processed % 100 == 0:
            save_crawl_state(state)
            commit_changes()
            update_tracking_issue(state)
    
    # 4. Final save
    IF state.frontier is empty:
        state.status = "completed"
        state.completed_at = now()
    ELSE:
        state.status = "paused"
    
    save_crawl_state(state)
    update_tracking_issue(state)
    update_source_entry(state)
```

---

## Progress Tracking Issue Template

```markdown
## 🕷️ Site Crawl: {source_url}

| Field | Value |
|-------|-------|
| **Source URL** | `{source_url}` |
| **Scope** | `{scope}` |
| **Max Pages** | {max_pages} |
| **Max Depth** | {max_depth} |
| **Started** | {started_at} |

---

### Scope Explanation

{scope_explanation}

---

### Progress

| Metric | Value |
|--------|-------|
| Pages Acquired | {visited_count} |
| Frontier Size | {frontier_size} |
| Total Discovered | {discovered_count} |
| In Scope | {in_scope_count} |
| Out of Scope | {out_of_scope_count} |
| Skipped | {skipped_count} |
| Failed | {failed_count} |

### Status: {status_emoji} {status}

**Last Activity**: {last_activity}

---

### Workflow Runs

| Run | Pages | Duration | Status |
|-----|-------|----------|--------|
{run_table}

<!-- crawl-tracking:{source_hash} -->
```

---

## Implementation Phases

### Phase 1: Core Data Models (3 days) ✅ COMPLETE

**Deliverables:**
- [x] `src/knowledge/crawl_state.py` - CrawlState dataclass
- [x] `src/knowledge/page_registry.py` - PageEntry and batching
- [x] Extend `src/knowledge/storage.py` - SourceEntry crawl fields
- [x] Unit tests for all models

**Files:**
```
src/knowledge/crawl_state.py      (NEW) ✅
src/knowledge/page_registry.py    (NEW) ✅
src/knowledge/storage.py          (MODIFY) ✅
tests/knowledge/test_crawl_state.py  (NEW) ✅
tests/knowledge/test_page_registry.py (NEW) ✅
```

### Phase 2: URL Scope & Link Extraction (2 days)

**Deliverables:**
- [ ] `src/parsing/url_scope.py` - Scope validation logic
- [ ] `src/parsing/link_extractor.py` - Link extraction
- [ ] `src/parsing/robots.py` - Robots.txt support
- [ ] Comprehensive scope validation tests

**Files:**
```
src/parsing/url_scope.py          (NEW)
src/parsing/link_extractor.py     (NEW)
src/parsing/robots.py             (NEW)
tests/parsing/test_url_scope.py   (NEW)
tests/parsing/test_link_extractor.py (NEW)
```

### Phase 3: Crawler Toolkit (3 days)

**Deliverables:**
- [ ] `src/orchestration/toolkit/crawler.py` - All crawler tools
- [ ] Tool registration in agent runtime
- [ ] Integration with existing storage

**Files:**
```
src/orchestration/toolkit/crawler.py  (NEW)
src/orchestration/tools.py            (MODIFY)
tests/orchestration/test_crawler_tools.py (NEW)
```

### Phase 4: Mission & Workflow (2 days)

**Deliverables:**
- [ ] `config/missions/crawl_source.yaml` - Mission definition
- [ ] `.github/workflows/4-op-crawl-source.yml` - Workflow
- [ ] Tracking Issue templates

**Files:**
```
config/missions/crawl_source.yaml     (NEW)
.github/workflows/4-op-crawl-source.yml (NEW)
```

### Phase 5: Integration & Testing (3 days)

**Deliverables:**
- [ ] End-to-end integration tests
- [ ] Performance testing with mock site
- [ ] Documentation
- [ ] Bug fixes from testing

**Files:**
```
tests/integration/test_crawl_e2e.py   (NEW)
docs/guides/site-crawling.md          (NEW)
```

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Phase 1-2 | Data models, URL scope, link extraction |
| 2 | Phase 3-4 | Crawler tools, mission, workflow |
| 3 | Phase 5 | Integration testing, documentation, polish |

**Total Estimate: 13 days** (with buffer for issues)

---

## Dependencies

- **Upstream**: Monitor Agent (provides SourceEntry registry)
- **Downstream**: Entity Extraction (consumes crawled content)

## Related Documents

- [RESEARCH-site-crawl.md](RESEARCH-site-crawl.md) - Technical research
- [../02-monitor/PLAN.md](../02-monitor/PLAN.md) - Monitor Agent plan

---

*Last Updated: 2025-12-30*
