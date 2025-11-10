#!/usr/bin/env python3
"""
Demonstration of Phase 2 approval gate features.

This script shows how the approval gate system integrates with the agent runtime
to provide human oversight for destructive operations.
"""

from src.orchestration.agent import AgentRuntime
from src.orchestration.approval import ApprovalGate, ApprovalStatus, create_approval_callback
from src.orchestration.evaluation import SimpleMissionEvaluator
from src.orchestration.missions import Mission
from src.orchestration.planner import DeterministicPlanner, PlanStep
from src.orchestration.safety import ActionRisk, SafetyValidator
from src.orchestration.tools import ToolDefinition, ToolRegistry, ToolResult
from src.orchestration.types import ExecutionContext


def demo_auto_approve_mode():
    """Demonstrate auto-approve mode for testing."""
    print("=" * 70)
    print("DEMO 1: Auto-Approve Mode (for testing)")
    print("=" * 70)
    
    # Create a mock destructive tool
    registry = ToolRegistry()
    
    def mock_close_handler(args):
        issue = args.get("issue_number", "unknown")
        return ToolResult(success=True, output={"issue": issue, "state": "closed"}, error=None)
    
    registry.register_tool(
        ToolDefinition(
            name="close_issue",
            description="Close an issue",
            parameters={"type": "object", "properties": {"issue_number": {"type": "integer"}}, "required": ["issue_number"]},
            handler=mock_close_handler,
            risk_level=ActionRisk.DESTRUCTIVE,
        )
    )
    
    # Create approval gate in auto-approve mode
    gate = ApprovalGate(auto_approve=True)
    callback = create_approval_callback(gate)
    
    # Setup safety validator with approval callback
    safety = SafetyValidator(
        risk_overrides={"close_issue": ActionRisk.DESTRUCTIVE},
        approval_callback=callback,
    )
    
    # Create a simple mission
    mission = Mission(
        id="demo-auto-approve",
        goal="Demonstrate auto-approve functionality",
        max_steps=3,
        constraints=(),
        success_criteria=(),
        allowed_tools=("close_issue",),
    )
    
    # Create plan that closes an issue
    steps = [
        PlanStep(
            description="Close issue #42",
            tool_name="close_issue",
            arguments={"issue_number": 42},
        ),
    ]
    
    planner = DeterministicPlanner(steps=steps, default_finish="Demo complete")
    evaluator = SimpleMissionEvaluator(success_condition=lambda steps: len(steps) > 0)
    
    # Create and run agent
    agent = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=safety,
        evaluator=evaluator,
    )
    
    context = ExecutionContext()
    outcome = agent.execute_mission(mission, context)
    
    print(f"\nMission Status: {outcome.status.value}")
    print(f"Steps Executed: {len(outcome.steps)}")
    if outcome.steps[0].result:
        print(f"Tool Result: {outcome.steps[0].result.output}")
    
    # Check approval decisions
    decisions = gate.get_decisions()
    print(f"\nApproval Decisions: {len(decisions)}")
    for i, decision in enumerate(decisions, 1):
        print(f"  {i}. Tool: {decision.tool_call.name}")
        print(f"     Status: {decision.status.value}")
        print(f"     Approved by: {decision.approved_by}")
    
    print("\n✓ Auto-approve mode allows all DESTRUCTIVE actions without prompts\n")


