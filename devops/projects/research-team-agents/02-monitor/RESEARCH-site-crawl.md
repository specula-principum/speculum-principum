# Research: Site-Wide Web Crawling Architecture

## Executive Summary

This document analyzes the requirements and proposes an architecture for expanding the Monitor Agent to traverse and track **tens of thousands of web pages** from a single source URL (e.g., denverbroncos.com), using GitHub services exclusively.

**Verdict: Feasible with architectural changes.** The current single-page acquisition design can be extended to site-wide crawling within GitHub's limits.

---

## Current State

The recent acquisition of `https://www.denverbroncos.com` demonstrated:
- Single page fetch: 1,760 characters extracted
- Storage: `evidence/parsed/denverbroncos.com/content.md` + `metadata.json`
- Registry: `knowledge-graph/sources/{hash}.json` with `last_content_hash`
- GitHub API for persistence via `GitHubStorageClient`

**Gap**: No link extraction, no URL frontier, no multi-page traversal.

---

## GitHub Service Limits

### Repository Storage

| Limit | Value | Impact on 10K Pages |
|-------|-------|---------------------|
| Recommended repo size | <1 GB | 10K × 10KB avg = **100 MB** ✅ |
| Hard repo limit | 5 GB | Safe for crawl data |
| File size warning | 50 MB | Individual pages OK |
| File size limit | 100 MB | Individual pages OK |

### API Rate Limits

| Authentication | Limit | Implication |
|----------------|-------|-------------|
| GITHUB_TOKEN (Actions) | 1,000 req/hour/repo | ~16 commits/min |
| Authenticated user | 5,000 req/hour | Comfortable margin |
| GitHub App | 5,000-12,500 req/hour | Best for automation |

**Critical limit**: Secondary rate limit of **80 content-generating requests/minute** (creating files).

### GitHub Actions Limits

| Limit | Value | Implication |
|-------|-------|-------------|
| Job execution time | 6 hours max | Need chunked crawls |
| Job matrix | 256 jobs/workflow | Parallel processing possible |
| Concurrent jobs | 20-500 (by plan) | Can parallelize |

### Directory Listing Limit

**Critical**: GitHub Contents API returns max **1,000 files per directory**.

Solution: Sharded directory structure.

---

## Constraints Analysis for 10K Pages

| Concern | Calculation | Verdict |
|---------|-------------|---------|
| **Storage size** | 10K × 10KB = 100MB | ✅ Well under 1GB |
| **File count** | 10K files in one dir | ❌ Exceeds 1000 limit |
| **API calls to create** | 10K commits | ❌ Rate limited |
| **Crawl duration** | 10K × 1sec = 2.7 hrs | ✅ Under 6hr limit |
| **API calls for batch** | ~200 with Trees API | ✅ Under 1000/hour |

---

## Proposed Architecture

### Core Concept: Sharded Storage + Resumable Crawl State

```
┌─────────────────────────────────────────────────────────────────┐
│                     SITE-WIDE CRAWL FLOW                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
    ┌─────────────────────────┴─────────────────────────┐
    │                                                   │
    ▼                                                   ▼
┌───────────────────┐                       ┌───────────────────┐
│   SourceEntry     │                       │   CrawlState      │
│ (existing model)  │──────references──────▶│   (NEW model)     │
│                   │                       │                   │
│ • source_url      │                       │ • frontier[]      │
│ • is_crawlable    │                       │ • visited_hashes  │
│ • crawl_scope     │                       │ • status          │
│ • total_pages     │                       │ • last_activity   │
└───────────────────┘                       └───────────────────┘
                                                    │
                                                    │ manages
                                                    ▼
                                          ┌───────────────────┐
                                          │   PageRegistry    │
                                          │   (NEW model)     │
                                          │                   │
                                          │ • batch_0000.json │
                                          │ • batch_0001.json │
                                          │ • ... (500 each)  │
                                          └───────────────────┘
```

### 1. Data Models

#### 1.1 CrawlState (NEW)

Tracks the state of a site-wide crawl, enabling resume across workflow runs:

