"""Tests for the approval gate system."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from src.orchestration.approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalStatus,
    MockApprovalGate,
)
from src.orchestration.types import ToolCall


@pytest.fixture
def sample_tool_call() -> ToolCall:
    """Create a sample tool call for testing."""
    return ToolCall(
        name="close_issue",
        arguments={"issue_number": 42, "reason": "Duplicate"},
    )


class TestApprovalGate:
    """Tests for ApprovalGate class."""

    def test_auto_approve_mode(self, sample_tool_call: ToolCall) -> None:
        """Verify auto-approve mode approves all requests."""
        gate = ApprovalGate(auto_approve=True)
        
        decision = gate.request_approval(sample_tool_call)
        
        assert decision.status == ApprovalStatus.APPROVED
        assert decision.tool_call == sample_tool_call
        assert "Auto-approved" in decision.reason  # type: ignore[operator]
        assert decision.approved_by == "system"

    def test_interactive_approve(self, sample_tool_call: ToolCall) -> None:
        """Verify interactive approval with 'yes' response."""
        gate = ApprovalGate()
        
        with patch("builtins.input", return_value="yes"):
            decision = gate.request_approval(sample_tool_call)
        
        assert decision.status == ApprovalStatus.APPROVED
        assert decision.tool_call == sample_tool_call
        assert decision.approved_by == "interactive-user"

    def test_interactive_reject(self, sample_tool_call: ToolCall) -> None:
        """Verify interactive rejection with 'no' response."""
        gate = ApprovalGate()
        
        with patch("builtins.input", return_value="no"):
            decision = gate.request_approval(sample_tool_call)
        
        assert decision.status == ApprovalStatus.REJECTED
        assert decision.tool_call == sample_tool_call
        assert "Rejected" in decision.reason  # type: ignore[operator]

    def test_record_decision(self, sample_tool_call: ToolCall) -> None:
        """Verify decisions are recorded in memory."""
        gate = ApprovalGate(auto_approve=True)
        
        decision1 = gate.request_approval(sample_tool_call)
        decision2 = gate.request_approval(sample_tool_call)
        
        decisions = gate.get_decisions()
        assert len(decisions) == 2
        assert decisions[0] == decision1
        assert decisions[1] == decision2

    def test_audit_log_written(self, sample_tool_call: ToolCall) -> None:
        """Verify approval decisions are written to audit log."""
        with TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.jsonl"
            gate = ApprovalGate(audit_log_path=audit_path, auto_approve=True)
            
            gate.request_approval(sample_tool_call)
            
            assert audit_path.exists()
            content = audit_path.read_text()
            assert "close_issue" in content
            assert "approved" in content

    def test_audit_log_multiple_entries(self, sample_tool_call: ToolCall) -> None:
        """Verify multiple decisions create multiple audit entries."""
        with TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.jsonl"
            gate = ApprovalGate(audit_log_path=audit_path, auto_approve=True)
            
            gate.request_approval(sample_tool_call)
            gate.request_approval(sample_tool_call)
            
            lines = audit_path.read_text().strip().split("\n")
            assert len(lines) == 2

    def test_context_displayed(self, sample_tool_call: ToolCall, capsys) -> None:  # type: ignore[no-untyped-def]
        """Verify context information is displayed to user."""
        gate = ApprovalGate()
        context = {"mission": "triage", "step": 5}
        
        with patch("builtins.input", return_value="yes"):
            gate.request_approval(sample_tool_call, context=context)
        
        captured = capsys.readouterr()
        assert "mission" in captured.out
        assert "triage" in captured.out


class TestMockApprovalGate:
    """Tests for MockApprovalGate class."""

    def test_default_approve(self, sample_tool_call: ToolCall) -> None:
        """Verify mock gate uses default response."""
        gate = MockApprovalGate(default_response=ApprovalStatus.APPROVED)
        
        decision = gate.request_approval(sample_tool_call)
        
        assert decision.status == ApprovalStatus.APPROVED
        assert decision.approved_by == "mock-gate"

    def test_default_reject(self, sample_tool_call: ToolCall) -> None:
        """Verify mock gate can default to rejection."""
        gate = MockApprovalGate(default_response=ApprovalStatus.REJECTED)
        
        decision = gate.request_approval(sample_tool_call)
        
        assert decision.status == ApprovalStatus.REJECTED

    def test_tool_specific_responses(self) -> None:
        """Verify mock gate can provide tool-specific responses."""
        gate = MockApprovalGate(
            default_response=ApprovalStatus.APPROVED,
            responses={
                "close_issue": ApprovalStatus.REJECTED,
                "lock_issue": ApprovalStatus.REJECTED,
            },
        )
        
        # close_issue should be rejected
        close_call = ToolCall(name="close_issue", arguments={"issue_number": 1})
        decision1 = gate.request_approval(close_call)
        assert decision1.status == ApprovalStatus.REJECTED
        
        # lock_issue should be rejected
        lock_call = ToolCall(name="lock_issue", arguments={"issue_number": 2})
        decision2 = gate.request_approval(lock_call)
        assert decision2.status == ApprovalStatus.REJECTED
        
        # add_label should use default (approved)
        label_call = ToolCall(name="add_label", arguments={"issue_number": 3})
        decision3 = gate.request_approval(label_call)
        assert decision3.status == ApprovalStatus.APPROVED

    def test_mock_records_decisions(self, sample_tool_call: ToolCall) -> None:
        """Verify mock gate records decisions like real gate."""
        gate = MockApprovalGate()
        
        gate.request_approval(sample_tool_call)
        gate.request_approval(sample_tool_call)
        
        decisions = gate.get_decisions()
        assert len(decisions) == 2


class TestApprovalDecision:
    """Tests for ApprovalDecision dataclass."""

    def test_to_dict(self) -> None:
        """Verify decision can be serialized to dictionary."""
        from datetime import datetime, timezone
        
        tool_call = ToolCall(name="merge_pr", arguments={"pr_number": 123})
        decision = ApprovalDecision(
            tool_call=tool_call,
            status=ApprovalStatus.APPROVED,
            reason="LGTM",
            approved_by="operator",
            timestamp=datetime(2025, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
        )
        
        data = decision.to_dict()
        
        assert data["tool_name"] == "merge_pr"
        assert data["tool_args"] == {"pr_number": 123}
        assert data["status"] == "approved"
        assert data["reason"] == "LGTM"
        assert data["approved_by"] == "operator"
        assert "2025-11-03" in data["timestamp"]  # type: ignore[operator]
