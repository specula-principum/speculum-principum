"""Unit tests for source curator toolkit."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.github import issues as github_issues
from src.knowledge.storage import SourceEntry, SourceRegistry
from src.orchestration.safety import ActionRisk
from src.orchestration.tools import ToolRegistry
from src.orchestration.toolkit.source_curator import (
    register_source_curator_tools,
    _get_source_handler,
    _list_sources_handler,
    _calculate_credibility_score_handler,
    _discover_sources_handler,
    _register_source_handler,
    _update_source_status_handler,
    _verify_source_accessibility_handler,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_registry(tmp_path: Path) -> SourceRegistry:
    """Create a temporary source registry."""
    return SourceRegistry(root=tmp_path)


@pytest.fixture
def sample_source(temp_registry: SourceRegistry) -> SourceEntry:
    """Create and save a sample source."""
    source = SourceEntry(
        url="https://example.gov/documents/report.html",
        name="Example Government Report",
        source_type="primary",
        status="active",
        last_verified=datetime(2025, 12, 24, 10, 0, 0, tzinfo=timezone.utc),
        added_at=datetime(2025, 12, 20, 8, 0, 0, tzinfo=timezone.utc),
        added_by="system",
        approval_issue=None,
        credibility_score=0.95,
        is_official=True,
        requires_auth=False,
        discovered_from=None,
        parent_source_url=None,
        content_type="webpage",
        update_frequency="monthly",
        topics=["government", "policy"],
        notes="Primary source",
    )
    temp_registry.save_source(source)
    return source


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestToolRegistration:
    """Tests for tool registration."""

    def test_registers_all_tools(self) -> None:
        """Should register all source curator tools."""
        registry = ToolRegistry()
        register_source_curator_tools(registry)

        expected_tools = [
            "get_source",
            "list_sources",
            "verify_source_accessibility",
            "calculate_credibility_score",
            "discover_sources",
            "register_source",
            "update_source_status",
            "propose_source",
            "process_source_approval",
            "sync_source_discussion",
        ]

        for tool_name in expected_tools:
            assert tool_name in registry, f"Tool '{tool_name}' not registered"

    def test_read_tools_are_safe(self) -> None:
        """Read-only tools should have SAFE risk level."""
        registry = ToolRegistry()
        register_source_curator_tools(registry)

        safe_tools = [
            "get_source",
            "list_sources",
            "verify_source_accessibility",
            "calculate_credibility_score",
            "discover_sources",
        ]

        for tool_name in safe_tools:
            tool = registry.get_tool(tool_name)
            assert tool.risk_level == ActionRisk.SAFE, f"Tool '{tool_name}' should be SAFE"

    def test_write_tools_require_review(self) -> None:
        """Write tools should have REVIEW risk level."""
        registry = ToolRegistry()
        register_source_curator_tools(registry)

        review_tools = [
            "register_source",
            "update_source_status",
            "propose_source",
            "sync_source_discussion",
        ]

        for tool_name in review_tools:
            tool = registry.get_tool(tool_name)
            assert tool.risk_level == ActionRisk.REVIEW, f"Tool '{tool_name}' should be REVIEW"

    def test_destructive_tools(self) -> None:
        """Destructive tools should have DESTRUCTIVE risk level."""
        registry = ToolRegistry()
        register_source_curator_tools(registry)

        destructive_tools = [
            "process_source_approval",
        ]

        for tool_name in destructive_tools:
            tool = registry.get_tool(tool_name)
            assert tool.risk_level == ActionRisk.DESTRUCTIVE, f"Tool '{tool_name}' should be DESTRUCTIVE"


# =============================================================================
# get_source Tests
# =============================================================================


class TestGetSource:
    """Tests for get_source tool handler."""

    def test_returns_existing_source(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should return source data for existing URL."""
        result = _get_source_handler({
            "url": sample_source.url,
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["url"] == sample_source.url
        assert result.output["name"] == sample_source.name

    def test_returns_error_for_missing_source(
        self,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should return error for non-existent URL."""
        result = _get_source_handler({
            "url": "https://nonexistent.example.com/page",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# list_sources Tests
# =============================================================================


class TestListSources:
    """Tests for list_sources tool handler."""

    def test_lists_all_sources(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should list all sources."""
        result = _list_sources_handler({
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["count"] == 1
        assert len(result.output["sources"]) == 1

    def test_filters_by_status(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should filter by status."""
        # Active sources
        result = _list_sources_handler({
            "status": "active",
            "kb_root": str(temp_registry.root),
        })
        assert result.output["count"] == 1

        # Deprecated sources
        result = _list_sources_handler({
            "status": "deprecated",
            "kb_root": str(temp_registry.root),
        })
        assert result.output["count"] == 0

    def test_empty_registry(self, tmp_path: Path) -> None:
        """Should handle empty registry."""
        result = _list_sources_handler({
            "kb_root": str(tmp_path),
        })

        assert result.success is True
        assert result.output["count"] == 0
        assert result.output["sources"] == []


# =============================================================================
# calculate_credibility_score Tests
# =============================================================================


class TestCalculateCredibilityScore:
    """Tests for calculate_credibility_score tool handler."""

    def test_scores_government_domain(self) -> None:
        """Government domains should score high."""
        result = _calculate_credibility_score_handler({
            "url": "https://www.usda.gov/reports/2025.pdf",
        })

        assert result.success is True
        assert result.output["credibility_score"] >= 0.9
        assert result.output["domain_type"] == "government"

    def test_scores_education_domain(self) -> None:
        """Education domains should score moderately high."""
        result = _calculate_credibility_score_handler({
            "url": "https://research.mit.edu/papers/study.pdf",
        })

        assert result.success is True
        assert result.output["credibility_score"] >= 0.8
        assert result.output["domain_type"] == "education"

    def test_scores_commercial_domain(self) -> None:
        """Commercial domains should score lower."""
        result = _calculate_credibility_score_handler({
            "url": "https://shop.example.com/product",
        })

        assert result.success is True
        assert result.output["credibility_score"] <= 0.5
        assert result.output["domain_type"] == "commercial"

    def test_includes_domain_info(self) -> None:
        """Should include domain information in output."""
        result = _calculate_credibility_score_handler({
            "url": "https://www.example.org/page",
        })

        assert result.success is True
        assert "domain" in result.output
        assert "domain_type" in result.output
        assert "is_https" in result.output
        assert result.output["is_https"] is True


# =============================================================================
# register_source Tests
# =============================================================================


class TestRegisterSource:
    """Tests for register_source tool handler."""

    def test_registers_primary_source(self, tmp_path: Path) -> None:
        """Should register a primary source."""
        result = _register_source_handler({
            "url": "https://example.gov/doc",
            "name": "Example Doc",
            "source_type": "primary",
            "kb_root": str(tmp_path),
        })

        assert result.success is True
        assert result.output["registered"] is True
        assert result.output["url"] == "https://example.gov/doc"

        # Verify it was saved
        registry = SourceRegistry(root=tmp_path)
        source = registry.get_source("https://example.gov/doc")
        assert source is not None
        assert source.status == "active"

    def test_derived_source_requires_approval(self, tmp_path: Path) -> None:
        """Derived sources should require approval_issue."""
        result = _register_source_handler({
            "url": "https://example.com/derived",
            "name": "Derived Source",
            "source_type": "derived",
            "kb_root": str(tmp_path),
        })

        assert result.success is False
        assert "approval_issue" in result.error.lower()

    def test_derived_source_with_approval(self, tmp_path: Path) -> None:
        """Derived sources with approval_issue should succeed."""
        result = _register_source_handler({
            "url": "https://example.com/derived",
            "name": "Derived Source",
            "source_type": "derived",
            "approval_issue": 42,
            "kb_root": str(tmp_path),
        })

        assert result.success is True
        assert result.output["registered"] is True

        # Derived sources start as pending_review
        registry = SourceRegistry(root=tmp_path)
        source = registry.get_source("https://example.com/derived")
        assert source.status == "pending_review"
        assert source.approval_issue == 42

    def test_prevents_duplicate_registration(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should prevent registering duplicate URLs."""
        result = _register_source_handler({
            "url": sample_source.url,
            "name": "Duplicate",
            "source_type": "primary",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "already registered" in result.error.lower()

    def test_calculates_credibility_if_not_provided(self, tmp_path: Path) -> None:
        """Should calculate credibility score if not provided."""
        result = _register_source_handler({
            "url": "https://example.gov/doc",
            "name": "Gov Doc",
            "source_type": "primary",
            "kb_root": str(tmp_path),
        })

        assert result.success is True
        assert result.output["source"]["credibility_score"] > 0

    def test_uses_provided_credibility(self, tmp_path: Path) -> None:
        """Should use provided credibility score."""
        result = _register_source_handler({
            "url": "https://example.com/doc",
            "name": "Custom Score",
            "source_type": "primary",
            "credibility_score": 0.75,
            "kb_root": str(tmp_path),
        })

        assert result.success is True
        assert result.output["source"]["credibility_score"] == 0.75


# =============================================================================
# update_source_status Tests
# =============================================================================


class TestUpdateSourceStatus:
    """Tests for update_source_status tool handler."""

    def test_updates_status(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should update source status."""
        result = _update_source_status_handler({
            "url": sample_source.url,
            "status": "deprecated",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["old_status"] == "active"
        assert result.output["new_status"] == "deprecated"

        # Verify the change
        updated = temp_registry.get_source(sample_source.url)
        assert updated.status == "deprecated"

    def test_updates_notes(
        self,
        temp_registry: SourceRegistry,
        sample_source: SourceEntry,
    ) -> None:
        """Should update notes when provided."""
        result = _update_source_status_handler({
            "url": sample_source.url,
            "status": "pending_review",
            "notes": "Needs verification",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True

        updated = temp_registry.get_source(sample_source.url)
        assert updated.notes == "Needs verification"

    def test_returns_error_for_missing_source(
        self,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should return error for non-existent source."""
        result = _update_source_status_handler({
            "url": "https://nonexistent.example.com/page",
            "status": "deprecated",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# verify_source_accessibility Tests
# =============================================================================


class TestVerifySourceAccessibility:
    """Tests for verify_source_accessibility tool handler."""

    def test_invalid_url_format(self) -> None:
        """Should handle invalid URL format."""
        result = _verify_source_accessibility_handler({
            "url": "not-a-valid-url",
        })

        assert result.success is False
        assert result.output["accessible"] is False

    @patch("src.orchestration.toolkit.source_curator.requests.head")
    def test_accessible_url(self, mock_head: MagicMock) -> None:
        """Should report accessible URLs correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.url = "https://example.gov/page"
        mock_head.return_value = mock_response

        result = _verify_source_accessibility_handler({
            "url": "https://example.gov/page",
        })

        assert result.success is True
        assert result.output["accessible"] is True
        assert result.output["status_code"] == 200

    @patch("src.orchestration.toolkit.source_curator.requests.head")
    def test_inaccessible_url(self, mock_head: MagicMock) -> None:
        """Should report inaccessible URLs correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.url = "https://example.gov/missing"
        mock_head.return_value = mock_response

        result = _verify_source_accessibility_handler({
            "url": "https://example.gov/missing",
        })

        assert result.success is True
        assert result.output["accessible"] is False
        assert result.output["status_code"] == 404


# =============================================================================
# discover_sources Tests
# =============================================================================


class TestDiscoverSources:
    """Tests for discover_sources tool handler."""

    def test_empty_parsed_directory(self, tmp_path: Path) -> None:
        """Should handle empty parsed directory."""
        result = _discover_sources_handler({
            "kb_root": str(tmp_path),
            "parsed_root": str(tmp_path / "parsed"),
        })

        assert result.success is True
        assert result.output["candidate_count"] == 0

    def test_respects_limit(self, tmp_path: Path) -> None:
        """Should respect limit parameter."""
        result = _discover_sources_handler({
            "limit": 5,
            "kb_root": str(tmp_path),
            "parsed_root": str(tmp_path / "parsed"),
        })

        assert result.success is True
        # Since there's no content, this just validates the parameter is accepted


# =============================================================================
# propose_source Tests
# =============================================================================


class TestProposeSource:
    """Tests for propose_source tool handler."""

    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_creates_proposal_issue(self, mock_issues: MagicMock) -> None:
        """Should create a GitHub issue with source proposal."""
        from src.orchestration.toolkit.source_curator import _propose_source_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"
        
        # Mock successful issue creation
        mock_outcome = MagicMock()
        mock_outcome.number = 42
        mock_outcome.html_url = "https://github.com/owner/repo/issues/42"
        mock_issues.create_issue.return_value = mock_outcome

        result = _propose_source_handler({
            "url": "https://example.gov/data",
            "name": "Example Government Data",
            "discovered_from": "abc123",
            "context_snippet": "Found at https://example.gov/data in doc",
        })

        assert result.success is True
        assert result.output["issue_number"] == 42
        assert result.output["url"] == "https://example.gov/data"
        assert result.output["domain_type"] == "government"
        assert result.output["credibility_score"] > 0

        # Verify create_issue was called with correct params
        mock_issues.create_issue.assert_called_once()
        call_kwargs = mock_issues.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["source-proposal"]
        assert "Source Proposal: Example Government Data" == call_kwargs["title"]

    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_handles_api_error(self, mock_issues: MagicMock) -> None:
        """Should handle GitHub API errors gracefully."""
        from src.orchestration.toolkit.source_curator import _propose_source_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"
        mock_issues.GitHubIssueError = github_issues.GitHubIssueError
        mock_issues.create_issue.side_effect = github_issues.GitHubIssueError("API error")

        result = _propose_source_handler({
            "url": "https://example.gov/data",
            "name": "Test Source",
        })

        assert result.success is False
        assert "API error" in result.error


# =============================================================================
# process_source_approval Tests
# =============================================================================


class TestProcessSourceApproval:
    """Tests for process_source_approval tool handler."""

    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_approves_and_registers_source(
        self,
        mock_issues: MagicMock,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should register source and close issue on approval."""
        from src.orchestration.toolkit.source_curator import _process_source_approval_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        result = _process_source_approval_handler({
            "issue_number": 42,
            "command": "approve",
            "source_url": "https://newexample.gov/approved",
            "source_name": "Approved Source",
            "comment_author": "testuser",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["action"] == "approved"
        assert result.output["registered"] is True
        assert result.output["issue_closed"] is True

        # Verify source was registered
        source = temp_registry.get_source("https://newexample.gov/approved")
        assert source is not None
        assert source.approval_issue == 42
        assert source.added_by == "testuser"
        assert source.source_type == "derived"
        assert source.status == "active"

        # Verify GitHub API calls
        mock_issues.post_comment.assert_called_once()
        mock_issues.update_issue.assert_called_once()

    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_rejects_source(self, mock_issues: MagicMock, temp_registry: SourceRegistry) -> None:
        """Should close issue with rejection reason."""
        from src.orchestration.toolkit.source_curator import _process_source_approval_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        result = _process_source_approval_handler({
            "issue_number": 42,
            "command": "reject",
            "source_url": "https://spam.com/bad",
            "source_name": "Bad Source",
            "comment_author": "testuser",
            "rejection_reason": "Not authoritative",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["action"] == "rejected"
        assert result.output["reason"] == "Not authoritative"
        assert result.output["issue_closed"] is True

        # Verify source was NOT registered
        source = temp_registry.get_source("https://spam.com/bad")
        assert source is None

    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_prevents_duplicate_approval(
        self,
        mock_issues: MagicMock,
        sample_source: SourceEntry,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should reject approval of already-registered source."""
        from src.orchestration.toolkit.source_curator import _process_source_approval_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        result = _process_source_approval_handler({
            "issue_number": 99,
            "command": "approve",
            "source_url": sample_source.url,
            "source_name": sample_source.name,
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "already registered" in result.error.lower()


# =============================================================================
# sync_source_discussion Tests
# =============================================================================


class TestSyncSourceDiscussion:
    """Tests for sync_source_discussion tool handler."""

    @patch("src.orchestration.toolkit.source_curator.github_discussions")
    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_creates_new_discussion(
        self,
        mock_issues: MagicMock,
        mock_discussions: MagicMock,
        sample_source: SourceEntry,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should create new discussion for source."""
        from src.orchestration.toolkit.source_curator import _sync_source_discussion_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        # Mock category lookup
        mock_category = MagicMock()
        mock_category.id = "cat123"
        mock_category.name = "Sources"
        mock_discussions.list_discussion_categories.return_value = [mock_category]
        mock_discussions.find_discussion_by_title.return_value = None

        # Mock discussion creation
        mock_discussion = MagicMock()
        mock_discussion.id = "disc456"
        mock_discussion.url = "https://github.com/owner/repo/discussions/1"
        mock_discussions.create_discussion.return_value = mock_discussion

        result = _sync_source_discussion_handler({
            "url": sample_source.url,
            "category_name": "Sources",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["action"] == "created"
        assert result.output["discussion_id"] == "disc456"
        mock_discussions.create_discussion.assert_called_once()

    @patch("src.orchestration.toolkit.source_curator.github_discussions")
    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_updates_existing_discussion(
        self,
        mock_issues: MagicMock,
        mock_discussions: MagicMock,
        sample_source: SourceEntry,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should update existing discussion for source."""
        from src.orchestration.toolkit.source_curator import _sync_source_discussion_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        # Mock category lookup
        mock_category = MagicMock()
        mock_category.id = "cat123"
        mock_category.name = "Sources"
        mock_discussions.list_discussion_categories.return_value = [mock_category]

        # Mock existing discussion
        mock_existing = MagicMock()
        mock_existing.id = "disc789"
        mock_existing.url = "https://github.com/owner/repo/discussions/5"
        mock_discussions.find_discussion_by_title.return_value = mock_existing

        result = _sync_source_discussion_handler({
            "url": sample_source.url,
            "kb_root": str(temp_registry.root),
        })

        assert result.success is True
        assert result.output["action"] == "updated"
        assert result.output["discussion_id"] == "disc789"
        mock_discussions.update_discussion.assert_called_once()

    @patch("src.orchestration.toolkit.source_curator.github_discussions")
    @patch("src.orchestration.toolkit.source_curator.github_issues")
    def test_handles_missing_category(
        self,
        mock_issues: MagicMock,
        mock_discussions: MagicMock,
        sample_source: SourceEntry,
        temp_registry: SourceRegistry,
    ) -> None:
        """Should error if Sources category doesn't exist."""
        from src.orchestration.toolkit.source_curator import _sync_source_discussion_handler
        
        mock_issues.resolve_repository.return_value = "owner/repo"
        mock_issues.resolve_token.return_value = "test-token"

        # Return categories that don't include "Sources"
        mock_other = MagicMock()
        mock_other.name = "General"
        mock_discussions.list_discussion_categories.return_value = [mock_other]

        result = _sync_source_discussion_handler({
            "url": sample_source.url,
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "Sources" in result.error
        assert "not found" in result.error.lower()

    def test_handles_missing_source(self, temp_registry: SourceRegistry) -> None:
        """Should error if source not in registry."""
        from src.orchestration.toolkit.source_curator import _sync_source_discussion_handler
        
        result = _sync_source_discussion_handler({
            "url": "https://nonexistent.example.com/data",
            "kb_root": str(temp_registry.root),
        })

        assert result.success is False
        assert "not found" in result.error.lower()