```python
@dataclass
class CrawlState:
    source_url: str                    # Root URL
    domain: str                        # Extracted domain
    status: str                        # "pending" | "crawling" | "completed" | "paused"
    
    # URL Frontier (URLs to visit)
    frontier: list[str]                # Active queue (max 1000 in memory)
    frontier_overflow_path: str | None # Path to overflow file for >1000 URLs
    
    # Visited tracking (deduplication)
    visited_count: int                 # Total pages visited
    visited_hashes: set[str]           # SHA-256 of visited URLs
    
    # Statistics
    discovered_count: int              # Total URLs discovered
    skipped_count: int                 # Out of scope / filtered
    failed_count: int                  # Failed fetches
    
    # Timestamps
    started_at: datetime | None
    last_activity: datetime | None
    completed_at: datetime | None
    
    # Configuration
    max_pages: int = 10000             # Safety limit
    max_depth: int = 5                 # Link depth from root
    crawl_scope: str = "subdomain"     # "page" | "subdomain" | "domain"
    include_patterns: list[str]        # fnmatch patterns to include
    exclude_patterns: list[str]        # fnmatch patterns to exclude
```

#### 1.2 PageEntry (NEW)

Metadata for each crawled page:

```python
@dataclass
class PageEntry:
    url: str                           # Full URL
    url_hash: str                      # SHA-256 of URL
    source_url: str                    # Parent SourceEntry URL
    
    # Discovery
    discovered_at: datetime
    discovered_from: str | None        # Referring URL
    link_depth: int                    # Hops from root
    
    # Fetch status
    status: str                        # "pending" | "fetched" | "failed" | "skipped"
    fetched_at: datetime | None
    http_status: int | None
    
    # Content
    content_hash: str | None           # SHA-256 of content
    content_path: str | None           # Relative path to stored content
    content_size: int | None
    extracted_chars: int | None
    
    # Metadata
    title: str | None
    outgoing_links: int | None
```

#### 1.3 SourceEntry Extensions

Add to existing `SourceEntry`:

```python
# Site-wide crawl metadata (NEW fields)
is_crawlable: bool = False             # Enable site-wide crawling
crawl_scope: str = "page"              # "page" | "subdomain" | "domain"
crawl_state_path: str | None = None    # Path to CrawlState file
total_pages_discovered: int = 0
total_pages_acquired: int = 0
last_crawl_started: datetime | None = None
last_crawl_completed: datetime | None = None
```

### 2. Storage Layout

#### 2.1 Sharded Content Storage

To avoid the 1,000-file directory limit, use hash-prefix sharding:

```
evidence/
└── parsed/
    └── denverbroncos.com/              # Domain folder
        ├── manifest.json               # Crawl manifest
        ├── 0/                          # Hash prefix shard (0-f)
        │   ├── 0a1b2c3d8e/             # Content hash prefix
        │   │   ├── content.md          # Extracted markdown
        │   │   └── metadata.json       # Page metadata
        │   └── 0f9e8d7c6b/
        │       ├── content.md
        │       └── metadata.json
        ├── 1/
        │   └── ...
        ├── 2/
        │   └── ...
        └── f/                          # 16 shards total
            └── ...
```

**Math**: 16 shards × 625 pages each = 10,000 pages, each shard well under 1,000 files.

#### 2.2 Page Registry (Batched Metadata)

```
knowledge-graph/
└── pages/
    └── {source_hash}/                  # Per-source folder
        ├── crawl_state.json            # CrawlState
        ├── registry.json               # Index of batch files
        ├── batch_0000.json             # Pages 0-499
        ├── batch_0001.json             # Pages 500-999
        ├── ...
        └── batch_0019.json             # Pages 9500-9999
```

**Batch file format**:
```json
{
  "batch_id": "0000",
  "page_count": 500,
  "pages": [
    { "url": "...", "url_hash": "...", "status": "fetched", ... },
    ...
  ]
}
```

### 3. Workflow Design

#### 3.1 Chunked Crawl Workflow

Since a full 10K page crawl (~3 hours at 1 req/sec) fits within the 6-hour limit but needs graceful resumption:

