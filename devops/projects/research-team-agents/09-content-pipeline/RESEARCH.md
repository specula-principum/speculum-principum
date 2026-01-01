# Content Pipeline Refactor - Technical Research

## Overview

This document contains detailed technical research supporting the [PLAN.md](./PLAN.md) refactoring proposal.

---

## 1. LLM Involvement Analysis

### 1.1 How the Current Agent Runtime Works

The agent system uses a multi-component architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgentRuntime.execute_mission()              │
│                     (src/orchestration/agent.py)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         LLMPlanner.plan_next()                  │
│                     (src/orchestration/llm.py)                  │
│                                                                 │
│  1. Build system prompt with mission goals/constraints          │
│  2. Build user prompt with current state + last tool result     │
│  3. Call GitHub Models API (chat_completion)                    │
│  4. Parse response for tool call or FINISH signal               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SafetyValidator.check_action()               │
│                   (src/orchestration/safety.py)                 │
│                                                                 │
│  - Check tool risk level (SAFE, REVIEW, DESTRUCTIVE)            │
│  - Apply approval policies if needed                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ToolRegistry.execute_definition()             │
│                    (src/orchestration/tools.py)                 │
│                                                                 │
│  - Look up tool handler by name                                 │
│  - Execute handler with arguments                               │
│  - Return ToolResult                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                      (Loop continues until
                       FINISH or max_steps)
```

### 1.2 Token Usage Per Iteration

Each agent step involves an LLM call. Examining `LLMPlanner._build_system_prompt()` and `_build_user_prompt()`:

**System Prompt Components:**
```python
# From src/orchestration/llm.py lines 120-180 (approximate)
- Mission goal text (~200-500 tokens)
- Mission constraints (~100-300 tokens)
- Available tool descriptions (~50 tokens per tool)
- System instructions (~500 tokens)
# Total: ~1,500-2,500 tokens
```

**User Prompt Components:**
```python
# From src/orchestration/llm.py lines 250-300 (approximate)
- Current step number and remaining steps
- History of previous tool calls + results
- Last tool result (can be large for data queries)
# Total: ~500-2,000 tokens (grows with history)
```

**LLM Response:**
- Tool call with arguments: ~100-300 tokens
- FINISH with summary: ~200-500 tokens

### 1.3 What the LLM Actually Decides

Reviewing the mission YAML files reveals the LLM is making routine decisions:

**Monitor Mission (`config/missions/monitor_sources.yaml`):**
```yaml
goal: |
  1. Call `get_sources_pending_initial` to find active sources needing initial acquisition
  2. For each source returned, call `create_initial_acquisition_issue`
  3. Call `get_sources_due_for_check` to find active sources due for update monitoring
  4. For each source returned, call `check_source_for_changes`
  5. If changes detected, call `create_content_update_issue`
  6. Call `update_source_monitoring_metadata`
```

The "goal" is literally a step-by-step algorithm. The LLM is translating natural language instructions into tool calls, but those instructions are already programmatic.

**Crawler Mission (`config/missions/crawl_source.yaml`):**
```yaml
goal: |
  ALGORITHM:
  state = load_crawl_state(source_url, scope, max_pages, force_restart)
  robots = fetch_robots_txt(source_url) if available
  
  while pages_processed < max_pages_per_run:
      urls = get_frontier_urls(source_url, count=1)
      if not urls:
          break
      ...
```

The goal includes actual pseudocode! The LLM is parsing pseudocode and executing it via tool calls. This is a classic case of over-engineering.

---

## 2. Programmatic Alternatives

### 2.1 Monitor Logic as Pure Python

The monitor algorithm can be expressed in ~50 lines:

```python
# Proposed: src/knowledge/pipeline/monitor.py

from src.knowledge.monitoring import SourceMonitor, ChangeDetection
from src.knowledge.storage import SourceRegistry
from src.integrations.github import issues as github_issues

def run_monitor(
    registry: SourceRegistry,
    create_issues: bool = True,
) -> dict:
    """Run monitor logic without LLM orchestration."""
    
    monitor = SourceMonitor(registry=registry)
    results = {
        "initial_count": 0,
        "changed_count": 0,
        "unchanged_count": 0,
        "error_count": 0,
        "issues_created": [],
    }
    
    # Mode 1: Initial acquisitions
    for source in monitor.get_sources_pending_initial():
        if create_issues:
            issue = github_issues.create_issue(
                title=f"Initial Acquisition: {source.name}",
                body=_build_initial_body(source),
                labels=["initial-acquisition", source.source_type],
            )
            results["issues_created"].append(issue.number)
        results["initial_count"] += 1
    
    # Mode 2: Update monitoring
    for source in monitor.get_sources_due_for_check():
        result = monitor.check_source(source)
        
        if result.status == "changed":
            if create_issues:
                issue = github_issues.create_issue(
                    title=f"Content Update: {source.name}",
                    body=_build_update_body(source, result),
                    labels=["content-update", source.source_type],
                )
                results["issues_created"].append(issue.number)
            results["changed_count"] += 1
        elif result.status == "unchanged":
            results["unchanged_count"] += 1
        elif result.status == "error":
            results["error_count"] += 1
        
        # Update source metadata
        _update_source_metadata(registry, source, result)
    
    return results
