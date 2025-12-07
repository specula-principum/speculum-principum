"""GitHub Discussions GraphQL client for discussion management."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from urllib import error, request
from urllib.parse import urlparse

DEFAULT_API_URL = "https://api.github.com"
AGENT_RESPONSE_TAG = "\n\n<!-- agent-response -->"


class GitHubDiscussionError(RuntimeError):
    """Raised when a GitHub Discussions API operation fails."""


@dataclass(frozen=True)
class DiscussionCategory:
    """Represents a GitHub Discussions category."""

    id: str
    name: str
    slug: str
    description: str = ""
    emoji: str = ""
    is_answerable: bool = False

    @classmethod
    def from_graphql(cls, data: Mapping[str, Any]) -> "DiscussionCategory":
        """Create from GraphQL response node."""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            slug=str(data.get("slug", "")),
            description=str(data.get("description", "")),
            emoji=str(data.get("emoji", "")),
            is_answerable=bool(data.get("isAnswerable", False)),
        )


@dataclass(frozen=True)
class Discussion:
    """Represents a GitHub Discussion."""

    id: str
    number: int
    title: str
    body: str
    url: str
    category_id: str = ""
    category_name: str = ""
    author_login: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_graphql(cls, data: Mapping[str, Any]) -> "Discussion":
        """Create from GraphQL response node."""
        category = data.get("category") or {}
        author = data.get("author") or {}
        return cls(
            id=str(data.get("id", "")),
            number=int(data.get("number", 0)),
            title=str(data.get("title", "")),
            body=str(data.get("body", "")),
            url=str(data.get("url", "")),
            category_id=str(category.get("id", "")),
            category_name=str(category.get("name", "")),
            author_login=str(author.get("login", "")),
            created_at=str(data.get("createdAt", "")),
            updated_at=str(data.get("updatedAt", "")),
        )


@dataclass(frozen=True)
class DiscussionComment:
    """Represents a comment on a GitHub Discussion."""

    id: str
    body: str
    url: str
    author_login: str = ""
    created_at: str = ""

    @classmethod
    def from_graphql(cls, data: Mapping[str, Any]) -> "DiscussionComment":
        """Create from GraphQL response node."""
        author = data.get("author") or {}
        return cls(
            id=str(data.get("id", "")),
            body=str(data.get("body", "")),
            url=str(data.get("url", "")),
            author_login=str(author.get("login", "")),
            created_at=str(data.get("createdAt", "")),
        )


def _graphql_endpoint(api_url: str) -> str:
    """Build the GraphQL endpoint from an API URL."""
    normalized = api_url.rstrip("/")
    if normalized.endswith("/api/v3"):
        return f"{normalized[:-len('/api/v3')]}/api/graphql"
    return f"{normalized}/graphql"


def _graphql_request(
    *,
    token: str,
    api_url: str,
    query: str,
    variables: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Execute a GraphQL request and return the data payload."""
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = dict(variables)

    url = _graphql_endpoint(api_url)
    raw_body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=raw_body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with request.urlopen(req) as response:
            response_bytes = response.read()
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise GitHubDiscussionError(
            f"GitHub GraphQL error ({exc.code}): {error_text.strip()}"
        ) from exc
    except error.URLError as exc:
        raise GitHubDiscussionError(
            f"Failed to reach GitHub GraphQL API: {exc.reason}"
        ) from exc

    data = json.loads(response_bytes.decode("utf-8"))
    if "errors" in data:
        errors = data.get("errors", [])
        messages = []
        for err in errors:
            if isinstance(err, Mapping):
                messages.append(err.get("message", "Unknown GraphQL error"))
        formatted = "; ".join(messages) if messages else "GitHub GraphQL reported errors."
        raise GitHubDiscussionError(formatted)

    output = data.get("data")
    if not isinstance(output, Mapping):
        raise GitHubDiscussionError("Unexpected GitHub GraphQL payload.")
    return output


def normalize_repository(repository: str | None) -> tuple[str, str]:
    """Split an ``owner/repo`` string into its two components."""
    if not repository:
        raise GitHubDiscussionError("Repository must be provided as 'owner/repo'.")
    owner, sep, name = repository.partition("/")
    if not sep or not owner or not name:
        raise GitHubDiscussionError(f"Invalid repository format: {repository!r}")
    return owner, name


