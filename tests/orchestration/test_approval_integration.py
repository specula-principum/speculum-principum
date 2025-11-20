"""Tests for approval gate integration with agent runtime."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.orchestration.agent import AgentRuntime
from src.orchestration.approval import ApprovalGate, ApprovalStatus, MockApprovalGate, create_approval_callback
from src.orchestration.evaluation import SimpleMissionEvaluator
from src.orchestration.missions import Mission
from src.orchestration.safety import ActionRisk, SafetyValidator
from src.orchestration.tools import ToolRegistry
from src.orchestration.types import ExecutionContext
from tests.orchestration.utils import MockPlanner, PlanStep


@pytest.fixture
def mock_destructive_tool_registry() -> ToolRegistry:
    """Registry with a mock destructive tool."""
    registry = ToolRegistry()
    
    # Register a mock destructive tool
    from src.orchestration.tools import ToolDefinition, ToolResult
    
    def mock_close_handler(args):
        return ToolResult(success=True, output={"closed": True}, error=None)
    
    registry.register_tool(
        ToolDefinition(
            name="close_issue",
            description="Close an issue (destructive operation)",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=mock_close_handler,
            risk_level=ActionRisk.DESTRUCTIVE,
        )
    )
    
    return registry


class TestApprovalGateIntegration:
    """Tests for integrating approval gates with the agent runtime."""

    def test_approval_gate_approves_destructive_action(
        self,
        mock_destructive_tool_registry: ToolRegistry,
    ) -> None:
        """Verify approval gate can approve destructive actions."""
        # Create approval gate that auto-approves
        gate = ApprovalGate(auto_approve=True)
        callback = create_approval_callback(gate)
        
        # Setup safety validator with approval callback
        safety = SafetyValidator(
            risk_overrides={"close_issue": ActionRisk.DESTRUCTIVE},
            approval_callback=callback,
        )
        
        # Create a simple mission
        mission = Mission(
            id="test-destructive",
            goal="Test destructive action approval",
            max_steps=3,
            constraints=(),
            success_criteria=(),
            allowed_tools=("close_issue",),
        )
        
        # Create plan that executes the destructive tool
        steps = [
            PlanStep(
                description="Closing the issue",
                tool_name="close_issue",
                arguments={},
            ),
        ]
        
        planner = MockPlanner(steps=steps, default_finish="Mission complete")
        evaluator = SimpleMissionEvaluator(
            success_condition=lambda steps: len(steps) > 0,
        )
        
        # Create agent runtime
        agent = AgentRuntime(
            planner=planner,
            tools=mock_destructive_tool_registry,
            safety=safety,
            evaluator=evaluator,
        )
        
        # Execute mission
        context = ExecutionContext()
        outcome = agent.execute_mission(mission, context)
        
        # Verify the action was executed
        assert len(outcome.steps) == 1
        assert outcome.steps[0].result is not None
        assert outcome.steps[0].result.success is True
        
        # Verify approval was recorded
        decisions = gate.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].status == ApprovalStatus.APPROVED

    def test_approval_gate_rejects_destructive_action(
        self,
        mock_destructive_tool_registry: ToolRegistry,
    ) -> None:
        """Verify approval gate can reject destructive actions."""
        # Create mock gate that rejects
        gate = MockApprovalGate(default_response=ApprovalStatus.REJECTED)
        callback = create_approval_callback(gate)
        
        # Setup safety validator with approval callback
        safety = SafetyValidator(
            risk_overrides={"close_issue": ActionRisk.DESTRUCTIVE},
            approval_callback=callback,
        )
        
        # Create a simple mission
        mission = Mission(
            id="test-destructive",
            goal="Test destructive action rejection",
            max_steps=3,
            constraints=(),
            success_criteria=(),
            allowed_tools=("close_issue",),
        )
        
        # Create plan that executes the destructive tool
        steps = [
            PlanStep(
                description="Closing the issue",
                tool_name="close_issue",
                arguments={},
            ),
        ]
        
        planner = MockPlanner(steps=steps, default_finish="Mission complete")
        evaluator = SimpleMissionEvaluator(
            success_condition=lambda steps: len(steps) > 0,
        )
        
        # Create agent runtime
        agent = AgentRuntime(
            planner=planner,
            tools=mock_destructive_tool_registry,
            safety=safety,
            evaluator=evaluator,
        )
        
        # Execute mission
        context = ExecutionContext()
        outcome = agent.execute_mission(mission, context)
        
        # Verify the action was blocked
        assert len(outcome.steps) == 1
        assert outcome.steps[0].result is not None
        assert outcome.steps[0].result.success is False
        assert "rejected" in outcome.steps[0].result.error.lower()  # type: ignore[union-attr]
        
        # Verify rejection was recorded
        decisions = gate.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].status == ApprovalStatus.REJECTED

    def test_interactive_approval_gate_with_user_input(
        self,
        mock_destructive_tool_registry: ToolRegistry,
    ) -> None:
        """Verify interactive approval gate prompts for user input."""
        # Create interactive gate (not auto-approve)
        gate = ApprovalGate(auto_approve=False)
        callback = create_approval_callback(gate)
        
        # Setup safety validator with approval callback
        safety = SafetyValidator(
            risk_overrides={"close_issue": ActionRisk.DESTRUCTIVE},
            approval_callback=callback,
        )
        
        # Create a simple mission
        mission = Mission(
            id="test-interactive",
            goal="Test interactive approval",
            max_steps=3,
            constraints=(),
            success_criteria=(),
            allowed_tools=("close_issue",),
        )
        
        # Create plan that executes the destructive tool
        steps = [
            PlanStep(
                description="Closing the issue",
                tool_name="close_issue",
                arguments={},
            ),
        ]
        
        planner = MockPlanner(steps=steps, default_finish="Mission complete")
        evaluator = SimpleMissionEvaluator(
            success_condition=lambda steps: len(steps) > 0,
        )
        
        # Create agent runtime
        agent = AgentRuntime(
            planner=planner,
            tools=mock_destructive_tool_registry,
            safety=safety,
            evaluator=evaluator,
        )
        
        # Mock user input to approve
        with patch("builtins.input", return_value="yes"):
            context = ExecutionContext()
            outcome = agent.execute_mission(mission, context)
        
        # Verify the action was executed after approval
        assert len(outcome.steps) == 1
        assert outcome.steps[0].result is not None
        assert outcome.steps[0].result.success is True
        
        # Verify approval was recorded
        decisions = gate.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].status == ApprovalStatus.APPROVED
        assert decisions[0].approved_by == "interactive-user"