```

### 2.2 Crawler Logic as Pure Python

The crawler algorithm can be expressed in ~80 lines:

```python
# Proposed: src/knowledge/pipeline/crawler.py

from src.knowledge.crawl_state import CrawlState, CrawlStateStorage
from src.knowledge.page_registry import PageRegistry
from src.parsing.web import WebParser
from src.parsing.link_extractor import extract_links
from src.parsing.url_scope import is_url_in_scope, filter_urls_by_scope
from src.parsing.robots import RobotsChecker

def run_crawler(
    source_url: str,
    scope: str = "path",
    max_pages: int = 1000,
    force_restart: bool = False,
) -> dict:
    """Run crawler logic without LLM orchestration."""
    
    storage = CrawlStateStorage()
    state = storage.load_state(source_url) if not force_restart else None
    
    if state is None:
        state = CrawlState(
            source_url=source_url,
            scope=scope,
            max_pages=max_pages,
            frontier=[source_url],
        )
    
    # Load robots.txt
    robots = RobotsChecker(source_url)
    
    # Initialize parser
    parser = WebParser()
    pages_processed = 0
    
    while state.frontier and pages_processed < max_pages:
        url = state.frontier.pop(0)
        url_hash = _hash(url)
        
        # Skip if visited
        if url_hash in state.visited_hashes:
            continue
        
        # Check robots.txt
        if not robots.can_fetch(url):
            state.skipped_count += 1
            continue
        
        # Fetch page
        try:
            document = parser.extract(ParseTarget(source=url, is_remote=True))
            content = parser.to_markdown(document)
            
            # Store content
            content_path = _store_content(source_url, url, content)
            
            # Extract links
            links = extract_links(document.raw_content, url)
            in_scope = filter_urls_by_scope(links, source_url, scope)
            
            # Add to frontier
            for link in in_scope:
                if _hash(link) not in state.visited_hashes:
                    state.frontier.append(link)
            
            state.visited_count += 1
            state.discovered_count += len(links)
            state.in_scope_count += len(in_scope)
            
        except Exception as e:
            state.failed_count += 1
        
        state.visited_hashes.add(url_hash)
        pages_processed += 1
        
        # Checkpoint every 10 pages
        if pages_processed % 10 == 0:
            storage.save_state(state)
    
    # Final save
    state.status = "completed" if not state.frontier else "paused"
    storage.save_state(state)
    
    return {
        "pages_processed": pages_processed,
        "frontier_remaining": len(state.frontier),
        "status": state.status,
    }
```

---

## 3. Workflow Coordination Options

### 3.1 Option A: Issue-Based Coordination (Current)

```
Monitor Workflow → Creates Issue → [Wait for pickup] → Crawler Workflow (manual)
```

**Problems:**
- Human intervention required to dispatch Crawler
- Issues accumulate if not processed
- No feedback loop to Monitor

### 3.2 Option B: Direct Workflow Chaining

```yaml
# Monitor workflow can trigger Crawler workflow
- name: Trigger Crawler for Initial Acquisitions
  if: steps.monitor.outputs.initial_sources != '[]'
  uses: peter-evans/repository-dispatch@v3
  with:
    event-type: crawl-source
    client-payload: |
      {
        "sources": ${{ steps.monitor.outputs.initial_sources }}
      }
```

**Tradeoffs:**
- Requires workflow_dispatch handling in Crawler
- Matrix jobs for multiple sources
- Workflow run limits (concurrent runs)

### 3.3 Option C: Unified Pipeline Workflow

```yaml
name: "5. Op: Content Pipeline"

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:
    inputs:
      mode:
        type: choice
        options:
          - full      # Monitor + Crawler
          - monitor   # Detection only
          - crawl     # Acquisition only
        default: full

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      
      - name: Run Pipeline
        run: |
          if [ "${{ inputs.mode }}" = "full" ] || [ "${{ inputs.mode }}" = "monitor" ]; then
            python main.py pipeline monitor
          fi
          
          if [ "${{ inputs.mode }}" = "full" ] || [ "${{ inputs.mode }}" = "crawl" ]; then
            python main.py pipeline crawl --from-pending
          fi
      
      - name: Commit Changes
        uses: stefanzweifel/git-auto-commit-action@v5
