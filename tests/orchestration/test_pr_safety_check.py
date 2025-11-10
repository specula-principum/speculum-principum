"""Integration tests for the PR safety check mission.

Phase 1 Goal #3: "PR safety check" mission correctly categorizes 10 test PRs.

This test suite validates the PR safety check mission's ability to:
1. Categorize PRs based on changed files
2. Assess auto-merge safety
3. Generate appropriate recommendations
4. Handle edge cases (deletions, mixed changes, etc.)
"""

from __future__ import annotations

from typing import Any

import pytest

from src.orchestration.demo import PRSafetyCategory, PRSafetyCheckResult, run_pr_safety_check_demo
from src.orchestration.types import MissionStatus


# Test Data: 10 representative PR scenarios


@pytest.fixture
def kb_only_safe_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3001: KB-only additive changes (safe for auto-merge)."""
    pr_data = {
        "number": 3001,
        "title": "Add new concepts from Chapter 6",
        "body": "Extracted new concepts and entities",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3001",
        "head": {"ref": "kb-extract-chapter-6"},
        "base": {"ref": "main"},
        "user": {"login": "copilot"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "kb-extraction"}],
    }
    files_data = [
        {"filename": "knowledge-base/concepts/fortuna.md", "status": "added", "additions": 45, "deletions": 0, "changes": 45},
        {"filename": "knowledge-base/entities/cesare-borgia.md", "status": "modified", "additions": 12, "deletions": 3, "changes": 15},
        {"filename": "knowledge-base/sources/prince-chapter-6/index.md", "status": "added", "additions": 78, "deletions": 0, "changes": 78},
    ]
    return pr_data, files_data


@pytest.fixture
def kb_only_with_deletions_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3002: KB-only with deletions (requires review)."""
    pr_data = {
        "number": 3002,
        "title": "Refactor KB structure",
        "body": "Reorganize concepts",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3002",
        "head": {"ref": "kb-refactor"},
        "base": {"ref": "main"},
        "user": {"login": "contributor"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [],
    }
    files_data = [
        {"filename": "knowledge-base/concepts/old-concept.md", "status": "removed", "additions": 0, "deletions": 50, "changes": 50},
        {"filename": "knowledge-base/concepts/new-concept.md", "status": "added", "additions": 55, "deletions": 0, "changes": 55},
    ]
    return pr_data, files_data


@pytest.fixture
def test_only_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3003: Test-only changes (safe for auto-merge)."""
    pr_data = {
        "number": 3003,
        "title": "Add tests for triage mission",
        "body": "Comprehensive test coverage",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3003",
        "head": {"ref": "add-triage-tests"},
        "base": {"ref": "main"},
        "user": {"login": "developer"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "tests"}],
    }
    files_data = [
        {"filename": "tests/orchestration/test_triage_mission.py", "status": "added", "additions": 250, "deletions": 0, "changes": 250},
        {"filename": "tests/orchestration/test_agent_runtime.py", "status": "modified", "additions": 15, "deletions": 5, "changes": 20},
    ]
    return pr_data, files_data


@pytest.fixture
def docs_only_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3004: Documentation-only changes (safe for auto-merge)."""
    pr_data = {
        "number": 3004,
        "title": "Update README with new features",
        "body": "Documentation improvements",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3004",
        "head": {"ref": "docs-update"},
        "base": {"ref": "main"},
        "user": {"login": "writer"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "documentation"}],
    }
    files_data = [
        {"filename": "README.md", "status": "modified", "additions": 30, "deletions": 10, "changes": 40},
        {"filename": "docs/architecture.md", "status": "added", "additions": 120, "deletions": 0, "changes": 120},
    ]
    return pr_data, files_data


