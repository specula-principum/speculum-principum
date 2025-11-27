"""Unit tests for GitHub Discussions GraphQL client."""

from __future__ import annotations

import json
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.github.discussions import (
    DEFAULT_API_URL,
    Discussion,
    DiscussionCategory,
    DiscussionComment,
    GitHubDiscussionError,
    add_discussion_comment,
    create_discussion,
    find_discussion_by_title,
    get_category_by_name,
    get_category_by_slug,
    get_discussion,
    get_repository_id,
    list_discussion_categories,
    list_discussion_comments,
    list_discussions,
    normalize_repository,
    resolve_repository,
    resolve_token,
    search_discussions,
    update_discussion,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_token() -> str:
    return "test-token-12345"


@pytest.fixture
def mock_repository() -> str:
    return "test-owner/test-repo"


@pytest.fixture
def sample_category_data() -> dict[str, Any]:
    return {
        "id": "DIC_abc123",
        "name": "People",
        "slug": "people",
        "description": "Profiles of people",
        "emoji": ":bust_in_silhouette:",
        "isAnswerable": False,
    }


@pytest.fixture
def sample_discussion_data() -> dict[str, Any]:
    return {
        "id": "D_xyz789",
        "number": 42,
        "title": "Niccolo Machiavelli",
        "body": "# Profile\n\nA Renaissance political philosopher.",
        "url": "https://github.com/test-owner/test-repo/discussions/42",
        "createdAt": "2025-11-27T10:00:00Z",
        "updatedAt": "2025-11-27T12:00:00Z",
        "category": {
            "id": "DIC_abc123",
            "name": "People",
        },
        "author": {
            "login": "testuser",
        },
    }


@pytest.fixture
def sample_comment_data() -> dict[str, Any]:
    return {
        "id": "DC_comment123",
        "body": "Updated: Added new associations.",
        "url": "https://github.com/test-owner/test-repo/discussions/42#discussioncomment-123",
        "createdAt": "2025-11-27T14:00:00Z",
        "author": {
            "login": "bot-user",
        },
    }


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDiscussionCategory:
    def test_from_graphql(self, sample_category_data: dict[str, Any]) -> None:
        category = DiscussionCategory.from_graphql(sample_category_data)
        assert category.id == "DIC_abc123"
        assert category.name == "People"
        assert category.slug == "people"
        assert category.description == "Profiles of people"
        assert category.emoji == ":bust_in_silhouette:"
        assert category.is_answerable is False

    def test_from_graphql_minimal(self) -> None:
        category = DiscussionCategory.from_graphql({"id": "DIC_1", "name": "General"})
        assert category.id == "DIC_1"
        assert category.name == "General"
        assert category.slug == ""
        assert category.description == ""

    def test_frozen(self, sample_category_data: dict[str, Any]) -> None:
        category = DiscussionCategory.from_graphql(sample_category_data)
        with pytest.raises(AttributeError):
            category.name = "Modified"  # type: ignore


class TestDiscussion:
    def test_from_graphql(self, sample_discussion_data: dict[str, Any]) -> None:
        discussion = Discussion.from_graphql(sample_discussion_data)
        assert discussion.id == "D_xyz789"
        assert discussion.number == 42
        assert discussion.title == "Niccolo Machiavelli"
        assert "Renaissance political philosopher" in discussion.body
        assert discussion.url == "https://github.com/test-owner/test-repo/discussions/42"
        assert discussion.category_id == "DIC_abc123"
        assert discussion.category_name == "People"
        assert discussion.author_login == "testuser"

    def test_from_graphql_no_category(self) -> None:
        data = {"id": "D_1", "number": 1, "title": "Test", "body": "Body", "url": "http://x"}
        discussion = Discussion.from_graphql(data)
        assert discussion.category_id == ""
        assert discussion.category_name == ""

    def test_from_graphql_no_author(self) -> None:
        data = {"id": "D_1", "number": 1, "title": "Test", "body": "Body", "url": "http://x"}
        discussion = Discussion.from_graphql(data)
        assert discussion.author_login == ""


class TestDiscussionComment:
    def test_from_graphql(self, sample_comment_data: dict[str, Any]) -> None:
        comment = DiscussionComment.from_graphql(sample_comment_data)
        assert comment.id == "DC_comment123"
        assert comment.body == "Updated: Added new associations."
        assert "discussioncomment-123" in comment.url
        assert comment.author_login == "bot-user"

    def test_from_graphql_no_author(self) -> None:
        data = {"id": "DC_1", "body": "test", "url": "http://x"}
        comment = DiscussionComment.from_graphql(data)
        assert comment.author_login == ""


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestNormalizeRepository:
    def test_valid_repository(self) -> None:
        owner, name = normalize_repository("owner/repo")
        assert owner == "owner"
        assert name == "repo"

    def test_none_repository(self) -> None:
        with pytest.raises(GitHubDiscussionError, match="Repository must be provided"):
            normalize_repository(None)

    def test_empty_repository(self) -> None:
        with pytest.raises(GitHubDiscussionError, match="Repository must be provided"):
            normalize_repository("")

    def test_no_separator(self) -> None:
        with pytest.raises(GitHubDiscussionError, match="Invalid repository format"):
            normalize_repository("noslash")

    def test_empty_owner(self) -> None:
        with pytest.raises(GitHubDiscussionError, match="Invalid repository format"):
            normalize_repository("/repo")

    def test_empty_name(self) -> None:
        with pytest.raises(GitHubDiscussionError, match="Invalid repository format"):
            normalize_repository("owner/")


class TestResolveRepository:
    def test_explicit_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_REPOSITORY", "env-owner/env-repo")
        result = resolve_repository("explicit/repo")
        assert result == "explicit/repo"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_REPOSITORY", "env-owner/env-repo")
        result = resolve_repository(None)
        assert result == "env-owner/env-repo"

    def test_no_repository_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        with patch("src.integrations.github.discussions._get_repository_from_git", return_value=None):
            with pytest.raises(GitHubDiscussionError, match="Repository not provided"):
                resolve_repository(None)


class TestResolveToken:
    def test_explicit_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GH_TOKEN", "env-token")
        result = resolve_token("explicit-token")
        assert result == "explicit-token"

    def test_gh_token_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GH_TOKEN", "gh-token")
        result = resolve_token(None)
        assert result == "gh-token"

    def test_github_token_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "github-token")
        result = resolve_token(None)
        assert result == "github-token"

    def test_no_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(GitHubDiscussionError, match="Token not provided"):
            resolve_token(None)


