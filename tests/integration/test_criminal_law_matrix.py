import pytest
import yaml
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

from src.core.issue_processor import IssueData, IssueProcessingStatus, IssueProcessor
from src.core.batch_processor import BatchConfig, BatchProcessor
from src.workflow.workflow_matcher import WorkflowMatcher
from src.workflow.workflow_state_manager import (
    WORKFLOW_LABEL_PREFIX,
    WorkflowState,
    TEMP_DISCOVERY_LABEL,
)
from src.agents.workflow_assignment_agent import AssignmentAction, WorkflowAssignmentAgent
import src.agents.workflow_assignment_agent as fallback_agent

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
CRIMINAL_LAW_DIR = ROOT / "docs" / "workflow" / "deliverables" / "criminal-law"
TEMPLATES_DIR = ROOT / "templates"
EXAMPLE_BODY = (
    "# Workflow Intake\n\n"
    "## Discovery\n\n"
    "- Source: integration-test\n"
    "- Summary: Elevated criminal-law workflow scenario.\n\n"
    "## AI Assessment\n\n"
    "_Fallback summary will be injected during processing._\n"
)


def _build_structured_content(issue_number: int) -> dict:
    """Create representative structured extraction data for integration fixtures."""
    now = datetime.now(timezone.utc)
    three_days_ago = now - timedelta(days=3)
    one_day_ago = now - timedelta(days=1)

    defendant_name = f"Jordan Case-{issue_number}"
    witness_name = f"Witness Rivera-{issue_number}"
    evidence_name = f"Digital Ledger-{issue_number}"
    venue_name = f"Metro Hall-{issue_number}"
    agency_name = f"GAO Liaison Office-{issue_number}"
    lead_name = f"Lead-{issue_number}-Wire"

    return {
        "summary": "Structured content synthesized for integration coverage.",
        "confidence_score": 0.82,
        "key_topics": ["asset tracing", "sentencing mitigation", "inter-agency coordination"],
        "urgency_level": "medium",
        "content_type": "integration-brief",
        "extraction_timestamp": now.isoformat(),
        "entities": [
            {
                "name": defendant_name,
                "type": "person",
                "confidence": 0.91,
                "attributes": {
                    "role": "Defendant",
                    "notes": "Primary subject of the proceeding.",
                    "risk_score": 0.73,
                    "risk_flags": ["flight risk", "asset dissipation"],
                    "conflicts": ["prior indictment"],
                },
            },
            {
                "name": witness_name,
                "type": "person",
                "confidence": 0.88,
                "attributes": {
                    "role": "Cooperating witness",
                    "notes": "Provides testimony corroborating financial flows.",
                    "risk_score": 0.64,
                    "risk_flags": ["credibility review"],
                    "conflicts": ["prior inconsistent statement"],
                },
            },
            {
                "name": evidence_name,
                "type": "thing",
                "confidence": 0.83,
                "attributes": {
                    "role": "Digital evidence",
                    "notes": "Exported payments ledger seized under warrant.",
                },
            },
            {
                "name": venue_name,
                "type": "place",
                "confidence": 0.8,
                "attributes": {
                    "jurisdiction": "NDCA",
                    "notes": "Primary venue for search warrant execution.",
                },
            },
            {
                "name": agency_name,
                "type": "organization",
                "confidence": 0.77,
                "attributes": {
                    "role": "GAO Liaison",
                    "notes": "Coordinates inter-agency decision points.",
                },
            },
            {
                "name": lead_name,
                "type": "lead",
                "confidence": 0.75,
                "attributes": {
                    "role": "International wire transfer",
                    "notes": "Trace beneficiary bank in follow-up tasks.",
                    "classification": "financial intelligence",
                },
            },
        ],
        "relationships": [
            {
                "entity1": defendant_name,
                "entity2": agency_name,
                "relationship": "coordinating-with",
                "confidence": 0.7,
                "context": "Weekly GAO briefing cadence established.",
            },
            {
                "entity1": witness_name,
                "entity2": evidence_name,
                "relationship": "corroborated-by",
                "confidence": 0.68,
                "context": "Ledger confirms payments described in testimony.",
            },
        ],
        "events": [
            {
                "timestamp": three_days_ago.strftime("%Y-%m-%d %H:%M UTC"),
                "description": "Search warrant executed at primary venue.",
                "entities_involved": [venue_name, evidence_name],
                "confidence": 0.72,
            },
            {
                "timestamp": one_day_ago.strftime("%Y-%m-%d %H:%M UTC"),
                "description": "Coordinated briefing with GAO liaison on wire transfers.",
                "entities_involved": [agency_name, lead_name],
                "confidence": 0.69,
            },
        ],
        "indicators": [
            {
                "type": "statute",
                "value": "18 U.S.C. § 1956",
                "confidence": 0.66,
                "description": "Primary money laundering provision implicated.",
            },
            {
                "type": "directive",
                "value": "GAO-2023-INT-17",
                "confidence": 0.61,
                "description": "GAO guidance for inter-agency financial tracing.",
            },
        ],
    }


