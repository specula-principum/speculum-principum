"""GitHub integration utilities."""

from .assign_copilot import (  # noqa: F401
    LocalAgentRunResult,
    compose_agent_prompt,
    generate_branch_name,
    run_issue_with_local_copilot,
)
from .automation import AutomationOutcome, run_end_to_end_automation
from .search_issues import GitHubIssueSearcher, IssueSearchResult

__all__ = [
    "GitHubIssueSearcher",
    "IssueSearchResult",
    "LocalAgentRunResult",
    "compose_agent_prompt",
    "generate_branch_name",
    "run_issue_with_local_copilot",
    "AutomationOutcome",
    "run_end_to_end_automation",
]
