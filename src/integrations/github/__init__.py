"""GitHub integration utilities."""

from .search_issues import GitHubIssueSearcher, IssueSearchResult
from .sync import (
    CODE_DIRECTORIES,
    CODE_FILES,
    PROTECTED_DIRECTORIES,
    FileInfo,
    SyncChange,
    SyncError,
    SyncResult,
    SyncStatus,
    ValidationResult,
    compare_files,
    configure_upstream_variable,
    filter_syncable_files,
    get_repository_variable,
    get_sync_status,
    get_template_repository,
    set_repository_variable,
    sync_from_upstream,
    update_sync_status,
    validate_pre_sync,
)

__all__ = [
    "GitHubIssueSearcher",
    "IssueSearchResult",
    # Sync utilities
    "CODE_DIRECTORIES",
    "CODE_FILES",
    "PROTECTED_DIRECTORIES",
    "FileInfo",
    "SyncChange",
    "SyncError",
    "SyncResult",
    "SyncStatus",
    "ValidationResult",
    "compare_files",
    "configure_upstream_variable",
    "filter_syncable_files",
    "get_repository_variable",
    "get_sync_status",
    "get_template_repository",
    "set_repository_variable",
    "sync_from_upstream",
    "update_sync_status",
    "validate_pre_sync",
]
