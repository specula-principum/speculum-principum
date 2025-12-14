# Automated PR Approval with Multi-Repo Trust

## Overview

Implement tiered auto-merge with cryptographic dispatch verification, dynamic satellite discovery via repository topics, and enhanced setup validation. Fully replace static JSON registry; block forks.

## Status: ✅ COMPLETED

All tasks have been implemented and integrated into the system.

## Completed Steps

### 1. ✅ Add dispatch verification to sync workflow
**File:** `.github/workflows/1-setup-sync-from-upstream.yml`

**Implemented:**
- Fork blocking check (`github.event.repository.fork`)
- Upstream repo validation against `vars.UPSTREAM_REPO`
- HMAC-SHA256 signature verification for repository_dispatch events
- Early exit with clear error messages on validation failure

### 2. ✅ Implement HMAC-signed dispatch payloads
**File:** `src/integrations/github/sync.py`

**Implemented:**
- `verify_dispatch_signature()` function using HMAC-SHA256
- Signature format: `hmac(secret, "upstream_repo|upstream_branch|timestamp")`
- Integration into `notify_downstream_repos()` function

### 3. ✅ Replace static registry with topic-based discovery
**File:** `src/integrations/github/sync.py`

**Implemented:**
- `discover_downstream_repos()` using GitHub Search API
- Query: `topic:speculum-downstream org:{org}`
- Dynamic discovery eliminates need for manual registry
- Removed `DOWNSTREAM_REPOS` JSON variable usage

### 4. ✅ Add satellite trust verification
**File:** `src/integrations/github/sync.py`

**Implemented:**
- `verify_satellite_trust()` function checking:
  - `repository.fork == false`
  - `template_repository` matches upstream
  - Has topic `speculum-downstream`
- Returns `(is_trusted, reason)` tuple

### 5. ✅ Create PR validation workflow
**File:** `.github/workflows/4-auto-merge-sync-prs.yml`

**Implemented:**
- Trigger on PRs with branch pattern `sync/upstream-*`
- Fork blocking
- File scope validation via Python function
- Branch and metadata verification
- Auto-merge enablement using GraphQL API
- Automatic PR approval

### 6. ✅ Add file-scope validation function
**File:** `src/integrations/github/sync.py`

**Implemented:**
- `validate_pr_file_scope()` function
- Checks all PR files against `CODE_DIRECTORIES`, `CODE_FILES`, `PROTECTED_DIRECTORIES`
- Returns `(is_valid, reason)` tuple
- Integration with `fetch_pull_request_files()` from pull_requests.py

### 7. ✅ Enhance setup workflow with validation
**File:** `.github/workflows/1-setup-initialize-repo.yml`

**Implemented:**
- Post-setup validation step checking:
  - GH_TOKEN secret exists
  - UPSTREAM_REPO variable configured
  - SYNC_SIGNATURE_SECRET exists
  - Repository not a fork
  - Repository has speculum-downstream topic
  - Template repository matches UPSTREAM_REPO
- Validation results posted to job summary
- Setup checklist provided

### 8. ✅ Add setup validation CLI command
**File:** `src/cli/commands/setup.py`

**Implemented:**
- `validate_setup()` function with comprehensive checks
- Integration into `setup_repo_cli()` 
- Validation results posted as issue comment
- Includes setup checklist for users

### 9. ✅ Document trust model and setup process
**File:** `docs/guides/upstream-sync.md`

**Implemented:**
- Trust Architecture table with all verification layers
- Auto-Approval Matrix showing PR types and conditions
- Manual setup steps with detailed instructions
- Security model explanation (HMAC, fork blocking, etc.)
- Template maintainer guide with topic-based discovery
- Migration notes from static registry

### 10. ✅ Remove deprecated downstream registry
**Files:** `config/downstream-repos.example.json`, `.github/workflows/3-mgmt-notify-downstream.yml`

**Implemented:**
- Deleted `config/downstream-repos.example.json`
- Updated notify workflow to use `notify_downstream_repos()` function
- Replaced JSON variable logic with topic-based discovery
- Removed `DOWNSTREAM_REPOS` variable dependency

## Steps

### 1. Add dispatch verification to sync workflow
**File:** `.github/workflows/1-setup-sync-from-upstream.yml`

Add steps to:
- Check `github.event.repository.fork` and exit if true
- Validate `client_payload.upstream_repo` matches `vars.UPSTREAM_REPO`
- Verify HMAC signature from `client_payload.signature`