@pytest.fixture
def config_only_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3005: Config-only changes (requires review)."""
    pr_data = {
        "number": 3005,
        "title": "Update mission configurations",
        "body": "Adjust extraction parameters",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3005",
        "head": {"ref": "config-update"},
        "base": {"ref": "main"},
        "user": {"login": "operator"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "configuration"}],
    }
    files_data = [
        {"filename": "config/extraction.yaml", "status": "modified", "additions": 8, "deletions": 3, "changes": 11},
        {"filename": ".github/workflows/ci.yml", "status": "modified", "additions": 5, "deletions": 2, "changes": 7},
    ]
    return pr_data, files_data


@pytest.fixture
def src_changes_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3006: Source code changes (requires review)."""
    pr_data = {
        "number": 3006,
        "title": "Refactor agent runtime",
        "body": "Improve performance",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3006",
        "head": {"ref": "runtime-refactor"},
        "base": {"ref": "main"},
        "user": {"login": "engineer"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "enhancement"}],
    }
    files_data = [
        {"filename": "src/orchestration/agent.py", "status": "modified", "additions": 85, "deletions": 42, "changes": 127},
        {"filename": "src/orchestration/planner.py", "status": "modified", "additions": 20, "deletions": 15, "changes": 35},
    ]
    return pr_data, files_data


@pytest.fixture
def mixed_kb_tests_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3007: Mixed KB + tests (requires review)."""
    pr_data = {
        "number": 3007,
        "title": "Add concepts with test coverage",
        "body": "KB changes with tests",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3007",
        "head": {"ref": "kb-with-tests"},
        "base": {"ref": "main"},
        "user": {"login": "contributor"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [],
    }
    files_data = [
        {"filename": "knowledge-base/concepts/virtu.md", "status": "added", "additions": 60, "deletions": 0, "changes": 60},
        {"filename": "tests/knowledge_base/test_concepts.py", "status": "modified", "additions": 25, "deletions": 5, "changes": 30},
    ]
    return pr_data, files_data


@pytest.fixture
def mixed_src_config_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3008: Mixed source + config (requires review)."""
    pr_data = {
        "number": 3008,
        "title": "Add new extraction stage",
        "body": "New feature with config",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3008",
        "head": {"ref": "new-stage"},
        "base": {"ref": "main"},
        "user": {"login": "developer"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "feature"}],
    }
    files_data = [
        {"filename": "src/extraction/linking.py", "status": "modified", "additions": 45, "deletions": 10, "changes": 55},
        {"filename": "config/extraction.yaml", "status": "modified", "additions": 12, "deletions": 2, "changes": 14},
    ]
    return pr_data, files_data


@pytest.fixture
def risky_multiple_deletions_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3009: Multiple deletions across categories (risky)."""
    pr_data = {
        "number": 3009,
        "title": "Cleanup and refactor",
        "body": "Remove deprecated code",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3009",
        "head": {"ref": "cleanup"},
        "base": {"ref": "main"},
        "user": {"login": "maintainer"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "refactor"}],
    }
    files_data = [
        {"filename": "src/old_module.py", "status": "removed", "additions": 0, "deletions": 200, "changes": 200},
        {"filename": "tests/test_old_module.py", "status": "removed", "additions": 0, "deletions": 150, "changes": 150},
        {"filename": "config/deprecated.yaml", "status": "removed", "additions": 0, "deletions": 30, "changes": 30},
    ]
    return pr_data, files_data


@pytest.fixture
def comprehensive_mixed_pr() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """PR #3010: Comprehensive changes across all categories (requires review)."""
    pr_data = {
        "number": 3010,
        "title": "Major feature release",
        "body": "Comprehensive changes",
        "state": "open",
        "html_url": "https://github.com/test/repo/pull/3010",
        "head": {"ref": "feature-release"},
        "base": {"ref": "main"},
        "user": {"login": "lead"},
        "mergeable": True,
        "merged": False,
        "draft": False,
        "labels": [{"name": "major-release"}],
    }
    files_data = [
        {"filename": "src/orchestration/missions.py", "status": "modified", "additions": 100, "deletions": 20, "changes": 120},
        {"filename": "knowledge-base/concepts/new-theory.md", "status": "added", "additions": 80, "deletions": 0, "changes": 80},
        {"filename": "tests/orchestration/test_missions.py", "status": "modified", "additions": 60, "deletions": 10, "changes": 70},
        {"filename": "config/mission.yaml", "status": "modified", "additions": 15, "deletions": 5, "changes": 20},
        {"filename": "README.md", "status": "modified", "additions": 25, "deletions": 8, "changes": 33},
    ]
    return pr_data, files_data


