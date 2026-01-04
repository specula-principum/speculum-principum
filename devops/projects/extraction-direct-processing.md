# Implementation Plan: Direct Extraction Processing (No Copilot)

**Goal:** Remove Copilot agent from extraction workflow, implement direct extraction with robust rate limit handling via GitHub Actions concurrency control and scheduled retries.

**Context:** Currently using Copilot agent assignment which consumes Pro plan quota. The agent architecture (LLM-based extraction tools) is good, but we want to call it directly from workflows instead of through Copilot's wrapper.

---

## Architecture Overview

**Before:** Issue labeled → Copilot assigned → Agent runs mission → Extracts
**After:** Issue labeled → Direct Python script → Uses extraction tools → Extracts

**Rate Limit Handling:**
- GitHub Actions `concurrency` limits to 1 extraction at a time (natural queue)
- `GitHubModelsClient` has 5 retries with exponential backoff (up to 10 min wait)
- Scheduled workflow re-queues items that hit persistent rate limits
- Failed extractions keep issue open with `extraction-rate-limited` label

---

## Implementation Tasks

### 1. Create Direct Extraction Script

**File:** `src/cli/commands/extraction_direct.py`

Create a new CLI command that mimics what the Copilot agent does but runs directly:

```python
"""Direct extraction processing without Copilot agent wrapper."""

def extract_directly(issue_number: int, repository: str, token: str) -> int:
    """
    Process extraction for an issue directly using extraction tools.
    
    This replaces the Copilot agent assignment approach.
    
    Steps:
    1. Fetch issue details, extract checksum from body
    2. Use assess_document_value tool (LLM assessment)
    3. If not substantive: mark_extraction_skipped, comment, label, close
    4. If substantive: 
       - extract_people_from_document
       - extract_organizations_from_document  
       - extract_concepts_from_document
       - extract_associations_from_document
       - mark_extraction_complete
       - create_extraction_pull_request
       - Comment with stats, label, close
    
    Returns:
        0 on success, 1 on error, 2 on rate limit (for workflow detection)
    """
    # Initialize extraction toolkit
    # Call tools in sequence
    # Handle RateLimitError specifically (return exit code 2)
    # Handle other errors (return exit code 1)
```

**Key Requirements:**
- Import `ExtractionToolkit` from `src.orchestration.toolkit.extraction`
- Import GitHub issue utilities from `src.integrations.github.issues`
- Catch `RateLimitError` specifically and return exit code 2
- Log all operations for debugging
- Call tools in the exact order specified in the mission

**Register the command:**
- Add to `src/cli/commands/__init__.py` 
- Add parser in `extraction_direct.py` with `register_commands(subparsers)`
- Command: `python main.py extraction-direct --issue-number N`

---

### 2. Update Main Extraction Workflow

**File:** `.github/workflows/extraction-process.yml`

Replace the Copilot assignment approach with direct execution:

```yaml
name: "Extraction: Process Queue"

on:
  issues:
    types: [labeled]

permissions:
  issues: write
  contents: write
  pull-requests: write

# CRITICAL: Limit concurrency to avoid rate limit bursts
concurrency:
  group: extraction-processing
  cancel-in-progress: false  # Queue them, don't cancel

jobs:
  extract:
    if: github.event.label.name == 'extraction-queue'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: 'pip'
          
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run Direct Extraction
        id: extract
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python main.py extraction-direct \
            --issue-number ${{ github.event.issue.number }} \
            --repository ${{ github.repository }} \
            2>&1 | tee extraction.log
          echo "exit_code=$?" >> $GITHUB_OUTPUT
      
      - name: Handle Rate Limit Errors
        if: steps.extract.outputs.exit_code == '2'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue edit ${{ github.event.issue.number }} \
            --remove-label "extraction-queue" \
            --add-label "extraction-rate-limited"
          
          gh issue comment ${{ github.event.issue.number }} \
            --body "⏸️ Rate limit encountered. Will retry automatically in 30 minutes."
      
      - name: Handle Other Errors
        if: steps.extract.outputs.exit_code == '1'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue edit ${{ github.event.issue.number }} \
            --remove-label "extraction-queue" \
            --add-label "extraction-error"
          
          # Post error comment with log excerpt
          echo "❌ Extraction failed. Check workflow logs for details." | \
            gh issue comment ${{ github.event.issue.number }} --body-file -
```

**Key Changes:**
- Remove Copilot assignment step
- Add `concurrency` group to limit to 1 concurrent extraction
- Use `continue-on-error` to handle failures gracefully
- Check exit code to differentiate rate limits (2) from errors (1)
- Auto-label rate-limited issues for retry workflow

---

### 3. Create Retry Workflow for Rate-Limited Issues

**File:** `.github/workflows/extraction-retry.yml`

New workflow to periodically re-queue rate-limited extractions:

