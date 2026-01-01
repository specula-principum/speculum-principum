# Content Pipeline Refactor - Planning Document

## Project Overview

**Mission:** Consolidate and streamline the Monitor Agent and Crawler Agent into a unified, programmatic content pipeline with minimal LLM orchestration overhead.

**Status:** ✅ Phase 6 Complete - Project Complete

**Prerequisites:** 
- Monitor Agent (02-monitor) - ✅ Complete
- Crawler Agent (03-crawler) - ✅ Complete

**Decision:** Proceed with Direction 1 - Programmatic Content Pipeline with politeness-aware scheduling.

---

## Problem Statement

Two major issues have been identified during product review:

### Issue 1: Excessive LLM Involvement

**Current State:**
Both the Monitor Agent and Crawler Agent are orchestrated by an LLM planner (`src/orchestration/llm.py`), which:
- Reads mission YAML files with goals/constraints as natural language
- Makes LLM API calls to determine which tool to invoke next
- Iterates through a plan→execute→observe loop with multiple LLM roundtrips

**Analysis:**
The actual work performed by these agents is **entirely deterministic and programmatic**:

| Agent | Actual Work | LLM Role |
|-------|-------------|----------|
| **Monitor** | `SourceMonitor.check_source()` - tiered HTTP checking | Decides which sources to check, when to create Issues |
| **Crawler** | Frontier management, `fetch_page()`, `extract_links()` | Decides when to fetch, when to save state |

The underlying implementations are already highly automated:
- `src/knowledge/monitoring.py` - `SourceMonitor` class handles all detection logic
- `src/knowledge/crawl_state.py` - `CrawlState` manages frontier automatically
- `src/parsing/link_extractor.py` - `extract_links()` is deterministic
- `src/parsing/url_scope.py` - `is_url_in_scope()` is deterministic

**LLM Cost Per Run:**
- Monitor mission: ~50 max steps × LLM calls for planning = significant token usage
- Crawler mission: ~150 max steps × LLM calls = substantial token usage
- Both missions can execute with **zero LLM involvement** given proper programmatic control flow

### Issue 2: Disjointed Workflow Execution

**Current State:**
Two separate workflows with no coordination:

```
.github/workflows/
├── 3-op-monitor-sources.yml    # Scheduled weekly, checks for changes
└── 4-op-crawl-source.yml       # Manual dispatch only
```

**Observed Problems:**

1. **No Automatic Progression:**
   - Monitor creates Issues for "initial-acquisition" or "content-update"
   - Crawler must be manually dispatched to act on these
   - No automated handoff between detection → acquisition

2. **Duplicated Responsibilities:**
   - Both agents fetch web content (Monitor for hash comparison, Crawler for storage)
   - Both use `WebParser` and HTTP requests
   - Both maintain politeness delays independently

3. **State Fragmentation:**
   - Monitor updates `SourceEntry` fields in `knowledge-graph/sources/`
   - Crawler maintains separate `CrawlState` in `knowledge-graph/crawls/`
   - No unified view of "what content do we have?"

4. **Workflow Trigger Mismatch:**
   - Monitor runs on schedule but only detects, doesn't acquire
   - Crawler requires manual input (source_url, scope) per invocation
   - No mechanism for Monitor to trigger Crawler automatically

### Issue 3: Politeness and Rate Limiting

**Concern:** Running a unified pipeline risks hammering source websites with too many requests in a short period.

**Current Mitigations (Partial):**
- `PolitenessPolicy` in `src/knowledge/monitoring.py` defines delays
- `next_check_after` field schedules when sources can be checked
- Crawler has 1-second minimum delay between requests
- `check_failures` triggers exponential backoff

**Gaps in Current Design:**
1. **No domain-level queuing** - If multiple sources share a domain, they could be checked simultaneously
2. **Bulk processing** - All due sources checked in one workflow run (no staggering)
3. **No jitter** - Predictable timing patterns across runs
4. **No global rate limit** - Total requests per workflow run unbounded

---

## Politeness Requirements for Unified Pipeline

### Design Principles

1. **Domain-Aware Scheduling**: Never hit the same domain more than once per N seconds
2. **Staggered Checks**: Spread source checks across multiple workflow runs
3. **Batch Limits**: Cap sources processed per workflow run
4. **Jitter**: Add randomization to avoid predictable patterns
5. **Robots.txt Respect**: Honor `Crawl-delay` directives