def _get_repository_from_git() -> str | None:
    """Extract repository owner/name from git remote URL."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        remote_url = result.stdout.strip()

        # Handle SSH URLs: git@github.com:owner/repo.git
        if remote_url.startswith("git@github.com:"):
            repo_path = remote_url.replace("git@github.com:", "")
            repo_path = repo_path.removesuffix(".git")
            return repo_path

        # Handle HTTPS URLs
        try:
            parsed = urlparse(remote_url)
            if parsed.hostname and parsed.hostname.lower() == "github.com":
                repo_path = parsed.path.lstrip("/")
                repo_path = repo_path.removesuffix(".git")
                return repo_path
        except Exception:
            pass

        return None
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def resolve_repository(explicit_repo: str | None) -> str:
    """Return the repository name, preferring explicit input over the environment."""
    if explicit_repo:
        return explicit_repo

    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo

    repo = _get_repository_from_git()
    if repo:
        return repo

    raise GitHubDiscussionError(
        "Repository not provided; set --repo, the GITHUB_REPOSITORY environment variable, "
        "or ensure you're in a git repository with a GitHub remote."
    )


def resolve_token(explicit_token: str | None) -> str:
    """Return the token, preferring explicit input over the environment."""
    if explicit_token:
        return explicit_token
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubDiscussionError(
            "Token not provided; set --token or the GH_TOKEN/GITHUB_TOKEN environment variable."
        )
    return token


# =============================================================================
# Repository Info
# =============================================================================


def get_repository_id(
    *,
    token: str,
    repository: str,
    api_url: str = DEFAULT_API_URL,
) -> str:
    """Get the GraphQL node ID for a repository."""
    owner, name = normalize_repository(repository)

    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables={"owner": owner, "name": name},
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping) or not repo_data.get("id"):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    return str(repo_data["id"])


# =============================================================================
# Discussion Categories
# =============================================================================


def list_discussion_categories(
    *,
    token: str,
    repository: str,
    api_url: str = DEFAULT_API_URL,
    limit: int = 25,
) -> list[DiscussionCategory]:
    """List all discussion categories for a repository."""
    owner, name = normalize_repository(repository)

    query = """
    query($owner: String!, $name: String!, $first: Int!) {
      repository(owner: $owner, name: $name) {
        discussionCategories(first: $first) {
          nodes {
            id
            name
            slug
            description
            emoji
            isAnswerable
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables={"owner": owner, "name": name, "first": limit},
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    categories_data = repo_data.get("discussionCategories")
    if not isinstance(categories_data, Mapping):
        return []

    nodes = categories_data.get("nodes", [])
    if not isinstance(nodes, Sequence):
        return []

    return [DiscussionCategory.from_graphql(n) for n in nodes if isinstance(n, Mapping)]


def get_category_by_name(
    *,
    token: str,
    repository: str,
    category_name: str,
    api_url: str = DEFAULT_API_URL,
) -> DiscussionCategory | None:
    """Find a discussion category by name (case-insensitive)."""
    categories = list_discussion_categories(
        token=token,
        repository=repository,
        api_url=api_url,
    )
    name_lower = category_name.lower()
    for cat in categories:
        if cat.name.lower() == name_lower:
            return cat
    return None


def get_category_by_slug(
    *,
    token: str,
    repository: str,
    category_slug: str,
    api_url: str = DEFAULT_API_URL,
) -> DiscussionCategory | None:
    """Find a discussion category by slug."""
    categories = list_discussion_categories(
        token=token,
        repository=repository,
        api_url=api_url,
    )
    for cat in categories:
        if cat.slug == category_slug:
            return cat
    return None


# =============================================================================
# Discussions
# =============================================================================


def list_discussions(
    *,
    token: str,
    repository: str,
    category_id: str | None = None,
    api_url: str = DEFAULT_API_URL,
    limit: int = 50,
) -> list[Discussion]:
    """List discussions in a repository, optionally filtered by category."""
    owner, name = normalize_repository(repository)

    query = """
    query($owner: String!, $name: String!, $first: Int!, $categoryId: ID) {
      repository(owner: $owner, name: $name) {
        discussions(first: $first, categoryId: $categoryId, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            id
            number
            title
            body
            url
            createdAt
            updatedAt
            category {
              id
              name
            }
            author {
              login
            }
          }
        }
      }
    }
    """

    variables: dict[str, Any] = {"owner": owner, "name": name, "first": limit}
    if category_id:
        variables["categoryId"] = category_id

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables=variables,
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    discussions_data = repo_data.get("discussions")
    if not isinstance(discussions_data, Mapping):
        return []

    nodes = discussions_data.get("nodes", [])
    if not isinstance(nodes, Sequence):
        return []

    return [Discussion.from_graphql(n) for n in nodes if isinstance(n, Mapping)]


def search_discussions(
    *,
    token: str,
    repository: str,
    search_query: str,
    api_url: str = DEFAULT_API_URL,
    limit: int = 20,
) -> list[Discussion]:
    """Search discussions in a repository by title/body text.
    
    Uses the GitHub search API with `in:title` qualifier for better title matching.
    """
    owner, name = normalize_repository(repository)

    # Use GitHub search syntax for discussions
    # Note: GitHub search doesn't have a direct GraphQL endpoint for discussions,
    # so we use a filtered list approach with client-side matching for now
    query = """
    query($owner: String!, $name: String!, $first: Int!) {
      repository(owner: $owner, name: $name) {
        discussions(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            id
            number
            title
            body
            url
            createdAt
            updatedAt
            category {
              id
              name
            }
            author {
              login
            }
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables={"owner": owner, "name": name, "first": 100},
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    discussions_data = repo_data.get("discussions")
    if not isinstance(discussions_data, Mapping):
        return []

    nodes = discussions_data.get("nodes", [])
    if not isinstance(nodes, Sequence):
        return []

    # Client-side filter by search query (case-insensitive)
    search_lower = search_query.lower()
    results = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        title = str(node.get("title", "")).lower()
        body = str(node.get("body", "")).lower()
        if search_lower in title or search_lower in body:
            results.append(Discussion.from_graphql(node))
            if len(results) >= limit:
                break

    return results


def find_discussion_by_title(
    *,
    token: str,
    repository: str,
    title: str,
    category_id: str | None = None,
    api_url: str = DEFAULT_API_URL,
) -> Discussion | None:
    """Find a discussion by exact title match (case-insensitive)."""
    discussions = list_discussions(
        token=token,
        repository=repository,
        category_id=category_id,
        api_url=api_url,
        limit=100,
    )
    title_lower = title.lower()
    for disc in discussions:
        if disc.title.lower() == title_lower:
            return disc
    return None


def get_discussion(
    *,
    token: str,
    repository: str,
    discussion_number: int,
    api_url: str = DEFAULT_API_URL,
) -> Discussion:
    """Get a single discussion by number."""
    owner, name = normalize_repository(repository)

    if discussion_number < 1:
        raise GitHubDiscussionError("Discussion number must be a positive integer.")

    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        discussion(number: $number) {
          id
          number
          title
          body
          url
          createdAt
          updatedAt
          category {
            id
            name
          }
          author {
            login
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables={"owner": owner, "name": name, "number": discussion_number},
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    discussion_data = repo_data.get("discussion")
    if not isinstance(discussion_data, Mapping) or not discussion_data.get("id"):
        raise GitHubDiscussionError(f"Discussion #{discussion_number} not found.")

    return Discussion.from_graphql(discussion_data)


def create_discussion(
    *,
    token: str,
    repository: str,
    category_id: str,
    title: str,
    body: str,
    api_url: str = DEFAULT_API_URL,
) -> Discussion:
    """Create a new discussion in a repository."""
    # Validate inputs before making API calls
    if not category_id:
        raise GitHubDiscussionError("Category ID is required to create a discussion.")
    if not title:
        raise GitHubDiscussionError("Title is required to create a discussion.")

    if "<!-- agent-response -->" not in body:
        body += AGENT_RESPONSE_TAG

    repository_id = get_repository_id(
        token=token,
        repository=repository,
        api_url=api_url,
    )

    mutation = """
    mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
      createDiscussion(input: {
        repositoryId: $repositoryId,
        categoryId: $categoryId,
        title: $title,
        body: $body
      }) {
        discussion {
          id
          number
          title
          body
          url
          createdAt
          updatedAt
          category {
            id
            name
          }
          author {
            login
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=mutation,
        variables={
            "repositoryId": repository_id,
            "categoryId": category_id,
            "title": title,
            "body": body,
        },
    )

    create_data = data.get("createDiscussion")
    if not isinstance(create_data, Mapping):
        raise GitHubDiscussionError("Failed to create discussion: unexpected response.")

    discussion_data = create_data.get("discussion")
    if not isinstance(discussion_data, Mapping) or not discussion_data.get("id"):
        raise GitHubDiscussionError("Failed to create discussion: no discussion returned.")

    return Discussion.from_graphql(discussion_data)


def update_discussion(
    *,
    token: str,
    discussion_id: str,
    title: str | None = None,
    body: str | None = None,
    api_url: str = DEFAULT_API_URL,
) -> Discussion:
    """Update an existing discussion's title and/or body."""
    if not discussion_id:
        raise GitHubDiscussionError("Discussion ID is required to update.")
    if title is None and body is None:
        raise GitHubDiscussionError("At least one of title or body must be provided.")

    # Build the input dynamically based on what's provided
    input_parts = ["discussionId: $discussionId"]
    variables: dict[str, Any] = {"discussionId": discussion_id}
    type_parts = ["$discussionId: ID!"]

    if title is not None:
        input_parts.append("title: $title")
        variables["title"] = title
        type_parts.append("$title: String!")

    if body is not None:
        input_parts.append("body: $body")
        variables["body"] = body
        type_parts.append("$body: String!")

    mutation = f"""
    mutation({", ".join(type_parts)}) {{
      updateDiscussion(input: {{{", ".join(input_parts)}}}) {{
        discussion {{
          id
          number
          title
          body
          url
          createdAt
          updatedAt
          category {{
            id
            name
          }}
          author {{
            login
          }}
        }}
      }}
    }}
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=mutation,
        variables=variables,
    )

    update_data = data.get("updateDiscussion")
    if not isinstance(update_data, Mapping):
        raise GitHubDiscussionError("Failed to update discussion: unexpected response.")

    discussion_data = update_data.get("discussion")
    if not isinstance(discussion_data, Mapping) or not discussion_data.get("id"):
        raise GitHubDiscussionError("Failed to update discussion: no discussion returned.")

    return Discussion.from_graphql(discussion_data)


# =============================================================================
# Discussion Comments
# =============================================================================


def list_discussion_comments(
    *,
    token: str,
    repository: str,
    discussion_number: int,
    api_url: str = DEFAULT_API_URL,
    limit: int = 50,
) -> list[DiscussionComment]:
    """List comments on a discussion."""
    owner, name = normalize_repository(repository)

    if discussion_number < 1:
        raise GitHubDiscussionError("Discussion number must be a positive integer.")

    query = """
    query($owner: String!, $name: String!, $number: Int!, $first: Int!) {
      repository(owner: $owner, name: $name) {
        discussion(number: $number) {
          comments(first: $first) {
            nodes {
              id
              body
              url
              createdAt
              author {
                login
              }
            }
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=query,
        variables={"owner": owner, "name": name, "number": discussion_number, "first": limit},
    )

    repo_data = data.get("repository")
    if not isinstance(repo_data, Mapping):
        raise GitHubDiscussionError(f"Repository not found: {repository}")

    discussion_data = repo_data.get("discussion")
    if not isinstance(discussion_data, Mapping):
        raise GitHubDiscussionError(f"Discussion #{discussion_number} not found.")

    comments_data = discussion_data.get("comments")
    if not isinstance(comments_data, Mapping):
        return []

    nodes = comments_data.get("nodes", [])
    if not isinstance(nodes, Sequence):
        return []

    return [DiscussionComment.from_graphql(n) for n in nodes if isinstance(n, Mapping)]


def add_discussion_comment(
    *,
    token: str,
    discussion_id: str,
    body: str,
    api_url: str = DEFAULT_API_URL,
) -> DiscussionComment:
    """Add a comment to a discussion."""
    if not discussion_id:
        raise GitHubDiscussionError("Discussion ID is required to add a comment.")
    if not body:
        raise GitHubDiscussionError("Comment body is required.")

    if "<!-- agent-response -->" not in body:
        body += AGENT_RESPONSE_TAG

    mutation = """
    mutation($discussionId: ID!, $body: String!) {
      addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
        comment {
          id
          body
          url
          createdAt
          author {
            login
          }
        }
      }
    }
    """

    data = _graphql_request(
        token=token,
        api_url=api_url,
        query=mutation,
        variables={"discussionId": discussion_id, "body": body},
    )

    add_data = data.get("addDiscussionComment")
    if not isinstance(add_data, Mapping):
        raise GitHubDiscussionError("Failed to add comment: unexpected response.")

    comment_data = add_data.get("comment")
    if not isinstance(comment_data, Mapping) or not comment_data.get("id"):
        raise GitHubDiscussionError("Failed to add comment: no comment returned.")

    return DiscussionComment.from_graphql(comment_data)
