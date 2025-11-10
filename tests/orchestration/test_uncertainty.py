"""Tests for uncertainty detection and confidence assessment."""

import pytest

from src.orchestration.uncertainty import (
    ConfidenceAssessment,
    ConfidenceLevel,
    UncertaintyDetector,
)
from src.orchestration.types import AgentStep, Thought, ThoughtType, ToolCall, ToolResult


@pytest.fixture
def detector():
    """Provide a default uncertainty detector."""
    return UncertaintyDetector()


def test_uncertainty_detector_initialization():
    """Test that detector initializes with valid parameters."""
    detector = UncertaintyDetector(escalation_threshold=0.6)
    assert detector.get_escalation_threshold() == 0.6


def test_uncertainty_detector_invalid_threshold():
    """Test that invalid threshold raises error."""
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        UncertaintyDetector(escalation_threshold=1.5)

    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        UncertaintyDetector(escalation_threshold=-0.1)


def test_assess_confidence_high_for_clear_action(detector):
    """Test that clear, confident thoughts score high."""
    thought = Thought(
        content="Fetch the issue details from GitHub to analyze the request",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="get_issue_details", arguments={"issue_number": 123}),
    )

    assessment = detector.assess_confidence(thought)

    assert assessment.score >= 0.8
    assert assessment.level == ConfidenceLevel.HIGH
    assert not assessment.should_escalate


def test_assess_confidence_low_for_uncertain_language(detector):
    """Test that thoughts with uncertainty markers score low."""
    thought = Thought(
        content="Maybe I should try to fetch the issue, but I'm not sure",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="get_issue_details", arguments={"issue_number": 123}),
    )

    assessment = detector.assess_confidence(thought)

    assert assessment.score < 0.8
    assert "uncertainty markers" in assessment.reasoning


def test_assess_confidence_low_for_action_without_tool_call(detector):
    """Test that action thoughts without tool calls score very low."""
    thought = Thought(
        content="I should do something but don't know what",
        type=ThoughtType.ACTION,
        tool_call=None,  # Missing tool call
    )

    assessment = detector.assess_confidence(thought)

    assert assessment.score < 0.5
    assert assessment.level == ConfidenceLevel.LOW
    assert assessment.should_escalate
    assert "lacks tool call" in assessment.reasoning


def test_assess_confidence_considers_recent_failures(detector):
    """Test that recent execution failures reduce confidence."""
    thought = Thought(
        content="Try again with the same approach",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="test_tool", arguments={}),
    )

    # Context with multiple recent failures
    context = {
        "recent_steps": [
            AgentStep(
                thought=Thought(content="Step 1", type=ThoughtType.ACTION),
                result=ToolResult(success=False, error="Failed"),
            ),
            AgentStep(
                thought=Thought(content="Step 2", type=ThoughtType.ACTION),
                result=ToolResult(success=False, error="Failed again"),
            ),
        ]
    }

    assessment = detector.assess_confidence(thought, context=context)

    assert assessment.score < 0.8
    assert "recent failures" in assessment.reasoning


def test_assess_confidence_low_for_missing_arguments(detector):
    """Test that tool calls without arguments reduce confidence."""
    thought = Thought(
        content="Call the tool",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="test_tool", arguments={}),  # Empty arguments
    )

    assessment = detector.assess_confidence(thought)

    assert assessment.score < 1.0
    assert "no arguments" in assessment.reasoning


def test_assess_confidence_low_for_brief_reasoning(detector):
    """Test that very brief thoughts reduce confidence."""
    thought = Thought(
        content="Do it",  # Very short
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="test_tool", arguments={"key": "value"}),
    )

    assessment = detector.assess_confidence(thought)

    assert assessment.score < 1.0
    assert "brief reasoning" in assessment.reasoning


def test_should_escalate_threshold(detector):
    """Test escalation threshold decision."""
    assert detector.should_escalate(0.3)  # Below default 0.5
    assert not detector.should_escalate(0.7)  # Above default 0.5


def test_custom_escalation_threshold():
    """Test that custom threshold affects escalation decisions."""
    detector = UncertaintyDetector(escalation_threshold=0.7)

    assert detector.should_escalate(0.6)  # Below 0.7
    assert not detector.should_escalate(0.8)  # Above 0.7


def test_analyze_execution_pattern_empty():
    """Test pattern analysis with no steps."""
    detector = UncertaintyDetector()
    analysis = detector.analyze_execution_pattern([])

    assert analysis["total_steps"] == 0
    assert analysis["failure_rate"] == 0.0
    assert len(analysis["concerns"]) == 0


def test_analyze_execution_pattern_high_failure_rate():
    """Test pattern analysis detects high failure rate."""
    detector = UncertaintyDetector()

    steps = [
        AgentStep(
            thought=Thought(content=f"Step {i}", type=ThoughtType.ACTION),
            result=ToolResult(success=(i % 2 == 0), error=None if i % 2 == 0 else "Failed"),
        )
        for i in range(10)
    ]

    analysis = detector.analyze_execution_pattern(steps)

    assert analysis["total_steps"] == 10
    assert analysis["failure_rate"] == 0.5
    assert any("failure rate" in concern.lower() for concern in analysis["concerns"])


