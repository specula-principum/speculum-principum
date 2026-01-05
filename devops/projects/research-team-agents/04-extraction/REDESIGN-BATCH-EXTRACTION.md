# Extraction Agent Redesign: Batch Processing with Event-Driven Triggers

**Status:** 📋 Ready for Implementation  
**Created:** 2026-01-04  
**Supersedes:** Original issue-per-document design in PLAN.md

---

## Problem Statement

The current extraction agent design (one GitHub Issue per document) has critical failures:

1. **Concurrency limiter ineffective** - All issues trigger simultaneously despite `cancel-in-progress: false`
2. **Rate limiting without recovery** - Individual documents hit LLM rate limits, retry cycle is 30 minutes
3. **Poor resource utilization** - Each document runs in isolated workflow with setup overhead
4. **No batch completion guarantee** - Documents process independently; no holistic "queue complete" state
5. **PR proliferation** - One PR per document creates review burden and potential conflicts

**Core Requirements:**
- **Rate limit resilience** - Must handle LLM endpoint rate limits gracefully with resume capability
- **Proper bookkeeping** - Every extraction must have receipt/record
- **Single PR strategy** - Cannot have multiple extraction PRs open simultaneously
- **Event-driven processing** - Trigger when documents added, not scheduled polling
- **Clean completion detection** - Know when entire queue is processed, auto-merge PR

---

## Solution Architecture

### Design: Manifest-Driven Batch Processing with Persistent PR Branch

**Key Principles:**
1. **Manifest is the queue** - No GitHub Issues for queue management
2. **One PR branch** - All extractions commit to `extraction/queue` branch
3. **Event-driven** - Trigger on push to `evidence/parsed/**`, not scheduled cron
4. **Append-only entities** - Files named by source checksum, never conflicts
5. **Discussion bookkeeping** - GitHub Discussion receives per-document receipts
6. **Auto-merge on clean** - PR merges automatically when all documents processed

### Workflow Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BATCH EXTRACTION PIPELINE FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

   Content Pipeline              Extraction Workflow           Post-Merge
   (adds documents)              (event-triggered)             (aggregation)
         │                              │                            │
         ▼                              │                            │
┌─────────────────┐                     │                            │
│ Parse documents │                     │                            │
│ Update manifest │                     │                            │
│ Commit to main  │                     │                            │
└────────┬────────┘                     │                            │
         │                              │                            │
         │ Push to evidence/parsed/     │                            │
         └─────────────────────────────▶│                            │
                                        ▼                            │
                               ┌─────────────────┐                   │
                               │ Query manifest  │                   │
                               │ Get N pending   │                   │
                               │ documents       │                   │
                               └────────┬────────┘                   │
                                        │                            │
                                        ▼                            │
                               ┌─────────────────┐                   │
                               │ Ensure PR open  │                   │
                               │ extraction/queue│                   │
                               └────────┬────────┘                   │
                                        │                            │
                                        ▼                            │
                               ┌─────────────────┐                   │
                               │ Loop: Process   │                   │
                               │ each doc        │                   │
                               │ sequentially    │                   │
                               └────────┬────────┘                   │
                                        │                            │
                      ┌─────────────────┼─────────────────┐          │
                      │                 │                 │          │
                  Success          Rate Limited        Error         │
                      │                 │                 │          │
                      ▼                 ▼                 ▼          │
             ┌─────────────────┐ ┌─────────────┐ ┌─────────────┐   │
             │ Post Discussion │ │ Update      │ │ Post error  │   │
             │ receipt         │ │ manifest    │ │ label issue │   │
             │ Mark complete   │ │ Exit code 42│ │ Exit code 1 │   │
             └────────┬────────┘ └──────┬──────┘ └─────────────┘   │
                      │                 │                            │
                      ▼                 ▼                            │
             ┌─────────────────┐ ┌─────────────┐                    │
             │ Next document   │ │ Schedule    │                    │
             │ in batch        │ │ retry after │                    │
             │                 │ │ 30 minutes  │                    │
             └────────┬────────┘ └─────────────┘                    │
                      │                                              │
                      ▼                                              │
             ┌─────────────────┐                                     │
             │ All docs done?  │                                     │
             │ Check manifest  │                                     │
             └────────┬────────┘                                     │
                      │                                              │
          ┌───────────┴───────────┐                                 │
          │ Pending > 0           │ Pending == 0                    │
          ▼                       ▼                                  │
    ┌──────────┐        ┌─────────────────┐                         │
    │ Leave PR │        │ Auto-merge PR   │                         │
    │ open for │        │ Delete branch   │─────────────────────────┤
    │ next run │        │ Trigger         │                         │
    └──────────┘        │ aggregation     │                         │
                        └────────┬────────┘                         │
                                 │                                   │
                                 └──────────────────────────────────▶│
                                                                     ▼
                                                            ┌─────────────────┐
                                                            │ Rebuild unified │
                                                            │ entity profiles │
                                                            │ (aggregation)   │
                                                            └─────────────────┘