# =============================================================================
# GraphQL API Tests (Mocked)
# =============================================================================


def _mock_graphql_response(data: Mapping[str, Any]) -> MagicMock:
    """Create a mock urllib response for GraphQL."""
    response = MagicMock()
    response.read.return_value = json.dumps({"data": data}).encode("utf-8")
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


class TestGetRepositoryId:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {"id": "R_abc123"}
        })
        result = get_repository_id(token=mock_token, repository=mock_repository)
        assert result == "R_abc123"

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_not_found(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({"repository": None})
        with pytest.raises(GitHubDiscussionError, match="Repository not found"):
            get_repository_id(token=mock_token, repository=mock_repository)


class TestListDiscussionCategories:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_category_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussionCategories": {
                    "nodes": [sample_category_data]
                }
            }
        })
        result = list_discussion_categories(token=mock_token, repository=mock_repository)
        assert len(result) == 1
        assert result[0].name == "People"

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_empty(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussionCategories": {"nodes": []}
            }
        })
        result = list_discussion_categories(token=mock_token, repository=mock_repository)
        assert result == []


class TestGetCategoryByName:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_found(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_category_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussionCategories": {
                    "nodes": [sample_category_data]
                }
            }
        })
        result = get_category_by_name(
            token=mock_token,
            repository=mock_repository,
            category_name="PEOPLE",  # case-insensitive
        )
        assert result is not None
        assert result.name == "People"

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_not_found(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_category_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussionCategories": {
                    "nodes": [sample_category_data]
                }
            }
        })
        result = get_category_by_name(
            token=mock_token,
            repository=mock_repository,
            category_name="Organizations",
        )
        assert result is None


class TestListDiscussions:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussions": {
                    "nodes": [sample_discussion_data]
                }
            }
        })
        result = list_discussions(token=mock_token, repository=mock_repository)
        assert len(result) == 1
        assert result[0].title == "Niccolo Machiavelli"


class TestSearchDiscussions:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_finds_by_title(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussions": {
                    "nodes": [sample_discussion_data]
                }
            }
        })
        result = search_discussions(
            token=mock_token,
            repository=mock_repository,
            search_query="Machiavelli",
        )
        assert len(result) == 1
        assert result[0].title == "Niccolo Machiavelli"

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_no_match(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussions": {
                    "nodes": [sample_discussion_data]
                }
            }
        })
        result = search_discussions(
            token=mock_token,
            repository=mock_repository,
            search_query="Napoleon",
        )
        assert len(result) == 0


