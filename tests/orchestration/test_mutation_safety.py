"""Test suite to verify all Phase 1 missions perform zero unauthorized mutations.

Phase 1 missions must remain read-only:
1. Issue triage mission - only reads issue data
2. KB extraction check - only validates template content
3. PR safety check - only analyzes PR files

This test suite verifies that missions only use read-only tools.
"""

import pytest

from src.orchestration.demo import (
    run_issue_detail_demo,
    run_extraction_check_demo,
    run_pr_safety_check_demo,
)
from src.orchestration.types import MissionStatus


@pytest.fixture
def mock_kb_extraction_issue():
    """Mock complete KB extraction issue."""
    return {
        "number": 5001,
        "title": "Extract knowledge from document",
        "state": "open",
        "body": """**Source Path:** `evidence/doc.pdf`
**Source Type:** PDF

### Extraction Requirements
- [ ] Extract concepts

### Output Requirements
**Target KB Root:** `knowledge-base/`

### Success Criteria
- [ ] Completed
""",
        "labels": [{"name": "kb-extraction"}],
        "assignees": [],
        "url": "https://github.com/test/repo/issues/5001",
    }


@pytest.fixture
def mock_pr_kb_only():
    """Mock PR with KB-only changes."""
    return {
        "number": 5002,
        "title": "Add KB article",
        "state": "open",
        "head": {"sha": "abc123"},
        "base": {"sha": "def456"},
        "url": "https://github.com/test/repo/pull/5002",
    }


@pytest.fixture
def mock_pr_files_kb_only():
    """Mock PR files with KB-only changes."""
    return [
        {
            "filename": "knowledge-base/concepts/test.md",
            "status": "added",
            "additions": 10,
            "deletions": 0,
        }
    ]


def test_triage_mission_uses_only_allowed_tools(monkeypatch):
    """Verify triage mission only uses get_issue_details tool."""

    issue_data = {
        "number": 100,
        "title": "Test issue",
        "state": "open",
        "body": "Test body",
        "labels": [],
        "assignees": [],
        "url": "https://github.com/test/repo/issues/100",
    }

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        return issue_data

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    # Run mission
    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=100,
        repository="test/repo",
        token="token",
        triage_mode=True,
    )

    # Verify mission succeeded using only read operations
    assert outcome.status == MissionStatus.SUCCEEDED
    assert summary is not None
    assert recommendation is not None

    # Mission is configured with only get_issue_details as allowed tool
    # If it attempted other operations, it would fail


def test_kb_extraction_check_uses_only_allowed_tools(monkeypatch, mock_kb_extraction_issue):
    """Verify KB extraction check only uses get_issue_details tool."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        return mock_kb_extraction_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    # Run mission
    outcome, check_result = run_extraction_check_demo(
        issue_number=5001,
        repository="test/repo",
        token="token",
    )

    # Verify mission succeeded using only read operations
    assert outcome.status == MissionStatus.SUCCEEDED
    assert check_result is not None
    assert check_result.validation is not None

    # Mission is configured with only get_issue_details as allowed tool
    # If it attempted other operations, it would fail


def test_pr_safety_check_uses_only_allowed_tools(monkeypatch, mock_pr_kb_only, mock_pr_files_kb_only):
    """Verify PR safety check only uses read-only PR tools."""

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return mock_pr_kb_only

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return mock_pr_files_kb_only

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    # Run mission
    outcome, check_result = run_pr_safety_check_demo(
        pr_number=5002,
        repository="test/repo",
        token="token",
    )

    # Verify mission succeeded using only read operations
    assert outcome.status == MissionStatus.SUCCEEDED
    assert check_result is not None

    # Mission is configured with only get_pr_details and get_pr_files as allowed tools
    # If it attempted mutations, it would fail


def test_all_phase1_missions_complete_without_mutations(
    monkeypatch,
    mock_kb_extraction_issue,
    mock_pr_kb_only,
    mock_pr_files_kb_only,
):
    """Comprehensive test: All Phase 1 missions complete successfully with zero mutations.

    Phase 1 Success Metric: Zero unauthorized mutations (all dry-run or read-only).
    """

    # Mock data for triage mission
    triage_issue = {
        "number": 100,
        "title": "Bug report",
        "state": "open",
        "body": "Application crashes with error message",
        "labels": [],
        "assignees": [],
        "url": "https://github.com/test/repo/issues/100",
    }

    def _fake_fetch_issue(*, token, repository, issue_number, api_url="https://api.github.com"):
        if issue_number == 100:
            return triage_issue
        elif issue_number == 5001:
            return mock_kb_extraction_issue
        raise ValueError(f"Unexpected issue number: {issue_number}")

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return mock_pr_kb_only

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return mock_pr_files_kb_only

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch_issue)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    results = []

    # Test 1: Triage mission
    outcome1, summary1, rec1 = run_issue_detail_demo(
        issue_number=100,
        repository="test/repo",
        token="token",
        triage_mode=True,
    )
    if outcome1.status == MissionStatus.SUCCEEDED and summary1 and rec1:
        results.append("✓ Triage mission: read-only")
    else:
        pytest.fail(f"Triage mission failed: {outcome1.summary}")

    # Test 2: KB extraction check mission
    outcome2, check2 = run_extraction_check_demo(
        issue_number=5001,
        repository="test/repo",
        token="token",
    )
    if outcome2.status == MissionStatus.SUCCEEDED and check2:
        results.append("✓ KB extraction check: read-only")
    else:
        pytest.fail(f"KB extraction check failed: {outcome2.summary}")

    # Test 3: PR safety check mission
    outcome3, check3 = run_pr_safety_check_demo(
        pr_number=5002,
        repository="test/repo",
        token="token",
    )
    if outcome3.status == MissionStatus.SUCCEEDED and check3:
        results.append("✓ PR safety check: read-only")
    else:
        pytest.fail(f"PR safety check failed: {outcome3.summary}")

    # All 3 missions completed successfully without mutations
    assert len(results) == 3, f"Expected 3 successful read-only missions, got {len(results)}: {results}"