```

---

## Implementation Plan

### Phase 1: Batch Extraction CLI (2 days)

**Goal:** Create command to process multiple documents in one run.

**Files to Create:**
- `src/cli/commands/extraction_batch.py` - New batch extraction logic

**Files to Modify:**
- `src/cli/commands/__init__.py` - Register new command
- `main.py` - Add `extraction run` command

**Command Interface:**
```bash
python main.py extraction run \
  --batch-size 10 \
  --repository owner/repo \
  --token $GH_TOKEN
```

**Logic:**
1. Query manifest for documents where:
   - `status == "completed"` (parsing done)
   - `extraction_complete` not in metadata
   - `extraction_skipped` not in metadata
   - Limit to `batch-size` documents
2. Ensure PR branch `extraction/queue` exists (create if needed)
3. Call `storage.begin_batch()` to defer commits
4. **For each document:**
   - Load content from `evidence/parsed/{artifact_path}`
   - Call existing extraction toolkit functions:
     - `assess_document_value()` (gpt-4o-mini)
     - If not substantive: set `extraction_skipped`, continue to next
     - If substantive: extract people, orgs, concepts, associations (4x gpt-4o calls)
   - Commit entities to `knowledge-graph/{type}/{checksum}.json`
   - Set `extraction_complete` in manifest metadata
   - Post Discussion receipt comment
   - **Rate limit handling:**
     - Catch `RateLimitError` exception
     - Set `extraction_rate_limited_at` in manifest metadata
     - Break loop, commit batch so far via `storage.flush_all()`
     - Exit with code 42
5. Call `storage.flush_all()` - Single commit to `extraction/queue` branch
6. Return exit code 0 (success) or 42 (rate limited)

**Metadata Fields to Add in ManifestEntry:**
- `extraction_complete: bool` - Entities extracted successfully
- `extraction_skipped: bool` - Document filtered as non-substantive
- `extraction_skipped_reason: str` - Why skipped
- `extraction_rate_limited_at: str` - ISO timestamp of last rate limit
- `extraction_last_batch_run: str` - Workflow run ID that processed this

**Error Handling:**
- `RateLimitError` → Exit 42 (handled gracefully, resume later)
- `GitHubIssueError` → Exit 1 (API failure, requires investigation)
- `Exception` (unexpected) → Exit 1 (log error, no retry)

---

### Phase 2: Event-Driven Workflow (1 day)

**Goal:** Trigger extraction automatically when documents added to evidence.

**Files to Create:**
- `.github/workflows/extraction-run.yml` - Main batch extraction workflow

**Workflow Triggers:**
```yaml
on:
  push:
    branches: [main]
    paths:
      - 'evidence/parsed/**'
      - 'evidence/parsed/manifest.json'
  
  workflow_dispatch:
    inputs:
      batch_size:
        description: 'Number of documents to process'
        default: '10'
      retry_after_rate_limit:
        description: 'Retry after rate limit (true/false)'
        default: 'false'
```

**Concurrency Control:**
```yaml
concurrency:
  group: extraction-run
  cancel-in-progress: false  # Queue runs, don't cancel