class TestFindDiscussionByTitle:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_found_exact_match(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussions": {
                    "nodes": [sample_discussion_data]
                }
            }
        })
        result = find_discussion_by_title(
            token=mock_token,
            repository=mock_repository,
            title="niccolo machiavelli",  # case-insensitive
        )
        assert result is not None
        assert result.number == 42

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_not_found(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussions": {
                    "nodes": [sample_discussion_data]
                }
            }
        })
        result = find_discussion_by_title(
            token=mock_token,
            repository=mock_repository,
            title="Different Person",
        )
        assert result is None


class TestGetDiscussion:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussion": sample_discussion_data
            }
        })
        result = get_discussion(
            token=mock_token,
            repository=mock_repository,
            discussion_number=42,
        )
        assert result.id == "D_xyz789"
        assert result.number == 42

    def test_invalid_number(self, mock_token: str, mock_repository: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="positive integer"):
            get_discussion(
                token=mock_token,
                repository=mock_repository,
                discussion_number=0,
            )


class TestCreateDiscussion:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        # First call returns repository ID, second call creates discussion
        mock_urlopen.side_effect = [
            _mock_graphql_response({"repository": {"id": "R_abc123"}}),
            _mock_graphql_response({
                "createDiscussion": {"discussion": sample_discussion_data}
            }),
        ]
        result = create_discussion(
            token=mock_token,
            repository=mock_repository,
            category_id="DIC_abc123",
            title="Niccolo Machiavelli",
            body="# Profile\n\nContent here.",
        )
        assert result.number == 42

    def test_missing_category(self, mock_token: str, mock_repository: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="Category ID is required"):
            create_discussion(
                token=mock_token,
                repository=mock_repository,
                category_id="",
                title="Test",
                body="Body",
            )

    def test_missing_title(self, mock_token: str, mock_repository: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="Title is required"):
            create_discussion(
                token=mock_token,
                repository=mock_repository,
                category_id="DIC_abc123",
                title="",
                body="Body",
            )


class TestUpdateDiscussion:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_update_body(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "updateDiscussion": {"discussion": sample_discussion_data}
        })
        result = update_discussion(
            token=mock_token,
            discussion_id="D_xyz789",
            body="Updated body content",
        )
        assert result.id == "D_xyz789"

    @patch("src.integrations.github.discussions.request.urlopen")
    def test_update_title_and_body(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        sample_discussion_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "updateDiscussion": {"discussion": sample_discussion_data}
        })
        result = update_discussion(
            token=mock_token,
            discussion_id="D_xyz789",
            title="New Title",
            body="New body",
        )
        assert result.id == "D_xyz789"

    def test_missing_discussion_id(self, mock_token: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="Discussion ID is required"):
            update_discussion(token=mock_token, discussion_id="", body="test")

    def test_no_updates(self, mock_token: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="At least one of"):
            update_discussion(token=mock_token, discussion_id="D_123")


class TestListDiscussionComments:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        mock_repository: str,
        sample_comment_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "repository": {
                "discussion": {
                    "comments": {
                        "nodes": [sample_comment_data]
                    }
                }
            }
        })
        result = list_discussion_comments(
            token=mock_token,
            repository=mock_repository,
            discussion_number=42,
        )
        assert len(result) == 1
        assert result[0].body == "Updated: Added new associations."

    def test_invalid_number(self, mock_token: str, mock_repository: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="positive integer"):
            list_discussion_comments(
                token=mock_token,
                repository=mock_repository,
                discussion_number=-1,
            )


class TestAddDiscussionComment:
    @patch("src.integrations.github.discussions.request.urlopen")
    def test_success(
        self,
        mock_urlopen: MagicMock,
        mock_token: str,
        sample_comment_data: dict[str, Any],
    ) -> None:
        mock_urlopen.return_value = _mock_graphql_response({
            "addDiscussionComment": {"comment": sample_comment_data}
        })
        result = add_discussion_comment(
            token=mock_token,
            discussion_id="D_xyz789",
            body="New changelog entry",
        )
        assert result.id == "DC_comment123"

    def test_missing_discussion_id(self, mock_token: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="Discussion ID is required"):
            add_discussion_comment(token=mock_token, discussion_id="", body="test")

    def test_missing_body(self, mock_token: str) -> None:
        with pytest.raises(GitHubDiscussionError, match="Comment body is required"):
            add_discussion_comment(token=mock_token, discussion_id="D_123", body="")
