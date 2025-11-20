# Code Search Implementation Guide

## Overview

This guide provides detailed technical specifications and implementation guidelines for adding code search capabilities to the orchestration mission system. This is a companion document to `code_search_enhancement.md`.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Agent                       │
│                  (src/orchestration/agent.py)                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ calls tools via
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tool Registry                             │
│              (src/orchestration/tools.py)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ registers tools from
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Toolkit                              │
│         (src/orchestration/toolkit/github.py)                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  NEW: register_github_code_search_tools()            │  │
│  │   - search_repository_code                           │  │
│  │   - read_file_contents                               │  │
│  │   - list_directory_contents                          │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                        │
└─────────────────────┼────────────────────────────────────────┘
                      │
                      │ uses
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              GitHub Integration Layer                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  NEW: src/integrations/github/code_search.py         │  │
│  │   - search_code()                                    │  │
│  │   - format_search_results()                          │  │
│  │   - extract_code_context()                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  NEW: src/integrations/github/repository_contents.py │  │
│  │   - get_file_contents()                              │  │
│  │   - list_directory()                                 │  │
│  │   - decode_content()                                 │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                        │
└─────────────────────┼────────────────────────────────────────┘
                      │
                      │ HTTP requests to
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub REST API                           │
│  - GET /search/code                                          │
│  - GET /repos/{owner}/{repo}/contents/{path}                 │
└─────────────────────────────────────────────────────────────┘
```

## Module Specifications

### Module 1: `src/integrations/github/code_search.py`

#### Purpose
Provides low-level interface to GitHub Code Search API.

#### Dependencies
```python
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .issues import DEFAULT_API_URL, resolve_token, resolve_repository, GitHubIssueError
```

#### Key Classes

```python
@dataclass
class CodeSearchResult:
    """Represents a single code search result."""
    path: str
    repository: str
    matched_line: str
    line_number: int
    context_before: List[str]
    context_after: List[str]
    score: float
    html_url: str
    sha: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool output."""
        return {
            "path": self.path,
            "repository": self.repository,
            "matched_line": self.matched_line,
            "line_number": self.line_number,
            "context": {
                "before": self.context_before,
                "after": self.context_after,
            },
            "score": self.score,
            "url": self.html_url,
            "sha": self.sha,
        }

@dataclass
class CodeSearchQuery:
    """Represents a code search query with filters."""
    query: str
    path: Optional[str] = None
    language: Optional[str] = None
    repository: Optional[str] = None
    
    def build_query_string(self) -> str:
        """Build GitHub search query string with filters."""
        parts = [self.query]
        
        if self.repository:
            parts.append(f"repo:{self.repository}")
        if self.path:
            parts.append(f"path:{self.path}")
        if self.language:
            parts.append(f"language:{self.language}")
            
        return " ".join(parts)
```

#### Key Functions

```python
def search_code(
    token: str,
    query: str,
    repository: str,
    path: Optional[str] = None,
    language: Optional[str] = None,
    max_results: int = 20,
    api_url: str = DEFAULT_API_URL,
) -> List[CodeSearchResult]:
    """
    Search for code in a GitHub repository.
    
    Args:
        token: GitHub authentication token
        query: Search query string
        repository: Repository in 'owner/name' format
        path: Optional path filter (e.g., 'src/')
        language: Optional language filter (e.g., 'python')
        max_results: Maximum results to return (1-100)
        api_url: GitHub API base URL
        
    Returns:
        List of CodeSearchResult objects
        
    Raises:
        GitHubIssueError: If the search fails
    """
    # Build query with filters
    search_query = CodeSearchQuery(
        query=query,
        path=path,
        language=language,
        repository=repository,
    )
    
    # Make API request
    url = f"{api_url}/search/code"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "q": search_query.build_query_string(),
        "per_page": min(max_results, 100),
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 403:
        raise GitHubIssueError("API rate limit exceeded for code search")
    elif response.status_code == 422:
        raise GitHubIssueError("Invalid search query")
    elif response.status_code != 200:
        raise GitHubIssueError(
            f"Code search failed: {response.status_code} - {response.text}"
        )
    
    data = response.json()
    return [_parse_search_item(item) for item in data.get("items", [])]


def _parse_search_item(item: Dict[str, Any]) -> CodeSearchResult:
    """Parse a single search result item from GitHub API."""
    # Extract text matches to get line numbers and context
    text_matches = item.get("text_matches", [])
    
    if text_matches:
        first_match = text_matches[0]
        fragment = first_match.get("fragment", "")
        lines = fragment.split("\n")
        
        # GitHub doesn't always provide line numbers, estimate from fragment
        line_number = _estimate_line_number(item.get("path", ""), fragment)
        matched_line = lines[0] if lines else ""
        context_before = []
        context_after = lines[1:3] if len(lines) > 1 else []
    else:
        line_number = 0
        matched_line = ""
        context_before = []
        context_after = []
    
    return CodeSearchResult(
        path=item.get("path", ""),
        repository=item.get("repository", {}).get("full_name", ""),
        matched_line=matched_line,
        line_number=line_number,
        context_before=context_before,
        context_after=context_after,
        score=item.get("score", 0.0),
        html_url=item.get("html_url", ""),
        sha=item.get("sha", ""),
    )


def _estimate_line_number(path: str, fragment: str) -> int:
    """
    Estimate line number from fragment.
    GitHub API doesn't always provide line numbers, so we estimate.
    """
    # This is a simplified estimation - in practice, you might
    # want to fetch the full file and search for the exact match
    return 0  # Placeholder


def extract_code_context(
    token: str,
    repository: str,
    path: str,
    line_number: int,
    context_lines: int = 3,
    api_url: str = DEFAULT_API_URL,
) -> Dict[str, Any]:
    """
    Fetch surrounding context for a specific line in a file.
    
    Args:
        token: GitHub authentication token
        repository: Repository in 'owner/name' format
        path: File path in repository
        line_number: Target line number (1-indexed)
        context_lines: Number of lines before/after to include
        api_url: GitHub API base URL
        
    Returns:
        Dictionary with file content, target line, and context
        
    Raises:
        GitHubIssueError: If fetching fails
    """
    from .repository_contents import get_file_contents
    
    file_data = get_file_contents(
        token=token,
        repository=repository,
        path=path,
        api_url=api_url,
    )
    
    content = file_data["content"]
    lines = content.split("\n")
    
    if line_number < 1 or line_number > len(lines):
        raise GitHubIssueError(f"Line number {line_number} out of range")
    
    start_line = max(0, line_number - context_lines - 1)
    end_line = min(len(lines), line_number + context_lines)
    
    return {
        "path": path,
        "line_number": line_number,
        "matched_line": lines[line_number - 1],
        "context_before": lines[start_line:line_number - 1],
        "context_after": lines[line_number:end_line],
        "total_lines": len(lines),
    }
```

### Module 2: `src/integrations/github/repository_contents.py`

#### Purpose
Provides interface to GitHub Contents API for reading files and listing directories.

#### Dependencies
```python
import base64
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .issues import DEFAULT_API_URL, resolve_token, resolve_repository, GitHubIssueError
```

#### Key Classes

```python
@dataclass
class FileContent:
    """Represents file content from repository."""
    path: str
    content: str
    size: int
    encoding: str
    sha: str
    ref: str
    url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool output."""
        return {
            "path": self.path,
            "content": self.content,
            "size": self.size,
            "encoding": self.encoding,
            "sha": self.sha,
            "ref": self.ref,
            "url": self.url,
        }