### Proposed Politeness Model

```python
@dataclass
class PipelinePoliteness:
    """Rate limiting configuration for the content pipeline."""
    
    # Per-domain limits
    min_domain_interval: timedelta = timedelta(seconds=2)  # Between requests to same domain
    max_domain_requests_per_run: int = 10  # Max pages from one domain per run
    
    # Per-run limits
    max_sources_per_run: int = 20  # Sources to process per workflow run
    max_total_requests_per_run: int = 100  # Total HTTP requests per run
    
    # Scheduling
    check_jitter_minutes: int = 60  # Random offset added to next_check_after
    stagger_initial_acquisitions: bool = True  # Spread new sources across runs
    
    # Backoff
    failure_backoff_base: timedelta = timedelta(hours=6)
    failure_backoff_max: timedelta = timedelta(days=7)
```

### Staggered Scheduling Algorithm

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGGERED CHECK SCHEDULING                           │
└─────────────────────────────────────────────────────────────────────────┘

GIVEN:
  - sources_due: List of sources where next_check_after <= now
  - max_per_run: Maximum sources to process (e.g., 20)
  - max_per_domain: Maximum sources per domain per run (e.g., 3)

ALGORITHM:
  1. Group sources_due by domain
  
  2. Build processing queue with domain fairness:
     queue = []
     for round in range(max_per_run):
         for domain, sources in domain_groups.items():
             if len([s for s in queue if s.domain == domain]) < max_per_domain:
                 if sources:
                     queue.append(sources.pop(0))
             if len(queue) >= max_per_run:
                 break
  
  3. Process queue with per-domain delays:
     last_request_by_domain = {}
     for source in queue:
         # Wait for domain cooldown
         if source.domain in last_request_by_domain:
             elapsed = now - last_request_by_domain[source.domain]
             if elapsed < min_domain_interval:
                 sleep(min_domain_interval - elapsed)
         
         # Check source
         result = check_source(source)
         last_request_by_domain[source.domain] = now
         
         # Schedule next check with jitter
         jitter = random.uniform(0, check_jitter_minutes * 60)
         source.next_check_after = calculate_next_check(source) + timedelta(seconds=jitter)
  
  4. Sources not processed remain in queue for next run
     (their next_check_after is already in the past)
```

### Example: Weekly Schedule with 50 Sources

```
Workflow runs weekly at Sunday 00:00 UTC
50 sources registered, max_per_run = 20

Week 1 Run:
  - Process sources 1-20 (selected by domain fairness)
  - Sources 21-50 remain due (will be picked up next run)
  - Each source gets next_check_after = now + interval + jitter

Week 2 Run:
  - Sources 21-40 now highest priority (longest overdue)
  - Sources 41-50 still waiting
  - Some sources from week 1 may be due again (if interval=weekly)

Effect: Load naturally spreads across runs, no single run hammers all sources
```

### Domain Fairness Example

```
Sources due for check:
  - example.com/page1, example.com/page2, example.com/page3, example.com/page4
  - other.org/doc1, other.org/doc2
  - third.net/article1

max_per_domain = 2
max_per_run = 5

Processing queue (domain-fair order):
  1. example.com/page1
  2. other.org/doc1
  3. third.net/article1
  4. example.com/page2  (2nd from example.com)
  5. other.org/doc2     (2nd from other.org)

NOT processed this run (exceeded domain limit):
  - example.com/page3, example.com/page4 → next run
```

---

## Current Architecture Analysis

### Data Flow (As Implemented)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CURRENT STATE                                   │
└─────────────────────────────────────────────────────────────────────────┘

MONITOR WORKFLOW (Scheduled)
    ↓
[LLM Planner] → Reads mission YAML, plans steps
    ↓
[Tool: get_sources_pending_initial] → Returns list of sources
    ↓
[LLM Planner] → Decides to iterate sources
    ↓
[Tool: create_initial_acquisition_issue] → Creates GitHub Issue
    ↓
[LLM Planner] → Decides to check next source or finish
    ↓
... (repeat for each source) ...
    ↓
OUTCOME: GitHub Issues created (but NOT processed)

════════════════════════════════════════════════════════════════════════════

CRAWLER WORKFLOW (Manual Dispatch)
    ↓
[LLM Planner] → Reads mission YAML, plans steps
    ↓
[Tool: load_crawl_state] → Loads or creates state
    ↓
[LLM Planner] → Decides to fetch robots.txt
    ↓
[Tool: check_robots_txt] → Returns allowed status
    ↓
[LLM Planner] → Decides to start crawl loop
    ↓
[Tool: get_frontier_urls] → Returns next URL
    ↓
[Tool: fetch_page] → Fetches content
    ↓
[LLM Planner] → Decides to extract links
    ↓
[Tool: extract_links] → Returns discovered URLs
    ↓
... (repeat for each page, with LLM decision at each step) ...
    ↓
OUTCOME: Content stored, state saved
```

