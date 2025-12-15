# Auto-Approval QA Testing Plan

## Overview
Light testing plan for the completed auto-approval feature set, covering cryptographic verification, topic-based discovery, fork blocking, and automated PR validation.

**Status:** Ready for testing  
**Testing Date:** TBD  
**Tester:** TBD

---

## Test Environment Setup

### ⚠️ Important Update: Actions Scope Required

**Issue:** QA testing revealed that PATs need the `actions:read` scope to read repository variables.

**Root Cause:** The GitHub API endpoint `/repos/{owner}/{repo}/actions/variables/{name}` requires special permissions to read Actions variables (secrets/variables).

**Known Issues:**
1. **Fine-grained PATs:** If using a fine-grained PAT, the token must:
   - Have "Actions: Read" permission selected
   - Have the specific repository added to "Repository access" list
   - Be owned by the same user/org as the target repository
2. **Classic PATs:** Must have `repo` + `workflow` scopes (not just `actions:read` alone)
3. **Organization repos:** May require additional org-level permissions

**Diagnostic Steps:**
1. Check PAT type: Settings → Developer settings → Personal access tokens
2. For **Fine-grained PATs**:
   - Verify "Variables: Read" permission is enabled (NOT "Actions")
   - Check "Repository access" → ensure test repo `terrence-giggy/mirror-revelation-space` is included
   - If restricted, add the repo explicitly or switch to "All repositories"
3. For **Classic PATs**:
   - Verify checkboxes: `repo` (full control), `workflow`
   - Note: Classic PATs only need `repo` scope for Variables API
4. Test token manually:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.github.com/repos/terrence-giggy/mirror-revelation-space/actions/variables/UPSTREAM_REPO
   ```

**Fix Applied:** All documentation updated to include complete permission requirements.

---

### ⚠️ Important Update: JSON Output Corruption Fixed

**Issue:** Initialize workflow's "Validate Setup Configuration" step failed with jq parse error:
```
jq: parse error: Invalid numeric literal at line 2, column 4
Error: Process completed with exit code 5.
```

**Root Cause:** When `validate-setup --json` was called, the Python function printed text output (validation messages) to stdout along with the JSON, corrupting the JSON structure that jq tried to parse.

**Fix Applied:**
- Added `quiet` parameter to `validate_setup()` function in [src/cli/commands/setup.py](src/cli/commands/setup.py)
- When `--json` flag is used, all print statements are suppressed (quiet=True)
- JSON output is now clean and parseable by jq
- Text output still works normally without `--json` flag

**Verification:**
```bash
# Clean JSON output
python -m main validate-setup --repo owner/repo --json | jq -r '.valid'
# Returns: true

# Text output still works
python -m main validate-setup --repo owner/repo
# Returns: formatted validation output with emojis
```

---

### ⚠️ Important Update: Sync Workflow Step Ordering Fixed

**Issue:** Downstream sync workflow failed with "No module named main" error during signature verification:
```
Run # Verify upstream repo matches allowed upstream
/usr/bin/python: No module named main
Error: Process completed with exit code 1.
```

**Root Cause:** The sync workflow was attempting to run `python -m main verify-dispatch` BEFORE checking out the repository code and installing dependencies. The workflow steps were in wrong order:
1. Block forks ✓
2. Verify dispatch signature ❌ (tried to run Python CLI without code)
3. Checkout code
4. Setup Python
5. Install dependencies

**Fix Applied:**
- Reordered steps in [.github/workflows/1-setup-sync-from-upstream.yml](.github/workflows/1-setup-sync-from-upstream.yml)
- Split verification into two steps:
  1. "Verify upstream repo matches" - bash-only checks (no dependencies needed)
  2. "Verify dispatch signature" - Python CLI verification (runs after checkout + dependencies)
- New order:
  1. Block forks ✓
  2. Verify upstream repo matches (bash only) ✓
  3. Checkout code ✓
  4. Setup Python ✓
  5. Install dependencies ✓
  6. Verify dispatch signature (Python CLI) ✓

**Impact:** Signature verification now works correctly in downstream repos receiving repository_dispatch events.

---

### ⚠️ Important Update: Malformed Bash Script Fixed

**Issue:** Downstream sync workflow failed with jq parse error after successfully syncing:
```
jq: parse error: Invalid numeric literal at line 1, column 10
```

**Root Cause:** The "Run sync" step in the workflow had malformed Python code mixed into the bash script (lines 207-211). The script contained:
```yaml
else:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write('changes_count=0\n')
"
```
This Python code was invalid in the bash context and caused the workflow to fail after the sync completed successfully.

**Fix Applied:**
- Removed the malformed Python code block from [.github/workflows/1-setup-sync-from-upstream.yml](.github/workflows/1-setup-sync-from-upstream.yml#L188-L202)
- The bash script now properly ends after the `fi` statement that closes the JSON parsing logic
- Workflow YAML syntax validated successfully

**Impact:** Sync workflow now completes successfully after creating pull requests in downstream repositories.

---

### ⚠️ Important Update: JSON Output Mixed with Progress Messages

**Issue:** Sync workflow continued to fail with jq parse error even after removing malformed Python code:
```
jq: parse error: Invalid numeric literal at line 1, column 10
Error: Process completed with exit code 5.
```

**Root Cause:** The `sync-upstream` command was outputting progress messages ("Resolving branches...", "Fetching repository trees...", etc.) to stdout along with the JSON output. When redirected to a file with `> /tmp/sync_result.json`, the file contained:
```
Resolving branches...
  Upstream branch: main