```

---

## 4. State Unification Analysis

### 4.1 Current State Fragmentation

**Monitor State** (in `SourceEntry`):
```python
last_content_hash: str | None
last_etag: str | None
last_modified_header: str | None
last_checked: datetime | None
check_failures: int
next_check_after: datetime | None
```

**Crawler State** (in `CrawlState`):
```python
source_url: str
source_hash: str
scope: str
status: str
frontier: list[str]
visited_hashes: set[str]
visited_count: int
discovered_count: int
# ... more statistics
```

**Page State** (in `PageRegistry`):
```python
url: str
url_hash: str
status: str
content_hash: str | None
content_path: str | None
title: str | None
# ... more metadata
```

### 4.2 Proposed Unified Model

Instead of separate state stores, consider a unified source status:

```python
@dataclass
class SourceStatus:
    """Unified status for a monitored/crawled source."""
    
    # Identity
    url: str
    url_hash: str
    name: str
    
    # Monitor fields
    last_checked: datetime | None
    last_content_hash: str | None
    check_failures: int
    next_check_after: datetime | None
    
    # Crawler fields
    crawl_status: str  # pending, crawling, paused, completed
    crawl_scope: str
    pages_acquired: int
    frontier_size: int
    
    # Combined state
    needs_initial: bool  # last_content_hash is None
    needs_update: bool   # content changed since last acquisition
    has_crawl_data: bool # CrawlState exists
    
    @property
    def ready_for_crawl(self) -> bool:
        """Source is ready to be crawled."""
        return self.needs_initial or self.needs_update
```

---

## 5. CLI Design Options

### 5.1 Option A: Separate Commands

```bash
# Current pattern
python main.py agent run --mission monitor_sources
python main.py agent run --mission crawl_source --input source_url=...

# Proposed pattern
python main.py monitor check              # Run detection
python main.py monitor list-pending       # Show sources needing work
python main.py crawl run <source_url>     # Crawl one source
python main.py crawl resume               # Resume paused crawls
```

### 5.2 Option B: Unified Pipeline Command

```bash
# Single entry point for all pipeline operations
python main.py pipeline run               # Full pipeline (detect + acquire)
python main.py pipeline check             # Detection only
python main.py pipeline acquire           # Acquisition only
python main.py pipeline status            # Show pipeline state
```

### 5.3 Option C: Hybrid with LLM Fallback

```bash
# Programmatic by default, LLM for exceptions
python main.py pipeline run               # Pure Python
python main.py pipeline run --with-llm    # LLM for error recovery
python main.py agent run --mission ...    # Full LLM mode (legacy)
```

---

## 6. Implementation Effort Estimate

### 6.1 Minimal Refactor (Direction 2 from PLAN.md)

Add `--no-llm` bypass to existing agent:

| Task | Files | Effort |
|------|-------|--------|
| Add bypass flag to CLI | `src/cli/commands/agent.py` | 2 hours |
| Create `DirectPlanner` class | `src/orchestration/direct.py` | 4 hours |
| Map mission goals to execution | `src/orchestration/direct.py` | 8 hours |
| Update workflow YAML | `.github/workflows/*.yml` | 2 hours |
| Testing | `tests/orchestration/` | 4 hours |
| **Total** | | **20 hours** |

### 6.2 Full Pipeline Refactor (Direction 1 from PLAN.md)

Create new `src/knowledge/pipeline/` module:

| Task | Files | Effort |
|------|-------|--------|
| `pipeline/monitor.py` | New module | 4 hours |
| `pipeline/crawler.py` | New module | 6 hours |
| `pipeline/runner.py` | Orchestration | 4 hours |
| CLI commands | `src/cli/commands/pipeline.py` | 4 hours |
| Unified workflow | `.github/workflows/5-op-content-pipeline.yml` | 4 hours |
| State migration | Update existing data | 4 hours |
| Testing | `tests/knowledge/test_pipeline.py` | 8 hours |
| Documentation | `docs/guides/content-pipeline.md` | 4 hours |
| **Total** | | **38 hours** |

### 6.3 Risk Comparison

| Approach | Risk | Reason |
|----------|------|--------|
| Minimal Refactor | Low | Preserves existing code, adds bypass |
| Full Pipeline | Medium | New module, but uses tested components |
| Current State | High (cost) | Ongoing LLM token costs |

---

## 7. Test Coverage Review

### 7.1 Existing Coverage

| Module | Test File | Test Count |
|--------|-----------|------------|
| `crawl_state.py` | `test_crawl_state.py` | 34 tests |
| `page_registry.py` | `test_page_registry.py` | 28 tests |
| `monitoring.py` | `test_source_monitoring.py` | ~20 tests |
| `url_scope.py` | `test_url_scope.py` | 69 tests |
| `link_extractor.py` | `test_link_extractor.py` | 52 tests |

### 7.2 Required New Tests

For programmatic pipeline:

| Test | Purpose |
|------|---------|
| `test_monitor_pipeline.py` | Monitor logic without LLM |
| `test_crawler_pipeline.py` | Crawler logic without LLM |
| `test_pipeline_integration.py` | Full pipeline flow |
| `test_workflow_outputs.py` | GitHub Actions output format |

---

*Last Updated: 2025-12-31*