```

**Job Steps:**
1. Checkout code
2. Setup Python + install dependencies
3. Run extraction:
   ```bash
   python main.py extraction run \
     --batch-size ${{ inputs.batch_size || 10 }} \
     --repository ${{ github.repository }} \
     --token ${{ secrets.GH_TOKEN }}
   ```
4. Capture exit code
5. **If exit code 42 (rate limited):**
   - Sleep 30 minutes (or use GitHub Actions scheduled dispatch)
   - Re-trigger workflow with `retry_after_rate_limit: true`
6. **If exit code 0 (success):**
   - Check if manifest has pending documents
   - If pending count == 0:
     - Merge PR `extraction/queue` → `main`
     - Delete branch `extraction/queue`
     - Trigger aggregation workflow

**Auto-Merge Logic:**
```bash
# Check pending count
pending=$(python main.py extraction pending --count-only)

if [ "$pending" -eq 0 ]; then
  # Get PR number for extraction/queue branch
  pr_number=$(gh pr list --head extraction/queue --json number -q '.[0].number')
  
  if [ -n "$pr_number" ]; then
    # Auto-merge PR
    gh pr merge $pr_number --auto --squash
    
    # Delete branch (after merge completes)
    sleep 10
    gh api repos/${{ github.repository }}/git/refs/heads/extraction/queue -X DELETE
  fi
fi
```

---

### Phase 3: Discussion Bookkeeping (1 day)

**Goal:** Track extraction progress in GitHub Discussion.

**Files to Create:**
- `src/cli/commands/extraction_discussion.py` - Discussion management

**Files to Modify:**
- `src/integrations/github/discussions.py` - Add discussion creation/update helpers (if not exists)

**Commands:**
```bash
# Create or find progress discussion
python main.py extraction discussion init

# Post document receipt
python main.py extraction discussion receipt \
  --checksum abc123def456 \
  --people 3 \
  --orgs 2 \
  --concepts 5 \
  --batch-run $GITHUB_RUN_ID
```

**Discussion Structure:**

**Title:** "Extraction Progress Tracking"  
**Category:** Announcements  
**Pinned:** Yes

**Body (auto-updated):**
```markdown
# Extraction Queue Status

