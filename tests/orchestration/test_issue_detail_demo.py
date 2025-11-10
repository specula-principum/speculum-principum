"""Integration tests for the issue detail Phase 0 demo mission."""

from __future__ import annotations

from typing import Any

import pytest

from src.orchestration.demo import IssueSummary, TriageRecommendation, run_issue_detail_demo
from src.orchestration.planner import PlanStep


@pytest.fixture(autouse=True)
def _stub_issue_fetch(monkeypatch):
    sample_issue: dict[str, Any] = {
        "number": 42,
        "title": "Demo issue",
        "state": "open",
        "body": "Example body",
        "html_url": "https://github.com/octo/repo/issues/42",
        "labels": [{"name": "triage"}],
        "assignees": [{"login": "octocat"}],
    }

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert token == "token"
        assert repository == "octo/repo"
        assert issue_number == 42
        return sample_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")


def test_issue_detail_demo_succeeds(monkeypatch):
    outcome, summary, recommendation = run_issue_detail_demo(issue_number=42, repository="octo/repo", token="token")

    assert outcome.summary is not None and "Demo issue" in outcome.summary
    assert summary == IssueSummary(
        number=42,
        title="Demo issue",
        state="open",
        labels=("triage",),
        url="https://github.com/octo/repo/issues/42",
    )
    assert recommendation is None


def test_issue_detail_demo_failure(monkeypatch):
    def _raise(*, token, repository, issue_number, api_url="https://api.github.com"):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _raise)

    outcome, summary, recommendation = run_issue_detail_demo(issue_number=99, repository="octo/repo", token="token")

    assert outcome.status.name in {"FAILED", "BLOCKED"}
    assert summary is None
    assert recommendation is None


def test_issue_detail_demo_with_plan_override(monkeypatch):
    sample_issue: dict[str, Any] = {
        "number": 7,
        "title": "Alternate",
        "state": "open",
        "html_url": "https://github.com/octo/repo/issues/7",
    }

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        return sample_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    plan_override = [
        PlanStep(
            description="Fetch via override",
            tool_name="get_issue_details",
            arguments={
                "issue_number": 7,
                "repository": "octo/repo",
                "token": "token",
            },
        )
    ]

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=1,
        repository="octo/repo",
        token="token",
        plan_override=plan_override,
        context_inputs={"issue_number": 7, "repository": "octo/repo", "token": "token"},
    )

    assert outcome.status.name == "SUCCEEDED"
    assert summary is not None and summary.number == 7
    assert recommendation is None


def test_issue_detail_triage_mode_produces_recommendation(monkeypatch):
    sample_issue: dict[str, Any] = {
        "number": 77,
        "title": "Feature request: add export",
        "state": "open",
        "body": "It would be great to have an export feature for reports.",
        "html_url": "https://github.com/octo/repo/issues/77",
    }

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        return sample_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, summary, recommendation = run_issue_detail_demo(
        issue_number=77,
        repository="octo/repo",
        token="token",
        triage_mode=True,
    )

    assert outcome.status.name == "SUCCEEDED"
    assert summary is not None and summary.number == 77
    assert isinstance(recommendation, TriageRecommendation)
    assert recommendation.classification == "feature-request"
    assert "Recommendation:" in (outcome.summary or "")