@dataclass
class DirectoryEntry:
    """Represents a file or directory in repository."""
    name: str
    path: str
    type: str  # "file" or "dir"
    size: int
    sha: str
    url: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool output."""
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "size": self.size,
            "sha": self.sha,
            "url": self.url,
        }
```

#### Key Functions

```python
def get_file_contents(
    token: str,
    repository: str,
    path: str,
    ref: Optional[str] = None,
    api_url: str = DEFAULT_API_URL,
) -> Dict[str, Any]:
    """
    Get the contents of a file from a GitHub repository.
    
    Args:
        token: GitHub authentication token
        repository: Repository in 'owner/name' format
        path: File path relative to repository root
        ref: Optional branch/tag/commit (defaults to default branch)
        api_url: GitHub API base URL
        
    Returns:
        Dictionary with file content and metadata
        
    Raises:
        GitHubIssueError: If the file cannot be read
    """
    owner, repo = repository.split("/")
    url = f"{api_url}/repos/{owner}/{repo}/contents/{path}"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    params = {}
    if ref:
        params["ref"] = ref
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 404:
        raise GitHubIssueError(f"File not found: {path}")
    elif response.status_code == 403:
        raise GitHubIssueError("API rate limit exceeded")
    elif response.status_code != 200:
        raise GitHubIssueError(
            f"Failed to read file: {response.status_code} - {response.text}"
        )
    
    data = response.json()
    
    # Check if it's a file (not a directory or submodule)
    if data.get("type") != "file":
        raise GitHubIssueError(f"Path is not a file: {path}")
    
    # Decode content
    content_encoded = data.get("content", "")
    encoding = data.get("encoding", "base64")
    
    if encoding == "base64":
        try:
            content = base64.b64decode(content_encoded).decode("utf-8")
        except UnicodeDecodeError:
            # File is binary
            raise GitHubIssueError(f"Cannot decode binary file: {path}")
    else:
        content = content_encoded
    
    # Check size limit (1MB)
    size = data.get("size", 0)
    if size > 1_000_000:
        raise GitHubIssueError(
            f"File too large: {size} bytes (limit: 1MB). "
            f"View directly at {data.get('html_url')}"
        )
    
    return {
        "path": path,
        "content": content,
        "size": size,
        "encoding": "utf-8",
        "sha": data.get("sha", ""),
        "ref": ref or "default",
        "url": data.get("html_url", ""),
    }


def list_directory(
    token: str,
    repository: str,
    path: str = "",
    ref: Optional[str] = None,
    recursive: bool = False,
    api_url: str = DEFAULT_API_URL,
) -> List[DirectoryEntry]:
    """
    List contents of a directory in a GitHub repository.
    
    Args:
        token: GitHub authentication token
        repository: Repository in 'owner/name' format
        path: Directory path (empty string for root)
        ref: Optional branch/tag/commit (defaults to default branch)
        recursive: Whether to list recursively (not fully implemented)
        api_url: GitHub API base URL
        
    Returns:
        List of DirectoryEntry objects
        
    Raises:
        GitHubIssueError: If the directory cannot be listed
    """
    owner, repo = repository.split("/")
    url = f"{api_url}/repos/{owner}/{repo}/contents/{path}"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    params = {}
    if ref:
        params["ref"] = ref
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    if response.status_code == 404:
        raise GitHubIssueError(f"Directory not found: {path}")
    elif response.status_code == 403:
        raise GitHubIssueError("API rate limit exceeded")
    elif response.status_code != 200:
        raise GitHubIssueError(
            f"Failed to list directory: {response.status_code} - {response.text}"
        )
    
    data = response.json()
    
    # Ensure it's a list (directory contents)
    if not isinstance(data, list):
        raise GitHubIssueError(f"Path is not a directory: {path}")
    
    entries = []
    for item in data:
        entry = DirectoryEntry(
            name=item.get("name", ""),
            path=item.get("path", ""),
            type=item.get("type", ""),
            size=item.get("size", 0),
            sha=item.get("sha", ""),
            url=item.get("html_url", ""),
        )
        entries.append(entry)
    
    # Note: Recursive listing would require additional API calls
    # for each subdirectory. Not implemented to avoid rate limits.
    if recursive:
        # TODO: Implement recursive listing with rate limit handling
        pass
    
    return entries
```

### Module 3: Tool Registration in `src/orchestration/toolkit/github.py`

#### New Function: `register_github_code_search_tools()`

Add this function to the existing `github.py` module:

```python
def register_github_code_search_tools(registry: ToolRegistry) -> None:
    """Register GitHub code search and repository content tools."""
    
    registry.register_tool(
        ToolDefinition(
            name="search_repository_code",
            description=(
                "Search for code patterns, functions, or text across repository files. "
                "Returns file paths, matched lines, and surrounding context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Search query (text, function name, or code pattern).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional path filter (e.g., 'src/' or '*.py').",
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter (e.g., 'python', 'javascript').",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                        "description": "Maximum number of results to return (1-100).",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token. Defaults to GITHUB_TOKEN env var.",
                    },
                    "api_url": {
                        "type": "string",
                        "description": "Override the GitHub API base URL.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=_search_repository_code_handler,
            risk_level=ActionRisk.SAFE,
        )
    )
    
    registry.register_tool(
        ToolDefinition(
            name="read_file_contents",
            description=(
                "Read the full contents of a file from the repository. "
                "Supports text files up to 1MB. Returns file content and metadata."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                        "description": "File path relative to repository root.",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Optional branch, tag, or commit SHA. Defaults to default branch.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token. Defaults to GITHUB_TOKEN env var.",
                    },
                    "api_url": {
                        "type": "string",
                        "description": "Override the GitHub API base URL.",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_read_file_contents_handler,
            risk_level=ActionRisk.SAFE,
        )
    )
    
    registry.register_tool(
        ToolDefinition(
            name="list_directory_contents",
            description=(
                "List files and directories at a given path in the repository. "
                "Returns names, types (file/dir), sizes, and URLs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "default": "",
                        "description": "Directory path relative to repository root. Empty for root.",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Optional branch, tag, or commit SHA. Defaults to default branch.",
                    },
                    "repository": {
                        "type": "string",
                        "description": "Repository name in 'owner/name' format. Defaults to GITHUB_REPOSITORY env var.",
                    },
                    "token": {
                        "type": "string",
                        "description": "GitHub token. Defaults to GITHUB_TOKEN env var.",
                    },
                    "api_url": {
                        "type": "string",
                        "description": "Override the GitHub API base URL.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_directory_contents_handler,
            risk_level=ActionRisk.SAFE,
        )
    )
```

#### Tool Handler Implementations

```python
def _search_repository_code_handler(args: Mapping[str, Any]) -> ToolResult:
    """Handler for search_repository_code tool."""
    from src.integrations.github import code_search
    
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return ToolResult(
            success=False,
            output=None,
            error="query must be a non-empty string."
        )
    
    repository_arg = args.get("repository")
    token_arg = args.get("token")
    api_url_arg = args.get("api_url")
    
    try:
        repository = github_issues.resolve_repository(
            str(repository_arg) if repository_arg else None
        )
        token = github_issues.resolve_token(
            str(token_arg) if token_arg else None
        )
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))
    
    api_url = str(api_url_arg) if api_url_arg else github_issues.DEFAULT_API_URL
    
    path = args.get("path")
    language = args.get("language")
    max_results = args.get("max_results", 20)
    
    try:
        results = code_search.search_code(
            token=token,
            query=str(query),
            repository=repository,
            path=str(path) if path else None,
            language=str(language) if language else None,
            max_results=int(max_results),
            api_url=api_url,
        )
        
        return ToolResult(
            success=True,
            output={
                "query": query,
                "repository": repository,
                "total_count": len(results),
                "results": [r.to_dict() for r in results],
            },
            error=None,
        )
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _read_file_contents_handler(args: Mapping[str, Any]) -> ToolResult:
    """Handler for read_file_contents tool."""
    from src.integrations.github import repository_contents
    
    path = args.get("path")
    if not isinstance(path, str) or not path.strip():
        return ToolResult(
            success=False,
            output=None,
            error="path must be a non-empty string."
        )
    
    repository_arg = args.get("repository")
    token_arg = args.get("token")
    api_url_arg = args.get("api_url")
    ref_arg = args.get("ref")
    
    try:
        repository = github_issues.resolve_repository(
            str(repository_arg) if repository_arg else None
        )
        token = github_issues.resolve_token(
            str(token_arg) if token_arg else None
        )
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))
    
    api_url = str(api_url_arg) if api_url_arg else github_issues.DEFAULT_API_URL
    ref = str(ref_arg) if ref_arg else None
    
    try:
        file_data = repository_contents.get_file_contents(
            token=token,
            repository=repository,
            path=str(path),
            ref=ref,
            api_url=api_url,
        )
        
        return ToolResult(success=True, output=file_data, error=None)
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))


def _list_directory_contents_handler(args: Mapping[str, Any]) -> ToolResult:
    """Handler for list_directory_contents tool."""
    from src.integrations.github import repository_contents
    
    path = args.get("path", "")
    repository_arg = args.get("repository")
    token_arg = args.get("token")
    api_url_arg = args.get("api_url")
    ref_arg = args.get("ref")
    
    try:
        repository = github_issues.resolve_repository(
            str(repository_arg) if repository_arg else None
        )
        token = github_issues.resolve_token(
            str(token_arg) if token_arg else None
        )
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))
    
    api_url = str(api_url_arg) if api_url_arg else github_issues.DEFAULT_API_URL
    ref = str(ref_arg) if ref_arg else None
    
    try:
        entries = repository_contents.list_directory(
            token=token,
            repository=repository,
            path=str(path),
            ref=ref,
            api_url=api_url,
        )
        
        return ToolResult(
            success=True,
            output={
                "path": path or "/",
                "entries": [e.to_dict() for e in entries],
                "total": len(entries),
            },
            error=None,
        )
    except github_issues.GitHubIssueError as exc:
        return ToolResult(success=False, output=None, error=str(exc))
```

## Testing Strategy

### Unit Tests

#### Test: `tests/integrations/github/test_code_search.py`

```python
import pytest
import responses
from src.integrations.github.code_search import search_code, CodeSearchQuery

@responses.activate
def test_search_code_success():
    """Test successful code search."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        json={
            "total_count": 1,
            "items": [
                {
                    "path": "src/example.py",
                    "score": 1.0,
                    "repository": {"full_name": "owner/repo"},
                    "text_matches": [
                        {"fragment": "def example():\n    pass"}
                    ],
                    "html_url": "https://github.com/owner/repo/blob/main/src/example.py",
                    "sha": "abc123",
                }
            ],
        },
        status=200,
    )
    
    results = search_code(
        token="fake-token",
        query="example",
        repository="owner/repo",
    )
    
    assert len(results) == 1
    assert results[0].path == "src/example.py"