### Where LLM Adds No Value

The LLM planner is making trivial decisions that could be hardcoded:

| LLM Decision | Could Be Replaced With |
|--------------|------------------------|
| "Should I check next source?" | `for source in sources:` |
| "Should I create an issue?" | `if source.needs_acquisition:` |
| "Should I fetch this URL?" | `while frontier:` |
| "Should I extract links?" | Always yes after successful fetch |
| "Should I save state?" | Every N pages or on exit |

### Where LLM Might Add Value

Exception handling and edge cases where human judgment helps:
- Deciding what to do when a source returns 403 Forbidden
- Interpreting unusual robots.txt rules
- Handling redirect chains to different domains
- Deciding scope when source structure changes

---

## Module Inventory

### Core Programmatic Logic (No LLM Needed)

| Module | Purpose | LLM-Free? |
|--------|---------|-----------|
| `src/knowledge/monitoring.py` | `SourceMonitor` - tiered change detection | ✅ Yes |
| `src/knowledge/storage.py` | `SourceRegistry` - source CRUD | ✅ Yes |
| `src/knowledge/crawl_state.py` | `CrawlState` - frontier management | ✅ Yes |
| `src/knowledge/page_registry.py` | `PageRegistry` - page batch storage | ✅ Yes |
| `src/parsing/web.py` | `WebParser` - content fetching | ✅ Yes |
| `src/parsing/link_extractor.py` | `extract_links()` | ✅ Yes |
| `src/parsing/url_scope.py` | `is_url_in_scope()`, `normalize_url()` | ✅ Yes |
| `src/parsing/robots.py` | `RobotsChecker` | ✅ Yes |
| `src/parsing/storage.py` | `ParseStorage` - evidence storage | ✅ Yes |

### LLM Orchestration Layer (Candidates for Removal)

| Module | Current Role | Could Be Replaced |
|--------|--------------|-------------------|
| `src/orchestration/agent.py` | Agent runtime loop | Direct Python loop |
| `src/orchestration/llm.py` | LLM-based planner | Scripted execution |
| `src/orchestration/planner.py` | Planner interface | N/A |
| `src/orchestration/missions.py` | Mission YAML loading | Config dataclass |
| `src/orchestration/toolkit/monitor.py` | Tool wrappers | Direct function calls |
| `src/orchestration/toolkit/crawler.py` | Tool wrappers | Direct function calls |

---

## Research Questions

### Q1: Can Both Agents Run Without LLM?

**Hypothesis:** Yes, both workflows are deterministic algorithms.

**Evidence:**
1. Monitor algorithm is documented in [02-monitor/PLAN.md](../02-monitor/PLAN.md):
   ```
   for source in get_sources_pending_initial():
       create_initial_acquisition_issue(source)
   for source in get_sources_due_for_check():
       result = check_source(source)
       if result.changed:
           create_content_update_issue(source)
   ```

2. Crawler algorithm is documented in [03-crawler/PLAN.md](../03-crawler/PLAN.md):
   ```
   state = load_crawl_state(source_url)
   while frontier and pages < max_pages:
       url = frontier.pop()
       if robots.can_fetch(url):
           content = fetch(url)
           store(content)
           links = extract_links(content)
           frontier.extend(filter_by_scope(links))
   save_state()
   ```

**Conclusion:** Both can be implemented as pure Python scripts with no LLM.

---

### Q2: How Should Workflows Be Unified?

**Current Split:**
```
Monitor (scheduled) → Creates Issues → [Human or Agent picks up Issue] → Crawler (manual)
```

**Options:**

#### Option A: Keep Separate, Add Chaining
```
Monitor (scheduled) → Creates Issues → workflow_dispatch event → Crawler (triggered)
```
- Pros: Minimal change, respects existing separation
- Cons: Still requires Issue-based coordination