```yaml
# .github/workflows/4-op-crawl-source.yml
name: "Crawl Source Site"

on:
  workflow_dispatch:
    inputs:
      source_url:
        description: "Source URL to crawl"
        required: true
      max_pages_per_run:
        description: "Pages to fetch this run"
        default: "1000"
      crawl_scope:
        description: "Crawl scope"
        type: choice
        options:
          - subdomain
          - domain
        default: subdomain
  schedule:
    # Resume pending crawls every 4 hours
    - cron: "0 */4 * * *"

jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 300  # 5 hours max
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      
      - run: pip install -r requirements.txt
      
      - name: Run Crawl Agent
        run: |
          python -m main agent \
            --mission crawl_source \
            --input source_url="${{ inputs.source_url }}" \
            --input max_pages=${{ inputs.max_pages_per_run }} \
            --input crawl_scope=${{ inputs.crawl_scope }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

#### 3.2 Crawl Algorithm

```
1. LOAD CrawlState (or CREATE if new)
2. IF frontier is empty AND visited_count == 0:
     ADD source_url to frontier
3. WHILE frontier not empty AND pages_this_run < max_pages_per_run:
     a. POP url from frontier
     b. IF url_hash in visited_hashes: SKIP
     c. CHECK robots.txt compliance
     d. WAIT for politeness delay (1 sec)
     e. FETCH page content
     f. IF fetch successful:
          - EXTRACT links
          - FILTER links by scope
          - ADD new links to frontier
          - STORE content (sharded)
          - UPDATE PageEntry in batch
          - ADD url_hash to visited_hashes
     g. INCREMENT pages_this_run
     h. IF pages_this_run % 100 == 0:
          - COMMIT batch to GitHub
          - SAVE CrawlState checkpoint
4. SAVE final CrawlState
5. IF frontier empty: MARK crawl complete
   ELSE: MARK crawl paused (for next run)
```

### 4. API Efficiency Strategies

#### 4.1 Batch Commits with Trees API

Instead of committing files one at a time (1000 API calls for 1000 files), use the Git Trees API:

```python
def batch_commit_files(client: GitHubStorageClient, files: list[tuple[str, str]]) -> None:
    """Commit multiple files in a single API transaction."""
    # 1. Create blobs for each file (1 call each, but can be batched)
    # 2. Create tree with all blobs (1 call)
    # 3. Create commit pointing to tree (1 call)
    # 4. Update ref to new commit (1 call)
    # Total: N+3 calls for N files, vs N×2 calls with Contents API
