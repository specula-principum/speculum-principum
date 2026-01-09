# Synthesis Agent: Merge Conflict Fix

## Problem Identified by QA

**Root Cause:** The CLI created multiple batch Issues in a single workflow run, all branching from the same commit.

**Original Code:**
```python
# synthesis.py (BROKEN)
for i in range(0, len(unresolved), batch_size):
    batch = unresolved[i:i + batch_size]
    create_issue(...)  # Creates Issue #1, #2, #3...
```

**Result:** All Issues created simultaneously → All PRs from same commit → Merge conflicts on shared files.

**Example:**
```
synthesis-queue runs once:
├── Creates Issue #1 (50 entities) → PR #1 from main@abc123
├── Creates Issue #2 (50 entities) → PR #2 from main@abc123 ← CONFLICT!
└── Creates Issue #3 (50 entities) → PR #3 from main@abc123 ← CONFLICT!
```

## Solution: Two-Part Fix

### Part 1: CLI Creates Only One Issue Per Run

**Changed:** `src/cli/commands/synthesis.py`

```python
# Before (BROKEN): Loop creates all batches
for i in range(0, len(unresolved), args.batch_size):
    batch = unresolved[i:i + args.batch_size]
    create_issue(...)  # Multiple Issues!

# After (FIXED): Create only first batch
batch = unresolved[:args.batch_size]
create_issue(...)  # Single Issue only
if remaining > 0:
    print(f"{remaining} entities remain (next batch)")
```

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
Trigger → Issue #1 created
       → PR #1 merges
       → Auto-trigger → Issue #2 created
       → PR #2 merges
       → Auto-trigger → Issue #3 created
       → ...until no work remains
```

### Three-Part Fix

| Component | File | What Changed |
|-----------|------|--------------|
| **CLI Logic** | `src/cli/commands/synthesis.py` | **CHANGED:** Only creates first batch (removed loop) |
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
