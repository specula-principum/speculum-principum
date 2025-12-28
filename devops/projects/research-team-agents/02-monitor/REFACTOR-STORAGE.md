# Storage Refactor: GitHub API Persistence

## Overview

**Problem:** Agent missions run in ephemeral GitHub Actions runners. Current storage classes (`SourceRegistry`, `KnowledgeGraphStorage`) write to local filesystem, which is discarded when the workflow ends.

**Solution:** Modify storage layer to persist writes directly via GitHub Contents API while keeping reads from local checkout (provided by `actions/checkout`).

**Status:** ✅ Completed (2025-12-27)

---

## Task Checklist

### Phase 1: Documentation & Awareness

- [x] **1.1** Update `.github/copilot-instructions.md` with GitHub Actions persistence rules
  - Document that all file writes in workflows must use GitHub API
  - Explain the local read / API write pattern
  - Add to Core Rules section
  - ✅ Already present in copilot-instructions.md

### Phase 2: GitHub API Write Layer

- [x] **2.1** Create `src/integrations/github/storage.py` - GitHub-backed storage utilities
  - `GitHubStorageClient` class wrapping `commit_file()` for writes
  - `read_file_content()` for API-based reads (fallback, rarely needed)
  - Batch commit support for multiple files in single commit
  - Environment detection: `GITHUB_ACTIONS` env var to auto-switch modes
  - ✅ Created with `is_github_actions()`, `get_github_storage_client()`, `GitHubStorageClient`

- [x] **2.2** Extend `src/integrations/github/files.py`
  - Add `commit_files_batch()` for atomic multi-file commits (uses Git Trees API)
  - Add `get_file_content()` for reading from GitHub API
  - ✅ Added both functions

### Phase 3: Storage Class Refactor

- [x] **3.1** Refactor `SourceRegistry` in `src/knowledge/storage.py`
  - Add `github_client: GitHubStorageClient | None` parameter to `__init__`
  - Add `project_root: Path | None` parameter for relative path computation
  - Modify `save_source()` to use batch commit when available
  - Modify `_save_registry_index()` similarly
  - Keep `get_source()` and reads using local Path (faster, no API calls)
  - ✅ Completed

- [x] **3.2** Refactor `KnowledgeGraphStorage` in `src/knowledge/storage.py`
  - Same pattern: inject `GitHubStorageClient` for writes
  - Methods affected: `save_extracted_people()`, `save_extracted_organizations()`, `save_extracted_concepts()`, `save_extracted_associations()`, `save_extracted_profiles()`
  - ✅ Completed

- [x] **3.3** Refactor `ParsedDocumentStorage` in `src/parsing/storage.py`
  - Same pattern for `_write_manifest()`
  - ✅ Completed

### Phase 4: Tool Handler Updates

- [x] **4.1** Create shared GitHub context resolver
  - Function to extract `GITHUB_TOKEN`, `GITHUB_REPOSITORY` from environment
  - Create `GitHubStorageClient` instance when running in Actions
  - Location: `src/orchestration/toolkit/_github_context.py`
  - ✅ Created `resolve_github_client()` function

- [x] **4.2** Update `src/orchestration/toolkit/source_curator.py`
  - All handlers that call `SourceRegistry.save_source()` pass github client
  - Affected handlers: `_register_source_handler`, `_update_source_status_handler`, `_implement_approved_source_handler`, `_propose_source_handler`, `_process_source_approval_handler`
  - ✅ Completed

- [x] **4.3** Update `src/orchestration/toolkit/monitor.py`
  - Handler: `_update_source_monitoring_metadata_handler`
  - ✅ Completed

- [x] **4.4** Update `src/orchestration/toolkit/extraction.py`
  - Handlers that save extracted entities via `ExtractionToolkit`
  - ✅ Completed

- [x] **4.5** Update `src/orchestration/toolkit/setup.py`
  - Remove git CLI-based `commit_and_push` tool (obsolete)
  - ✅ Completed - Removed function and tool registration; subprocess import cleaned up

### Phase 5: Workflow Cleanup

- [ ] **5.1** Remove git commit steps from workflows (they become no-ops)
  - `3-op-monitor-sources.yml` - Remove `stefanzweifel/git-auto-commit-action`
  - `2-op-curate-sources.yml` - No changes needed (never had commit step)
  - `2-op-implement-source.yml` - No changes needed
  - `2-op-parse-and-extract.yml` - No changes needed
  - ⏸️ Deferred - requires end-to-end testing first

### Phase 6: Testing

- [x] **6.1** Unit tests for `GitHubStorageClient`
  - `tests/integrations/github/test_github_storage.py`
  - Mock GitHub API responses
  - Test commit_file, batch commits, error handling
  - ✅ 17 tests passing

- [x] **6.2** Integration tests for storage classes with GitHub client
  - `tests/knowledge/test_storage_github.py`
  - Test SourceRegistry with mocked GitHubStorageClient
  - Test KnowledgeGraphStorage with mocked GitHubStorageClient
  - ✅ 8 tests passing

