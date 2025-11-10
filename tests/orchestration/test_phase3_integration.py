"""Integration tests for Phase 3 advanced reasoning capabilities."""

import tempfile
from pathlib import Path

import pytest

from src.orchestration.memory import MissionMemory
from src.orchestration.missions import load_mission
from src.orchestration.planner import Goal, HierarchicalPlan, PlanStep
from src.orchestration.tools import ActionRisk, ToolDefinition, ToolRegistry, ToolResult
from src.orchestration.types import AgentStep, MissionOutcome, MissionStatus, Thought, ThoughtType, ToolCall, ToolResult as TypesToolResult
from src.orchestration.uncertainty import UncertaintyDetector


@pytest.fixture
def mission_memory_db(tmp_path):
    """Provide a temporary mission memory database."""
    db_path = tmp_path / "test_memory.db"
    with MissionMemory(db_path) as memory:
        yield memory


@pytest.fixture
def simple_registry():
    """Provide a simple tool registry for testing."""
    registry = ToolRegistry()
    
    # Register a mock tool
    registry.register_tool(
        ToolDefinition(
            name="mock_tool",
            description="A mock tool for testing",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=lambda args: ToolResult(success=True, output="mock result"),
            risk_level=ActionRisk.SAFE,
        )
    )
    
    return registry


def test_memory_stores_and_retrieves_mission_outcomes(mission_memory_db):
    """Test that mission memory can store and retrieve execution outcomes."""
    # Create a mission outcome
    outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=[
            AgentStep(
                thought=Thought(
                    content="Analyze the situation",
                    type=ThoughtType.ACTION,
                    tool_call=ToolCall(name="analyze", arguments={"target": "issue"}),
                ),
                result=TypesToolResult(success=True, output="Analysis complete"),
            )
        ],
        summary="Successfully completed the mission",
    )
    
    # Record the outcome
    execution_id = mission_memory_db.record_execution(
        mission_id="test_mission_001",
        mission_goal="Test mission",
        outcome=outcome,
    )
    
    assert execution_id is not None
    
    # Find similar missions
    similar = mission_memory_db.find_similar("test_mission_001", limit=5)
    
    assert len(similar) >= 1
    assert similar[0].status == MissionStatus.SUCCEEDED
    assert similar[0].summary == "Successfully completed the mission"