@responses.activate
def test_search_code_rate_limit():
    """Test rate limit handling."""
    responses.add(
        responses.GET,
        "https://api.github.com/search/code",
        json={"message": "API rate limit exceeded"},
        status=403,
    )
    
    with pytest.raises(Exception, match="rate limit"):
        search_code(
            token="fake-token",
            query="example",
            repository="owner/repo",
        )


def test_code_search_query_build():
    """Test query string building."""
    query = CodeSearchQuery(
        query="function",
        path="src/",
        language="python",
        repository="owner/repo",
    )
    
    query_string = query.build_query_string()
    assert "function" in query_string
    assert "repo:owner/repo" in query_string
    assert "path:src/" in query_string
    assert "language:python" in query_string
```

#### Test: `tests/integrations/github/test_repository_contents.py`

```python
import pytest
import responses
import base64
from src.integrations.github.repository_contents import (
    get_file_contents,
    list_directory,
)


@responses.activate
def test_get_file_contents_success():
    """Test successful file content retrieval."""
    content = "print('hello world')"
    encoded_content = base64.b64encode(content.encode()).decode()
    
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/repo/contents/src/example.py",
        json={
            "type": "file",
            "content": encoded_content,
            "encoding": "base64",
            "size": len(content),
            "sha": "abc123",
            "html_url": "https://github.com/owner/repo/blob/main/src/example.py",
        },
        status=200,
    )
    
    result = get_file_contents(
        token="fake-token",
        repository="owner/repo",
        path="src/example.py",
    )
    
    assert result["content"] == content
    assert result["size"] == len(content)
    assert result["encoding"] == "utf-8"