```

**Batching strategy**: Commit every 100 pages (~100 files = ~103 API calls).

For 10K pages: 100 batches × 103 calls = **10,300 API calls** (spread across ~10 workflow runs = 1,030/run, within limits).

#### 4.2 Minimize Registry Updates

Instead of updating registry on each page:
- Buffer PageEntry updates in memory
- Write batch file when 500 pages accumulated
- Results in 20 batch file writes for 10K pages

### 5. Link Extraction & Scope Filtering

#### 5.1 Link Extractor

```python
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def extract_links(html: str, base_url: str) -> list[str]:
    """Extract all links from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)
        # Normalize (remove fragments, trailing slashes)
        normalized = normalize_url(absolute_url)
        if normalized:
            links.append(normalized)
    
    return list(set(links))  # Deduplicate
```

#### 5.2 Scope Filter

```python
def is_in_crawl_scope(
    url: str, 
    source_url: str, 
    scope: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> bool:
    """Check if URL should be crawled based on scope configuration."""
    source_domain = urlparse(source_url).netloc.replace("www.", "")
    url_domain = urlparse(url).netloc.replace("www.", "")
    
    # Scope check
    if scope == "subdomain":
        # Must be exact domain match (with or without www)
        if url_domain != source_domain and url_domain != f"www.{source_domain}":
            return False
    elif scope == "domain":
        # Include all subdomains
        if not url_domain.endswith(source_domain):
            return False
    
    # Pattern exclusions (always checked)
    for pattern in exclude_patterns:
        if fnmatch(url, pattern):
            return False
    
    # Pattern inclusions (if specified)
    if include_patterns:
        return any(fnmatch(url, p) for p in include_patterns)
    
    return True
```

#### 5.3 Default Exclusion Patterns

```python
DEFAULT_EXCLUDE_PATTERNS = [
    "*.pdf",           # Binary files
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp",  # Images
    "*.mp3", "*.mp4", "*.avi", "*.mov",             # Media
    "*.zip", "*.tar", "*.gz",                       # Archives
    "*?*session*", "*?*token*",                     # Session URLs
    "*/admin/*", "*/login/*", "*/logout/*",         # Auth pages
    "*/search/*", "*/search?*",                     # Search results
    "*#*",                                          # Anchor links
]
```

### 6. Progress Tracking via Issues

Create a GitHub Issue when site crawl starts:

```markdown
## 🕷️ Site Crawl: denverbroncos.com

**Source URL**: https://www.denverbroncos.com
**Scope**: subdomain
**Max Pages**: 10,000
**Started**: 2025-12-29T10:00:00Z

---

### Progress

| Metric | Value |
|--------|-------|
| Discovered | 5,234 |
| Acquired | 2,150 |
| Failed | 12 |
| Skipped | 47 |
| Frontier | 3,025 |

### Runs

| Run | Pages | Duration | Status |
|-----|-------|----------|--------|
| 1 | 1,000 | 52min | ✅ Complete |
| 2 | 1,000 | 48min | ✅ Complete |
| 3 | 150 | 8min | 🔄 Running |

---

### Recent Activity

- `2025-12-29T10:52:00Z` - Completed batch 2
- `2025-12-29T11:00:05Z` - Started batch 3
- `2025-12-29T11:08:12Z` - Checkpoint saved (150 pages)

<!-- crawl-tracking:{source_hash} -->
```

---

## Implementation Roadmap

### Phase 1: Core Data Models (Estimate: 2-3 days)

| Module | Purpose |
|--------|---------|
| `src/knowledge/crawl_state.py` | CrawlState dataclass and persistence |
| `src/knowledge/page_registry.py` | PageEntry batched storage |
| Extend `src/knowledge/storage.py` | SourceEntry crawl fields |

### Phase 2: Link Extraction (Estimate: 1-2 days)

| Module | Purpose |
|--------|---------|
| `src/parsing/link_extractor.py` | BeautifulSoup-based link extraction |
| `src/parsing/url_utils.py` | URL normalization, scope filtering |
| Tests for edge cases | Relative URLs, redirects, fragments |

### Phase 3: Crawl Agent (Estimate: 3-4 days)

| Module | Purpose |
|--------|---------|
| `src/orchestration/toolkit/crawler.py` | Crawl-specific tools |
| `config/missions/crawl_source.yaml` | Crawl mission definition |
| `.github/workflows/4-op-crawl-source.yml` | Crawl workflow |

### Phase 4: GitHub API Optimization (Estimate: 2-3 days)

| Module | Purpose |
|--------|---------|
| `src/integrations/github/trees.py` | Batch commits via Trees API |
| `src/integrations/github/storage.py` | Extend for batch operations |

### Phase 5: Testing & Polish (Estimate: 2-3 days)

| Task | Scope |
|------|-------|
| Unit tests | All new modules |
| Integration tests | End-to-end crawl simulation |
| Documentation | Usage guides, mission docs |

**Total Estimate**: 10-15 days of implementation work.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rate limit exceeded | Medium | High | Batch commits, checkpointing |
| Workflow timeout | Low | Medium | Chunked runs, auto-resume |
| Storage bloat | Low | Medium | Content dedup, size limits |
| Infinite crawl loops | Medium | High | max_pages limit, depth limit |
| Target site blocks crawler | Medium | Medium | Polite delays, user-agent |
| Firewall blocks domains | High | High | Clear documentation, allowlist process |

---

## Recommendations

1. **Start with subdomain scope** - Avoid accidentally crawling the entire internet by defaulting to `subdomain` scope.

2. **Conservative rate limiting** - 1 request/second is respectful; some sites may require slower.

3. **Implement robots.txt** - Essential for legal compliance and avoiding blocks.

4. **Set sensible defaults** - `max_pages=10000`, `max_depth=5` prevents runaway crawls.

5. **Progress visibility** - GitHub Issues for tracking makes crawl state visible to humans.

6. **Incremental value** - Entity extraction should run on pages as they're acquired, not wait for full crawl.

---

## Conclusion

Site-wide crawling of 10K+ pages is **feasible within GitHub's constraints** through:

- **Sharded storage** (16 hash-prefix directories)
- **Batched registries** (500 pages per JSON file)
- **Resumable crawl state** (persistent frontier)
- **Chunked workflows** (1K pages per run)
- **Batch API commits** (Trees API efficiency)

The main implementation effort is in the data models and crawl orchestration logic. The existing `WebParser` and storage infrastructure can be reused with minor extensions.

---

*Research conducted: 2025-12-29*
*Author: GitHub Copilot (Claude Opus 4.5)*
