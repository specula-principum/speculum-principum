# Upstream Sync Guide
> Test sync: 2025-12-14

This guide explains how to keep your cloned research repository in sync with the upstream template repository (speculum-principum).

## Overview

The speculum-principum project is designed as a template that gets cloned for specific research topics. Cloned repositories need to receive code updates (bug fixes, new features) from the base template while preserving their own research content.

### How It Works

1. **Code directories** (`src/`, `tests/`, `.github/`, etc.) are synced from upstream
2. **Research directories** (`evidence/`, `knowledge-graph/`, `reports/`) are preserved locally
3. Sync creates a **Pull Request** for review before merging changes

## Setting Up Upstream Sync

### Step 1: Configure the Upstream Repository

After creating your research repo from the template, configure the upstream source:

#### Option A: Automatic Detection (Template Repos)

If your repository was created using GitHub's "Use this template" feature, the upstream is detected automatically. Simply run the setup workflow:

1. Go to **Actions** → **Initialize Repository**
2. Click **Run workflow**
3. The `UPSTREAM_REPO` variable will be set automatically

#### Option B: Manual Configuration

Set the `UPSTREAM_REPO` repository variable manually:

1. Go to **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. Click **New repository variable**
3. Name: `UPSTREAM_REPO`
4. Value: `owner/speculum-principum` (your template repo)

### Step 2: Set Up Authentication

The sync workflow needs a Personal Access Token (PAT) to create branches and pull requests:

1. Create a **classic** or **fine-grained** PAT:
   
   **Classic PAT** ([create here](https://github.com/settings/tokens/new)):
   - Select scopes: `repo` (full control of private repositories)
   
   **Fine-grained PAT** ([create here](https://github.com/settings/tokens?type=beta)):
   - **Repository access**: Only select repositories → choose your cloned repo
   - **Permissions**: 
     - Contents: Read and write
     - Pull requests: Read and write
     - Metadata: Read-only (automatic)

2. Go to your cloned repo's **Settings → Secrets and variables → Actions → Secrets**
3. Add secret named `GH_TOKEN` with your PAT

> **Note:** The sync now uses the Contents API which works with both classic and fine-grained PATs. Classic PATs with `repo` scope or fine-grained PATs with Contents/PR write permissions are both supported.

#### Optional: Private Upstream Authentication

If your upstream repository is **private**, you also need to provide access to it:

1. Create another PAT with read access to the upstream repo
2. Add it as a secret named `GH_TOKEN`

For **public** upstream repos, only `GH_TOKEN` is needed.

## Running a Sync

### Manual Sync

1. Go to **Actions** → **Sync from Upstream**
2. Click **Run workflow**
3. Fill in the options:
   - **upstream_repo**: Pre-filled from `UPSTREAM_REPO` variable
   - **upstream_branch**: Leave empty for default branch
   - **dry_run**: Check to preview changes without applying
   - **force_sync**: Check to skip validation and overwrite local changes
4. Click **Run workflow**

### Automatic Sync

The sync workflow runs automatically:
- **Weekly**: Every Sunday at midnight UTC
- **On release**: When the upstream publishes a release (if notifications are configured)

### Via API (Repository Dispatch)

Trigger sync programmatically:

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/OWNER/REPO/dispatches \
  -d '{"event_type":"upstream-sync","client_payload":{"upstream_repo":"owner/speculum-principum"}}'
```

## Understanding Sync Results

### Pull Request Created

When changes are detected, the workflow creates a PR with:
- Summary of added, updated, and removed files
- List of all changed files
- Link to compare with upstream

**Review the PR carefully** before merging to ensure changes are compatible with your research.

### No Changes

If your repository is already in sync, no PR is created.

### Validation Failed

If the sync detects **file differences** in code directories, it will fail with a warning to protect against data loss.

**Common causes:**
1. **Outdated files** (upstream has new changes) - This is normal on first sync or after upstream updates
2. **Local modifications** (you edited code files) - Rare in template workflows

**To proceed:**
- **First sync or receiving upstream updates**: Use `force_sync=true` - this is safe when you haven't edited code files
- **You made intentional code changes**: Review carefully before using `force_sync=true` or merge conflicts manually

> **Note**: The validation can't distinguish between outdated files and local modifications. If you know you haven't modified code directories, it's safe to force sync.

## Directory Classification

| Type | Directories | Behavior |
|------|-------------|----------|
| **Code** | `src/`, `tests/`, `.github/`, `config/missions/`, `docs/`, `main.py`, `requirements.txt`, `pytest.ini` | Synced from upstream |
| **Research** | `evidence/`, `knowledge-graph/`, `reports/`, `dev_data/`, `devops/` | Preserved locally, never synced |

## Sync Status Tracking

The following repository variables track sync history:

| Variable | Description |
|----------|-------------|
| `SYNC_LAST_SHA` | Commit SHA of last successful sync |
| `SYNC_LAST_TIME` | Timestamp of last sync |
| `SYNC_COUNT` | Total number of syncs performed |
| `SYNC_LAST_PR` | PR number from last sync |

## Troubleshooting

### "No upstream repository specified"

Set the `UPSTREAM_REPO` repository variable or provide it as a workflow input.

### "Local modifications detected"

Your code directories have changes not present in upstream. Either:
1. Commit your changes to a separate branch first
2. Run with `force_sync=true` to overwrite (⚠️ data loss risk)

### "Resource not accessible by personal access token" (403 error)

This error occurred in older versions that used the Git Data API. The sync has been updated to use the Contents API which works with standard PATs.

**If you're still seeing this error:**
1. Make sure you're using the latest version of the sync code
2. Verify your `GH_TOKEN` has the required permissions:
   - Classic PAT: `repo` scope
   - Fine-grained PAT: Contents (write) + Pull requests (write)
3. Check that the token hasn't expired
4. Ensure the token has access to the target repository

### "Failed to reach GitHub API"

Check:
- Network connectivity
- Token permissions (needs `repo` scope for private repos)
- Rate limits (5,000 requests/hour)

### Workflow file changes not applied

GitHub Actions workflows in `.github/workflows/` are synced but may require manual re-enabling if they were previously disabled.

## For Template Maintainers

### Notifying Downstream Repos

When releasing updates, notify downstream repositories:

1. Configure the `DOWNSTREAM_REPOS` repository variable:
   - Go to **Settings → Secrets and variables → Actions → Variables**
   - Create a new variable named `DOWNSTREAM_REPOS`
   - Set value as a JSON array:
   ```json
   ["owner/research-repo-1", "owner/research-repo-2"]
   ```

2. Add a PAT secret named `DOWNSTREAM_TOKEN` with write access to downstream repos

3. The **Notify Downstream Repos** workflow runs automatically on releases

> **Why a variable?** Using repository variables keeps the list upstream-only and prevents it from being cloned with template repos.

### Best Practices

- Use semantic versioning for releases
- Document breaking changes in release notes
- Test sync with a staging repo before major releases
- Keep the downstream registry updated

## API Reference

### Key Functions (for developers)

```python
from src.integrations.github.sync import (
    sync_from_upstream,      # Main sync operation
    validate_pre_sync,       # Check for local modifications
    get_sync_status,         # Read sync tracking variables
    configure_upstream_variable,  # Set UPSTREAM_REPO variable
)
```

### Example: Dry Run Sync

```python
from src.integrations.github.sync import sync_from_upstream

result = sync_from_upstream(
    downstream_repo="owner/my-research",
    upstream_repo="owner/speculum-principum",
    downstream_token=token,
    dry_run=True,
)

print(result.summary())
print(f"Changes: {len(result.changes)}")
```