...
{
  "changes_count": 1,
  ...
}
```
jq could not parse this mixed content as valid JSON.

**Fix Applied:**
- Added `verbose` parameter to `sync_from_upstream()` function in [src/integrations/github/sync.py](src/integrations/github/sync.py)
- Added `verbose` parameter to `commit_files()` helper function
- Wrapped all progress print statements with `if verbose:` checks (28 print statements total)
- CLI handler in [src/cli/commands/sync.py](src/cli/commands/sync.py) now passes `verbose=not args.json`
- When `--json` flag is used, all text output is suppressed, only JSON is printed
- All 85 sync-related tests pass

**Verification:**
```bash
# Clean JSON output
python -m main sync-upstream --downstream-repo owner/downstream \
  --upstream-repo owner/upstream --json | jq -r '.changes_count'
# Returns: 1 (no mixed output)

# Text output still works
python -m main sync-upstream --downstream-repo owner/downstream \
  --upstream-repo owner/upstream
# Returns: formatted progress messages + summary
```

**Impact:** Sync workflow now outputs clean JSON parseable by jq, fixing the repository_dispatch workflow execution.

---

### ⚠️ Important Update: PR Validation Errors Fixed

**Issue:** Auto-merge workflow failed on "Validate PR file scope" step with no error information:
```
Run python -m main validate-pr \
Error: Process completed with exit code 1.
```

**Root Causes:**
1. **URL Construction Bug:** The `fetch_pull_request_files()` function was incorrectly formatting the repository name in the API URL. It used `f"{api_url}/repos/{normalized_repo}/..."` where `normalized_repo` is a tuple `('owner', 'name')`, resulting in malformed URLs like `/repos/('owner', 'name')/...` with control characters.

2. **Error Handling:** When exceptions occurred, the `validate-pr` command with `--json` flag would fail without outputting valid JSON, causing jq to fail silently.

3. **Workflow Error Visibility:** The workflow wasn't displaying validation output or jq parsing errors, making debugging difficult.

**Fixes Applied:**

1. **Fixed URL Construction** in [src/integrations/github/pull_requests.py](src/integrations/github/pull_requests.py):
   ```python
   # Before
   normalized_repo = normalize_repository(repository)
   endpoint = f"{api_url}/repos/{normalized_repo}/pulls/{pr_number}/files"
   
   # After  
   normalized_repo = normalize_repository(repository)
   owner, name = normalized_repo
   endpoint = f"{api_url}/repos/{owner}/{name}/pulls/{pr_number}/files"
   ```
   Applied to both `fetch_pull_request()` and `fetch_pull_request_files()`

2. **Improved Error Handling** in [src/cli/commands/github.py](src/cli/commands/github.py):
   - Always output valid JSON even when exceptions occur
   - Separate error handling for authentication vs validation failures
   - Include error messages in JSON response

3. **Enhanced Workflow Debugging** in [.github/workflows/4-auto-merge-sync-prs.yml](.github/workflows/4-auto-merge-sync-prs.yml):
   - Display validation JSON output before parsing
   - Check if validation file exists and has content
   - Show clear error messages for jq parsing failures
   - Use `2>&1 || true` to capture all output including errors

**Verification:**
```bash
# Command now works correctly
python -m main validate-pr --repo owner/repo --pr 4 --json
# Returns:
{
  "valid": true,
  "reason": "All 1 file(s) within allowed scope",
  "pr_number": 4
}

