"""GitHub file manipulation helpers."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib import error, request

from .issues import API_VERSION, DEFAULT_API_URL, GitHubIssueError, normalize_repository

def commit_file(
    *,
    token: str,
    repository: str,
    path: str,
    content: str | bytes,
    message: str,
    branch: str,
    api_url: str = DEFAULT_API_URL,
) -> dict[str, Any]:
    """Create or update a file in a repository.

    Args:
        token: GitHub API token
        repository: Repository in "owner/repo" format
        path: Path to the file
        content: Content of the file (string or bytes)
        message: Commit message
        branch: Branch to commit to
        api_url: GitHub API base URL

    Returns:
        Dictionary containing the commit details
    """
    owner, name = normalize_repository(repository)
    endpoint = f"{api_url.rstrip('/')}/repos/{owner}/{name}/contents/{path}"

    # If content is string, encode to bytes
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    encoded_content = base64.b64encode(content_bytes).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded_content,
        "branch": branch,
    }

    # Check if file exists to get SHA (needed for update)
    try:
        get_req = request.Request(f"{endpoint}?ref={branch}")
        get_req.add_header("Authorization", f"Bearer {token}")
        get_req.add_header("Accept", "application/vnd.github+json")
        get_req.add_header("X-GitHub-Api-Version", API_VERSION)
        
        with request.urlopen(get_req) as response:
            data = json.loads(response.read().decode("utf-8"))
            payload["sha"] = data["sha"]
    except error.HTTPError as exc:
        if exc.code != 404:
             raise GitHubIssueError(f"Failed to check file existence: {exc}")
    except Exception:
        pass # File doesn't exist, proceed with creation

    raw_body = json.dumps(payload).encode("utf-8")
    req = request.Request(endpoint, data=raw_body, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", API_VERSION)
    req.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubIssueError(
            f"GitHub API error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubIssueError(f"Failed to reach GitHub API: {exc.reason}") from exc