@responses.activate
def test_get_file_contents_not_found():
    """Test file not found error."""
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/repo/contents/missing.py",
        json={"message": "Not Found"},
        status=404,
    )
    
    with pytest.raises(Exception, match="File not found"):
        get_file_contents(
            token="fake-token",
            repository="owner/repo",
            path="missing.py",
        )


@responses.activate
def test_list_directory_success():
    """Test successful directory listing."""
    responses.add(
        responses.GET,
        "https://api.github.com/repos/owner/repo/contents/src",
        json=[
            {
                "name": "example.py",
                "path": "src/example.py",
                "type": "file",
                "size": 1234,
                "sha": "abc123",
                "html_url": "https://github.com/owner/repo/blob/main/src/example.py",
            },
            {
                "name": "utils",
                "path": "src/utils",
                "type": "dir",
                "size": 0,
                "sha": "def456",
                "html_url": "https://github.com/owner/repo/tree/main/src/utils",
            },
        ],
        status=200,
    )
    
    entries = list_directory(
        token="fake-token",
        repository="owner/repo",
        path="src",
    )
    
    assert len(entries) == 2
    assert entries[0].name == "example.py"
    assert entries[0].type == "file"
    assert entries[1].name == "utils"
    assert entries[1].type == "dir"
```

### Integration Tests

#### Test: `tests/orchestration/toolkit/test_github_code_search_tools.py`

```python
import pytest
from src.orchestration.tools import ToolRegistry
from src.orchestration.toolkit.github import register_github_code_search_tools


