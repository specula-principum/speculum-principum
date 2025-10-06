"""
Test fixtures and mock data for Speculum Principum tests
"""

import subprocess
import warnings

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from github import Github
from github.Repository import Repository
from github.Issue import Issue
from github.GithubException import GithubException
from src.utils.config_manager import (
    MonitorConfig,
    SiteConfig,
    GitHubConfig,
    SearchConfig,
    SiteMonitorSettings,
)


@pytest.fixture(autouse=True)
def restore_repository_branch():
    """Ensure tests leave the git repository on its original branch."""

    repo_root = Path(__file__).resolve().parent.parent
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        yield
        return

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        original_branch = result.stdout.strip()
    except subprocess.CalledProcessError:
        # Detached HEAD or repository unavailable; skip restoration.
        yield
        return

    try:
        yield
    finally:
        try:
            current_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            if current_branch != original_branch:
                subprocess.run(
                    ["git", "checkout", original_branch],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
        except subprocess.CalledProcessError as exc:
            warnings.warn(
                f"Failed to restore git branch '{original_branch}': {exc.stderr or exc.stdout or exc}",
                RuntimeWarning,
            )


@pytest.fixture
def mock_github_token():
    """Mock GitHub token for testing"""
    return "ghp_test_token_1234567890abcdef"


@pytest.fixture
def mock_repository_name():
    """Mock repository name for testing"""
    return "testuser/testrepo"


@pytest.fixture
def mock_issue_data():
    """Mock issue data for testing"""
    return {
        "title": "Test Issue",
        "body": "This is a test issue description",
        "labels": ["bug", "urgent"],
        "assignees": ["testuser1", "testuser2"]
    }


@pytest.fixture
def mock_github_issue():
    """Mock GitHub Issue object"""
    issue = Mock(spec=Issue)
    issue.number = 123
    issue.title = "Test Issue"
    issue.body = "This is a test issue description"
    issue.html_url = "https://github.com/testuser/testrepo/issues/123"
    issue.state = "open"
    issue.labels = [Mock(name="bug"), Mock(name="urgent")]
    issue.assignees = [Mock(login="testuser1"), Mock(login="testuser2")]
    return issue


@pytest.fixture
def mock_github_label():
    """Mock GitHub Label object"""
    label = Mock()
    label.name = "bug"
    return label


@pytest.fixture
def mock_github_repository():
    """Mock GitHub Repository object"""
    repo = Mock(spec=Repository)
    repo.name = "testrepo"
    repo.full_name = "testuser/testrepo"
    repo.description = "Test repository for Speculum Principum"
    repo.html_url = "https://github.com/testuser/testrepo"
    repo.open_issues_count = 5
    
    # Mock methods
    repo.create_issue = Mock()
    repo.get_labels = Mock()
    repo.get_issues = Mock()
    
    return repo


@pytest.fixture
def mock_github_client():
    """Mock GitHub client"""
    github = Mock(spec=Github)
    github.get_repo = Mock()
    return github


@pytest.fixture
def sample_repo_info():
    """Sample repository information"""
    return {
        'name': 'testrepo',
        'full_name': 'testuser/testrepo',
        'description': 'Test repository for Speculum Principum',
        'url': 'https://github.com/testuser/testrepo',
        'issues_count': 5
    }


@pytest.fixture
def environment_variables(monkeypatch, mock_github_token, mock_repository_name):
    """Set up environment variables for testing"""
    monkeypatch.setenv("GITHUB_TOKEN", mock_github_token)
    monkeypatch.setenv("GITHUB_REPOSITORY", mock_repository_name)
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_api_key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test_search_engine_id")


@pytest.fixture
def sample_config_with_agent():
    """Create sample configuration with agent enabled"""
    config = Mock(spec=MonitorConfig)
    
    # GitHub configuration
    config.github = Mock(spec=GitHubConfig)
    config.github.repository = "owner/repo"
    
    # Search configuration
    config.search = Mock(spec=SearchConfig)
    config.search.daily_query_limit = 90
    config.search.results_per_query = 10
    config.search.date_range_days = 7
    
    # Sites configuration
    site = Mock(spec=SiteConfig)
    site.name = "Example Site"
    site.query = "example search query"
    config.sites = [site]
    
    # Storage and logging
    config.storage_path = "test_processed.json"
    config.log_level = "INFO"
    config.deduplication_retention_days = 30
    
    # Agent configuration (enabled)
    config.agent = Mock()
    config.agent.enabled = True
    config.agent.workflow_dir = "docs/workflow/deliverables"
    config.agent.output_dir = "study"
    config.agent.enable_git = True

    config.site_monitor = SiteMonitorSettings()
    
    return config


@pytest.fixture
def minimal_config():
    """Create minimal configuration for basic tests"""
    config = Mock(spec=MonitorConfig)
    config.github = Mock()
    config.github.repository = "test/repo"
    config.search = Mock()
    config.search.daily_query_limit = 100
    config.sites = [Mock(name="test-site")]
    config.storage_path = "test.json"
    config.log_level = "INFO"
    config.agent = Mock()
    config.agent.enabled = False
    return config
    monkeypatch.setenv("GITHUB_TOKEN", mock_github_token)
    monkeypatch.setenv("GITHUB_REPOSITORY", mock_repository_name)


@pytest.fixture
def mock_labels_list():
    """Mock list of repository labels"""
    labels = []
    for label_name in ["bug", "urgent", "enhancement", "question"]:
        label = Mock()
        label.name = label_name
        labels.append(label)
    return labels


@pytest.fixture
def cli_args_create_issue():
    """Mock CLI arguments for create-issue operation"""
    return [
        "create-issue",
        "--title", "Test Issue from CLI",
        "--body", "This is a test issue created from CLI",
        "--labels", "bug", "urgent",
        "--assignees", "testuser1", "testuser2"
    ]


@pytest.fixture
def cli_args_minimal():
    """Mock minimal CLI arguments for create-issue operation"""
    return [
        "create-issue",
        "--title", "Minimal Test Issue"
    ]


class MockGitHubException(GithubException):
    """Mock GitHub exception for testing"""
    def __init__(self, message):
        super().__init__(status=400, data={"message": message})


@pytest.fixture
def mock_github_exception():
    """Mock GitHub exception"""
    return MockGitHubException("API rate limit exceeded")


@pytest.fixture
def mock_issue_creation_response(mock_github_issue):
    """Mock successful issue creation response"""
    return mock_github_issue


@pytest.fixture
def sample_config():
    """Fixture providing a sample configuration"""
    sites = [
        SiteConfig(
            url="example.com",
            name="Example Site",
            keywords=["documentation"],
            max_results=10
        )
    ]
    
    github = GitHubConfig(
        repository="owner/repo",
        issue_labels=["site-monitor"],
        default_assignees=[]
    )
    
    search = SearchConfig(
        api_key="test-key",
        search_engine_id="test-engine",
        daily_query_limit=90
    )
    
    return MonitorConfig(
        sites=sites,
        github=github,
        search=search,
        storage_path="test_processed.json",
        log_level="INFO",
        site_monitor=SiteMonitorSettings(),
    )


@pytest.fixture
def mock_page_capture_service():
    """Patch PageCaptureService to avoid network and filesystem interactions."""
    with patch('src.core.site_monitor.PageCaptureService') as mock_service:
        yield mock_service


# E2E Test Fixtures
@pytest.fixture
def e2e_temp_dir():
    """Create temporary directory for e2e tests."""
    import tempfile
    import shutil
    
    temp_dir = Path(tempfile.mkdtemp(prefix="speculum_e2e_"))
    
    # Create subdirectories
    (temp_dir / "workflows").mkdir()
    (temp_dir / "output").mkdir()
    (temp_dir / "templates").mkdir()
    
    # Copy template files
    template_src = Path(__file__).parent.parent / "templates"
    if template_src.exists():
        for template_file in template_src.glob("*.md"):
            shutil.copy2(template_file, temp_dir / "templates")
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def e2e_config(e2e_temp_dir):
    """Create e2e test configuration file."""
    import yaml
    
    config_data = {
        'sites': [
            {
                'url': 'https://example.com',
                'name': 'Example Site',
                'max_results': 2
            }
        ],
        'github': {
            'repository': 'testorg/testrepo',
            'issue_labels': ['site-monitor', 'automated'],
            'default_assignees': ['testuser']
        },
        'search': {
            'api_key': 'test-api-key',
            'search_engine_id': 'test-search-engine',
            'daily_query_limit': 90,
            'results_per_query': 10,
            'date_range_days': 30
        },
        'agent': {
            'username': 'testuser',
            'workflow_directory': str(e2e_temp_dir / "workflows"),
            'template_directory': str(e2e_temp_dir / "templates"),
            'output_directory': str(e2e_temp_dir / "output"),
            'processing': {
                'default_timeout_minutes': 60,
                'max_concurrent_issues': 3,
                'retry_attempts': 2,
                'require_review': True,
                'auto_create_pr': False
            },
            'git': {
                'branch_prefix': 'test-agent',
                'commit_message_template': 'Test Agent: {workflow_name} for issue #{issue_number}',
                'auto_push': False
            },
            'validation': {
                'min_word_count': 50,
                'require_citations': False,
                'spell_check': False
            }
        },
        'storage_path': str(e2e_temp_dir / "test_processed.json"),
        'log_level': 'DEBUG'
    }
    
    config_file = e2e_temp_dir / "e2e_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    return config_file


@pytest.fixture
def mock_research_issue():
    """Mock GitHub issue for research workflow testing."""
    issue = Mock()
    issue.number = 123
    issue.title = "Research Analysis Test Issue"
    issue.body = "This is a test issue for research analysis workflow"
    issue.labels = [
        Mock(name="site-monitor"),
        Mock(name="research"),
        Mock(name="analysis")
    ]
    issue.html_url = "https://github.com/testorg/testrepo/issues/123"
    issue.state = "open"
    issue.user = Mock(login="testuser")
    issue.created_at = "2024-01-01T00:00:00Z"
    issue.updated_at = "2024-01-01T00:00:00Z"
    return issue


@pytest.fixture
def mock_technical_issue():
    """Mock GitHub issue for technical review workflow testing."""
    issue = Mock()
    issue.number = 456
    issue.title = "Technical Review Test Issue"
    issue.body = "This is a test issue for technical review workflow"
    issue.labels = [
        Mock(name="site-monitor"),
        Mock(name="technical-review"),
        Mock(name="architecture")
    ]
    issue.html_url = "https://github.com/testorg/testrepo/issues/456"
    issue.state = "open"
    issue.user = Mock(login="testuser")
    issue.created_at = "2024-01-01T00:00:00Z"
    issue.updated_at = "2024-01-01T00:00:00Z"
    return issue


@pytest.fixture
def research_workflow_data(e2e_temp_dir):
    """Create research workflow configuration for testing."""
    import yaml
    
    workflow_data = {
        'name': 'Research Analysis',
        'description': 'Comprehensive research and analysis workflow for detailed investigation',
        'version': '1.0.0',
        'trigger_labels': ['research', 'analysis', 'deep-dive'],
        'output': {
            'folder_structure': 'study/{issue_number}-research-analysis',
            'file_pattern': '{deliverable_name}.md',
            'branch_pattern': 'research-analysis/issue-{issue_number}'
        },
        'deliverables': [
            {
                'name': 'research-overview',
                'title': 'Research Overview',
                'description': 'High-level overview and scope definition',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 1
            },
            {
                'name': 'background-analysis',
                'title': 'Background Analysis',
                'description': 'Historical context and existing knowledge review',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 2
            },
            {
                'name': 'methodology',
                'title': 'Research Methodology',
                'description': 'Approach and methods used for investigation',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 3
            },
            {
                'name': 'findings',
                'title': 'Key Findings',
                'description': 'Primary research results and discoveries',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 4
            }
        ]
    }
    
    workflow_file = e2e_temp_dir / "workflows" / "research-analysis.yaml"
    with open(workflow_file, 'w') as f:
        yaml.dump(workflow_data, f)
    
    return workflow_data


@pytest.fixture
def technical_workflow_data(e2e_temp_dir):
    """Create technical review workflow configuration for testing."""
    import yaml
    
    workflow_data = {
        'name': 'Technical Review',
        'description': 'Structured technical review and assessment workflow',
        'version': '1.0.0',
        'trigger_labels': ['technical-review', 'code-review', 'architecture', 'security-review'],
        'output': {
            'folder_structure': 'study/{issue_number}-technical-review',
            'file_pattern': '{deliverable_name}.md',
            'branch_pattern': 'technical-review/issue-{issue_number}'
        },
        'deliverables': [
            {
                'name': 'technical-overview',
                'title': 'Technical Overview',
                'description': 'High-level technical assessment and scope',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 1
            },
            {
                'name': 'architecture-analysis',
                'title': 'Architecture Analysis',
                'description': 'System architecture review and assessment',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 2
            },
            {
                'name': 'security-assessment',
                'title': 'Security Assessment',
                'description': 'Security implications and vulnerability analysis',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 3
            },
            {
                'name': 'performance-analysis',
                'title': 'Performance Analysis',
                'description': 'Performance characteristics and optimization opportunities',
                'template': 'base_deliverable.md',
                'required': True,
                'order': 4
            }
        ]
    }
    
    workflow_file = e2e_temp_dir / "workflows" / "technical-review.yaml"
    with open(workflow_file, 'w') as f:
        yaml.dump(workflow_data, f)
    
    return workflow_data


@pytest.fixture
def mock_github_client_e2e(mock_research_issue, mock_technical_issue):
    """Enhanced mock GitHub client for e2e testing."""
    github = Mock()
    repo = Mock()
    
    # Setup repository mock
    repo.name = "testrepo"
    repo.full_name = "testorg/testrepo"
    repo.description = "Test repository for E2E testing"
    repo.html_url = "https://github.com/testorg/testrepo"
    
    # Setup issue retrieval
    def get_issue(number):
        if number == 123:
            return mock_research_issue
        elif number == 456:
            return mock_technical_issue
        else:
            # Return a generic issue for other numbers
            issue = Mock()
            issue.number = number
            issue.title = f"Test Issue {number}"
            issue.body = f"Test issue body for {number}"
            issue.labels = [Mock(name="site-monitor")]
            return issue
    
    repo.get_issue = get_issue
    github.get_repo.return_value = repo
    
    return github