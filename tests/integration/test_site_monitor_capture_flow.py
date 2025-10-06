import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from src.core.site_monitor import SiteMonitorService
from src.agents.ai_workflow_assignment_agent import AIWorkflowAssignmentAgent
from src.clients.search_client import SearchResult
from src.utils.config_manager import (
    MonitorConfig,
    SiteConfig,
    GitHubConfig,
    SearchConfig,
    SiteMonitorSettings,
    IssueTemplateConfig,
    PageCaptureConfig,
)


@pytest.fixture(autouse=True)
def patch_trafilatura(monkeypatch):
    extracted_text = "# Headline\n\nThis is the leading paragraph about new guidance.\n\n## Section One\n\nAdditional insights appear here."

    def fake_extract(html, **kwargs):
        return extracted_text

    monkeypatch.setattr("src.core.page_capture.trafilatura_extract", fake_extract)
    return extracted_text


@pytest.fixture(autouse=True)
def patch_requests(monkeypatch):
    class DummyResponse:
        status_code = 200
        text = "<html><body><h1>Headline</h1><p>This is the leading paragraph about new guidance.</p><h2>Section One</h2></body></html>"

    def fake_get(self, url, timeout):  # pragma: no cover - network-free test helper
        return DummyResponse()

    monkeypatch.setattr("requests.Session.get", fake_get)


class FakeRepo:
    def __init__(self):
        self.labels = [
            SimpleNamespace(name="site-monitor"),
            SimpleNamespace(name="automated"),
            SimpleNamespace(name="documentation"),
            SimpleNamespace(name="monitor::triage"),
            SimpleNamespace(name="state::discovery"),
        ]
        self.created_issues = []

    def get_labels(self):
        return self.labels

    def create_issue(self, title, body, labels=None, assignees=None):
        issue = SimpleNamespace(
            number=len(self.created_issues) + 1,
            title=title,
            body=body,
            labels=labels or [],
            assignees=assignees or [],
        )
        self.created_issues.append(issue)
        return issue


class FakeAuth:
    class Token:  # pragma: no cover - token shim
        def __init__(self, token):
            self.token = token


class FakeSearchClient:
    def __init__(self, config):
        self.config = config
        self._results = {}

    def set_results(self, results):
        self._results = results

    def search_all_sites(self, sites):
        return self._results

    def get_rate_limit_status(self):
        return {"calls_made_today": 1, "daily_limit": 10, "calls_remaining": 9}


class DummyWorkflowMatcher:
    def __init__(self, workflow_directory):  # pragma: no cover - matcher shim
        self.workflow_directory = workflow_directory

    def get_available_workflows(self):
        return []


@pytest.mark.integration
def test_capture_issue_prompt_flow(tmp_path, monkeypatch, patch_trafilatura):
    artifacts_dir = tmp_path / "artifacts" / "discoveries"

    site_config = SiteConfig(
        url="https://example.com",
        name="Example Site",
        keywords=["guidance"],
        max_results=5,
    )
    github_config = GitHubConfig(
        repository="owner/repo",
        issue_labels=["site-monitor", "automated"],
        default_assignees=[],
    )
    search_config = SearchConfig(
        api_key="fake-key",
        search_engine_id="engine-id",
        daily_query_limit=10,
    )
    issue_template = IssueTemplateConfig(
        layout="minimal",
        include_excerpt=True,
        excerpt_max_chars=160,
        include_capture_badge=True,
    )
    page_capture = PageCaptureConfig(
        enabled=True,
        artifacts_dir=str(artifacts_dir),
        store_raw_html=False,
        max_text_bytes=4096,
        timeout_seconds=2,
        retry_attempts=0,
        cache_ttl_minutes=0,
    )
    site_settings = SiteMonitorSettings(
        issue_template=issue_template,
        page_capture=page_capture,
    )
    monitor_config = MonitorConfig(
        sites=[site_config],
        github=github_config,
        search=search_config,
        storage_path=str(tmp_path / "processed.json"),
        log_level="DEBUG",
        site_monitor=site_settings,
    )

    fake_repo = FakeRepo()

    def fake_github_factory(auth):
        return SimpleNamespace(get_repo=lambda repo_name: fake_repo)

    monkeypatch.setattr("src.clients.github_issue_creator.Github", fake_github_factory)
    monkeypatch.setattr("src.clients.github_issue_creator.Auth", FakeAuth)
    monkeypatch.setattr("src.core.site_monitor.GoogleCustomSearchClient", FakeSearchClient)

    config_path = tmp_path / "config.yaml"
    config_path.write_text("sites: []\n", encoding="utf-8")

    service = SiteMonitorService(
        config=monitor_config,
        github_token="fake-token",
        config_path=str(config_path),
    )

    search_result = SearchResult(
        title="Strategic Guidance Released",
        link="https://example.com/strategic-guidance",
        snippet="Initial snippet",
        display_link="example.com",
        cache_id="cache123",
    )
    fake_search_client = cast(FakeSearchClient, service.search_client)
    fake_search_client.set_results({"Example Site": [search_result]})

    cycle = service.run_monitoring_cycle()

    assert cycle["success"] is True
    assert cycle["individual_issues_created"] == 1
    assert fake_repo.created_issues, "Expected a discovery issue to be created"

    issue = fake_repo.created_issues[0]
    assert "Discovery Intake" in issue.body
    assert "Page capture" in issue.body
    assert "Preview excerpt" in issue.body

    entry = service.dedup_manager.get_entry_by_url(search_result.link)
    assert entry is not None
    assert entry.capture_status == "success"
    assert entry.artifact_path is None
    expected_content_dir = artifacts_dir / entry.content_hash
    assert not expected_content_dir.exists()

    service.dedup_manager.save_processed_entries()

    monkeypatch.setattr(
        "src.agents.ai_workflow_assignment_agent.ConfigManager.load_config",
        lambda path: monitor_config,
    )
    monkeypatch.setattr(
        "src.agents.ai_workflow_assignment_agent.WorkflowMatcher",
        lambda workflow_directory: DummyWorkflowMatcher(workflow_directory),
    )

    agent = AIWorkflowAssignmentAgent(
        github_token="fake-token",
        repo_name="owner/repo",
        config_path=str(config_path),
        enable_ai=False,
    )
    agent.prompts_config.include_page_extract = True
    agent.prompts_config.page_extract_max_chars = 400
    agent.dedup_manager.set_artifacts_base_dir(None)

    extract = agent._load_page_extract({"body": issue.body})
    assert extract is not None
    assert "Primary Content Summary" in extract
    assert "leading paragraph" in extract

    stored_data = json.loads(Path(monitor_config.storage_path).read_text(encoding="utf-8"))
    assert stored_data["entries"][0]["artifact_path"] is None
    assert stored_data["entries"][0]["capture_status"] == "success"
