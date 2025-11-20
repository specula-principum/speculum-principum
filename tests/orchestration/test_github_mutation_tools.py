"""Tests for GitHub mutation tools (write operations)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.orchestration.safety import ActionRisk
from src.orchestration.tools import ToolRegistry
from src.orchestration.toolkit.github import register_github_mutation_tools


@pytest.fixture
def mutation_registry() -> ToolRegistry:
    """Registry with mutation tools registered."""
    registry = ToolRegistry()
    register_github_mutation_tools(registry)
    return registry


class TestAddLabel:
    """Tests for add_label tool."""

    def test_add_label_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify add_label adds labels to an issue."""
        with patch("src.integrations.github.issues.add_labels") as mock_add:
            mock_add.return_value = None
            
            result = mutation_registry.execute_tool(
                "add_label",
                {
                    "issue_number": 42,
                    "labels": ["bug", "high-priority"],
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output == {
                "issue_number": 42,
                "labels_added": ["bug", "high-priority"],
            }
            mock_add.assert_called_once()

    def test_add_label_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify add_label is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("add_label")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW

    def test_add_label_empty_list_fails(self, mutation_registry: ToolRegistry) -> None:
        """Verify add_label rejects empty label list."""
        result = mutation_registry.execute_tool(
            "add_label",
            {
                "issue_number": 42,
                "labels": [],
                "repository": "owner/repo",
                "token": "test-token",
            },
        )
        
        assert result.success is False
        assert result.error is not None
        assert "Argument validation failed" in result.error


class TestRemoveLabel:
    """Tests for remove_label tool."""

    def test_remove_label_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify remove_label removes a label from an issue."""
        with patch("src.integrations.github.issues.remove_label") as mock_remove:
            mock_remove.return_value = None
            
            result = mutation_registry.execute_tool(
                "remove_label",
                {
                    "issue_number": 42,
                    "label": "wontfix",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output == {
                "issue_number": 42,
                "label_removed": "wontfix",
            }
            mock_remove.assert_called_once()

    def test_remove_label_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify remove_label is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("remove_label")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW


class TestPostComment:
    """Tests for post_comment tool."""

    def test_post_comment_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify post_comment posts a comment and returns URL."""
        with patch("src.integrations.github.issues.post_comment") as mock_post:
            mock_post.return_value = "https://github.com/owner/repo/issues/42#comment-123"
            
            result = mutation_registry.execute_tool(
                "post_comment",
                {
                    "issue_number": 42,
                    "body": "This issue has been reviewed.",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["comment_url"] == "https://github.com/owner/repo/issues/42#comment-123"
            mock_post.assert_called_once()
            
            # Verify marker was appended
            call_kwargs = mock_post.call_args.kwargs
            assert "<!-- agent-response -->" in call_kwargs["body"]

    def test_post_comment_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify post_comment is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("post_comment")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW

    def test_post_comment_empty_body_fails(self, mutation_registry: ToolRegistry) -> None:
        """Verify post_comment rejects empty body."""
        result = mutation_registry.execute_tool(
            "post_comment",
            {
                "issue_number": 42,
                "body": "",
                "repository": "owner/repo",
                "token": "test-token",
            },
        )
        
        assert result.success is False
        assert result.error is not None
        assert "Argument validation failed" in result.error


class TestAssignIssue:
    """Tests for assign_issue tool."""

    def test_assign_issue_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify assign_issue assigns users to an issue."""
        with patch("src.integrations.github.issues.assign_issue") as mock_assign:
            mock_assign.return_value = None
            
            result = mutation_registry.execute_tool(
                "assign_issue",
                {
                    "issue_number": 42,
                    "assignees": ["octocat", "github-actions"],
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output == {
                "issue_number": 42,
                "assignees": ["octocat", "github-actions"],
            }
            mock_assign.assert_called_once()

    def test_assign_issue_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify assign_issue is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("assign_issue")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW


class TestUpdateIssueBody:
    """Tests for update_issue_body tool."""

    def test_update_issue_body_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify update_issue_body updates issue description."""
        with patch("src.integrations.github.issues.update_issue") as mock_update:
            mock_update.return_value = None
            
            result = mutation_registry.execute_tool(
                "update_issue_body",
                {
                    "issue_number": 42,
                    "body": "Updated issue description",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["updated"] is True
            mock_update.assert_called_once()

    def test_update_issue_body_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify update_issue_body is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("update_issue_body")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW


class TestCloseIssue:
    """Tests for close_issue tool."""

    def test_close_issue_with_reason_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify close_issue closes issue with reason comment."""
        with patch("src.integrations.github.issues.post_comment") as mock_comment, \
             patch("src.integrations.github.issues.update_issue") as mock_update:
            mock_comment.return_value = "https://github.com/owner/repo/issues/42#comment-123"
            mock_update.return_value = None
            
            result = mutation_registry.execute_tool(
                "close_issue",
                {
                    "issue_number": 42,
                    "reason": "Duplicate of #41",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["closed"] is True
            mock_comment.assert_called_once()
            mock_update.assert_called_once()

    def test_close_issue_without_reason_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify close_issue can close without reason comment."""
        with patch("src.integrations.github.issues.post_comment") as mock_comment, \
             patch("src.integrations.github.issues.update_issue") as mock_update:
            mock_update.return_value = None
            
            result = mutation_registry.execute_tool(
                "close_issue",
                {
                    "issue_number": 42,
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["closed"] is True
            mock_comment.assert_not_called()
            mock_update.assert_called_once()

    def test_close_issue_is_destructive(self, mutation_registry: ToolRegistry) -> None:
        """Verify close_issue is classified as DESTRUCTIVE risk."""
        tool = mutation_registry.get_tool("close_issue")
        assert tool is not None
        assert tool.risk_level == ActionRisk.DESTRUCTIVE


class TestLockIssue:
    """Tests for lock_issue tool."""

    def test_lock_issue_with_reason_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify lock_issue locks issue with reason."""
        with patch("src.integrations.github.issues.lock_issue") as mock_lock:
            mock_lock.return_value = None
            
            result = mutation_registry.execute_tool(
                "lock_issue",
                {
                    "issue_number": 42,
                    "lock_reason": "spam",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["locked"] is True
            mock_lock.assert_called_once()

    def test_lock_issue_is_destructive(self, mutation_registry: ToolRegistry) -> None:
        """Verify lock_issue is classified as DESTRUCTIVE risk."""
        tool = mutation_registry.get_tool("lock_issue")
        assert tool is not None
        assert tool.risk_level == ActionRisk.DESTRUCTIVE


class TestApprovePR:
    """Tests for approve_pr tool."""

    def test_approve_pr_with_comment_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify approve_pr approves PR with comment."""
        with patch("src.integrations.github.pull_requests.create_pr_review") as mock_review:
            mock_review.return_value = "https://github.com/owner/repo/pull/42#review-123"
            
            result = mutation_registry.execute_tool(
                "approve_pr",
                {
                    "pr_number": 42,
                    "comment": "LGTM!",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["approved"] is True
            assert "review_url" in result.output
            mock_review.assert_called_once()

    def test_approve_pr_requires_review(self, mutation_registry: ToolRegistry) -> None:
        """Verify approve_pr is classified as REVIEW risk."""
        tool = mutation_registry.get_tool("approve_pr")
        assert tool is not None
        assert tool.risk_level == ActionRisk.REVIEW


class TestMergePR:
    """Tests for merge_pr tool."""

    def test_merge_pr_default_method_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify merge_pr merges PR with default method."""
        with patch("src.integrations.github.pull_requests.merge_pull_request") as mock_merge:
            mock_merge.return_value = {"sha": "abc123", "merged": True}
            
            result = mutation_registry.execute_tool(
                "merge_pr",
                {
                    "pr_number": 42,
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["merged"] is True
            assert result.output["sha"] == "abc123"
            mock_merge.assert_called_once()

    def test_merge_pr_squash_method_success(self, mutation_registry: ToolRegistry) -> None:
        """Verify merge_pr supports squash merge method."""
        with patch("src.integrations.github.pull_requests.merge_pull_request") as mock_merge:
            mock_merge.return_value = {"sha": "def456", "merged": True}
            
            result = mutation_registry.execute_tool(
                "merge_pr",
                {
                    "pr_number": 42,
                    "merge_method": "squash",
                    "repository": "owner/repo",
                    "token": "test-token",
                },
            )
            
            assert result.success is True
            assert result.output is not None
            assert result.output["merged"] is True
            mock_merge.assert_called_once()

    def test_merge_pr_is_destructive(self, mutation_registry: ToolRegistry) -> None:
        """Verify merge_pr is classified as DESTRUCTIVE risk."""
        tool = mutation_registry.get_tool("merge_pr")
        assert tool is not None
        assert tool.risk_level == ActionRisk.DESTRUCTIVE


class TestMutationToolsInventory:
    """Verify all required mutation tools are registered."""

    def test_all_mutation_tools_registered(self, mutation_registry: ToolRegistry) -> None:
        """Verify all 9 mutation tools are present."""
        expected_tools = [
            "add_label",
            "remove_label",
            "post_comment",
            "assign_issue",
            "update_issue_body",
            "close_issue",
            "lock_issue",
            "approve_pr",
            "merge_pr",
        ]
        
        for tool_name in expected_tools:
            tool = mutation_registry.get_tool(tool_name)
            assert tool is not None, f"Tool {tool_name} not registered"

    def test_risk_levels_appropriate(self, mutation_registry: ToolRegistry) -> None:
        """Verify mutation tools have appropriate risk classifications."""
        review_tools = ["add_label", "remove_label", "post_comment", "assign_issue", "update_issue_body", "approve_pr"]
        destructive_tools = ["close_issue", "lock_issue", "merge_pr"]
        
        for tool_name in review_tools:
            tool = mutation_registry.get_tool(tool_name)
            assert tool.risk_level == ActionRisk.REVIEW, f"{tool_name} should be REVIEW risk"
        
        for tool_name in destructive_tools:
            tool = mutation_registry.get_tool(tool_name)
            assert tool.risk_level == ActionRisk.DESTRUCTIVE, f"{tool_name} should be DESTRUCTIVE risk"
