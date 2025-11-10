"""Integration tests for the triage_new_issue mission.

Phase 1 Goal: Agent triages 5 test issues with 100% accuracy.

This test suite validates the triage mission against 5 distinct issue types:
1. KB extraction request (should classify as kb-extraction)
2. Bug report (should classify as bug)
3. Feature request (should classify as feature-request)
4. Incomplete/question issue (should classify as needs-info)
5. Ambiguous issue requiring human review (should classify as needs-review)
"""

from __future__ import annotations

from typing import Any

import pytest

from src.orchestration.demo import IssueSummary, TriageRecommendation, run_issue_detail_demo
from src.orchestration.types import MissionStatus


# Test Data: 5 representative issue types for triage validation


@pytest.fixture
def kb_extraction_issue() -> dict[str, Any]:
    """Issue #1: Clear KB extraction request."""
    return {
        "number": 1001,
        "title": "Extract knowledge from The Prince Chapter 3",
        "state": "open",
        "body": (
            "Please extract knowledge from The Prince, Chapter 3.\n\n"
            "Source: evidence/sources/the_prince_chapter_3.pdf\n"
            "Requirements:\n"
            "- Extract key concepts about mixed principalities\n"
            "- Identify relationships between concepts\n"
            "- Generate structured markdown output\n"
        ),
        "html_url": "https://github.com/test/repo/issues/1001",
        "labels": [],
        "assignees": [],
    }


@pytest.fixture
def bug_report_issue() -> dict[str, Any]:
    """Issue #2: Bug report with error details."""
    return {
        "number": 1002,
        "title": "Parsing fails for DOCX files with embedded images",
        "state": "open",
        "body": (
            "When parsing DOCX files that contain embedded images, the parser crashes.\n\n"
            "**Error:**\n"
            "```\n"
            "Traceback (most recent call last):\n"
            '  File "src/parsing/docx.py", line 45, in parse\n'
            "    image_data = element.image.blob\n"
            "AttributeError: 'NoneType' object has no attribute 'blob'\n"
            "```\n\n"
            "**Steps to reproduce:**\n"
            "1. Run `python -m main parse evidence/test.docx`\n"
            "2. Observe the stacktrace\n"
        ),
        "html_url": "https://github.com/test/repo/issues/1002",
        "labels": [],
        "assignees": [],
    }


@pytest.fixture
def feature_request_issue() -> dict[str, Any]:
    """Issue #3: Feature request for enhancement."""
    return {
        "number": 1003,
        "title": "Add support for exporting knowledge base to JSON",
        "state": "open",
        "body": (
            "It would be great to have an export feature that generates JSON output "
            "from the knowledge base for integration with external tools.\n\n"
            "**Proposed behavior:**\n"
            "- Add `--format json` flag to KB commands\n"
            "- Output structured JSON with concepts, relationships, and metadata\n"
            "- Include schema documentation\n\n"
            "**Use case:**\n"
            "Integrate with external analytics dashboards and visualization tools.\n"
        ),
        "html_url": "https://github.com/test/repo/issues/1003",
        "labels": [],
        "assignees": [],
    }


@pytest.fixture
def needs_info_issue() -> dict[str, Any]:
    """Issue #4: Question/incomplete issue needing clarification."""
    return {
        "number": 1004,
        "title": "How do I configure the extraction pipeline?",
        "state": "open",
        "body": (
            "I'm trying to set up the extraction pipeline but I'm not sure how to configure it.\n\n"
            "Can someone help me understand:\n"
            "- Which config files control extraction behavior?\n"
            "- How to customize the taxonomy?\n"
            "- Where to find documentation on extraction stages?\n\n"
            "Thanks!\n"
        ),
        "html_url": "https://github.com/test/repo/issues/1004",
        "labels": [],
        "assignees": [],
    }


@pytest.fixture
def ambiguous_issue() -> dict[str, Any]:
    """Issue #5: Ambiguous issue requiring human judgment."""
    return {
        "number": 1005,
        "title": "Repository organization",
        "state": "open",
        "body": (
            "The current repository structure could be improved. "
            "Some thoughts on better organization patterns.\n"
        ),
        "html_url": "https://github.com/test/repo/issues/1005",
        "labels": [],
        "assignees": [],
    }


# Test Suite: Validate triage classification accuracy


