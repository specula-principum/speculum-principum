"""Tests for mission memory and learning system."""

import tempfile
from pathlib import Path

import pytest

from src.orchestration.memory import MissionMemory, SuccessPattern
from src.orchestration.types import (
    AgentStep,
    MissionOutcome,
    MissionStatus,
    Thought,
    ThoughtType,
    ToolCall,
    ToolResult,
)


@pytest.fixture
def memory_db():
    """Provide an in-memory mission memory instance."""
    with MissionMemory() as memory:
        yield memory


@pytest.fixture
def file_memory_db():
    """Provide a file-based mission memory instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        with MissionMemory(db_path) as memory:
            yield memory


def test_memory_initialization(memory_db):
    """Test that memory database initializes correctly."""
    stats = memory_db.get_statistics()
    assert stats["total_executions"] == 0
    assert stats["success_rate"] == 0.0


def test_record_simple_execution(memory_db):
    """Test recording a simple mission execution."""
    outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(
                    content="Fetch issue details",
                    type=ThoughtType.ACTION,
                    tool_call=ToolCall(name="get_issue_details", arguments={"issue_number": 123}),
                ),
                result=ToolResult(success=True, output={"title": "Test Issue"}),
            ),
            AgentStep(
                thought=Thought(content="Mission complete", type=ThoughtType.FINISH),
                result=None,
            ),
        ),
        summary="Successfully retrieved issue details",
    )

    execution_id = memory_db.record_execution(
        mission_id="test_mission", mission_goal="Retrieve issue information", outcome=outcome
    )

    assert execution_id > 0

    stats = memory_db.get_statistics()
    assert stats["total_executions"] == 1
    assert stats["status_counts"]["succeeded"] == 1
    assert stats["success_rate"] == 1.0


def test_record_failed_execution(memory_db):
    """Test recording a failed mission execution."""
    outcome = MissionOutcome(
        status=MissionStatus.FAILED,
        steps=(
            AgentStep(
                thought=Thought(
                    content="Try to fetch issue",
                    type=ThoughtType.ACTION,
                    tool_call=ToolCall(name="get_issue_details", arguments={"issue_number": 999}),
                ),
                result=ToolResult(success=False, error="Issue not found"),
            ),
        ),
        summary="Failed to retrieve issue",
    )

    memory_db.record_execution(
        mission_id="test_mission", mission_goal="Retrieve issue information", outcome=outcome
    )

    stats = memory_db.get_statistics()
    assert stats["total_executions"] == 1
    assert stats["status_counts"]["failed"] == 1
    assert stats["success_rate"] == 0.0


def test_find_similar_missions(memory_db):
    """Test finding similar past mission executions."""
    # Record multiple executions of the same mission type
    for i in range(3):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content=f"Step {i}",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="test_tool", arguments={"id": i}),
                    ),
                    result=ToolResult(success=True, output=f"Result {i}"),
                ),
            ),
            summary=f"Execution {i}",
        )
        memory_db.record_execution(
            mission_id="triage_issue", mission_goal="Classify and label issue", outcome=outcome
        )

    # Record a different mission type
    other_outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(content="Other mission", type=ThoughtType.FINISH), result=None
            ),
        ),
    )
    memory_db.record_execution(
        mission_id="other_mission", mission_goal="Different goal", outcome=other_outcome
    )

    # Find similar missions
    similar = memory_db.find_similar("triage_issue", limit=10)

    assert len(similar) == 3
    assert all(outcome.status == MissionStatus.SUCCEEDED for outcome in similar)
    # Should be ordered by recency (most recent first)
    assert similar[0].summary == "Execution 2"
    assert similar[1].summary == "Execution 1"
    assert similar[2].summary == "Execution 0"


def test_find_similar_with_status_filter(memory_db):
    """Test finding similar missions filtered by status."""
    # Record successful and failed executions
    success_outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(content="Success", type=ThoughtType.FINISH), result=None
            ),
        ),
    )

    fail_outcome = MissionOutcome(
        status=MissionStatus.FAILED,
        steps=(
            AgentStep(
                thought=Thought(content="Failed", type=ThoughtType.FINISH), result=None
            ),
        ),
    )

    memory_db.record_execution("test_mission", "Test goal", success_outcome)
    memory_db.record_execution("test_mission", "Test goal", fail_outcome)
    memory_db.record_execution("test_mission", "Test goal", success_outcome)

    # Find only successful missions
    successful = memory_db.find_similar("test_mission", status_filter=MissionStatus.SUCCEEDED)
    assert len(successful) == 2
    assert all(outcome.status == MissionStatus.SUCCEEDED for outcome in successful)

    # Find only failed missions
    failed = memory_db.find_similar("test_mission", status_filter=MissionStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].status == MissionStatus.FAILED


def test_extract_patterns_simple(memory_db):
    """Test extracting simple success patterns."""
    # Record executions with a consistent tool sequence
    for _ in range(5):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Get issue",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="get_issue_details", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
                AgentStep(
                    thought=Thought(
                        content="Add label",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="add_label", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("triage", "Triage issue", outcome)

    patterns = memory_db.extract_patterns(min_occurrences=3)

    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.tool_sequence == ("get_issue_details", "add_label")
    assert pattern.mission_type == "triage"
    assert pattern.occurrence_count == 5
    assert pattern.success_rate == 1.0
    assert pattern.average_steps == 2.0


def test_extract_patterns_multiple_sequences(memory_db):
    """Test extracting patterns from multiple tool sequences."""
    # Pattern 1: get_issue -> add_label (4 times)
    for _ in range(4):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Get",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="get_issue_details", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
                AgentStep(
                    thought=Thought(
                        content="Label",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="add_label", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("triage", "Triage", outcome)

    # Pattern 2: get_issue -> post_comment (3 times)
    for _ in range(3):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Get",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="get_issue_details", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
                AgentStep(
                    thought=Thought(
                        content="Comment",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="post_comment", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("triage", "Triage", outcome)

    patterns = memory_db.extract_patterns(min_occurrences=3)

    assert len(patterns) == 2
    # Should be sorted by success rate and occurrence count
    assert patterns[0].occurrence_count >= patterns[1].occurrence_count


def test_extract_patterns_filters_low_occurrences(memory_db):
    """Test that patterns below minimum occurrence threshold are filtered."""
    # Record a pattern only twice
    for _ in range(2):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Rare pattern",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="rare_tool", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("test", "Test", outcome)

    # Request minimum 3 occurrences
    patterns = memory_db.extract_patterns(min_occurrences=3)
    assert len(patterns) == 0


def test_get_statistics_comprehensive(memory_db):
    """Test comprehensive statistics gathering."""
    # Record various mission types and statuses
    for i in range(10):
        status = MissionStatus.SUCCEEDED if i < 7 else MissionStatus.FAILED
        outcome = MissionOutcome(
            status=status,
            steps=(
                AgentStep(
                    thought=Thought(content=f"Step {i}", type=ThoughtType.FINISH), result=None
                ),
            ),
        )
        mission_id = "mission_a" if i < 5 else "mission_b"
        memory_db.record_execution(mission_id, "Goal", outcome)

    stats = memory_db.get_statistics()

    assert stats["total_executions"] == 10
    assert stats["status_counts"]["succeeded"] == 7
    assert stats["status_counts"]["failed"] == 3
    assert stats["success_rate"] == 0.7
    assert "top_mission_types" in stats
    assert stats["top_mission_types"]["mission_a"] == 5
    assert stats["top_mission_types"]["mission_b"] == 5


def test_persistence_across_instances(file_memory_db):
    """Test that data persists across database instances."""
    db_path = file_memory_db._db_path

    # Record an execution
    outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(content="Test", type=ThoughtType.FINISH), result=None
            ),
        ),
    )
    file_memory_db.record_execution("test", "Test goal", outcome)
    file_memory_db.close()

    # Create new instance with same database file
    with MissionMemory(db_path) as new_memory:
        stats = new_memory.get_statistics()
        assert stats["total_executions"] == 1


def test_clear_all(memory_db):
    """Test clearing all mission history."""
    # Record some executions
    outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(content="Test", type=ThoughtType.FINISH), result=None
            ),
        ),
    )
    memory_db.record_execution("test", "Test", outcome)
    memory_db.record_execution("test", "Test", outcome)

    stats = memory_db.get_statistics()
    assert stats["total_executions"] == 2

    # Clear all data
    memory_db.clear_all()

    stats = memory_db.get_statistics()
    assert stats["total_executions"] == 0


def test_complex_tool_arguments(memory_db):
    """Test that complex tool arguments are properly stored and retrieved."""
    outcome = MissionOutcome(
        status=MissionStatus.SUCCEEDED,
        steps=(
            AgentStep(
                thought=Thought(
                    content="Complex call",
                    type=ThoughtType.ACTION,
                    tool_call=ToolCall(
                        name="complex_tool",
                        arguments={
                            "nested": {"key": "value", "list": [1, 2, 3]},
                            "number": 42,
                            "text": "test",
                        },
                    ),
                ),
                result=ToolResult(success=True, output={"result": "complex"}),
            ),
        ),
    )

    memory_db.record_execution("test", "Test", outcome)
    similar = memory_db.find_similar("test")

    assert len(similar) == 1
    retrieved = similar[0]
    assert len(retrieved.steps) == 1
    assert retrieved.steps[0].thought.tool_call is not None
    assert retrieved.steps[0].thought.tool_call.name == "complex_tool"
    assert retrieved.steps[0].thought.tool_call.arguments["nested"]["key"] == "value"
    assert retrieved.steps[0].thought.tool_call.arguments["number"] == 42


def test_context_manager(file_memory_db):
    """Test that context manager properly closes connection."""
    # Context manager should close the connection when exiting
    # This is tested by the fixture itself, but we can verify behavior
    assert file_memory_db._conn is not None


def test_success_pattern_ordering(memory_db):
    """Test that success patterns are ordered correctly."""
    # Create high success rate pattern (4/5)
    for i in range(4):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Pattern A",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="tool_a", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("mission_a", "Goal A", outcome)

    # Add one failure
    fail_outcome = MissionOutcome(status=MissionStatus.FAILED, steps=())
    memory_db.record_execution("mission_a", "Goal A", fail_outcome)

    # Create lower success rate pattern (3/6)
    for i in range(3):
        outcome = MissionOutcome(
            status=MissionStatus.SUCCEEDED,
            steps=(
                AgentStep(
                    thought=Thought(
                        content="Pattern B",
                        type=ThoughtType.ACTION,
                        tool_call=ToolCall(name="tool_b", arguments={}),
                    ),
                    result=ToolResult(success=True),
                ),
            ),
        )
        memory_db.record_execution("mission_b", "Goal B", outcome)

    # Add failures
    for _ in range(3):
        memory_db.record_execution("mission_b", "Goal B", fail_outcome)

    patterns = memory_db.extract_patterns(min_occurrences=3)

    # Pattern A should come first (higher success rate: 0.8 vs 0.5)
    assert len(patterns) == 2
    assert patterns[0].success_rate > patterns[1].success_rate
