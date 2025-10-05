"""
GitHub Operations Module
Handles GitHub API operations for Speculum Principum
"""

from github import Github, Auth
from github.GithubException import GithubException
from typing import List, Optional, Dict, Any
from unittest.mock import Mock
from datetime import datetime, timedelta
from textwrap import dedent
import logging

from ..workflow.workflow_state_manager import ensure_discovery_labels

logger = logging.getLogger(__name__)


class GitHubIssueCreator:
    """Handles creation and management of GitHub issues"""
    
    def __init__(self, token: str, repository: str):
        """
        Initialize the GitHub issue creator
        
        Args:
            token: GitHub personal access token
            repository: Repository name in format 'owner/repo'
        """
        self.github = Github(auth=Auth.Token(token))
        self.repository = repository
        self.repo = self.github.get_repo(repository)
    
    def _extract_github_error_message(self, e: GithubException) -> str:
        """
        Safely extract error message from GitHub exception.
        
        Args:
            e: GithubException instance
            
        Returns:
            String error message
        """
        try:
            if hasattr(e, 'data') and e.data and hasattr(e.data, 'get'):
                return e.data.get('message', str(e))
            else:
                return str(e)
        except (AttributeError, TypeError):
            return str(e)
    
    def create_issue(
        self, 
        title: str, 
        body: str = "", 
        labels: Optional[List[str]] = None, 
        assignees: Optional[List[str]] = None
    ):
        """
        Create a new GitHub issue
        
        Args:
            title: Issue title
            body: Issue description/body
            labels: List of label names to apply
            assignees: List of usernames to assign
            
        Returns:
            Created issue object
            
        Raises:
            GithubException: If issue creation fails
        """
        try:
            # Validate labels exist in the repository
            if labels:
                repo_labels = []
                for label in self.repo.get_labels():
                    # Handle both real GitHub label objects and mock objects
                    if hasattr(label, 'name') and not isinstance(label.name, Mock):
                        # For real GitHub label objects
                        repo_labels.append(label.name)
                    elif hasattr(label, '_mock_name'):
                        # For mock objects created with Mock(name="labelname")
                        repo_labels.append(getattr(label, '_mock_name', str(label)))
                    else:
                        # Fallback for other mock setups
                        repo_labels.append(str(label))
                
                invalid_labels = [label for label in labels if label not in repo_labels]
                if invalid_labels:
                    print(f"Warning: Labels not found in repository: {invalid_labels}")
                    labels = [label for label in labels if label in repo_labels]
            
            # Create the issue
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or [],
                assignees=assignees or []
            )
            
            return issue
            
        except GithubException as e:
            raise RuntimeError(f"Failed to create GitHub issue: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error creating issue: {str(e)}") from e
    
    def get_repository_info(self):
        """Get basic repository information"""
        try:
            return {
                'name': self.repo.name,
                'full_name': self.repo.full_name,
                'description': self.repo.description,
                'url': self.repo.html_url,
                'issues_count': self.repo.open_issues_count
            }
        except GithubException as e:
            raise RuntimeError(f"Failed to get repository info: {self._extract_github_error_message(e)}") from e

    def get_issue(self, issue_number: int):
        """
        Get a specific issue by number
        
        Args:
            issue_number: GitHub issue number
            
        Returns:
            GitHub issue object
            
        Raises:
            RuntimeError: If issue retrieval fails
        """
        try:
            return self.repo.get_issue(issue_number)
        except GithubException as e:
            raise RuntimeError(f"Failed to get issue #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error getting issue #{issue_number}: {str(e)}") from e

    def get_issues_with_labels(self, 
                              labels: List[str], 
                              state: str = "open",
                              limit: Optional[int] = None) -> List:
        """
        Get issues that have specific labels
        
        Args:
            labels: List of label names to filter by
            state: Issue state ('open', 'closed', 'all')
            limit: Maximum number of issues to return
            
        Returns:
            List of GitHub issue objects
            
        Raises:
            RuntimeError: If issue retrieval fails
        """
        try:
            issues = self.repo.get_issues(state=state, labels=labels)
            if limit:
                return list(issues[:limit])
            return list(issues)
        except GithubException as e:
            raise RuntimeError(f"Failed to get issues with labels {labels}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error getting issues with labels {labels}: {str(e)}") from e

    def assign_issue(self, issue_number: int, assignees: List[str]) -> bool:
        """
        Assign an issue to specific users
        
        Args:
            issue_number: GitHub issue number
            assignees: List of usernames to assign
            
        Returns:
            True if assignment was successful
            
        Raises:
            RuntimeError: If assignment fails
        """
        try:
            issue = self.get_issue(issue_number)
            issue.add_to_assignees(*assignees)
            return True
        except GithubException as e:
            raise RuntimeError(f"Failed to assign issue #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error assigning issue #{issue_number}: {str(e)}") from e

    def unassign_issue(self, issue_number: int, assignees: List[str]) -> bool:
        """
        Remove assignment from an issue
        
        Args:
            issue_number: GitHub issue number
            assignees: List of usernames to unassign
            
        Returns:
            True if unassignment was successful
            
        Raises:
            RuntimeError: If unassignment fails
        """
        try:
            issue = self.get_issue(issue_number)
            issue.remove_from_assignees(*assignees)
            return True
        except GithubException as e:
            raise RuntimeError(f"Failed to unassign issue #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error unassigning issue #{issue_number}: {str(e)}") from e

    def create_individual_result_issue(self, site_name: str, result: Any, 
                                      labels: Optional[List[str]] = None) -> Any:
        """
        Create a GitHub issue for a single search result
        
        Args:
            site_name: Name of the monitored site
            result: SearchResult object with title, link, snippet attributes
            labels: Additional labels to apply
            
        Returns:
            Created GitHub issue object
        """
        # Build issue title - limit to reasonable length
        title_content = result.title[:100] if len(result.title) <= 100 else result.title[:97] + "..."
        title = f"📄 {site_name}: {title_content}"
        
        # Build issue body
        body = self._build_individual_result_body(site_name, result)
        
        # Combine default and custom labels while preserving order/casing
        default_labels = ['site-monitor', 'automated', 'documentation']
        provided_labels = labels or []

        deduped_labels: List[str] = []
        seen_labels = set()
        for label in default_labels + provided_labels:
            normalized = label.lower()
            if normalized not in seen_labels:
                deduped_labels.append(label)
                seen_labels.add(normalized)

        discovery_plan = ensure_discovery_labels(deduped_labels)
        for required_label in sorted(discovery_plan.labels_to_add):
            if required_label not in seen_labels:
                deduped_labels.append(required_label)
                seen_labels.add(required_label)
        
        # Create the issue
        issue = self.create_issue(
            title=title,
            body=body,
            labels=deduped_labels
        )
        
        logger.info(f"Created individual result issue #{issue.number} for {site_name}")
        return issue
    
    def _build_individual_result_body(self, site_name: str, result: Any) -> str:
        """Build the body content for an individual search result issue"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        snippet = (result.snippet or "_No preview available._").strip()
        snippet = " ".join(snippet.split())  # Collapse whitespace/newlines
        display_link = result.display_link or result.link

        body = dedent(
            f"""
            # Workflow Intake: {site_name}

            ## Discovery

            - **Site**: {site_name}
            - **Title**: {result.title}
            - **URL**: {result.link}
            - **Source**: {display_link}
            - **Detected**: {timestamp}

            > {snippet}

            ### Next Actions
            - [ ] Run `python main.py assign-workflows --config config.yaml --limit 10 --dry-run` to classify this discovery.
            - [ ] Review discovery metadata for duplicates or priority adjustments.
            - [ ] Confirm ownership and readiness for specialist processing.

            ## AI Assessment

            _Pending automated assignment. This section will be populated by the workflow assignment service._

            ## Specialist Guidance

            _Pending unified issue processing. Guidance will be generated once the issue reaches `state::assigned`._

            ## Copilot Assignment

            _Pending unified issue processing. Copilot will be assigned after specialist guidance is published._

            ---
            *This issue was automatically created by the Site Monitor service for a single search result.*
            """
        ).strip()

        return body

    def close_old_monitoring_issues(self, days_old: int = 7, 
                                  dry_run: bool = True) -> List[int]:
        """
        Close old site monitoring issues
        
        Args:
            days_old: Close issues older than this many days
            dry_run: If True, only return issue numbers that would be closed
            
        Returns:
            List of issue numbers that were (or would be) closed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        closed_issues = []
        
        try:
            # Search for open site monitoring issues
            issues = self.repo.get_issues(state='open', labels=['site-monitor'])
            
            for issue in issues:
                # Skip if issue is newer than cutoff
                if issue.created_at.replace(tzinfo=None) > cutoff_date:
                    continue
                
                if not dry_run:
                    # Add closing comment
                    close_comment = f"""## 🔒 Auto-closing Issue

This site monitoring issue is being automatically closed as it's older than {days_old} days.

**Closed at**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

---
*This issue was automatically closed by the Site Monitor service.*
"""
                    issue.create_comment(close_comment)
                    issue.edit(state='closed')
                    
                    logger.info(f"Closed old monitoring issue #{issue.number}")
                
                closed_issues.append(issue.number)
            
            if dry_run and closed_issues:
                logger.info(f"Dry run: would close {len(closed_issues)} old issues")
            elif closed_issues:
                logger.info(f"Closed {len(closed_issues)} old monitoring issues")
            
            return closed_issues
            
        except GithubException as e:
            logger.error(f"Failed to close old monitoring issues: {e}")
            raise RuntimeError(f"Failed to close old monitoring issues: {self._extract_github_error_message(e)}") from e

    def get_unprocessed_monitoring_issues(self, limit: Optional[int] = None, 
                                        force_reprocess: bool = False) -> List[Any]:
        """
        Get site-monitor labeled issues that haven't been processed by the agent.
        
        Args:
            limit: Maximum number of issues to return (None for all)
            force_reprocess: Whether to include already assigned issues
            
        Returns:
            List of GitHub issue objects ready for processing
        """
        try:
            # Search for open site-monitor issues
            issues = self.repo.get_issues(
                state='open', 
                labels=['site-monitor'],
                sort='created',
                direction='desc'
            )
            
            unprocessed_issues = []
            for issue in issues:
                # Skip if limit reached
                if limit and len(unprocessed_issues) >= limit:
                    break
                
                # Check if issue is already assigned to an agent (unless force_reprocess)
                if not force_reprocess and issue.assignee:
                    logger.debug(f"Skipping assigned issue #{issue.number}")
                    continue
                
                # Check if issue has been processed (look for agent comments)
                if self._issue_has_agent_activity(issue) and not force_reprocess:
                    logger.debug(f"Skipping issue #{issue.number} with existing agent activity")
                    continue
                
                unprocessed_issues.append(issue)
            
            logger.info(f"Found {len(unprocessed_issues)} unprocessed site-monitor issues")
            return unprocessed_issues
            
        except GithubException as e:
            logger.error(f"Failed to get unprocessed monitoring issues: {e}")
            raise RuntimeError(f"Failed to get unprocessed monitoring issues: {self._extract_github_error_message(e)}") from e

    def _issue_has_agent_activity(self, issue) -> bool:
        """
        Check if an issue has comments or activity from the automated agent.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            True if the issue shows signs of agent processing
        """
        try:
            # Check for comments from known agent users
            agent_indicators = [
                'github-actions[bot]',
                'automated workflow',
                '🤖',  # Robot emoji commonly used by agents
                'deliverable generated',
                'workflow matched'
            ]
            
            for comment in issue.get_comments():
                comment_body = comment.body.lower()
                comment_user = comment.user.login if comment.user else ''
                
                # Check if comment is from a bot user
                if any(bot_name in comment_user for bot_name in ['[bot]', 'github-actions']):
                    return True
                
                # Check if comment contains agent indicators
                if any(indicator in comment_body for indicator in agent_indicators):
                    return True
            
            return False
            
        except GithubException as e:
            logger.debug(f"Could not check agent activity for issue #{issue.number}: {e}")
            return False  # Assume no activity if we can't check

    def assign_issue_to_agent(self, issue_number: int, agent_username: str) -> bool:
        """
        Assign an issue to the automated agent for processing.
        
        Args:
            issue_number: Issue number to assign
            agent_username: Username of the agent to assign
            
        Returns:
            True if assignment was successful
        """
        try:
            issue = self.repo.get_issue(issue_number)
            issue.add_to_assignees(agent_username)
            logger.info(f"Assigned issue #{issue_number} to {agent_username}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to assign issue #{issue_number} to {agent_username}: {e}")
            return False

    def unassign_issue_from_agent(self, issue_number: int, agent_username: str) -> bool:
        """
        Remove agent assignment from an issue (e.g., when clarification is needed).
        
        Args:
            issue_number: Issue number to unassign
            agent_username: Username of the agent to remove
            
        Returns:
            True if unassignment was successful
        """
        try:
            issue = self.repo.get_issue(issue_number)
            issue.remove_from_assignees(agent_username)
            logger.info(f"Unassigned issue #{issue_number} from {agent_username}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to unassign issue #{issue_number} from {agent_username}: {e}")
            return False

    def create_monitoring_labels(self, labels_config: Optional[List[Dict[str, str]]] = None) -> List[str]:
        """
        Create labels for site monitoring if they don't exist
        
        Args:
            labels_config: List of label configurations with 'name', 'color', 'description'
            
        Returns:
            List of created label names
        """
        if labels_config is None:
            labels_config = [
                {
                    'name': 'site-monitor',
                    'color': '0E8A16',  # Green
                    'description': 'Automated site monitoring results'
                },
                {
                    'name': 'daily-summary',
                    'color': '1D76DB',  # Blue
                    'description': 'Daily monitoring summary'
                },
                {
                    'name': 'automated',
                    'color': '5319E7',  # Purple
                    'description': 'Automatically generated content'
                },
                {
                    'name': 'documentation',
                    'color': 'FEF2C0',  # Light yellow
                    'description': 'Documentation related updates'
                },
                {
                    'name': 'monitor::triage',
                    'color': 'FBCA04',  # Mustard yellow
                    'description': 'Temporary discovery label awaiting workflow assignment'
                },
                {
                    'name': 'state::discovery',
                    'color': 'C2E0C6',  # Light green
                    'description': 'Workflow state: discovery intake'
                },
                {
                    'name': 'state::assigned',
                    'color': 'BFD4F2',  # Light blue
                    'description': 'Workflow state: assigned to specialist processing'
                },
                {
                    'name': 'state::copilot',
                    'color': 'E6E6E6',  # Light gray
                    'description': 'Workflow state: Copilot executing deliverables'
                },
                {
                    'name': 'state::done',
                    'color': 'BFDADC',  # Teal
                    'description': 'Workflow state: work completed'
                }
            ]
        
        created_labels = []
        
        try:
            # Get existing labels
            existing_labels = {label.name for label in self.repo.get_labels()}
            
            for label_config in labels_config:
                label_name = label_config['name']
                
                if label_name not in existing_labels:
                    self.repo.create_label(
                        name=label_name,
                        color=label_config['color'],
                        description=label_config.get('description', '')
                    )
                    created_labels.append(label_name)
                    logger.info(f"Created label: {label_name}")
                else:
                    logger.debug(f"Label already exists: {label_name}")
            
            return created_labels
            
        except GithubException as e:
            logger.error(f"Failed to create labels: {e}")
            raise RuntimeError(f"Failed to create labels: {self._extract_github_error_message(e)}") from e

    def add_comment(self, issue_number: int, comment_body: str):
        """
        Add a comment to an issue
        
        Args:
            issue_number: GitHub issue number
            comment_body: Comment text content
            
        Returns:
            Created comment object
            
        Raises:
            RuntimeError: If comment creation fails
        """
        try:
            issue = self.get_issue(issue_number)
            return issue.create_comment(comment_body)
        except GithubException as e:
            raise RuntimeError(f"Failed to add comment to issue #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error adding comment to issue #{issue_number}: {str(e)}") from e

    def update_issue_labels(self, issue_number: int, labels: List[str]) -> bool:
        """
        Update labels on an issue
        
        Args:
            issue_number: GitHub issue number
            labels: List of label names to set
            
        Returns:
            True if labels were updated successfully
            
        Raises:
            RuntimeError: If label update fails
        """
        try:
            issue = self.get_issue(issue_number)
            # Validate labels exist in repository
            repo_labels = []
            for label in self.repo.get_labels():
                # Handle both real GitHub label objects and mock objects
                if hasattr(label, 'name') and not isinstance(label.name, Mock):
                    # For real GitHub label objects
                    repo_labels.append(label.name)
                elif hasattr(label, '_mock_name'):
                    # For mock objects created with Mock(name="labelname")
                    repo_labels.append(getattr(label, '_mock_name', str(label)))
                else:
                    # Fallback for other mock setups
                    repo_labels.append(str(label))
            
            invalid_labels = [label for label in labels if label not in repo_labels]
            if invalid_labels:
                print(f"Warning: Labels not found in repository: {invalid_labels}")
                labels = [label for label in labels if label in repo_labels]
            
            issue.set_labels(*labels)
            return True
        except GithubException as e:
            raise RuntimeError(f"Failed to update labels on issue #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error updating labels on issue #{issue_number}: {str(e)}") from e

    def get_issue_data(self, issue_number: int) -> Dict[str, Any]:
        """
        Get standardized issue data for processing
        
        Args:
            issue_number: GitHub issue number
            
        Returns:
            Dictionary with standardized issue data
            
        Raises:
            RuntimeError: If issue retrieval fails
        """
        try:
            issue = self.get_issue(issue_number)
            
            # Extract assignee usernames
            assignees = []
            if issue.assignees:
                assignees = [assignee.login for assignee in issue.assignees]
            
            # Extract label names
            labels = []
            if issue.labels:
                labels = [label.name for label in issue.labels]
            
            return {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body or '',
                'labels': labels,
                'assignees': assignees,
                'created_at': issue.created_at.isoformat() if issue.created_at else datetime.now().isoformat(),
                'updated_at': issue.updated_at.isoformat() if issue.updated_at else datetime.now().isoformat(),
                'url': issue.html_url,
                'state': issue.state
            }
        except GithubException as e:
            raise RuntimeError(f"Failed to get issue data for #{issue_number}: {self._extract_github_error_message(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error getting issue data for #{issue_number}: {str(e)}") from e