#### Option B: Single Unified Workflow
```
ContentPipeline (scheduled/manual)
  ├── Phase 1: Check for changes (Monitor logic)
  ├── Phase 2: Acquire changed content (Crawler logic, if needed)
  └── Phase 3: Update registry and commit
```
- Pros: Single execution context, no coordination overhead
- Cons: Longer workflow runs, potential timeouts

#### Option C: Pipeline with Stages
```
Pipeline Controller (scheduled/manual)
  ├── Stage: Discovery → Outputs sources needing work
  ├── Stage: Acquisition → Processes each source
  └── Stage: Finalization → Updates registry
```
- Pros: Modular, can run stages independently
- Cons: More complex orchestration

---

### Q3: What Is the Optimal Execution Model?

**Current:** LLM agent loop with tool calls

**Alternatives:**

| Model | Description | Complexity | LLM Cost |
|-------|-------------|------------|----------|
| **Pure Python** | `python main.py pipeline run` | Low | None |
| **CLI Commands** | `main.py monitor check && main.py crawl run` | Low | None |
| **Hybrid** | Programmatic for happy path, LLM for exceptions | Medium | Low |
| **Current** | LLM for all decisions | High | High |

**Recommendation:** Pure Python for core flow, optional LLM escalation for exceptions.

---

## Proposed Solution Directions

### Direction 1: Programmatic Content Pipeline

Create a new `src/knowledge/pipeline.py` module that:
- Combines Monitor + Crawler logic
- Runs as pure Python with no LLM
- Enforces politeness via domain-aware scheduling
- Exposes CLI commands via `main.py`

```
main.py pipeline check      # Run Monitor logic (detect changes)
main.py pipeline acquire    # Run Crawler logic (fetch content)  
main.py pipeline run        # Run full pipeline (check + acquire)
main.py pipeline status     # Show pending sources and schedule
```

**Politeness Integration:**
```python
def run_pipeline(
    max_sources: int = 20,           # Limit per run
    max_per_domain: int = 3,         # Domain fairness
    min_domain_delay: float = 2.0,   # Seconds between same-domain requests
    jitter_minutes: int = 60,        # Randomization for next check
) -> PipelineResult:
    """
    Run unified content pipeline with politeness constraints.
    
    1. Collect sources due for check (respects next_check_after)
    2. Apply domain-fair queuing (max_per_domain limit)
    3. Process up to max_sources with delays
    4. Schedule remaining sources for next run
    5. Apply jitter to next_check_after timestamps
    """
```

**Workflow Implications:**
- Single workflow `5-op-content-pipeline.yml`
- Scheduled (weekly) + manual dispatch
- No GitHub Issues for coordination (direct execution)
- Naturally spreads load across runs via scheduling

### Direction 2: Refactor Existing with LLM Bypass

Keep existing structure but add "direct execution" mode:
- `config/missions/` remain for documentation
- `--no-llm` flag bypasses planner, runs deterministic logic
- Minimal code changes, preserves LLM option for debugging

```
python main.py agent run --mission monitor_sources --no-llm
python main.py agent run --mission crawl_source --no-llm
```

### Direction 3: Event-Driven Pipeline

Use GitHub Actions outputs and workflow chaining:
- Monitor workflow outputs list of sources needing acquisition
- Triggers Crawler workflow via `workflow_dispatch` with matrix
- Each source acquired in parallel jobs

```yaml
# Monitor outputs
- source_url: https://example.com
  action: initial-acquisition
- source_url: https://other.com
  action: content-update

# Triggers N parallel Crawler jobs
```

---

## Implementation Plan

### Phase 1: Research & Decision ✅ COMPLETE

- [x] Document current LLM involvement
- [x] Analyze programmatic alternatives
- [x] Identify workflow coordination gaps
- [x] Define politeness requirements
- [x] Stakeholder review → **Direction 1 approved**

---

### Phase 2: Core Pipeline Module (3-4 days)

**Goal:** Create `src/knowledge/pipeline/` with unified detection + acquisition logic.

**Status:** ✅ Complete

| Deliverable | File | Status |
|-------------|------|--------|
| Pipeline config | `src/knowledge/pipeline/config.py` | ✅ Done |
| Scheduler | `src/knowledge/pipeline/scheduler.py` | ✅ Done |
| Monitor runner | `src/knowledge/pipeline/monitor.py` | ✅ Done |
| Crawler runner | `src/knowledge/pipeline/crawler.py` | ✅ Done |
| Unified runner | `src/knowledge/pipeline/runner.py` | ✅ Done |
| Package init | `src/knowledge/pipeline/__init__.py` | ✅ Done |