class _StubExtractionResult:
    def __init__(self, structured_content: dict) -> None:
        self.success = True
        self.structured_content = structured_content
        self.error_message = None


class _StubExtractionAgent:
    def extract_content(self, issue_dict: dict) -> _StubExtractionResult:
        issue_number = issue_dict.get("number", 0)
        return _StubExtractionResult(_build_structured_content(issue_number))


def _write_config(tmp_path: Path, output_dir: Path) -> Path:
    config = {
        "sites": [
            {
                "url": "https://example.com",
                "name": "Example",
                "max_results": 1,
            }
        ],
        "github": {
            "repository": "owner/repo",
            "issue_labels": ["site-monitor"],
            "default_assignees": [],
        },
        "search": {
            "api_key": "test-key",
            "search_engine_id": "test-cx",
            "daily_query_limit": 10,
            "results_per_query": 1,
            "date_range_days": 1,
        },
        "agent": {
            "username": "integration-bot",
            "workflow_directory": str(CRIMINAL_LAW_DIR),
            "template_directory": str(TEMPLATES_DIR),
            "output_directory": str(output_dir),
            "processing": {
                "default_timeout_minutes": 10,
                "max_concurrent_issues": 2,
                "retry_attempts": 0,
                "require_review": False,
                "auto_create_pr": False,
            },
            "git": {
                "branch_prefix": "integration",
                "commit_message_template": "Integration Test: {workflow_name}",
                "auto_push": False,
            },
        },
        "storage_path": str(tmp_path / "processed.json"),
        "log_level": "INFO",
    }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


@pytest.fixture
def issue_processor(tmp_path: Path) -> IssueProcessor:
    output_dir = tmp_path / "outputs"
    config_path = _write_config(tmp_path, output_dir)
    processor = IssueProcessor(
        config_path=str(config_path),
        workflow_dir=str(CRIMINAL_LAW_DIR),
        output_base_dir=str(output_dir),
        enable_git=False,
        enable_state_saving=False,
    )
    processor.enable_ai_extraction = True
    processor.content_extraction_agent = _StubExtractionAgent()  # type: ignore[assignment]
    return processor


def test_issue_processor_handles_all_criminal_law_workflows(issue_processor: IssueProcessor) -> None:
    workflows = sorted(
        issue_processor.workflow_matcher.get_available_workflows(),
        key=lambda wf: wf.name,
    )
    assert len(workflows) == 10

    label_counts = Counter(label for wf in workflows for label in wf.trigger_labels)

    for idx, workflow in enumerate(workflows, start=1):
        issue_number = 9000 + idx
        unique_labels = [label for label in workflow.trigger_labels if label_counts[label] == 1]
        assert unique_labels, f"Workflow {workflow.name} must expose at least one unique trigger label"
        labels = ["site-monitor", unique_labels[0]]
        timestamp = datetime.now(timezone.utc)
        issue_data = IssueData(
            number=issue_number,
            title=f"Integration Flow {workflow.name}",
            body=EXAMPLE_BODY,
            labels=labels,
            assignees=[],
            created_at=timestamp,
            updated_at=timestamp,
            url=f"https://example.com/issues/{issue_number}",
        )

        result = issue_processor.process_issue(issue_data)

        assert result.status == IssueProcessingStatus.COMPLETED
        assert result.workflow_name == workflow.name
        assert result.created_files, "Expected deliverable artifacts to be generated"
        for created_file in result.created_files:
            assert Path(created_file).is_file()