# Error handling also outputs valid JSON
python -m main validate-pr --repo invalid --pr 999 --json
# Returns:
{
  "valid": false,
  "reason": "Validation error: ...",
  "pr_number": 999
}
```

**Impact:** PR validation now works correctly and provides clear error messages when validation fails.

### Prerequisites
- [ ] Access to upstream repo (template repository)
- [ ] Access to at least 2 downstream satellite repos
- [ ] One repo with `speculum-downstream` topic
- [ ] One repo without proper setup (for negative testing)
- [ ] Admin permissions on test repos

### Configuration Checklist
- [ ] `GH_TOKEN` secret configured (Classic: `repo` + `workflow` | Fine-grained: Variables permission)
- [ ] `SYNC_SIGNATURE_SECRET` secret configured (shared between upstream/downstream)
- [ ] `UPSTREAM_REPO` variable set correctly
- [ ] Topic `speculum-downstream` added to satellite repos

---

## Test Cases

### 1. Fork Blocking

**1.1 Fork Detection in Sync Workflow**
- **Setup:** Create a fork of a satellite repo
- **Action:** Trigger `repository_dispatch` event on the fork
- **Expected:** Workflow exits early with "Repository is a fork" message
- **Status:** ⬜ Not Started
- **Result:** 

**1.2 Fork Detection in PR Auto-Merge**
- **Setup:** Use forked repo from 1.1
- **Action:** Create PR with branch `sync/upstream-test`
- **Expected:** Auto-merge workflow blocks with fork error
- **Status:** ⬜ Not Started
- **Result:**

**1.3 Fork Detection in Setup Validation**
- **Setup:** Run setup workflow on forked repo
- **Action:** Check validation step output
- **Expected:** Validation fails with "Repository is a fork" message
- **Status:** ⬜ Not Started
- **Result:**

---

### 2. HMAC Signature Verification

**2.1 Valid Signature**
- **Setup:** Matching `SYNC_SIGNATURE_SECRET` on upstream and downstream
- **Action:** Trigger `notify_downstream_repos()` from upstream
- **Expected:** Downstream sync workflow succeeds, signature validates
- **Status:** ⬜ Not Started
- **Result:**

**2.2 Invalid Signature**
- **Setup:** Mismatched `SYNC_SIGNATURE_SECRET` values
- **Action:** Send repository_dispatch with wrong signature
- **Expected:** Downstream sync fails with "Invalid dispatch signature" error
- **Status:** ⬜ Not Started
- **Result:**

**2.3 Missing Signature**
- **Setup:** Manual repository_dispatch without signature field
- **Action:** Trigger event via API
- **Expected:** Sync workflow rejects with missing signature error
- **Status:** ⬜ Not Started
- **Result:**

---

### 3. Topic-Based Discovery

**3.1 Discover Repos with Correct Topic**
- **Setup:** 2+ repos with `speculum-downstream` topic in org
- **Action:** Run `discover_downstream_repos(org)`
- **Expected:** Both repos returned in results
- **Status:** ⬜ Not Started
- **Result:**

**3.2 Filter Repos Without Topic**
- **Setup:** 1 repo with topic, 1 repo without
- **Action:** Run discovery function
- **Expected:** Only repo with topic returned
- **Status:** ⬜ Not Started
- **Result:**

**3.3 Empty Organization**
- **Setup:** Org with no downstream repos
- **Action:** Run discovery function
- **Expected:** Empty list returned, no errors
- **Status:** ⬜ Not Started
- **Result:**

---

### 4. Satellite Trust Verification

**4.1 Valid Satellite**
- **Setup:** Repo with: not fork, correct template_repository, has topic
- **Action:** Run `verify_satellite_trust(repo)`
- **Expected:** Returns `(True, None)`
- **Status:** ⬜ Not Started
- **Result:**

**4.2 Fork Detection**
- **Setup:** Forked repo with topic
- **Action:** Run trust verification
- **Expected:** Returns `(False, "Repository is a fork")`
- **Status:** ⬜ Not Started
- **Result:**

**4.3 Wrong Template**
- **Setup:** Repo created from different template with topic added
- **Action:** Run trust verification
- **Expected:** Returns `(False, "Template repository mismatch")`
- **Status:** ⬜ Not Started
- **Result:**

**4.4 Missing Topic**
- **Setup:** Valid repo without `speculum-downstream` topic
- **Action:** Run trust verification
- **Expected:** Returns `(False, "Missing required topic")`
- **Status:** ⬜ Not Started
- **Result:**

---

### 5. PR File Scope Validation

**5.1 Valid Code-Only PR**
- **Setup:** PR modifying only files in `CODE_DIRECTORIES` (src/, tests/, .github/)
- **Action:** Run `validate_pr_file_scope(repo, pr_number)`
- **Expected:** Returns `(True, None)`
- **Status:** ⬜ Not Started
- **Result:**

**5.2 Protected Directory Violation**
- **Setup:** PR modifying files in `evidence/` or `knowledge-graph/`
- **Action:** Run file scope validation
- **Expected:** Returns `(False, "Protected directories modified")`
- **Status:** ⬜ Not Started
- **Result:**

**5.3 Mixed Scope PR**
- **Setup:** PR with changes in both `src/` and `evidence/`
- **Action:** Run file scope validation
- **Expected:** Returns `(False, "Protected directories modified")`
- **Status:** ⬜ Not Started
- **Result:**

**5.4 Valid Config Files**
- **Setup:** PR updating `requirements.txt`, `pytest.ini`, `main.py`
- **Action:** Run file scope validation
- **Expected:** Returns `(True, None)`
- **Status:** ⬜ Not Started
- **Result:**

---

### 6. PR Auto-Merge Workflow

**6.1 Valid Sync PR**
- **Setup:** PR from branch `sync/upstream-20251214`, valid file scope
- **Action:** Create PR, let workflow run
- **Expected:** PR auto-approved and auto-merge enabled
- **Status:** ⬜ Not Started
- **Result:**

**6.2 Invalid Branch Pattern**
- **Setup:** PR from branch `feature/update-code`
- **Action:** Create PR, check workflow
- **Expected:** Workflow skips (not triggered or exits early)
- **Status:** ⬜ Not Started
- **Result:**

**6.3 Invalid File Scope**
- **Setup:** PR from `sync/upstream-*` modifying protected dirs
- **Action:** Create PR, let workflow run
- **Expected:** Validation fails, no auto-approval
- **Status:** ⬜ Not Started
- **Result:**

**6.4 PR on Fork**
- **Setup:** Fork repo, create sync PR
- **Action:** Let workflow attempt to run
- **Expected:** Workflow blocks immediately with fork error
- **Status:** ⬜ Not Started
- **Result:**

---

### 7. Setup Validation

**7.1 Complete Valid Setup**
- **Setup:** New satellite with all secrets, variables, and topic configured
- **Action:** Run setup workflow
- **Expected:** All validation checks pass, green summary
- **Status:** ⬜ Not Started
- **Result:**

**7.2 Missing GH_TOKEN**
- **Setup:** Repo without `GH_TOKEN` secret
- **Action:** Run setup validation
- **Expected:** Validation fails with missing secret error
- **Status:** ⬜ Not Started
- **Result:**

**7.3 Missing SYNC_SIGNATURE_SECRET**
- **Setup:** Repo without signature secret
- **Action:** Run setup validation
- **Expected:** Validation fails with missing secret error
- **Status:** ⬜ Not Started
- **Result:**

**7.4 Missing UPSTREAM_REPO Variable**
- **Setup:** Repo without variable configured
- **Action:** Run setup validation
- **Expected:** Validation fails with missing variable error
- **Status:** ⬜ Not Started
- **Result:**

**7.5 Missing Topic**
- **Setup:** Repo without `speculum-downstream` topic
- **Action:** Run setup validation
- **Expected:** Validation warns about missing topic
- **Status:** ⬜ Not Started
- **Result:**

**7.6 CLI Validation Command**
- **Setup:** Use repo from 7.1
- **Action:** Run `python main.py setup validate` via CLI
- **Expected:** Validation results posted as issue comment
- **Status:** ⬜ Not Started
- **Result:**

---

### 8. End-to-End Integration

**8.1 Full Sync Flow**
- **Setup:** Upstream with changes, 2 valid downstream repos
- **Action:** 
  1. Push changes to upstream `main`
  2. Trigger notification workflow
  3. Wait for downstream PRs
  4. Verify auto-approval
- **Expected:** Both downstream repos receive PRs that auto-approve and enable auto-merge
- **Status:** ⬜ Not Started
- **Result:**

**8.2 Discovery and Notify**
- **Setup:** 3 repos in org: 2 with topic, 1 without
- **Action:** Run notify workflow from upstream
- **Expected:** Only 2 repos with topic receive dispatch events
- **Status:** ⬜ Not Started
- **Result:**

**8.3 Signature Mismatch Handling**
- **Setup:** Upstream and downstream with different secrets
- **Action:** Trigger sync, observe downstream failure
- **Expected:** Clear error message about signature validation failure
- **Status:** ⬜ Not Started
- **Result:**

---

## Test Matrix Summary

| Category | Total Tests | Priority |
|----------|-------------|----------|
| Fork Blocking | 3 | High |
| HMAC Verification | 3 | High |
| Topic Discovery | 3 | Medium |
| Satellite Trust | 4 | High |
| File Scope | 4 | High |
| Auto-Merge | 4 | High |
| Setup Validation | 6 | Medium |
| E2E Integration | 3 | High |
| **Total** | **30** | - |

---

## Success Criteria

### Must Pass (Critical)
- [ ] All fork blocking tests (1.1, 1.2, 1.3)
- [ ] Valid and invalid HMAC tests (2.1, 2.2)
- [ ] Valid satellite trust (4.1)
- [ ] Code-only PR validation (5.1)
- [ ] Protected directory blocking (5.2)
- [ ] Valid sync PR auto-merge (6.1)
- [ ] Complete setup validation (7.1)
- [ ] Full E2E sync flow (8.1)

### Should Pass (Important)
- [ ] Missing signature handling (2.3)
- [ ] Discovery filtering (3.1, 3.2)
- [ ] Invalid branch pattern (6.2)
- [ ] Missing secrets detection (7.2, 7.3, 7.4)
- [ ] Discovery and notify E2E (8.2)

### Nice to Have
- [ ] Empty org handling (3.3)
- [ ] Wrong template detection (4.3)
- [ ] CLI validation (7.6)

---

## Known Limitations & Edge Cases

1. **Rate Limiting:** GitHub Search API limited to 30 req/min
   - Test with small batches only
   
2. **GraphQL Auto-Merge:** Requires specific permissions
   - Verify `GH_TOKEN` has `repo` + `workflow` scopes (Classic) OR Variables permission (Fine-grained)
   
3. **Repository Dispatch:** May have delays
   - Allow 30-60s between trigger and workflow start
   
4. **Topic Indexing:** GitHub topics may take time to index
   - Wait 5min after adding topic before testing discovery

---

## Test Execution Notes

### Before Testing
- [ ] Document baseline state of all test repos
- [ ] Backup any existing PRs/issues
- [ ] Verify all secrets are correctly configured
- [ ] Check workflow files are latest version

### During Testing
- Use checkboxes to mark test status: ⬜ Not Started, 🟡 In Progress, ✅ Pass, ❌ Fail
- Document actual results in "Result:" field
- Capture workflow run IDs for failed tests
- Screenshot validation errors

### After Testing
- [ ] Document all failures with reproduction steps
- [ ] Create issues for bugs found
- [ ] Update implementation plan if design changes needed
- [ ] Clean up test PRs and branches
- [ ] Archive workflow run logs

---

## Bug Report Template

```markdown
**Test Case:** [Test ID and name]
**Severity:** Critical / High / Medium / Low
**Status:** Open / In Progress / Resolved

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Result:**

**Actual Result:**

**Evidence:**
- Workflow run: [URL]
- Logs: [snippet or URL]
- Screenshots: [if applicable]

**Impact:**

**Fix Proposal:**
```

---

## Sign-Off

- [ ] All critical tests passed
- [ ] All bugs documented
- [ ] Implementation plan updated if needed
- [ ] Ready for production deployment

**QA Completed By:** _______________  
**Date:** _______________  
**Approved By:** _______________  
**Date:** _______________