# Test Suite


def test_pr_safety_check_kb_only_safe(monkeypatch, kb_only_safe_pr):
    """Test that KB-only additive PR is categorized as safe for auto-merge."""
    pr_data, files_data = kb_only_safe_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        assert pr_number == 3001
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        assert pr_number == 3001
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3001,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category == "kb-only"
    assert safety_result.category.is_safe_for_auto_merge is True
    assert len(safety_result.category.risky_changes) == 0
    assert "auto-merge" in safety_result.recommended_action.lower()


def test_pr_safety_check_kb_with_deletions(monkeypatch, kb_only_with_deletions_pr):
    """Test that KB-only PR with deletions requires review."""
    pr_data, files_data = kb_only_with_deletions_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3002,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert "deletions" in safety_result.category.category.lower()
    assert safety_result.category.is_safe_for_auto_merge is False
    assert len(safety_result.category.risky_changes) > 0


def test_pr_safety_check_test_only(monkeypatch, test_only_pr):
    """Test that test-only PR is safe for auto-merge."""
    pr_data, files_data = test_only_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3003,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category == "test-only"
    assert safety_result.category.is_safe_for_auto_merge is True


def test_pr_safety_check_docs_only(monkeypatch, docs_only_pr):
    """Test that documentation-only PR is safe for auto-merge."""
    pr_data, files_data = docs_only_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3004,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category == "documentation-only"
    assert safety_result.category.is_safe_for_auto_merge is True


def test_pr_safety_check_config_only(monkeypatch, config_only_pr):
    """Test that config-only PR requires review."""
    pr_data, files_data = config_only_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3005,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category == "config-only"
    assert safety_result.category.is_safe_for_auto_merge is False
    assert "review" in safety_result.recommended_action.lower()


def test_pr_safety_check_src_changes(monkeypatch, src_changes_pr):
    """Test that source code changes require review."""
    pr_data, files_data = src_changes_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3006,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category == "src-changes"
    assert safety_result.category.is_safe_for_auto_merge is False
    assert "review" in safety_result.recommended_action.lower() or "test" in safety_result.recommended_action.lower()


def test_pr_safety_check_mixed_kb_tests(monkeypatch, mixed_kb_tests_pr):
    """Test that mixed KB + tests requires review."""
    pr_data, files_data = mixed_kb_tests_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3007,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category.startswith("mixed-")
    assert safety_result.category.is_safe_for_auto_merge is False


def test_pr_safety_check_risky_deletions(monkeypatch, risky_multiple_deletions_pr):
    """Test that multiple deletions are flagged as risky."""
    pr_data, files_data = risky_multiple_deletions_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3009,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert len(safety_result.category.risky_changes) == 3
    assert safety_result.category.is_safe_for_auto_merge is False
    assert "risky" in safety_result.recommended_action.lower() or "careful" in safety_result.recommended_action.lower()


def test_pr_safety_check_comprehensive_mixed(monkeypatch, comprehensive_mixed_pr):
    """Test that comprehensive mixed PR requires review."""
    pr_data, files_data = comprehensive_mixed_pr

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        return pr_data

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        return files_data

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    outcome, safety_result = run_pr_safety_check_demo(
        pr_number=3010,
        repository="test/repo",
        token="test-token",
    )

    assert outcome.status == MissionStatus.SUCCEEDED
    assert safety_result is not None
    assert safety_result.category.category.startswith("mixed-")
    assert safety_result.category.is_safe_for_auto_merge is False
    assert "comprehensive" in safety_result.recommended_action.lower() or "review" in safety_result.recommended_action.lower()