def test_register_code_search_tools():
    """Test that code search tools are registered correctly."""
    registry = ToolRegistry()
    register_github_code_search_tools(registry)
    
    assert "search_repository_code" in registry
    assert "read_file_contents" in registry
    assert "list_directory_contents" in registry


def test_search_repository_code_tool_validation():
    """Test parameter validation for search_repository_code."""
    registry = ToolRegistry()
    register_github_code_search_tools(registry)
    
    # Missing required parameter
    result = registry.execute_tool("search_repository_code", {})
    assert not result.success
    assert "query" in result.error.lower()
    
    # Invalid max_results
    result = registry.execute_tool(
        "search_repository_code",
        {"query": "test", "max_results": 200}
    )
    assert not result.success


def test_read_file_contents_tool_validation():
    """Test parameter validation for read_file_contents."""
    registry = ToolRegistry()
    register_github_code_search_tools(registry)
    
    # Missing required parameter
    result = registry.execute_tool("read_file_contents", {})
    assert not result.success
    assert "path" in result.error.lower()
```

## Example Mission: Code Exploration

Create `config/missions/code_exploration.yaml`:

```yaml
# Mission to explore code and answer technical questions.

id: code_exploration
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-11-20
  summary_tooling: code-qa

goal: |
  Answer technical questions about the repository's codebase by searching
  through files, reading implementations, and providing code-backed responses.
  
  Actions Required:
  1. Fetch the issue details to understand the question.
  2. Search the codebase for relevant files and functions.
  3. Read file contents to understand implementation details.
  4. Formulate an answer with specific code references.
  5. Post the answer as a comment.