**Tests Created:**
- `tests/knowledge/test_pipeline_config.py` - 11 tests
- `tests/knowledge/test_pipeline_scheduler.py` - 25 tests
- `tests/knowledge/test_pipeline_monitor.py` - 14 tests
- `tests/knowledge/test_pipeline_crawler.py` - 19 tests
- `tests/knowledge/test_pipeline_runner.py` - 16 tests
- **Total: 85 tests, all passing**

**Tasks:**
- [x] Create `PipelinePoliteness` config dataclass
- [x] Implement `DomainScheduler` for fair queuing
- [x] Extract monitor logic from toolkit to standalone function
- [x] Extract crawler logic from toolkit to standalone function
- [x] Create `run_pipeline()` unified entry point
- [x] Unit tests for scheduler and runners

---

### Phase 3: CLI Commands (1-2 days)

**Goal:** Expose pipeline via `main.py` CLI.

| Command | Description |
|---------|-------------|
| `main.py pipeline run` | Full pipeline (detect + acquire) |
| `main.py pipeline check` | Detection only |
| `main.py pipeline acquire` | Acquisition only (for pending sources) |
| `main.py pipeline status` | Show source status and schedule |

**Status:** ✅ Complete

**Deliverables:**
- `src/cli/commands/pipeline.py` - CLI command module (445 lines)
- `main.py` - Updated with pipeline command registration
- `tests/cli/test_pipeline_commands.py` - 15 tests, all passing

**Tasks:**
- [x] Create `src/cli/commands/pipeline.py`
- [x] Register commands in `main.py`
- [x] Add `--dry-run` flag for testing
- [x] Add `--max-sources` and `--max-per-domain` options
- [x] Add `--json` flag for JSON output
- [x] Unit tests for CLI commands

---

### Phase 4: GitHub Workflow (1 day)

**Goal:** Single unified workflow replacing monitor + crawler workflows.

**Status:** ✅ Complete

**File:** `.github/workflows/5-op-content-pipeline.yml`

**Features:**
- Scheduled weekly run (Sunday 00:00 UTC)
- Manual dispatch with mode selection (full/check/acquire)
- Politeness controls (max_sources, max_per_domain, min_interval)
- Dry-run support for testing
- JSON output parsing for step summary
- Auto-commit of updated sources and content

**Tasks:**
- [x] Create workflow file
- [x] Add politeness input parameters
- [x] Add dry-run mode
- [x] Add step summary with results
- [ ] Deprecate old workflows (Phase 6)

---

### Phase 5: Testing & Documentation (2 days)

**Goal:** Comprehensive test coverage and updated docs.

**Status:** ✅ Complete

| Test File | Coverage | Status |
|-----------|----------|--------|
| `tests/knowledge/test_pipeline_config.py` | Politeness config | ✅ 11 tests |
| `tests/knowledge/test_pipeline_scheduler.py` | Domain scheduling, jitter | ✅ 25 tests |
| `tests/knowledge/test_pipeline_monitor.py` | Detection logic | ✅ 14 tests |
| `tests/knowledge/test_pipeline_crawler.py` | Acquisition logic | ✅ 19 tests |
| `tests/knowledge/test_pipeline_runner.py` | Unified pipeline | ✅ 16 tests |
| `tests/cli/test_pipeline_commands.py` | CLI interface | ✅ 15 tests |
| `tests/knowledge/test_pipeline_integration.py` | Integration tests | ✅ 16 tests |

**Documentation:**
- [x] Created `docs/guides/content-pipeline.md`
- [x] Updated `docs/guides/monitor-agent.md` → deprecation notice
- [x] Updated `docs/guides/crawler-agent.md` → deprecation notice

---

### Phase 6: Migration & Cleanup (1 day)

**Goal:** Transition from old workflows to new pipeline.

**Status:** ✅ Complete

**Archived Files:**