def test_triage_kb_extraction_issue(monkeypatch, kb_extraction_issue):
    """Test triage correctly identifies KB extraction requests."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 1001
        return kb_extraction_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1001,
        repository="test/repo",
        token="test-token",
        triage_mode=True,
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify issue summary was captured
    assert summary is not None
    assert summary.number == 1001
    assert summary.title == "Extract knowledge from The Prince Chapter 3"
    assert summary.state == "open"

    # Verify triage recommendation is correct
    assert recommendation is not None
    assert recommendation.classification == "kb-extraction", (
        f"Expected 'kb-extraction', got '{recommendation.classification}'\n"
        f"Rationale: {recommendation.rationale}"
    )
    assert "kb-extraction" in recommendation.suggested_labels


def test_triage_bug_report_issue(monkeypatch, bug_report_issue):
    """Test triage correctly identifies bug reports."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 1002
        return bug_report_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1002,
        repository="test/repo",
        token="test-token",
        triage_mode=True,
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify issue summary was captured
    assert summary is not None
    assert summary.number == 1002
    assert "DOCX" in summary.title or "docx" in summary.title.lower()

    # Verify triage recommendation is correct
    assert recommendation is not None
    assert recommendation.classification == "bug", (
        f"Expected 'bug', got '{recommendation.classification}'\n"
        f"Rationale: {recommendation.rationale}"
    )
    assert "bug" in recommendation.suggested_labels


def test_triage_feature_request_issue(monkeypatch, feature_request_issue):
    """Test triage correctly identifies feature requests."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 1003
        return feature_request_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1003,
        repository="test/repo",
        token="test-token",
        triage_mode=True,
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify issue summary was captured
    assert summary is not None
    assert summary.number == 1003
    assert "export" in summary.title.lower() or "JSON" in summary.title

    # Verify triage recommendation is correct
    assert recommendation is not None
    assert recommendation.classification == "feature-request", (
        f"Expected 'feature-request', got '{recommendation.classification}'\n"
        f"Rationale: {recommendation.rationale}"
    )
    assert "feature-request" in recommendation.suggested_labels


def test_triage_needs_info_issue(monkeypatch, needs_info_issue):
    """Test triage correctly identifies issues needing more information."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 1004
        return needs_info_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1004,
        repository="test/repo",
        token="test-token",
        triage_mode=True,
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify issue summary was captured
    assert summary is not None
    assert summary.number == 1004
    assert "configure" in summary.title.lower() or "how" in summary.title.lower()

    # Verify triage recommendation is correct
    assert recommendation is not None
    assert recommendation.classification == "needs-info", (
        f"Expected 'needs-info', got '{recommendation.classification}'\n"
        f"Rationale: {recommendation.rationale}"
    )
    assert "needs-info" in recommendation.suggested_labels


def test_triage_ambiguous_issue_escalates(monkeypatch, ambiguous_issue):
    """Test triage escalates ambiguous issues for human review."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 1005
        return ambiguous_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1005,
        repository="test/repo",
        token="test-token",
        triage_mode=True,
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify issue summary was captured
    assert summary is not None
    assert summary.number == 1005
    assert "organization" in summary.title.lower()

    # Verify triage recommendation indicates human review needed
    assert recommendation is not None
    assert recommendation.classification == "needs-review", (
        f"Expected 'needs-review', got '{recommendation.classification}'\n"
        f"Rationale: {recommendation.rationale}"
    )
    # Ambiguous cases may have no suggested labels or generic escalation labels
    assert "review" in recommendation.rationale.lower() or not recommendation.suggested_labels


# Comprehensive validation test


def test_triage_all_five_issues_100_percent_accuracy(
    monkeypatch,
    kb_extraction_issue,
    bug_report_issue,
    feature_request_issue,
    needs_info_issue,
    ambiguous_issue,
):
    """Comprehensive test: Validate triage accuracy across all 5 test cases.

    Phase 1 Success Metric: Agent triages 5 test issues with 100% accuracy.
    """

    test_cases = [
        (1001, kb_extraction_issue, "kb-extraction"),
        (1002, bug_report_issue, "bug"),
        (1003, feature_request_issue, "feature-request"),
        (1004, needs_info_issue, "needs-info"),
        (1005, ambiguous_issue, "needs-review"),
    ]

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        for num, issue_data, _ in test_cases:
            if issue_number == num:
                return issue_data
        raise ValueError(f"Unexpected issue number: {issue_number}")

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    results = []
    failures = []

    for issue_number, _, expected_classification in test_cases:
        outcome, summary, recommendation = run_issue_detail_demo(
            issue_number=issue_number,
            repository="test/repo",
            token="test-token",
            triage_mode=True,
        )

        if outcome.status != MissionStatus.SUCCEEDED:
            failures.append(f"Issue #{issue_number}: Mission failed - {outcome.summary}")
            continue

        if summary is None or recommendation is None:
            failures.append(f"Issue #{issue_number}: Missing summary or recommendation")
            continue

        actual_classification = recommendation.classification
        if actual_classification != expected_classification:
            failures.append(
                f"Issue #{issue_number}: Expected '{expected_classification}', "
                f"got '{actual_classification}' - {recommendation.rationale}"
            )
        else:
            results.append(f"Issue #{issue_number}: ✓ {actual_classification}")

    # Report results
    if failures:
        report = "\n".join(results + failures)
        pytest.fail(f"Triage accuracy test failed:\n{report}\n\nAccuracy: {len(results)}/5 ({len(results)*20}%)")

    # All 5 issues correctly classified = 100% accuracy
    assert len(results) == 5, f"Expected 5 successful triages, got {len(results)}"
