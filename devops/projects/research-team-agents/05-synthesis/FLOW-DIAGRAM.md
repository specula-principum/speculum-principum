# Sequential Processing Flow Diagram

## Before Fix: Parallel Processing (BROKEN)

```
Time →
═══════════════════════════════════════════════════════════════════════

Trigger (extraction completes)
│
├── synthesis-queue.yml runs
│   ├── Checks for open Issues: NONE FOUND
│   ├── Creates Issue #1 (50 entities)
│   ├── Creates Issue #2 (50 entities)
│   └── Creates Issue #3 (50 entities)
│
├── All branch from main@abc123 ←────── PROBLEM: Same commit!
│
├── Copilot processes Issue #1 → PR #1 (branch: synthesis-batch-1)
├── Copilot processes Issue #2 → PR #2 (branch: synthesis-batch-2)
└── Copilot processes Issue #3 → PR #3 (branch: synthesis-batch-3)

PR #1 merges → main@def456 ✅
│
├── PR #2 tries to merge → CONFLICT ❌
│   └── alias-map.json changed in def456 (from PR #1)
│
└── PR #3 tries to merge → CONFLICT ❌
    └── alias-map.json changed in def456 (from PR #1)

RESULT: 1 successful merge, 2 failed merges requiring manual resolution
```

## After Fix: Sequential Processing (WORKING)

```
Time →
═══════════════════════════════════════════════════════════════════════

T=0: Trigger (extraction completes)
│
└── synthesis-queue.yml runs
    ├── Checks for open Issues: NONE FOUND ✅
    ├── Creates Issue #1 (50 entities)
    └── Skips creating more (queue gate active)

T=1: Copilot processes Issue #1
│
├── Branches from main@abc123
├── Processes 50 entities
├── Creates PR #1
└── pr-auto-approve-kb.yml merges → main@def456 ✅

T=2: synthesis-continue.yml detects PR merge
│
└── Dispatches synthesis-queue.yml
    ├── Checks for open Issues: NONE FOUND ✅
    ├── Creates Issue #2 (50 entities)
    └── Skips creating more (queue gate active)

T=3: Copilot processes Issue #2
│
├── Branches from main@def456 ←────── Includes PR #1 changes!
├── Processes 50 entities
├── Creates PR #2
└── pr-auto-approve-kb.yml merges → main@ghi789 ✅

T=4: synthesis-continue.yml detects PR merge
│
└── Dispatches synthesis-queue.yml
    ├── Checks for open Issues: NONE FOUND ✅
    ├── Creates Issue #3 (50 entities)
    └── Skips creating more (queue gate active)

T=5: Copilot processes Issue #3
│
├── Branches from main@ghi789 ←────── Includes PR #1 + #2 changes!
├── Processes 50 entities
├── Creates PR #3
└── pr-auto-approve-kb.yml merges → main@jkl012 ✅

T=6: synthesis-continue.yml detects PR merge
│
└── Dispatches synthesis-queue.yml
    ├── Checks for remaining work: NONE FOUND ✅
    └── Does NOT create Issue (pipeline complete)

RESULT: 3 successful merges, 0 conflicts, automatic progression ✅
```

## Key Differences

| Aspect | Before (Broken) | After (Fixed) |
|--------|-----------------|---------------|
| **Issue Creation** | All at once | One at a time |
| **Branch Point** | Same commit (main@abc123) | Latest main after each merge |
| **Conflicts** | Guaranteed on shared files | None - sequential writes |
| **Progression** | Manual (resolve conflicts) | Automatic (trigger on merge) |
| **Human Intervention** | Required for conflicts | None (fully automated) |

## Workflow Responsibilities

```
┌────────────────────────────────────────────────────────────────┐
│                  WORKFLOW COORDINATION                          │
└────────────────────────────────────────────────────────────────┘

synthesis-queue.yml
├─ Role: Queue Gate
├─ Trigger: workflow_run, schedule, manual
├─ Logic: IF no open synthesis-batch Issues THEN create one
└─ Output: Issue #N with 50 entities

pr-auto-approve-kb.yml
├─ Role: Auto-Merger
├─ Trigger: PR opened/updated
├─ Logic: IF only KB files changed THEN approve + merge
└─ Output: Merged PR → main updated

synthesis-continue.yml ← NEW WORKFLOW
├─ Role: Pipeline Driver
├─ Trigger: PR closed (if merged)
├─ Logic: IF synthesis PR merged AND no open Issues
│          THEN dispatch synthesis-queue.yml
└─ Output: Triggers next batch creation
```

## Testing Scenarios

### Scenario 1: Happy Path (150 entities)

```
Start: 150 entities extracted, none in canonical store

synthesis-queue → Issue #1 (50)
  → PR #1 merges
    → synthesis-continue → synthesis-queue → Issue #2 (50)
      → PR #2 merges
        → synthesis-continue → synthesis-queue → Issue #3 (50)
          → PR #3 merges
            → synthesis-continue → synthesis-queue → (no Issue - done!)

End: 150 entities in canonical store, 0 conflicts ✅
```

### Scenario 2: Rate Limit Mid-Batch

```
synthesis-queue → Issue #1 (50)
  → Copilot processes 30/50 entities
    → Rate limit hit!
      → Issue #1 stays OPEN
        → synthesis-continue (on next PR merge) sees open Issue
          → Does NOT dispatch (queue busy)
            → Wait for rate limit to clear...
              → Copilot resumes Issue #1
                → PR #1 merges
                  → synthesis-continue → Issue #2... (continues normally)

End: Graceful handling, no duplicate Issues ✅
```

### Scenario 3: Concurrent Triggers

```
T=0: Extraction completes → synthesis-queue dispatched
T=0.1: Scheduled cron → synthesis-queue dispatched (again!)

synthesis-queue (first) → Checks for Issues → None → Creates Issue #1
synthesis-queue (second) → Checks for Issues → Issue #1 exists! → Skips

End: Only one Issue created (race protected) ✅
```

---

**Summary:** The fix creates a feedback loop where each PR merge triggers the next batch, ensuring sequential processing without merge conflicts.