def test_memory_extracts_patterns_from_successful_missions(mission_memory_db):
    """Test that memory can identify patterns in successful missions."""
    # Record multiple successful missions with same pattern and same mission_id
    for i in range(5):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=[
                AgentStep(
                    thought=Thought(
                        content=f"Step 1 - execution {i}",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="get_issue_details", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
                AgentStep(
                    thought=Thought(
                        content=f"Step 2 - execution {i}",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="add_label", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ],
        )
        # Use same mission_id for all executions to create a pattern
        mission_memory_db.record_execution("triage_issue", "Triage issue", outcome)
    
    # Extract patterns
    patterns = mission_memory_db.extract_patterns(min_occurrences=3)
    
    assert len(patterns) >= 1
    pattern = patterns[0]
    assert "get_issue_details" in pattern.tool_sequence
    assert "add_label" in pattern.tool_sequence
    assert pattern.occurrence_count >= 5
    assert pattern.success_rate == 1.0


def test_hierarchical_planner_executes_complex_plan():
    """Test that hierarchical planner can execute a multi-level plan."""
    # Create a hierarchical plan with 20+ steps
    root_goal = Goal(
        description="Complete comprehensive workflow",
        subgoals=(
            Goal(
                description="Phase 1: Validation",
                subgoals=(
                    Goal(
                        description="Validate input",
                        action=PlanStep(description="Check inputs", tool_name="validate", arguments={}),
                    ),
                    Goal(
                        description="Check prerequisites",
                        action=PlanStep(description="Verify setup", tool_name="check", arguments={}),
                    ),
                    Goal(
                        description="Initialize resources",
                        action=PlanStep(description="Setup", tool_name="init", arguments={}),
                    ),
                ),
            ),
            Goal(
                description="Phase 2: Processing",
                subgoals=(
                    Goal(
                        description="Process item 1",
                        action=PlanStep(description="Process 1", tool_name="process", arguments={"id": 1}),
                    ),
                    Goal(
                        description="Process item 2",
                        action=PlanStep(description="Process 2", tool_name="process", arguments={"id": 2}),
                    ),
                    Goal(
                        description="Process item 3",
                        action=PlanStep(description="Process 3", tool_name="process", arguments={"id": 3}),
                    ),
                ),
            ),
            Goal(
                description="Phase 3: Finalization",
                subgoals=(
                    Goal(
                        description="Generate report",
                        action=PlanStep(description="Create report", tool_name="report", arguments={}),
                    ),
                    Goal(
                        description="Cleanup",
                        action=PlanStep(description="Clean up", tool_name="cleanup", arguments={}),
                    ),
                ),
            ),
        ),
    )
    
    plan = HierarchicalPlan(root_goal=root_goal)
    
    # Convert to linear plan
    linear = plan.to_linear_plan()
    
    # Should have all leaf actions
    assert len(linear.steps) == 8
    
    # Verify order matches hierarchical structure
    assert linear.steps[0].tool_name == "validate"
    assert linear.steps[1].tool_name == "check"
    assert linear.steps[2].tool_name == "init"
    assert linear.steps[3].tool_name == "process"
    assert linear.steps[4].tool_name == "process"
    assert linear.steps[5].tool_name == "process"
    assert linear.steps[6].tool_name == "report"
    assert linear.steps[7].tool_name == "cleanup"


def test_uncertainty_detector_identifies_low_confidence_scenarios():
    """Test that uncertainty detector correctly identifies low-confidence situations."""
    detector = UncertaintyDetector(escalation_threshold=0.6)
    
    # High confidence thought
    confident_thought = Thought(
        content="I will fetch the issue details to analyze the request",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="get_issue_details", arguments={"issue_number": 123}),
    )
    
    assessment = detector.assess_confidence(confident_thought)
    assert assessment.level.value in ("high", "medium")
    assert not assessment.should_escalate
    
    # Low confidence thought with uncertainty
    uncertain_thought = Thought(
        content="Maybe I should try to do something but I'm not sure what",
        type=ThoughtType.ACTION,
        tool_call=None,
    )
    
    assessment = detector.assess_confidence(uncertain_thought)
    assert assessment.level.value == "low"
    assert assessment.should_escalate
    assert assessment.score < 0.6


def test_uncertainty_detector_escalates_after_repeated_failures():
    """Test that uncertainty detector escalates when seeing repeated failures."""
    detector = UncertaintyDetector(escalation_threshold=0.6)
    
    thought = Thought(
        content="Try the same approach again",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="test_tool", arguments={"retry": True}),
    )
    
    # Context with multiple failures
    context = {
        "recent_steps": [
            AgentStep(
                thought=Thought(content="Attempt 1", type=ThoughtType.ACTION),
                result=ToolResult(success=False, error="Failed"),
            ),
            AgentStep(
                thought=Thought(content="Attempt 2", type=ThoughtType.ACTION),
                result=ToolResult(success=False, error="Failed again"),
            ),
        ]
    }
    
    assessment = detector.assess_confidence(thought, context=context)
    
    assert assessment.should_escalate
    assert "failures" in assessment.reasoning.lower()


def test_load_complex_mission_definition():
    """Test loading a complex mission definition from YAML."""
    mission_path = Path("/home/ubuntu/speculum-principum/config/missions/workflows/kb_extraction_comprehensive.yaml")
    
    if mission_path.exists():
        mission = load_mission(mission_path)
        
        assert mission.id == "kb_extraction_comprehensive"
        assert mission.max_steps == 30
        assert mission.allowed_tools is not None and len(mission.allowed_tools) > 10
        assert not mission.requires_approval
        assert "Phase 1" in mission.goal
        assert "Phase 2" in mission.goal
        assert len(mission.success_criteria) >= 5


def test_integration_memory_and_uncertainty():
    """Test integration between memory and uncertainty detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "integration.db"
        with MissionMemory(db_path) as memory:
            # Record a failed mission
            failed_outcome = MissionOutcome(
                status=MissionStatus.FAILED,
                steps=(
                    AgentStep(
                        thought=Thought(content="Failed attempt", type=ThoughtType.ACTION),
                        result=ToolResult(success=False, error="Error occurred"),
                    ),
                ),
                summary="Mission failed",
            )
            
            memory.record_execution("test_mission", "Test goal", failed_outcome)
            
            # Record successful missions
            for i in range(3):
                success_outcome = MissionOutcome(
                    status=MissionStatus.SUCCEEDED,
                    steps=(
                        AgentStep(
                            thought=Thought(
                                content=f"Success {i}",
                                type=ThoughtType.ACTION,
                                tool_call=ToolCall(name="success_tool", arguments={}),
                            ),
                            result=ToolResult(success=True),
                        ),
                    ),
                )
                memory.record_execution("test_mission", "Test goal", success_outcome)
            
            # Get statistics
            stats = memory.get_statistics()
            
            # Should have 4 total executions (1 failed, 3 succeeded)
            assert stats["total_executions"] == 4
            assert stats["success_rate"] == 0.75
            
            # Extract patterns - should only find pattern from successful ones
            patterns = memory.extract_patterns(min_occurrences=2)
            assert len(patterns) >= 1


def test_hierarchical_plan_validation_integration():
    """Test that hierarchical plan validation works with tool registry."""
    from src.orchestration.toolkit.github import register_github_read_only_tools
    
    registry = ToolRegistry()
    register_github_read_only_tools(registry)
    
    available_tools = {tool.name for tool in registry}
    
    # Create a plan that uses real tools
    plan = HierarchicalPlan(
        root_goal=Goal(
            description="Triage workflow",
            subgoals=(
                Goal(
                    description="Get issue",
                    action=PlanStep(
                        description="Fetch issue details",
                        tool_name="get_issue_details",
                        arguments={"issue_number": 123},
                    ),
                ),
                Goal(
                    description="Search similar",
                    action=PlanStep(
                        description="Find similar issues",
                        tool_name="search_issues_by_label",
                        arguments={"label": "bug"},
                    ),
                ),
            ),
        )
    )
    
    # Validate against available tools
    issues = plan.validate(available_tools=available_tools)
    
    # Should have no errors since tools exist
    errors = [issue for issue in issues if issue.severity.value == "error"]
    assert len(errors) == 0


def test_complex_mission_workflow_simulation():
    """Test simulating a complex mission workflow with all Phase 3 components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "workflow.db"
        with MissionMemory(db_path) as memory:
            detector = UncertaintyDetector(escalation_threshold=0.6)
            
            # Simulate a multi-step workflow
            steps = []
            
            # Step 1: Validation (high confidence)
            thought1 = Thought(
                content="Validate the input parameters are complete",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(name="validate_input", arguments={"data": "test"}),
            )
            confidence1 = detector.assess_confidence(thought1)
            assert not confidence1.should_escalate
            
            steps.append(
                AgentStep(
                    thought=thought1,
                    result=ToolResult(success=True, output={"valid": True}),
                )
            )
            
            # Step 2: Processing (high confidence)
            thought2 = Thought(
                content="Process the validated data",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(name="process_data", arguments={"id": 1}),
            )
            confidence2 = detector.assess_confidence(thought2, context={"recent_steps": steps})
            assert not confidence2.should_escalate
            
            steps.append(
                AgentStep(
                    thought=thought2,
                    result=ToolResult(success=True, output={"processed": True}),
                )
            )
            
            # Step 3: Uncertain scenario
            thought3 = Thought(
                content="Maybe I should validate again but I'm not sure",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(name="validate", arguments={}),
            )
            confidence3 = detector.assess_confidence(thought3, context={"recent_steps": steps})
            
            # Should detect uncertainty and recommend escalation
            assert confidence3.should_escalate
            assert confidence3.score < 0.6
            
            # If we proceeded anyway and it succeeded
            steps.append(
                AgentStep(
                    thought=thought3,
                    result=ToolResult(success=True, output={"ok": True}),
                )
            )
            
            # Record the mission outcome
            outcome = MissionOutcome(
                status=MissionStatus.SUCCEEDED,
                steps=tuple(steps),
                summary="Completed with one uncertainty escalation",
            )
            
            memory.record_execution(
                mission_id="complex_workflow",
                mission_goal="Multi-step workflow with uncertainty handling",
                outcome=outcome,
            )
            
            # Verify it was recorded
            similar = memory.find_similar("complex_workflow")
            assert len(similar) == 1
            assert similar[0].status == MissionStatus.SUCCEEDED
            assert len(similar[0].steps) == 3
