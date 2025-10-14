"""GitHub integration utilities."""

from .assign_copilot import (
	CopilotHandoffResult,
	assign_issues_to_copilot,
	compose_agent_prompt,
	generate_branch_name,
)
from .search_issues import GitHubIssueSearcher, IssueSearchResult

__all__ = [
	"CopilotHandoffResult",
	"GitHubIssueSearcher",
	"IssueSearchResult",
	"assign_issues_to_copilot",
	"compose_agent_prompt",
	"generate_branch_name",
]