def test_analyze_execution_pattern_repeated_tool():
    """Test pattern analysis detects repeated tool usage (possible loop)."""
    detector = UncertaintyDetector()

    steps = [
        AgentStep(
            thought=Thought(
                content=f"Call same tool {i}",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(name="same_tool", arguments={}),
            ),
            result=ToolResult(success=True),
        )
        for i in range(5)
    ]

    analysis = detector.analyze_execution_pattern(steps)

    assert analysis["repeated_tools"]["same_tool"] == 5
    assert any("same_tool" in concern for concern in analysis["concerns"])
    assert any("possible loop" in concern for concern in analysis["concerns"])


def test_analyze_execution_pattern_alternating_tools():
    """Test pattern analysis detects alternating tool pattern."""
    detector = UncertaintyDetector()

    steps = [
        AgentStep(
            thought=Thought(
                content=f"Step {i}",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(name="tool_a" if i % 2 == 0 else "tool_b", arguments={}),
            ),
            result=ToolResult(success=True),
        )
        for i in range(4)
    ]

    analysis = detector.analyze_execution_pattern(steps)

    assert any("alternating" in concern.lower() for concern in analysis["concerns"])


def test_generate_escalation_question_basic():
    """Test generating escalation question for basic thought."""
    detector = UncertaintyDetector()

    thought = Thought(
        content="I'm not sure what to do here",
        type=ThoughtType.ACTION,
        tool_call=None,
    )

    confidence = ConfidenceAssessment(
        score=0.3,
        level=ConfidenceLevel.LOW,
        reasoning="Action thought lacks tool call",
        should_escalate=True,
    )

    question = detector.generate_escalation_question(thought, confidence)

    assert "low confidence" in question.lower()
    assert "0.30" in question
    assert thought.content in question
    assert "Should I proceed" in question


def test_generate_escalation_question_with_tool():
    """Test generating escalation question with tool call details."""
    detector = UncertaintyDetector()

    thought = Thought(
        content="Maybe use this tool?",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="test_tool", arguments={"key": "value"}),
    )

    confidence = ConfidenceAssessment(
        score=0.4,
        level=ConfidenceLevel.LOW,
        reasoning="Uncertain language",
        should_escalate=True,
    )

    question = detector.generate_escalation_question(thought, confidence)

    assert "test_tool" in question
    assert "key" in question
    assert "value" in question


def test_set_escalation_threshold():
    """Test updating escalation threshold."""
    detector = UncertaintyDetector(escalation_threshold=0.5)

    detector.set_escalation_threshold(0.7)
    assert detector.get_escalation_threshold() == 0.7

    # Should now escalate at higher threshold
    assert detector.should_escalate(0.6)


def test_set_invalid_escalation_threshold():
    """Test that setting invalid threshold raises error."""
    detector = UncertaintyDetector()

    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        detector.set_escalation_threshold(1.5)


def test_confidence_level_enum():
    """Test confidence level enum values."""
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"


def test_confidence_assessment_dataclass():
    """Test confidence assessment structure."""
    assessment = ConfidenceAssessment(
        score=0.75,
        level=ConfidenceLevel.MEDIUM,
        reasoning="Some concern",
        should_escalate=False,
    )

    assert assessment.score == 0.75
    assert assessment.level == ConfidenceLevel.MEDIUM
    assert assessment.reasoning == "Some concern"
    assert not assessment.should_escalate


def test_multiple_uncertainty_factors():
    """Test that multiple uncertainty factors compound correctly."""
    detector = UncertaintyDetector()

    thought = Thought(
        content="Maybe",  # Brief + uncertain language
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="tool", arguments={}),  # No arguments
    )

    assessment = detector.assess_confidence(thought)

    # Multiple factors should significantly reduce confidence
    assert assessment.score < 0.5
    assert assessment.should_escalate
    # Check that multiple reasons are captured
    assert "uncertainty markers" in assessment.reasoning
    assert ("brief reasoning" in assessment.reasoning or "no arguments" in assessment.reasoning)


def test_detector_without_error_escalation():
    """Test detector with error escalation disabled."""
    detector = UncertaintyDetector(require_escalation_on_errors=False)

    thought = Thought(
        content="Try again",
        type=ThoughtType.ACTION,
        tool_call=ToolCall(name="tool", arguments={"key": "value"}),
    )

    context = {
        "recent_steps": [
            AgentStep(
                thought=Thought(content="Failed", type=ThoughtType.ACTION),
                result=ToolResult(success=False, error="Error"),
            )
            for _ in range(3)
        ]
    }

    assessment = detector.assess_confidence(thought, context=context)

    # Failures should not affect confidence when error escalation is disabled
    # (though other factors might still reduce it)
    assert "recent failures" not in assessment.reasoning


def test_finish_thought_high_confidence(detector):
    """Test that finish thoughts with clear content score high."""
    thought = Thought(
        content="Successfully completed the task. All objectives met.",
        type=ThoughtType.FINISH,
        tool_call=None,  # Finish thoughts don't need tool calls
    )

    assessment = detector.assess_confidence(thought)

    # Finish thoughts without tool calls shouldn't be penalized
    assert assessment.level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
