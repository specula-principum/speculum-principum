"""Human-in-the-loop approval system for risky agent actions."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .types import ToolCall

if TYPE_CHECKING:
    from .safety import ApprovalCallback


class ApprovalStatus(Enum):
    """Possible outcomes of an approval request."""
    
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ApprovalDecision:
    """Result of a human approval request."""
    
    tool_call: ToolCall
    status: ApprovalStatus
    reason: str | None = None
    approved_by: str | None = None
    timestamp: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert decision to JSON-serializable dictionary."""
        return {
            "tool_name": self.tool_call.name,
            "tool_args": self.tool_call.arguments,
            "status": self.status.value,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class ApprovalGate:
    """Manages human approval workflow for risky agent actions."""
    
    def __init__(
        self,
        audit_log_path: Path | None = None,
        auto_approve: bool = False,
    ) -> None:
        """Initialize approval gate.
        
        Args:
            audit_log_path: Path to audit log file (JSONL format)
            auto_approve: If True, automatically approve all requests (testing only)
        """
        self.audit_log_path = audit_log_path
        self.auto_approve = auto_approve
        self._decisions: list[ApprovalDecision] = []
    
    def request_approval(
        self,
        tool_call: ToolCall,
        context: Mapping[str, Any] | None = None,
    ) -> ApprovalDecision:
        """Request human approval for a risky action.
        
        Args:
            tool_call: The tool call that needs approval
            context: Optional context to help human make decision
            
        Returns:
            ApprovalDecision indicating whether action was approved
        """
        if self.auto_approve:
            decision = ApprovalDecision(
                tool_call=tool_call,
                status=ApprovalStatus.APPROVED,
                reason="Auto-approved (testing mode)",
                approved_by="system",
                timestamp=datetime.now(timezone.utc),
            )
            self.record_decision(decision)
            return decision
        
        # Display approval request to user
        self._display_approval_request(tool_call, context)
        
        # Get user input
        response = self._get_user_response()
        
        if response.lower() in ("y", "yes", "approve"):
            decision = ApprovalDecision(
                tool_call=tool_call,
                status=ApprovalStatus.APPROVED,
                reason="Approved by operator",
                approved_by="interactive-user",
                timestamp=datetime.now(timezone.utc),
            )
        else:
            decision = ApprovalDecision(
                tool_call=tool_call,
                status=ApprovalStatus.REJECTED,
                reason=f"Rejected by operator: {response}",
                approved_by="interactive-user",
                timestamp=datetime.now(timezone.utc),
            )
        
        self.record_decision(decision)
        return decision
    
    def record_decision(self, decision: ApprovalDecision) -> None:
        """Record approval decision to audit log.
        
        Args:
            decision: The approval decision to record
        """
        self._decisions.append(decision)
        
        if self.audit_log_path:
            self._write_audit_entry(decision)
    
    def get_decisions(self) -> list[ApprovalDecision]:
        """Return all approval decisions made during this session.
        
        Returns:
            List of approval decisions
        """
        return self._decisions.copy()
    
    def _display_approval_request(
        self,
        tool_call: ToolCall,
        context: Mapping[str, Any] | None,
    ) -> None:
        """Display approval request to user.
        
        Args:
            tool_call: Tool call requiring approval
            context: Optional context information
        """
        print("\n" + "=" * 70)
        print("⚠️  APPROVAL REQUIRED")
        print("=" * 70)
        print(f"\nTool: {tool_call.name}")
        print("Arguments:")
        for key, value in tool_call.arguments.items():
            # Truncate long values for display
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:97] + "..."
            print(f"  {key}: {value_str}")
        
        if context:
            print("\nContext:")
            for key, value in context.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                print(f"  {key}: {value_str}")
        
        print("\n" + "-" * 70)
    
    def _get_user_response(self) -> str:
        """Prompt user for approval decision.
        
        Returns:
            User's response string
        """
        try:
            response = input("\nApprove this action? (y/n): ").strip()
            return response
        except (EOFError, KeyboardInterrupt):
            print("\n\nApproval interrupted by user")
            return "n"
    
    def _write_audit_entry(self, decision: ApprovalDecision) -> None:
        """Write decision to audit log file.
        
        Args:
            decision: Decision to record
        """
        if not self.audit_log_path:
            return
        
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                json_line = json.dumps(decision.to_dict())
                f.write(json_line + "\n")
        except OSError as exc:
            print(f"Warning: Failed to write audit log: {exc}", file=sys.stderr)


class MockApprovalGate(ApprovalGate):
    """Mock approval gate for testing that returns pre-configured responses."""
    
    def __init__(
        self,
        default_response: ApprovalStatus = ApprovalStatus.APPROVED,
        responses: dict[str, ApprovalStatus] | None = None,
    ) -> None:
        """Initialize mock approval gate.
        
        Args:
            default_response: Default response for all approval requests
            responses: Optional mapping of tool names to specific responses
        """
        super().__init__(auto_approve=False)
        self.default_response = default_response
        self.responses = responses or {}
    
    def request_approval(
        self,
        tool_call: ToolCall,
        context: Mapping[str, Any] | None = None,
    ) -> ApprovalDecision:
        """Return pre-configured approval decision without user interaction.
        
        Args:
            tool_call: The tool call that needs approval
            context: Optional context (ignored in mock)
            
        Returns:
            Pre-configured ApprovalDecision
        """
        status = self.responses.get(tool_call.name, self.default_response)
        
        decision = ApprovalDecision(
            tool_call=tool_call,
            status=status,
            reason=f"Mock response: {status.value}",
            approved_by="mock-gate",
            timestamp=datetime.now(timezone.utc),
        )
        
        self.record_decision(decision)
        return decision


def create_approval_callback(gate: ApprovalGate) -> "ApprovalCallback":
    """Create a safety validator callback from an approval gate.
    
    This bridges the ApprovalGate interface with the SafetyValidator's
    callback mechanism.
    
    Args:
        gate: Approval gate instance to use for approval requests
        
    Returns:
        Callback function compatible with SafetyValidator
    """
    from .safety import ApprovalDecision as SafetyDecision
    from .safety import ActionRisk
    from .types import ExecutionContext
    
    def callback(
        tool_call: ToolCall,
        mission: Any,
        context: ExecutionContext,
        risk: ActionRisk,
    ) -> SafetyDecision:
        """Request approval via the gate and convert to safety decision."""
        # For REVIEW risk, auto-approve in non-interactive mode
        if risk == ActionRisk.REVIEW and gate.auto_approve:
            return SafetyDecision.approved_decision(risk=risk)
        
        # For DESTRUCTIVE risk, always request approval
        if risk == ActionRisk.DESTRUCTIVE:
            approval_context: dict[str, Any] = {
                "mission_id": getattr(mission, "id", "unknown"),
                "risk_level": risk.value,
            }
            gate_decision = gate.request_approval(tool_call, context=approval_context)
            
            if gate_decision.status == ApprovalStatus.APPROVED:
                return SafetyDecision.approved_decision(risk=risk)
            else:
                reason = gate_decision.reason or "Approval denied by operator"
                return SafetyDecision.denied(risk=risk, reason=reason)
        
        # Default: approve REVIEW level actions
        return SafetyDecision.approved_decision(risk=risk)
    
    return callback