### 2. Implement HMAC-signed dispatch payloads
**File:** `src/integrations/github/sync.py`

- Modify `notify_downstream_repos()` to include `signature` field computed via HMAC-SHA256 using `SYNC_SIGNATURE_SECRET`
- Add `verify_dispatch_signature(payload, secret)` function

### 3. Replace static registry with topic-based discovery
**File:** `src/integrations/github/sync.py`

- Add `discover_downstream_repos(org, topic="speculum-downstream")` using GitHub Search API (`GET /search/repositories?q=topic:{topic}+org:{org}`)
- Remove `DOWNSTREAM_REPOS` JSON variable usage
- Update `notify_downstream_repos()` to call discovery function

### 4. Add satellite trust verification
**File:** `src/integrations/github/sync.py`

Create `verify_satellite_trust(repo)` that checks:
- `repository.fork == false`
- `repository.template_repository` matches upstream
- Has topic `speculum-downstream`

Use before notifying downstream repos.

### 5. Create PR validation workflow
**File:** `.github/workflows/4-auto-merge-sync-prs.yml` (new)

Trigger on `pull_request: [opened, reopened, synchronize]`

Jobs:
- Verify repo is not a fork
- Verify branch matches `sync/upstream-*`
- Call Python validation for file scope
- Enable auto-merge if all pass

### 6. Add file-scope validation function
**File:** `src/integrations/github/sync.py`

Create `validate_pr_file_scope(repo, pr_number)` using:
- `get_pull_request_files()` from issues.py
- Constants `CODE_DIRECTORIES`, `CODE_FILES`, `PROTECTED_DIRECTORIES`

Return `(eligible: bool, reason: str)`.

### 7. Enhance setup workflow with validation
**File:** `.github/workflows/1-setup-initialize-repo.yml`

Add validation steps after current setup:
- Verify `GH_TOKEN` secret exists and has required scopes
- Verify `UPSTREAM_REPO` variable is set
- Verify `SYNC_SIGNATURE_SECRET` secret exists
- Verify repo has topic `speculum-downstream`
- Verify repo is not a fork

### 8. Add setup validation CLI command
**File:** `src/cli/commands/setup.py`

- Add `validate_setup(repo)` function performing the checks from step 7 via API
- Extend `setup_repo_cli()` to call validation and report issues
- Post validation results as comment on setup issue

### 9. Document trust model and setup process
**File:** `docs/guides/upstream-sync.md`

Sections:
- Manual setup steps: template clone → add secrets (`GH_TOKEN` + `SYNC_SIGNATURE_SECRET`) → set `UPSTREAM_REPO` variable → add topic `speculum-downstream` → run setup workflow
- Trust verification chain
- Auto-approval matrix
- Fork blocking rationale

### 10. Remove deprecated downstream registry
- Delete `config/downstream-repos.example.json`
- Update any references in code/docs
- Remove `DOWNSTREAM_REPOS` variable handling from sync functions

---

## Trust Architecture

| Layer | Verification | Location |
|-------|-------------|----------|
| Fork blocking | `repository.fork == false` | Sync workflow, PR workflow, setup validation |
| Template origin | `template_repository` field | `verify_satellite_trust()` |
| Upstream allowlist | `vars.UPSTREAM_REPO` matches payload | Sync workflow |
| Signed dispatch | HMAC-SHA256 signature validation | Sync workflow |
| Satellite discovery | Topic `speculum-downstream` in org | `discover_downstream_repos()` |
| PR scope | Files in `CODE_DIRECTORIES`/`CODE_FILES` only | PR validation workflow |
| PR origin | Branch `sync/upstream-*` + expected author | PR validation workflow |

---

## Auto-Approval Matrix

| PR Type | Source | Auto-Approve | Conditions |
|---------|--------|--------------|------------|
| Upstream sync | Sync workflow | ✅ Yes | Valid signature, file scope valid, not fork |
| Knowledge/evidence | Copilot/workflow | ✅ Yes | Files only in `PROTECTED_DIRECTORIES`, author verified |
| Code changes | Copilot | ❌ No | Human review required |
| Manual PR | Human | ❌ No | Human review required |

---

## Follow-up Considerations

1. **Signature failure handling:** Fail workflow with clear error, create issue/alert for investigation
2. **Discovery rate limiting:** Add caching with TTL for GitHub Search API (30 req/min limit)
3. **Secret rotation:** Support dual-secret validation during rotation window