constraints:
  - Always cite specific files and line numbers in answers.
  - If code is ambiguous, read the actual implementation.
  - If unsure, acknowledge limitations in the response.
  - Do not close the issue.

success_criteria:
  - Issue details retrieved.
  - Relevant code files identified and read.
  - Answer posted with code references and citations.

max_steps: 10
allowed_tools:
  - get_issue_details
  - search_repository_code
  - read_file_contents
  - list_directory_contents
  - post_comment
requires_approval: false
```

## Configuration Updates

### Update `__init__.py` exports

Add to `src/orchestration/toolkit/__init__.py`:

```python
from .github import (
    register_github_mutation_tools,
    register_github_pr_tools,
    register_github_read_only_tools,
    register_github_code_search_tools,  # NEW
)

__all__ = [
    "register_github_read_only_tools",
    "register_github_pr_tools",
    "register_github_mutation_tools",
    "register_github_code_search_tools",  # NEW
    "register_parsing_tools",
]
```

## Deployment Checklist

- [ ] Create `src/integrations/github/code_search.py`
- [ ] Create `src/integrations/github/repository_contents.py`
- [ ] Update `src/orchestration/toolkit/github.py` with new tools
- [ ] Update `src/orchestration/toolkit/__init__.py` exports
- [ ] Add unit tests for code_search module
- [ ] Add unit tests for repository_contents module
- [ ] Add integration tests for tool registration
- [ ] Create example mission file
- [ ] Update README.md documentation
- [ ] Run full test suite
- [ ] Test with real GitHub API (sandbox repo)
- [ ] Monitor API rate limits during testing
- [ ] Document known limitations
- [ ] Create PR with changes
- [ ] Code review
- [ ] Merge and deploy

## Performance Considerations

### API Rate Limits

GitHub imposes these rate limits:
- **Code Search**: 30 requests per minute
- **Contents API**: 5000 requests per hour

**Mitigation strategies:**
1. Implement result caching (TTL: 1 hour)
2. Use conditional requests (ETags)
3. Batch operations where possible
4. Add rate limit monitoring
5. Implement exponential backoff

### Response Times

Expected performance:
- Code search: 1-3 seconds
- File read (< 100KB): < 1 second
- Directory listing: < 1 second

## Security Considerations

1. **Read-Only Access**: All tools are read-only (ActionRisk.SAFE)
2. **Token Security**: Never log or expose GitHub tokens
3. **File Size Limits**: Enforce 1MB limit to prevent DoS
4. **Path Validation**: Validate paths to prevent traversal attacks
5. **Rate Limiting**: Prevent API abuse
6. **Permission Checking**: Respect repository access controls via token

## Conclusion

This implementation guide provides all the technical details needed to add code search capabilities to the orchestration system. The design follows existing patterns in the codebase, uses established GitHub APIs, and maintains high standards for testing and security.

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-20  
**Status:** Draft - Ready for Implementation
