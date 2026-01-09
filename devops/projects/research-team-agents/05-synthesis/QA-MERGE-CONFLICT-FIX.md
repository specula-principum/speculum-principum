# Synthesis Agent: Merge Conflict Fix

## Problem Identified by QA

**Root Cause:** The CLI created multiple batch Issues in a single workflow run.

**Two Issues:**

1. **Batch Loop:** Created multiple Issues per entity type
```python
# BROKEN: Loop through batches
for i in range(0, len(unresolved), batch_size):
    create_issue(...)  # Issue #1, #2, #3...
```

2. **Entity Type Loop:** Created one Issue per entity type
```python
# BROKEN: Loop through types
for entity_type in ["Person", "Organization", "Concept"]:
    create_issue(...)  # 3 Issues total!
```

**Result:** All Issues created simultaneously → All PRs from same commit → Merge conflicts on shared files.

**Example:**
```
synthesis-queue runs once:
├── Creates Issue #1 (Person batch 1) → PR #1 from main@abc123
├── Creates Issue #2 (Org batch 1) → PR #2 from main@abc123 ← CONFLICT!
└── Creates Issue #3 (Concept batch 1) → PR #3 from main@abc123 ← CONFLICT!
```

## Solution: Two-Part Fix

### Part 1: CLI Creates Only One Issue Per Run

**Changed:** `src/cli/commands/synthesis.py`

```python
# Before (BROKEN): Loop creates all batches AND all types
for entity_type in ["Person", "Organization", "Concept"]:
    for i in range(0, len(unresolved), batch_size):
        create_issue(...)  # Multiple Issues!

# After (FIXED): Process first type with work, first batch only
for entity_type in ["Person", "Organization", "Concept"]:
    unresolved = gather_entities(entity_type)
    if not unresolved:
        continue  # Skip empty types
    
    batch = unresolved[:batch_size]  # Only first batch
    create_issue(...)
    return  # Exit after creating ONE Issue
```

**Key Changes:**
- ✅ Removed batch loop (only first batch)
- ✅ Exit after creating first Issue (only first entity type with work)
- ✅ Show remaining work in output for visibility

### Part 2: Auto-Continue After Merge

**Added:** `.github/workflows/synthesis-continue.yml`

- Triggers when synthesis PR merges
- Dispatches `synthesis-queue.yml` to create next batch
- Repeat until no work remains

### Combined Flow

**Before (Parallel - Broken):**
```
Trigger → Issue #1, #2, #3 all created
       → All PRs from same commit
       → Merge conflicts
```

**After (Sequential - Fixed):**
```
Run 1: Person entities found
       → Create Issue #1 (Person batch 1, 50 entities)
       → PR #1 merges → Continue trigger

Run 2: Person batch 2 OR Organization batch 1
       → Create Issue #2
       → PR #2 merges → Continue trigger

Run 3: Next batch/type with work
       → Create Issue #3
       → ...continues until all types and batches complete
```

### Three-Part Fix

| Component | File | What Changed |
|-----------|------|--------------|
| **CLI Logic** | `src/cli/commands/synthesis.py` | **CHANGED:** Creates only ONE Issue per run (removed batch loop AND exits after first entity type with work) |
| **Queue Gate** | `.github/workflows/synthesis-queue.yml` | **EXISTING:** Checks for open Issues before creating |
| **Auto-Continue** | `.github/workflows/synthesis-continue.yml` | **NEW:** Triggers next batch after PR merge |

### The New Workflow

**`.github/workflows/synthesis-continue.yml`**

**Trigger:** When any PR with label `synthesis` is merged

**Logic:**
1. Check if any `synthesis-batch` Issues are still open
2. If none open, dispatch `synthesis-queue.yml` to create next batch
3. Repeat until no more work remains

**Result:** Automatic sequential processing without merge conflicts

## Testing the Fix

### Setup Test Scenario

1. Extract 150+ entities (enough for 3+ batches at 50 entities/batch)
2. Trigger synthesis manually or wait for scheduled run

### Expected Behavior

```bash
# First trigger
synthesis-queue.yml runs → Creates Issue #1 → Copilot processes → PR #1

# After PR #1 merges
synthesis-continue.yml runs → Dispatches synthesis-queue.yml → Issue #2 → PR #2

# After PR #2 merges
synthesis-continue.yml runs → Dispatches synthesis-queue.yml → Issue #3 → PR #3

# After PR #3 merges (no work remains)
synthesis-continue.yml runs → Dispatches synthesis-queue.yml → No Issue created
```

### Verification Checklist

- [ ] Only one `synthesis-batch` Issue open at a time
- [ ] Each PR branches from latest `main` (includes previous PR's changes)
- [ ] No merge conflicts when PRs merge
- [ ] New batch automatically created after PR merge (if work remains)
- [ ] Pipeline stops gracefully when no work remains

### Manual Override

If needed, use force flag to bypass queue check:

```bash
# In GitHub Actions UI
workflow_dispatch on synthesis-queue.yml
→ Set force: true
```

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Copilot rate-limited mid-batch | Issue stays open, no new Issue created until resolved |
| Multiple triggers fire simultaneously | Race protected - only first creates Issue |
| Manual Issue closure | Next trigger creates new Issue normally |

## Files Modified

1. **Modified:** `src/cli/commands/synthesis.py` - Removed batch loop, create one Issue only
2. **Created:** `.github/workflows/synthesis-continue.yml` (67 lines) - Auto-trigger next batch
3. **Updated:** `devops/projects/research-team-agents/05-synthesis/PLAN.md` (added Sequential Processing section)

---

**Status:** Ready for QA re-test ✅

**Next Steps:**
1. Deploy to production
2. Test with real extraction pipeline
3. Monitor GitHub Actions logs for proper sequencing
4. Verify no merge conflicts occur

---

*Fix implemented: January 8, 2026*
