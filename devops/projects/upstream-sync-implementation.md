# Upstream Sync Implementation Plan

**Project:** Template-to-Clone Code Sync Architecture  
**Created:** 2025-12-12  
**Status:** Phase 1-3 Complete, Phase 4 In Progress

## Problem Statement

This project (speculum-principum) is designed to be used as a base template that gets cloned for specific research topics. Cloned repos need to receive code updates from the base repo while maintaining their own research content.

**Current broken approach:** Using GitHub's template feature and attempting to add an upstream git remote. This fails because:
1. Template repos don't maintain an upstream relationship
2. The `git remote add` command is useless when all operations must happen on GitHub.com
3. GitHub doesn't allow forking into the same account/org multiple times

**Constraint:** All operations must work entirely on GitHub.com using Actions, Issues, Discussions, and Copilot—no local git operations.

---

## Solution Architecture

Use the **template model** with a **GitHub Actions-based sync workflow** that uses the GitHub API to fetch and apply code changes from the upstream template repository.

### Directory Classification

| Type | Directories | Sync Behavior |
|------|-------------|---------------|
| **Code (sync from upstream)** | `src/`, `tests/`, `.github/`, `config/missions/`, `docs/`, `main.py`, `requirements.txt`, `pytest.ini` | Overwrite from upstream |
| **Research (preserve locally)** | `evidence/`, `knowledge-graph/`, `reports/`, `dev_data/` | Never sync, preserve local |
| **Config (merge carefully)** | `config/settings/` (if exists) | Manual review required |

---

## Implementation Tasks

### Phase 1: Core Sync Infrastructure
- [x] **1.1** Create `sync-from-upstream.yml` workflow
  - Trigger: `workflow_dispatch` (manual) + `schedule` (weekly)
  - Inputs: upstream repo URL, branch, dry-run option
  - Uses GitHub API to fetch upstream files
  
- [x] **1.2** Create sync utility in `src/integrations/github/sync.py`
  - Function to enumerate files in code directories from upstream
  - Function to compare file contents (SHA comparison)
  - Function to create sync branch and commit changes
  - Function to open PR with change summary

- [x] **1.3** Update setup mission to capture upstream repo
  - Modify `config/missions/setup_repo.yaml` to store upstream URL
  - Store as repository variable `UPSTREAM_REPO`
  - Auto-detect from `template_repository` API field when available

### Phase 2: Notification System
- [x] **2.1** Create `notify-downstream.yml` in base repo
  - Trigger: `release` published or manual dispatch
  - Read list of registered downstream repos
  - Send `repository_dispatch` event to each

- [x] **2.2** Create downstream registry mechanism
  - GitHub Discussion category for registration
  - Or: JSON file in base repo with downstream repo list
  - Include PAT/App token handling documentation

- [x] **2.3** Add `on: repository_dispatch` trigger to sync workflow
  - React to upstream notifications
  - Auto-create sync PR when notified

### Phase 3: Conflict Resolution & Safety
- [x] **3.1** Implement pre-sync validation
  - Check for local modifications in code directories
  - Warn or block if unexpected changes detected
  - Option to force-overwrite

- [x] **3.2** Add sync status tracking
  - Create/update Issue with sync status
  - Record last successful sync commit SHA
  - Track sync history

- [x] **3.3** Test coverage
  - Unit tests for sync utilities
  - Integration tests with mock API responses
  - End-to-end test with actual repos

### Phase 4: Documentation & Rollout
- [x] **4.1** Update README.md with template usage instructions
- [x] **4.2** Create setup guide in `docs/guides/`
- [x] **4.3** Update `configure_template_remote` tool or replace it
- [ ] **4.4** Test with real cloned research repo

---

## Technical Details

### GitHub API Endpoints Used

| Purpose | Endpoint | Notes |
|---------|----------|-------|
| Get directory tree | `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` | Single call for entire structure |
| Get file content | `GET /repos/{owner}/{repo}/contents/{path}` | Base64 encoded content |
| Create/update file | `PUT /repos/{owner}/{repo}/contents/{path}` | Requires current SHA for update |
| Create branch | `POST /repos/{owner}/{repo}/git/refs` | From default branch HEAD |
| Create PR | `POST /repos/{owner}/{repo}/pulls` | Sync branch → main |
| Repository dispatch | `POST /repos/{owner}/{repo}/dispatches` | Cross-repo notification |

### Authentication Requirements

- **Downstream repos accessing upstream:** Need read access to upstream repo
  - If upstream is public: No extra auth needed
  - If upstream is private: PAT or GitHub App with repo read scope
  
- **Base repo notifying downstream:** Need write access to downstream repos
  - Requires PAT stored as secret in base repo
  - Or GitHub App installed on all repos

### Rate Limit Considerations

- GitHub API: 5,000 requests/hour (authenticated)
- Use Git Trees API for bulk file enumeration (1 request vs N requests)
- Cache upstream tree SHA to skip unchanged syncs
- Implement exponential backoff for retries

---

## Open Questions

1. **Should sync be fully automatic or require PR approval?**
   - Recommendation: PR-based for visibility, with auto-merge option for trusted updates

2. **How to handle workflow file updates?**
   - GitHub Actions in cloned repos won't auto-update
   - May need manual re-enable after sync

3. **What about breaking changes in code?**
   - Consider semantic versioning in base repo
   - Allow downstream to pin to specific version/tag

---

## Session Log

| Date | Session | Work Completed | Next Steps |
|------|---------|----------------|------------|
| 2025-12-12 | Initial planning | Researched options, confirmed fork limitations, created plan | Start Phase 1.1 |
| 2025-12-12 | Phase 1 implementation | Created `sync.py` with full sync utilities (tree enumeration, file comparison, branch creation, PR creation). Created `sync-from-upstream.yml` workflow with manual/scheduled/dispatch triggers. Added 28 unit tests (all passing). Exported sync utilities from `__init__.py`. | Continue with Phase 1.3 (setup mission) or Phase 2 (notification system) |
| 2025-12-12 | Phase 1.3 & Phase 2 | Added `configure_upstream_variable()`, `get_repository_variable()`, `set_repository_variable()`, `get_template_repository()` API functions. Updated `configure_upstream_remote` tool to use API-based variable setting instead of git commands. Created `notify-downstream.yml` workflow with release trigger and downstream registry support. Added `repository_dispatch` trigger to sync workflow. Created `downstream-repos.example.json`. Now at 37 passing tests. | Phase 3 (conflict resolution) or Phase 4 (documentation) |
| 2025-12-12 | Phase 3 & 4 | Added `ValidationResult`, `validate_pre_sync()`, `SyncStatus`, `get_sync_status()`, `update_sync_status()`. Integrated validation and status tracking into `sync_from_upstream()` with `force_sync` and `track_status` options. Updated workflow with `force_sync` input. Created comprehensive `docs/guides/upstream-sync.md` guide. Now at 46 passing tests. | Remaining: 4.1 (README update), 4.4 (real-world testing) |

