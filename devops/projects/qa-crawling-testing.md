# QA Testing Guide: Multi-Page Crawling Feature

## What Changed

### Issue
The previous LLM-powered acquisition workflow crawled linked pages and verified domain approvals. The deterministic pipeline was only acquiring single pages.

### Fix
Restored multi-page crawling capability with these changes:

1. **Workflow Updates** (`.github/workflows/content-monitor-acquire.yml`)
   - ✅ Added Playwright browser installation step
   - ✅ Enhanced error reporting with detailed logs and summaries
   - ✅ Added crawl control inputs (`crawl_enabled`, `max_pages_per_crawl`)
   - ✅ Shows crawl configuration in summary report

2. **CLI Updates** (`src/cli/commands/pipeline.py`)
   - ✅ Added `--no-crawl` flag to disable crawling
   - ✅ Added `--max-pages-per-crawl` option (default: 100)
   - ✅ Pass crawl options to pipeline configuration

3. **Pipeline Configuration** (`src/knowledge/pipeline/config.py`)
   - ✅ Added `enable_crawling` field (default: True)
   - ✅ Added `max_pages_per_crawl` field (default: 100)

4. **Crawler Logic** (`src/knowledge/pipeline/crawler.py`)
   - ✅ Uses `config.enable_crawling` to determine crawl behavior
   - ✅ Respects `max_pages_per_crawl` limit
   - ✅ Honors `force_fresh` to restart crawls

5. **Documentation**
   - ✅ Updated mission (`config/missions/acquire_source.yaml`)
   - ✅ Created crawling guide (`docs/guides/crawling-configuration.md`)

## How Crawling Works

### Single-Page Sources (`is_crawlable: false`)
- Acquires only the source URL
- Stores one file in `evidence/parsed/`
- Updates `last_content_hash` in source metadata

### Multi-Page Sources (`is_crawlable: true`)
- Acquires source URL
- Extracts links from HTML
- Filters links by `crawl_scope` (path/host/domain)
- Fetches linked pages up to `max_pages_per_crawl`
- Respects `crawl_max_depth` for link traversal
- Stores all pages in `evidence/parsed/`
- Saves crawl state to `knowledge-graph/crawls/`
- Updates `total_pages_acquired` in source metadata

### Politeness & Safety
- Checks robots.txt before each request
- Respects Crawl-delay directive
- Enforces minimum delay between requests (default: 2-5s)
- Limits pages per domain per run
- Resumable across workflow runs (saves state)

## Testing Instructions

### 1. Verify Playwright Installation

The workflow should successfully install Chromium on the first run:

```bash
playwright install chromium --with-deps
```

**Expected**: No "Executable doesn't exist" errors

### 2. Test Single-Page Acquisition

For sources with `is_crawlable: false`:

```bash
python main.py pipeline run --max-sources 1 --dry-run
```

**Expected**:
- 1 page acquired
- No crawl state created
- Single file in `evidence/parsed/`

### 3. Test Multi-Page Crawling

For sources with `is_crawlable: true`:

```bash
python main.py pipeline run \
  --max-sources 1 \
  --max-pages-per-crawl 10 \
  --dry-run
```

**Expected**:
- Multiple pages discovered and acquired
- Crawl state saved to `knowledge-graph/crawls/`
- Multiple files in `evidence/parsed/`
- Source metadata shows `total_pages_acquired > 1`

### 4. Test Crawl Scope Filtering

Create a test source with different scopes:

**Path scope** (`crawl_scope: "path"`):
- Only follows links under same path
- Example: `https://example.com/docs/` → only `/docs/*`

**Host scope** (`crawl_scope: "host"`):
- Only same hostname
- Example: `www.example.com` → only `www.example.com/*`

**Domain scope** (`crawl_scope: "domain"`):
- Same domain, any subdomain
- Example: `example.com` → `www.example.com`, `api.example.com`, etc.

### 5. Test Workflow Inputs

Via GitHub Actions UI:

| Input | Test Value | Expected Behavior |
|-------|------------|-------------------|
| `mode` | `full` | Monitor + acquire |
| `max_sources` | `5` | Process max 5 sources |
| `max_per_domain` | `2` | Max 2 sources per domain |
| `min_interval` | `2` | 2s between requests |
| `crawl_enabled` | `false` | Only single pages |
| `max_pages_per_crawl` | `20` | Max 20 pages per crawl |
| `dry_run` | `true` | No actual changes |
| `force_fresh` | `true` | Restart all crawls |

### 6. Verify Error Reporting

Run with an invalid source URL:

**Expected**:
- Error appears in workflow summary
- Collapsible error details shown
- Exit code tracked
- Failed source count shown

### 7. Check PR Content

After successful run:

**Expected PR should include**:
- Multiple files if source is crawlable
- Crawl state files in `knowledge-graph/crawls/`
- Updated source metadata with page counts
- Manifest entries for all acquired pages

## Common Issues & Solutions

### Issue: Only 1 page acquired for crawlable source

**Cause**: Source not configured as crawlable

**Fix**: Set `is_crawlable: true` in source JSON file

### Issue: Crawl not following any links

**Cause**: Scope too restrictive or robots.txt blocking

**Fix**: 
- Check `crawl_scope` setting
- Verify robots.txt at source domain
- Check page actually contains HTML links

### Issue: Playwright errors

**Cause**: Browsers not installed

**Fix**: Workflow now includes `playwright install chromium --with-deps`

### Issue: Crawl restarting every run

**Cause**: Crawl state not being saved/committed

**Fix**: 
- Verify GitHub storage client is working
- Check file pattern in commit step includes `knowledge-graph/crawls/**`
- Don't use `--force-fresh` unless intentional

## Success Criteria

✅ Playwright installs successfully  
✅ Single-page sources acquire 1 page  
✅ Crawlable sources acquire multiple pages  
✅ Scope filtering works correctly  
✅ Crawl state persists across runs  
✅ Error reporting shows detailed information  
✅ PR includes all acquired content  
✅ Summary shows crawl statistics  

## Questions for QA

1. Do crawlable sources now acquire multiple pages?
2. Are crawl state files being created in `knowledge-graph/crawls/`?
3. Does the PR show multiple file updates for crawlable sources?
4. Is scope filtering working as expected (path/host/domain)?
5. Are error messages now visible in the workflow summary?
6. Does the summary show crawl statistics (pages acquired)?

Please test and provide feedback on any issues encountered.