def test_batch_processor_handles_full_criminal_law_matrix(
    issue_processor: IssueProcessor, tmp_path: Path
) -> None:
    workflows = sorted(
        issue_processor.workflow_matcher.get_available_workflows(),
        key=lambda wf: wf.name,
    )
    assert len(workflows) == 10

    base_issue_number = 9100
    timestamp = datetime.now(timezone.utc).isoformat()
    issue_payloads: dict[int, dict] = {}
    label_counts = Counter(label for wf in workflows for label in wf.trigger_labels)

    for idx, workflow in enumerate(workflows, start=1):
        issue_number = base_issue_number + idx
        unique_labels = [label for label in workflow.trigger_labels if label_counts[label] == 1]
        assert unique_labels, f"Workflow {workflow.name} must expose at least one unique trigger label"
        labels = ["site-monitor", unique_labels[0]]
        issue_payloads[issue_number] = {
            "number": issue_number,
            "title": f"Batch Flow {workflow.name}",
            "body": EXAMPLE_BODY,
            "labels": labels,
            "assignees": [],
            "created_at": timestamp,
            "updated_at": timestamp,
            "url": f"https://example.com/issues/{issue_number}",
            "state": "open",
        }

    class StubGitHubClient:
        def __init__(self, payloads: dict[int, dict]) -> None:
            self._payloads = payloads

        def get_issue_data(self, issue_number: int) -> dict:
            return dict(self._payloads[issue_number])

    batch_config = BatchConfig(
        max_batch_size=3,
        max_concurrent_workers=1,
        retry_count=0,
        retry_delay_seconds=0.0,
        rate_limit_delay=0.0,
    )

    batch_processor = BatchProcessor(  # type: ignore[arg-type]
        issue_processor=issue_processor,
    github_client=StubGitHubClient(issue_payloads),  # type: ignore[arg-type]
        config=batch_config,
        telemetry_publishers=[],
    )

    issue_numbers = sorted(issue_payloads.keys())
    metrics, results = batch_processor.process_issues(issue_numbers, dry_run=False)

    assert metrics.total_issues == len(issue_payloads)
    assert metrics.success_count == len(issue_payloads)
    assert metrics.error_count == 0
    assert all(result.status == IssueProcessingStatus.COMPLETED for result in results)

    observed = {result.workflow_name for result in results}
    expected = {workflow.name for workflow in workflows}
    assert expected == observed

    for result in results:
        assert result.created_files, "Expected deliverable artifacts to be generated"
        for created_file in result.created_files:
            assert Path(created_file).is_file()


def test_fallback_assignment_selects_taxonomy_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    matcher = WorkflowMatcher(str(CRIMINAL_LAW_DIR))
    workflows = matcher.get_available_workflows()
    label_counts = Counter(label for wf in workflows for label in wf.trigger_labels)

    selected_workflow = None
    unique_label = None
    for workflow in workflows:
        candidates = [label for label in workflow.trigger_labels if label_counts[label] == 1]
        if candidates:
            selected_workflow = workflow
            unique_label = candidates[0]
            break

    assert selected_workflow is not None, "Expected a workflow with a unique trigger label"
    assert unique_label is not None

    class StubLabel:
        def __init__(self, name: str) -> None:
            self.name = name

    class StubIssue:
        def __init__(self, number: int, title: str, body: str, labels: list[str]) -> None:
            self.number = number
            self.title = title
            self.body = body
            self.labels = [StubLabel(label) for label in labels]

    issue_registry: dict[int, StubIssue] = {}

    class StubRepo:
        def __init__(self, registry: dict[int, StubIssue]) -> None:
            self._registry = registry

        def get_issue(self, number: int) -> StubIssue:
            return self._registry[number]

    class StubGitHubIssueCreator:
        def __init__(self, token: str, repository: str) -> None:
            self.repo = StubRepo(issue_registry)

    monkeypatch.setattr(fallback_agent, "GitHubIssueCreator", StubGitHubIssueCreator)
    dummy_config = SimpleNamespace(agent=SimpleNamespace(username="fallback-bot"))
    monkeypatch.setattr(fallback_agent.ConfigManager, "load_config", lambda _: dummy_config)

    issue_number = 9200
    base_labels = [
        "site-monitor",
        unique_label,
        WorkflowState.DISCOVERY.label,
        TEMP_DISCOVERY_LABEL,
    ]
    issue_registry[issue_number] = StubIssue(
        number=issue_number,
        title="Fallback Coverage",
        body=EXAMPLE_BODY,
        labels=base_labels,
    )

    agent = WorkflowAssignmentAgent(
        github_token="dummy-token",
        repo_name="owner/repo",
        config_path="dummy.yaml",
        workflow_directory=str(CRIMINAL_LAW_DIR),
    )

    issue_data = {
        "number": issue_number,
        "title": "Fallback Coverage",
        "body": EXAMPLE_BODY,
        "labels": base_labels,
        "assignee": None,
    }

    result = agent.process_issue_assignment(issue_data, dry_run=True)

    expected_workflow_label = f"{WORKFLOW_LABEL_PREFIX}{agent._slugify_label(selected_workflow.name)}"
    assert result.labels_added is not None
    added_labels = {label.lower() for label in result.labels_added}

    assert result.action == AssignmentAction.ASSIGN_WORKFLOW
    assert result.workflow_name == selected_workflow.name
    assert expected_workflow_label in added_labels
    assert WorkflowState.ASSIGNED.label in added_labels
    assert "fallback heuristics" in result.message.lower()