- [ ] **6.3** End-to-end workflow test
  - Manual test: Run monitor workflow, verify files committed to repo
  - ⏸️ Pending - requires deployment to test environment

---

## Technical Design

### GitHubStorageClient Interface (Implemented)

```python
# src/integrations/github/storage.py
class GitHubStorageClient:
    """Client for persisting files via GitHub API."""
    
    def __init__(
        self,
        token: str,
        repository: str,
        branch: str = "main",
        api_url: str = DEFAULT_API_URL,
    ) -> None: ...
    
    def commit_file(
        self,
        path: str | Path,
        content: str | bytes,
        message: str,
    ) -> dict[str, Any]: ...
    
    def commit_files_batch(
        self,
        files: list[tuple[str | Path, str | bytes]],
        message: str,
    ) -> dict[str, Any]: ...
    
    @classmethod
    def from_environment(cls) -> "GitHubStorageClient | None":
        """Create client from GITHUB_TOKEN and GITHUB_REPOSITORY env vars.
        
        Returns None if not running in GitHub Actions.
        """
        ...

def is_github_actions() -> bool:
    """Check if running in GitHub Actions."""
    ...

def get_github_storage_client() -> GitHubStorageClient | None:
    """Convenience function to get client if in Actions."""
    ...
```

### Storage Class Pattern (Implemented)

```python
class SourceRegistry:
    def __init__(
        self,
        root: Path | None = None,
        github_client: GitHubStorageClient | None = None,
        project_root: Path | None = None,  # For relative path computation
    ) -> None:
        self.root = root or _DEFAULT_KB_ROOT
        self._github_client = github_client
        self._project_root = project_root or Path.cwd()
        # ... existing init ...
    
    def _get_relative_path(self, path: Path) -> str:
        """Get path relative to project root for GitHub API."""
        try:
            return str(path.relative_to(self._project_root))
        except ValueError:
            return str(path)
    
    def save_source(self, source: SourceEntry) -> None:
        path = self._get_source_path(source.url)
        source_content = json.dumps(source.to_dict(), indent=2)
        # ... build index_content ...
        
        if self._github_client:
            # Batch commit both source and index
            self._github_client.commit_files_batch(
                files=[
                    (self._get_relative_path(path), source_content),
                    (self._get_relative_path(self._registry_path), index_content),
                ],
                message=f"Update source: {source.name}",
            )
        else:
            # Local atomic writes
            ...
```

### Tool Handler Usage Pattern

```python
# src/orchestration/toolkit/_github_context.py
from src.integrations.github.storage import get_github_storage_client

def resolve_github_client() -> GitHubStorageClient | None:
    """Get GitHub storage client for tool handlers."""
    return get_github_storage_client()

# In handlers:
from ._github_context import resolve_github_client

def _register_source_handler(args: Mapping[str, Any]) -> ToolResult:
    github_client = resolve_github_client()
    registry = SourceRegistry(root=registry_path, github_client=github_client)
    # ... handler logic ...
```

---

## Dependencies

- Existing: `src/integrations/github/files.py` (has `commit_file()`, now also `commit_files_batch()`, `get_file_content()`)
- Existing: `src/integrations/github/sync.py` (has Git Trees API usage)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GitHub API rate limits | Commits fail if rate limited | Batch multiple file changes into single commit |
| Commit conflicts | Concurrent workflows could conflict | Use branch protection, serialize critical workflows |
| Token permissions | Writes fail without `contents: write` | Document required permissions in workflow |

---

## Files Changed

### New Files
- `src/integrations/github/storage.py` - GitHubStorageClient and helpers
- `src/orchestration/toolkit/_github_context.py` - Shared context resolver
- `tests/integrations/github/test_github_storage.py` - Unit tests (17 tests)
- `tests/knowledge/test_storage_github.py` - Integration tests (8 tests)

### Modified Files
- `src/integrations/github/files.py` - Added `commit_files_batch()`, `get_file_content()`
- `src/knowledge/storage.py` - Updated `SourceRegistry`, `KnowledgeGraphStorage`
- `src/parsing/storage.py` - Updated `ParseStorage`
- `src/orchestration/toolkit/source_curator.py` - Inject github_client
- `src/orchestration/toolkit/monitor.py` - Inject github_client
- `src/orchestration/toolkit/extraction.py` - Inject github_client

---

## Estimated Effort

| Phase | Hours |
|-------|-------|
| Phase 1: Documentation | 0.5 |
| Phase 2: API Write Layer | 1.5 |
| Phase 3: Storage Refactor | 2.0 |
| Phase 4: Tool Handlers | 1.0 |
| Phase 5: Workflow Cleanup | 0.5 |
| Phase 6: Testing | 1.5 |
| **Total** | **7.0** |

---

*Created: 2025-12-27*
