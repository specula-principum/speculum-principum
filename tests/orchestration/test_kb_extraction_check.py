"""Integration tests for the KB extraction check mission.

Phase 1 Goal #2: "KB extraction check" mission identifies missing template fields.

This test suite validates the KB extraction check mission's ability to:
1. Validate complete extraction templates
2. Identify missing required fields
3. Generate appropriate recommendations for action
"""

from __future__ import annotations

from typing import Any

import pytest

from src.orchestration.demo import (
    ExtractionCheckResult,
    TemplateValidationResult,
    run_extraction_check_demo,
)
from src.orchestration.types import MissionStatus


# Test Data: Various extraction issue templates


@pytest.fixture
def complete_extraction_issue() -> dict[str, Any]:
    """Issue #2001: Complete KB extraction request with all required fields."""
    return {
        "number": 2001,
        "title": "Extract knowledge from The Prince Chapter 5",
        "state": "open",
        "body": """## Task: Extract Knowledge from Source Material

**Source Path:** `evidence/sources/the_prince_chapter_5.pdf`
**Source Type:** PDF  
**Processing Date:** 2025-11-03

### Extraction Requirements

- [ ] Extract concepts (min frequency: 2)
- [ ] Extract entities (people, places, organizations)
- [ ] Build relationship graph
- [ ] Generate source document with references

### Output Requirements

**Target KB Root:** `knowledge-base/`

**Expected Artifacts:**
- Concept documents in `knowledge-base/concepts/`
- Entity documents in `knowledge-base/entities/`
- Source document in `knowledge-base/sources/prince-chapter-5/`
- Updated indexes and navigation
- Quality report with metrics

### Quality Standards

- Minimum completeness: 0.80
- Minimum findability: 0.75
- All documents must validate against IA schema
- All links must resolve

### Success Criteria

- [ ] All extraction tools completed successfully
- [ ] Quality metrics meet thresholds
- [ ] Validation passes with no errors
- [ ] Quality report generated
- [ ] Changes committed to branch `kb-extract-2001`
""",
        "html_url": "https://github.com/test/repo/issues/2001",
        "labels": [{"name": "kb-extraction"}, {"name": "ready-for-copilot"}],
        "assignees": [],
    }


@pytest.fixture
def missing_source_path_issue() -> dict[str, Any]:
    """Issue #2002: Missing source path field."""
    return {
        "number": 2002,
        "title": "Extract knowledge from document",
        "state": "open",
        "body": """## Task: Extract Knowledge

**Source Type:** PDF  

### Extraction Requirements

- [ ] Extract concepts
- [ ] Extract entities

### Success Criteria

- [ ] Extraction completed
""",
        "html_url": "https://github.com/test/repo/issues/2002",
        "labels": [{"name": "kb-extraction"}],
        "assignees": [],
    }


@pytest.fixture
def missing_multiple_fields_issue() -> dict[str, Any]:
    """Issue #2003: Missing multiple required fields (source type, requirements, output)."""
    return {
        "number": 2003,
        "title": "KB extraction request",
        "state": "open",
        "body": """Please extract knowledge from evidence/doc.pdf

Thanks!
""",
        "html_url": "https://github.com/test/repo/issues/2003",
        "labels": [{"name": "kb-extraction"}],
        "assignees": [],
    }


@pytest.fixture
def minimal_but_complete_issue() -> dict[str, Any]:
    """Issue #2004: Minimal but has all required fields."""
    return {
        "number": 2004,
        "title": "Extract from source",
        "state": "open",
        "body": """Source path: evidence/test.md
Type: markdown
Extraction requirements: extract concepts and entities
Target KB root: knowledge-base/
Success criteria:
- [ ] Completed
- [ ] Validated
""",
        "html_url": "https://github.com/test/repo/issues/2004",
        "labels": [],
        "assignees": [],
    }


@pytest.fixture
def empty_body_issue() -> dict[str, Any]:
    """Issue #2005: Empty issue body."""
    return {
        "number": 2005,
        "title": "Extract knowledge",
        "state": "open",
        "body": "",
        "html_url": "https://github.com/test/repo/issues/2005",
        "labels": [{"name": "kb-extraction"}],
        "assignees": [],
    }


# Test Suite


def test_extraction_check_validates_complete_template(monkeypatch, complete_extraction_issue):
    """Test that a complete extraction template passes validation."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 2001
        return complete_extraction_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, check_result = run_extraction_check_demo(
        issue_number=2001,
        repository="test/repo",
        token="test-token",
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED, f"Mission failed: {outcome.summary}"

    # Verify extraction check result
    assert check_result is not None
    assert isinstance(check_result, ExtractionCheckResult)

    # Verify validation passed
    assert check_result.validation.is_valid, (
        f"Expected valid template but got: {check_result.validation.validation_message}\n"
        f"Missing fields: {check_result.validation.missing_fields}"
    )

    # Verify all required fields present
    assert len(check_result.validation.present_fields) == 5
    assert len(check_result.validation.missing_fields) == 0

    # Verify recommendation
    assert "proceed" in check_result.recommended_action.lower()
    assert "complete" in check_result.recommended_action.lower()


def test_extraction_check_identifies_missing_source_path(monkeypatch, missing_source_path_issue):
    """Test that missing source path is detected."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 2002
        return missing_source_path_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, check_result = run_extraction_check_demo(
        issue_number=2002,
        repository="test/repo",
        token="test-token",
    )

    # Verify mission succeeded (validation can succeed even if template is invalid)
    assert outcome.status == MissionStatus.SUCCEEDED

    # Verify extraction check result
    assert check_result is not None
    assert not check_result.validation.is_valid

    # Verify source_path and output_requirements are identified as missing
    assert "source_path" in check_result.validation.missing_fields
    assert "output_requirements" in check_result.validation.missing_fields

    # Verify recommendation suggests clarification
    assert "clarification" in check_result.recommended_action.lower() or "missing" in check_result.recommended_action.lower()