```yaml
name: "Extraction: Retry Rate Limited"

on:
  schedule:
    # Run every 30 minutes
    - cron: '*/30 * * * *'
  
  # Allow manual triggering
  workflow_dispatch:

permissions:
  issues: write

jobs:
  retry:
    runs-on: ubuntu-latest
    
    steps:
      - name: Find and Re-queue Rate Limited Issues
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Get all issues with extraction-rate-limited label
          gh issue list \
            --repo ${{ github.repository }} \
            --label "extraction-rate-limited" \
            --state open \
            --json number \
            --jq '.[].number' | while read issue_num; do
            
            echo "Re-queuing issue #$issue_num"
            
            # Swap labels to trigger extraction workflow again
            gh issue edit "$issue_num" \
              --remove-label "extraction-rate-limited" \
              --add-label "extraction-queue"
            
            # Space out re-queuing to avoid burst (10s between each)
            sleep 10
          done
          
          echo "Re-queue complete"
```

**Key Features:**
- Runs every 30 minutes automatically
- Can be triggered manually from Actions tab
- Finds all `extraction-rate-limited` issues
- Swaps label back to `extraction-queue` to re-trigger
- Spaces out re-queuing (10s delay) to avoid burst

---

### 4. Update Extraction Queue CLI Commands

**File:** `src/cli/commands/extraction_queue.py`

Update the Issue body template to reflect direct processing:

**Changes needed:**
1. Remove references to "@copilot" assignment
2. Update instructions to say "This issue will be processed automatically"
3. Simplify the instructions since user doesn't need to guide Copilot

**New template section:**
```markdown
## Automatic Processing

This issue will be processed automatically by the extraction workflow.

The workflow will:
1. ✅ Assess if content is substantive (using LLM)
2. ✅ Extract entities if substantive (people, orgs, concepts, associations)
3. ✅ Create a PR with changes
4. ✅ Close this issue with results

**If rate limited:** Issue will be labeled `extraction-rate-limited` and retried in 30 minutes.

**If extraction fails:** Issue will be labeled `extraction-error` for manual review.

No manual intervention needed - just wait for the workflow to complete.
```

---

### 5. Update Documentation

**File:** `docs/guides/extraction-pipeline.md`

Update the extraction pipeline documentation:

1. Remove Copilot assignment sections
2. Document the new direct processing approach
3. Explain rate limit handling strategy
4. Add troubleshooting section for `extraction-rate-limited` and `extraction-error` labels

---

## Testing Plan

### Local Testing

```bash
# Test the direct extraction command locally
python main.py extraction-direct --issue-number <test-issue-number>

# Verify exit codes work correctly
echo $?  # Should be 0 (success), 1 (error), or 2 (rate limit)
```

### Workflow Testing

1. Create a test issue with `extraction-queue` label
2. Verify workflow triggers and runs extraction
3. Check concurrency works (label multiple issues simultaneously)
4. Test rate limit handling:
   - Force a rate limit error (may need to create many test issues)
   - Verify issue gets `extraction-rate-limited` label
   - Wait for retry workflow (or trigger manually)
   - Verify issue is re-queued

---

## Migration Steps

1. ✅ Keep existing extraction tools (already implemented)
2. Create `extraction_direct.py` CLI command
3. Test locally with a real extraction queue issue
4. Create new workflow files (but don't activate yet)
5. Test new workflows in a test repository or branch
6. Rename old workflow: `extraction-process.yml.disabled`
7. Activate new workflows
8. Monitor first few extractions
9. Update documentation
10. Clean up old workflow file after confirmation

---

## Rollback Plan

If issues arise:
1. Remove `extraction-queue` label from all pending issues
2. Rename new workflows: `*.yml.disabled`
3. Rename old workflow back: `extraction-process.yml`
4. Issues can be re-labeled to use old Copilot approach

---

## Success Criteria

- ✅ Extractions complete without Copilot assignment
- ✅ Rate limits handled gracefully (auto-retry)
- ✅ Concurrency prevents rate limit bursts
- ✅ Failed extractions clearly labeled for investigation
- ✅ Zero manual intervention needed for normal operation
- ✅ Copilot Pro plan usage reduced to zero for extractions

---

## Notes

- The extraction tools we built are still used (no changes needed there)
- `GitHubModelsClient` is still used (for LLM calls), just not wrapped in Copilot agent
- The mission file (`extract_document.yaml`) is no longer used but keep it for reference
- GitHub Actions concurrency limits per repo, so this naturally queues all extractions
- 30-minute retry interval is configurable in the cron schedule

---

## Reference Files

- Extraction tools: `src/orchestration/toolkit/extraction.py` (already implemented)
- GitHub issue utilities: `src/integrations/github/issues.py`
- GitHub Models client: `src/integrations/github/models.py`
- Current workflow: `.github/workflows/extraction-process.yml`