# Comprehensive validation test


def test_pr_safety_check_all_ten_scenarios(
    monkeypatch,
    kb_only_safe_pr,
    kb_only_with_deletions_pr,
    test_only_pr,
    docs_only_pr,
    config_only_pr,
    src_changes_pr,
    mixed_kb_tests_pr,
    mixed_src_config_pr,
    risky_multiple_deletions_pr,
    comprehensive_mixed_pr,
):
    """Comprehensive test: Validate PR safety check across all 10 test scenarios.

    Phase 1 Success Metric: PR safety check mission correctly categorizes 10 test PRs.
    """

    test_cases = [
        (3001, kb_only_safe_pr, "kb-only", True, "KB-only safe"),
        (3002, kb_only_with_deletions_pr, "kb-only-with-deletions", False, "KB with deletions"),
        (3003, test_only_pr, "test-only", True, "test-only"),
        (3004, docs_only_pr, "documentation-only", True, "docs-only"),
        (3005, config_only_pr, "config-only", False, "config-only"),
        (3006, src_changes_pr, "src-changes", False, "src changes"),
        (3007, mixed_kb_tests_pr, "mixed-", False, "mixed KB+tests"),
        (3008, mixed_src_config_pr, "mixed-", False, "mixed src+config"),
        (3009, risky_multiple_deletions_pr, "mixed-", False, "risky deletions"),
        (3010, comprehensive_mixed_pr, "mixed-", False, "comprehensive mixed"),
    ]

    def _fake_fetch_pr(*, token, repository, pr_number, api_url="https://api.github.com"):
        for num, (pr_data, _), _, _, _ in test_cases:
            if pr_number == num:
                return pr_data
        raise ValueError(f"Unexpected PR number: {pr_number}")

    def _fake_fetch_files(*, token, repository, pr_number, api_url="https://api.github.com"):
        for num, (_, files_data), _, _, _ in test_cases:
            if pr_number == num:
                return files_data
        raise ValueError(f"Unexpected PR number: {pr_number}")

    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request", _fake_fetch_pr)
    monkeypatch.setattr("src.integrations.github.pull_requests.fetch_pull_request_files", _fake_fetch_files)

    results = []
    failures = []

    for pr_number, _, expected_category_prefix, expected_safe, description in test_cases:
        outcome, safety_result = run_pr_safety_check_demo(
            pr_number=pr_number,
            repository="test/repo",
            token="test-token",
        )

        if outcome.status != MissionStatus.SUCCEEDED:
            failures.append(f"PR #{pr_number} ({description}): Mission failed - {outcome.summary}")
            continue

        if safety_result is None:
            failures.append(f"PR #{pr_number} ({description}): Missing safety result")
            continue

        actual_category = safety_result.category.category
        actual_safe = safety_result.category.is_safe_for_auto_merge

        if not actual_category.startswith(expected_category_prefix):
            failures.append(
                f"PR #{pr_number} ({description}): Expected category '{expected_category_prefix}*', "
                f"got '{actual_category}'"
            )
        elif actual_safe != expected_safe:
            failures.append(
                f"PR #{pr_number} ({description}): Expected safe={expected_safe}, "
                f"got safe={actual_safe}"
            )
        else:
            safe_symbol = "✓" if actual_safe else "✗"
            results.append(f"PR #{pr_number} ({description}): {safe_symbol} {actual_category}")

    # Report results
    if failures:
        report = "\n".join(results + failures)
        pytest.fail(f"PR safety check validation test failed:\n{report}\n\nAccuracy: {len(results)}/10 ({len(results)*10}%)")

    # All 10 PRs correctly categorized
    assert len(results) == 10, f"Expected 10 successful categorizations, got {len(results)}"