def demo_approval_decision_logging():
    """Demonstrate approval decision audit logging."""
    print("=" * 70)
    print("DEMO 2: Approval Decision Audit Logging")
    print("=" * 70)
    
    from pathlib import Path
    import tempfile
    
    # Create temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        log_path = Path(f.name)
    
    try:
        gate = ApprovalGate(auto_approve=True, audit_log_path=log_path)
        
        # Simulate some approval requests
        from src.orchestration.types import ToolCall
        
        for i in range(3):
            tool_call = ToolCall(
                name=f"tool_{i}",
                arguments={"param": f"value_{i}"}
            )
            context_info = {
                "mission_id": "demo-logging",
                "step": f"{i+1}/3"
            }
            gate.request_approval(tool_call, context_info)
        
        print(f"\nAudit log written to: {log_path}")
        print(f"Total decisions: {len(gate.get_decisions())}")
        
        # Read and display log entries
        print("\nAudit Log Entries:")
        print("-" * 70)
        with log_path.open() as f:
            import json
            for i, line in enumerate(f, 1):
                entry = json.loads(line)
                print(f"{i}. {entry['timestamp'][:19]}")
                print(f"   Tool: {entry['tool_name']}")
                print(f"   Status: {entry['status']}")
                print(f"   Approved by: {entry.get('approved_by', 'N/A')}")
                print()
        
        print("✓ All approval decisions are permanently logged for audit\n")
        
    finally:
        # Cleanup
        if log_path.exists():
            log_path.unlink()


def demo_safety_validator_integration():
    """Demonstrate how approval gates integrate with SafetyValidator."""
    print("=" * 70)
    print("DEMO 3: SafetyValidator Integration")
    print("=" * 70)
    
    # This demo shows the conceptual integration
    # In practice, the integration happens via the approval_callback parameter
    
    print("\nThe SafetyValidator uses an approval_callback to request approval")
    print("for DESTRUCTIVE operations. Here's how it works:")
    print()
    print("1. Agent runtime creates ApprovalGate:")
    print("   gate = ApprovalGate(auto_approve=False)")
    print()
    print("2. Create callback bridge:")
    print("   callback = create_approval_callback(gate)")
    print()
    print("3. Pass to SafetyValidator:")
    print("   safety = SafetyValidator(approval_callback=callback)")
    print()
    print("4. When DESTRUCTIVE action is attempted:")
    print("   - SafetyValidator calls approval_callback")
    print("   - Callback invokes gate.request_approval()")
    print("   - Gate prompts operator (if interactive)")
    print("   - Decision is returned and logged")
    print()
    
    # Show practical example
    gate = ApprovalGate(auto_approve=True)
    callback = create_approval_callback(gate)
    
    # The safety validator would use this callback
    _ = SafetyValidator(
        risk_overrides={"close_issue": ActionRisk.DESTRUCTIVE},
        approval_callback=callback,
    )
    
    print("Example with auto-approve mode:")
    print("-" * 70)
    
    from src.orchestration.types import ToolCall
    
    mission = Mission(
        id="demo-safety",
        goal="Test safety integration",
        max_steps=5,
        constraints=(),
        success_criteria=(),
        allowed_tools=("close_issue",),
    )
    
    context = ExecutionContext()
    tool_call = ToolCall(name="close_issue", arguments={"issue_number": 42})
    
    # The safety validator would call the approval callback internally
    # We can simulate this by calling it directly
    decision = callback(tool_call, mission, context, ActionRisk.DESTRUCTIVE)
    
    print("\nTool: close_issue")
    print("Risk: DESTRUCTIVE")
    print(f"Safety Decision: {'APPROVED' if decision.approved else 'DENIED'}")
    
    # Check approval was logged
    decisions = gate.get_decisions()
    print(f"\nApproval Requests Logged: {len(decisions)}")
    
    for dec in decisions:
        print(f"  - {dec.tool_call.name}: {dec.status.value}")
    
    print("\n✓ SafetyValidator routes DESTRUCTIVE actions through approval gate\n")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "PHASE 2 APPROVAL GATE DEMONSTRATION" + " " * 17 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    demo_auto_approve_mode()
    demo_approval_decision_logging()
    demo_safety_validator_integration()
    
    print("=" * 70)
    print("All demonstrations completed successfully!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("  1. Approval gates provide human oversight for DESTRUCTIVE operations")
    print("  2. Auto-approve mode enables testing without manual intervention")
    print("  3. All approval decisions are logged for audit compliance")
    print("  4. SafetyValidator integrates seamlessly with approval callbacks")
    print()
    print("For interactive mode, use: --interactive flag in CLI commands")
    print()


if __name__ == "__main__":
    main()