def test_extraction_check_handles_severely_incomplete_template(monkeypatch, missing_multiple_fields_issue):
    """Test that severely incomplete templates trigger strong recommendations."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 2003
        return missing_multiple_fields_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, check_result = run_extraction_check_demo(
        issue_number=2003,
        repository="test/repo",
        token="test-token",
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED

    # Verify extraction check result
    assert check_result is not None
    assert not check_result.validation.is_valid

    # Verify multiple fields missing (at least 3)
    assert len(check_result.validation.missing_fields) >= 3

    # Verify recommendation is to use proper template
    assert "template" in check_result.recommended_action.lower()
    assert "incomplete" in check_result.recommended_action.lower()


def test_extraction_check_accepts_minimal_format(monkeypatch, minimal_but_complete_issue):
    """Test that minimal formatting is accepted if all fields present."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 2004
        return minimal_but_complete_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, check_result = run_extraction_check_demo(
        issue_number=2004,
        repository="test/repo",
        token="test-token",
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED

    # Verify extraction check result
    assert check_result is not None

    # Should pass validation despite minimal formatting
    assert check_result.validation.is_valid, (
        f"Minimal template should pass but got: {check_result.validation.validation_message}\n"
        f"Missing fields: {check_result.validation.missing_fields}"
    )


def test_extraction_check_handles_empty_body(monkeypatch, empty_body_issue):
    """Test that empty issue body fails validation gracefully."""

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        assert issue_number == 2005
        return empty_body_issue

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    outcome, check_result = run_extraction_check_demo(
        issue_number=2005,
        repository="test/repo",
        token="test-token",
    )

    # Verify mission succeeded
    assert outcome.status == MissionStatus.SUCCEEDED

    # Verify extraction check result
    assert check_result is not None
    assert not check_result.validation.is_valid

    # Verify all fields marked as missing
    assert len(check_result.validation.missing_fields) == 5
    assert len(check_result.validation.present_fields) == 0


# Comprehensive validation test


def test_extraction_check_validates_all_test_cases(
    monkeypatch,
    complete_extraction_issue,
    missing_source_path_issue,
    missing_multiple_fields_issue,
    minimal_but_complete_issue,
    empty_body_issue,
):
    """Comprehensive test: Validate extraction check across all test scenarios.

    Phase 1 Success Metric: KB extraction check mission identifies missing template fields.
    """

    test_cases = [
        (2001, complete_extraction_issue, True, "complete template"),
        (2002, missing_source_path_issue, False, "missing source path"),
        (2003, missing_multiple_fields_issue, False, "severely incomplete"),
        (2004, minimal_but_complete_issue, True, "minimal but complete"),
        (2005, empty_body_issue, False, "empty body"),
    ]

    def _fake_fetch(*, token, repository, issue_number, api_url="https://api.github.com"):
        for num, issue_data, _, _ in test_cases:
            if issue_number == num:
                return issue_data
        raise ValueError(f"Unexpected issue number: {issue_number}")

    monkeypatch.setattr("src.integrations.github.issues.fetch_issue", _fake_fetch)

    results = []
    failures = []

    for issue_number, _, expected_valid, description in test_cases:
        outcome, check_result = run_extraction_check_demo(
            issue_number=issue_number,
            repository="test/repo",
            token="test-token",
        )

        if outcome.status != MissionStatus.SUCCEEDED:
            failures.append(f"Issue #{issue_number} ({description}): Mission failed - {outcome.summary}")
            continue

        if check_result is None:
            failures.append(f"Issue #{issue_number} ({description}): Missing extraction check result")
            continue

        actual_valid = check_result.validation.is_valid
        if actual_valid != expected_valid:
            failures.append(
                f"Issue #{issue_number} ({description}): Expected valid={expected_valid}, "
                f"got valid={actual_valid} - {check_result.validation.validation_message}"
            )
        else:
            status_symbol = "✓" if actual_valid else "✗"
            results.append(f"Issue #{issue_number} ({description}): {status_symbol} validation={actual_valid}")

    # Report results
    if failures:
        report = "\n".join(results + failures)
        pytest.fail(f"Extraction check validation test failed:\n{report}\n\nAccuracy: {len(results)}/5 ({len(results)*20}%)")

    # All 5 test cases validated correctly
    assert len(results) == 5, f"Expected 5 successful validations, got {len(results)}"