**Current PR:** [extraction/queue #47](url) (if open, else "No active PR")

**Progress:**
- ✅ Completed: 47 documents
- ⏸️ Rate Limited: 2 documents
- ⏭️ Skipped: 8 documents (non-substantive)
- 📋 Pending: 63 documents
- **Total:** 120 documents

**Last Run:** 2026-01-04 14:32 UTC (run #142)

---

## Recent Extractions (last 10)

<!-- Auto-generated comments appear below -->
```

**Comment Format:**
```markdown
✅ **doc-abc123de** extracted (batch run #142)
- 3 people, 2 organizations, 5 concepts, 7 associations
- Source: The Prince (Machiavelli)
- Artifact: `evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/index.md`
```

---

### Phase 4: Cleanup & Migration (1 day)

**Goal:** Remove old issue-based queue system.

**Files to Delete:**
- `.github/workflows/extraction-queue.yml` - Issue creation workflow
- `.github/workflows/extraction-process.yml` - Copilot assignment workflow
- `.github/workflows/extraction-retry.yml` - 30-min retry workflow
- `src/cli/commands/extraction_queue.py` - Queue management (issue-based)
- `src/cli/commands/extraction_direct.py` - Per-issue extraction (keep assess/extract functions, refactor into toolkit)
- `.github/ISSUE_TEMPLATE/extraction-queue.md` - Issue template
- `config/missions/extract_document.yaml` - Copilot mission (no longer used)

**Files to Refactor:**
- `src/orchestration/toolkit/extraction.py` - Keep core extraction functions, remove PR creation logic (move to batch CLI)

**Migration Steps:**
1. Close all open `extraction-queue` Issues with comment: "Extraction system migrated to batch processing. See Discussion: [link]"
2. Remove labels: `extraction-queue`, `extraction-rate-limited`, `extraction-complete`, `extraction-skipped`
3. Run initial batch to process any pending documents from old system

---

### Phase 5: Post-Merge Aggregation (1 day)

**Goal:** Rebuild unified entity profiles after extraction PR merges.

**Files to Create:**
- `.github/workflows/extraction-aggregate.yml` - Aggregation workflow
- `src/cli/commands/aggregate.py` - Aggregation CLI (if not exists)

**Workflow Trigger:**
```yaml
on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  aggregate:
    if: |
      github.event.pull_request.merged == true &&
      startsWith(github.event.pull_request.head.ref, 'extraction/queue')
    runs-on: ubuntu-latest
    steps:
      # Run aggregation to rebuild profiles
```

**Aggregation Logic:**
1. Scan all files in `knowledge-graph/{people,organizations,concepts,associations,profiles}/`
2. Build `AggregatedEntity` objects for each unique entity name
3. Optionally: Write materialized aggregates to `knowledge-graph/aggregated/{type}/{entity-name-slug}.json`
4. Update Discussion with aggregation summary

---

## Technical Details

### Entity Storage Pattern (Existing - No Changes)

**Append-Only by Source Checksum:**
```
knowledge-graph/
  people/
    abc123def456.json  # Document 1 extractions
    789fedcba098.json  # Document 2 extractions (no conflict!)
  profiles/
    abc123def456.json  # Detailed profiles from doc 1
    789fedcba098.json  # Detailed profiles from doc 2
```

**Why No Conflicts:**
- Each document creates NEW file with its checksum
- Different checksums = different filenames
- Concurrent PRs add different files
- Aggregation reads ALL files and merges in-memory

### Persistent PR Branch Strategy

**Branch Lifecycle:**
1. First document to extract: Create `extraction/queue` branch from `main`
2. Open PR: `extraction/queue` → `main` with title "Entity Extractions (Batch)"
3. Each workflow run: Commit to existing `extraction/queue` branch
4. PR accumulates commits over multiple runs
5. When manifest clean (all pending processed): Auto-merge PR
6. Delete branch after merge
7. Next document added: Recreate `extraction/queue` and start cycle again

**Branch Check Logic:**
```python
# In extraction_batch.py
def ensure_pr_branch_exists(repository: str, token: str) -> str:
    """Ensure extraction/queue branch exists, create PR if needed."""
    branch_name = "extraction/queue"
    
    # Check if branch exists
    try:
        github_client.get_branch(repository, branch_name)
        logger.info(f"Branch {branch_name} already exists")
        return branch_name
    except BranchNotFoundError:
        # Create branch from main
        main_sha = github_client.get_branch(repository, "main").sha
        github_client.create_branch(repository, branch_name, main_sha)
        
        # Create PR
        pr = github_client.create_pr(
            repository=repository,
            title="Entity Extractions (Batch)",
            body="Automated entity extraction from documents...",
            head=branch_name,
            base="main",
        )
        logger.info(f"Created PR #{pr.number} for {branch_name}")
        return branch_name
```

### Rate Limit Exit Code Convention

| Exit Code | Meaning | Workflow Response |
|-----------|---------|-------------------|
| 0 | Success - batch completed | Check manifest, auto-merge if clean |
| 42 | Rate limited - partial completion | Schedule retry after 30 min |
| 1 | Error - unexpected failure | Fail workflow, alert maintainer |

### Manifest Query for Pending Documents

```python
def get_pending_documents(storage: ParseStorage, limit: int = 10) -> list[ManifestEntry]:
    """Get documents ready for extraction."""
    pending = []
    for entry in storage.manifest.entries.values():
        # Must be successfully parsed
        if entry.status != "completed":
            continue
        
        # Skip if already extracted
        if entry.metadata.get("extraction_complete"):
            continue
        
        # Skip if marked non-substantive
        if entry.metadata.get("extraction_skipped"):
            continue
        
        pending.append(entry)
        
        if len(pending) >= limit:
            break
    
    return pending
```

### Discussion Update Frequency

- **Per document:** Post receipt comment (async, non-blocking)
- **Per batch run:** Update pinned post with statistics
- **On PR merge:** Post aggregation summary

---

## Testing Plan

### Unit Tests

**Files to Test:**
- `tests/cli/test_extraction_batch.py` - Batch processing logic
- `tests/cli/test_extraction_discussion.py` - Discussion management
- `tests/integrations/test_github_pr_branch.py` - PR branch lifecycle

**Test Scenarios:**
1. Query pending documents from manifest
2. Handle `RateLimitError` gracefully (exit 42)
3. Update manifest metadata after successful extraction
4. Skip already-extracted documents
5. Create PR branch if missing
6. Reuse existing PR branch
7. Parse Discussion for status updates

### Integration Tests

**Manual Testing Steps:**
1. Add test documents to `evidence/parsed/` via content pipeline
2. Trigger `extraction-run.yml` manually
3. Verify PR created at `extraction/queue`
4. Check Discussion for receipt comments
5. Simulate rate limit (set low batch size)
6. Verify retry after 30 min
7. Verify auto-merge when clean

---

## Rollout Strategy

### Phase 1: Parallel Systems (Week 1)
- Implement new batch system alongside old issue-based system
- Test with small subset of documents
- Compare outputs for consistency

### Phase 2: Migration (Week 2)
- Disable old workflows (don't delete files yet)
- Close pending extraction Issues with migration notice
- Run batch extraction on all pending documents
- Monitor Discussion for progress

### Phase 3: Cleanup (Week 3)
- Delete old workflow files
- Remove obsolete commands
- Update documentation

---

## Success Criteria

1. ✅ Documents trigger extraction automatically when added to `evidence/parsed/`
2. ✅ Only one PR open at a time for extractions (`extraction/queue`)
3. ✅ Rate limits handled gracefully with auto-resume
4. ✅ PR auto-merges when all pending documents processed
5. ✅ Every extraction has receipt in Discussion
6. ✅ Concurrent document additions queue properly (no conflicts)
7. ✅ Aggregation runs automatically after PR merge
8. ✅ Zero manual intervention required for normal operations

---

## Open Questions

1. **Batch size tuning** - Start with 10 documents/run or adjust based on rate limits?
   - **Recommendation:** Start with 5, increase if no rate limits observed

2. **Retry delay** - 30 minutes enough for LLM rate limit reset?
   - **Recommendation:** Make configurable, start with 30 min

3. **Orphaned PR cleanup** - What if workflow crashes without merging PR?
   - **Recommendation:** Weekly scheduled job to check for stale `extraction/queue` branches >7 days old

4. **Manual intervention** - How to re-process a document if extraction was bad?
   - **Recommendation:** CLI command `extraction reprocess --checksum abc123` clears metadata flags

5. **Aggregation materialization** - Should we cache aggregated profiles or compute on-demand?
   - **Recommendation:** Start with on-demand, add cache if performance issue

---

## Dependencies

### Existing Modules (Reuse)
- `src/knowledge/extraction.py` - Entity extractors
- `src/knowledge/storage.py` - Knowledge graph storage
- `src/knowledge/aggregation.py` - Entity aggregation
- `src/parsing/storage.py` - Manifest management
- `src/integrations/github/storage.py` - GitHub API batch commits
- `src/integrations/github/issues.py` - Issue/PR operations
- `src/orchestration/toolkit/extraction.py` - LLM-based extraction tools

### New Modules (Create)
- `src/cli/commands/extraction_batch.py` - Batch extraction CLI
- `src/cli/commands/extraction_discussion.py` - Discussion bookkeeping
- `src/integrations/github/pr_branches.py` - PR branch lifecycle (if not exists)

### External Dependencies (No Changes)
- GitHub API (issues, PRs, discussions, contents)
- LLM endpoint (OpenAI-compatible via GitHub Models)

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Batch Extraction CLI | 2 days | - |
| Phase 2: Event-Driven Workflow | 1 day | Phase 1 |
| Phase 3: Discussion Bookkeeping | 1 day | Phase 1 |
| Phase 4: Cleanup & Migration | 1 day | Phases 1-3 |
| Phase 5: Post-Merge Aggregation | 1 day | Phase 4 |
| **Testing & Documentation** | 2 days | All phases |
| **Total** | **8 days** | |

---

*Last Updated: 2026-01-04*
*Status: Ready for Implementation*