| Original Location | New Location |
|-------------------|--------------|
| `.github/workflows/3-op-monitor-sources.yml` | `.github/workflows/deprecated/` |
| `.github/workflows/4-op-crawl-source.yml` | `.github/workflows/deprecated/` |
| `config/missions/monitor_sources.yaml` | `config/missions/deprecated/` |
| `config/missions/crawl_source.yaml` | `config/missions/deprecated/` |
| `src/orchestration/toolkit/monitor.py` | `src/orchestration/toolkit/deprecated/` |
| `src/orchestration/toolkit/crawler.py` | `src/orchestration/toolkit/deprecated/` |
| `tests/orchestration/test_monitor_*.py` | `tests/orchestration/deprecated/` |
| `tests/orchestration/test_crawler_*.py` | `tests/orchestration/deprecated/` |

**Tasks Completed:**
- [x] Archived old workflow files
- [x] Archived old mission YAML files
- [x] Archived old toolkit modules
- [x] Archived associated test files
- [x] Removed deprecated imports from `toolkit/__init__.py`
- [x] Removed deprecated tool registration from `agent.py`
- [x] Added `conftest.py` to skip deprecated tests

---

## Timeline Summary

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Research & Decision | - | ✅ Complete |
| Phase 2: Core Pipeline Module | 3-4 days | ✅ Complete |
| Phase 3: CLI Commands | 1-2 days | ✅ Complete |
| Phase 4: GitHub Workflow | 1 day | ✅ Complete |
| Phase 5: Testing & Documentation | 2 days | ✅ Complete (116 tests) |
| Phase 6: Migration & Cleanup | 1 day | ✅ Complete |
| **Total** | **8-10 days** | ✅ **All Phases Complete** |

---

## Appendix: Token Cost Analysis

### Current LLM Usage Estimate

**Monitor Mission:**
- System prompt: ~1,500 tokens
- Per-step user prompt: ~500 tokens
- LLM response: ~200 tokens
- Average steps per run: 10-30
- **Total per run: 21,000 - 63,000 tokens**

**Crawler Mission:**
- System prompt: ~2,000 tokens
- Per-step user prompt: ~800 tokens
- LLM response: ~300 tokens
- Average steps per run: 50-150
- **Total per run: 155,000 - 465,000 tokens**

**Combined Weekly Cost (assuming weekly runs):**
- ~176,000 - 528,000 tokens/week
- At $0.01/1K tokens input, $0.03/1K output: **$5-15/week**

**After Refactor:**
- Zero LLM tokens for programmatic execution
- Optional LLM for exception handling: ~10,000 tokens/week
- **Savings: 95%+ reduction in LLM costs**

---

## Appendix: Current Tool Mapping

### Monitor Agent Tools → Python Functions

| Tool | Handler | Direct Replacement |
|------|---------|-------------------|
| `get_sources_pending_initial` | `_get_sources_pending_initial_handler` | `SourceMonitor.get_sources_pending_initial()` |
| `get_sources_due_for_check` | `_get_sources_due_for_check_handler` | `SourceMonitor.get_sources_due_for_check()` |
| `check_source_for_changes` | `_check_source_for_changes_handler` | `SourceMonitor.check_source()` |
| `create_initial_acquisition_issue` | `_create_initial_acquisition_issue_handler` | `github_issues.create_issue()` |
| `create_content_update_issue` | `_create_content_update_issue_handler` | `github_issues.create_issue()` |
| `update_source_monitoring_metadata` | `_update_source_monitoring_metadata_handler` | `SourceRegistry.save_source()` |

### Crawler Agent Tools → Python Functions

| Tool | Handler | Direct Replacement |
|------|---------|-------------------|
| `load_crawl_state` | `_load_crawl_state_handler` | `CrawlStateStorage.load_state()` |
| `save_crawl_state` | `_save_crawl_state_handler` | `CrawlStateStorage.save_state()` |
| `get_frontier_urls` | `_get_frontier_urls_handler` | `state.frontier[:count]` |
| `add_to_frontier` | `_add_to_frontier_handler` | `state.frontier.extend()` |
| `fetch_page` | `_fetch_page_handler` | `WebParser.extract()` |
| `extract_links` | `_extract_links_handler` | `link_extractor.extract_links()` |
| `check_robots_txt` | `_check_robots_txt_handler` | `RobotsChecker.can_fetch()` |
| `store_page_content` | `_store_page_content_handler` | `ParseStorage.store()` |
| `filter_urls_by_scope` | `_filter_urls_by_scope_handler` | `url_scope.filter_urls_by_scope()` |

---

*Last Updated: 2025-12-31*
