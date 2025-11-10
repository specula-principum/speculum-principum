"""Uncertainty detection and confidence assessment for the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .types import AgentStep, Thought, ThoughtType


class ConfidenceLevel(Enum):
    """Confidence level categories for agent reasoning."""

    HIGH = "high"  # Confidence >= 0.8
    MEDIUM = "medium"  # Confidence >= 0.5
    LOW = "low"  # Confidence < 0.5


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Result of confidence assessment for a thought or decision."""

    score: float  # 0.0 to 1.0
    level: ConfidenceLevel
    reasoning: str
    should_escalate: bool


class UncertaintyDetector:
    """Identifies when agent needs human guidance based on confidence scoring."""

    def __init__(
        self,
        *,
        escalation_threshold: float = 0.5,
        require_escalation_on_errors: bool = True,
    ) -> None:
        """Initialize uncertainty detector with configuration.

        Args:
            escalation_threshold: Confidence score below which to escalate (0.0-1.0)
            require_escalation_on_errors: Whether repeated errors should trigger escalation
        """
        if not 0.0 <= escalation_threshold <= 1.0:
            raise ValueError("Escalation threshold must be between 0.0 and 1.0")

        self._escalation_threshold = escalation_threshold
        self._require_escalation_on_errors = require_escalation_on_errors

    def assess_confidence(self, thought: Thought, context: dict[str, Any] | None = None) -> ConfidenceAssessment:
        """Score confidence in the current reasoning step.

        Args:
            thought: The thought to assess
            context: Additional context (execution history, tool results, etc.)

        Returns:
            Confidence assessment with score and escalation recommendation
        """
        context = context or {}

        # Base confidence score
        score = 1.0
        reasons: list[str] = []

        # Factor 1: Check if thought has clear action
        if thought.type == ThoughtType.ACTION and thought.tool_call is None:
            score *= 0.3
            reasons.append("Action thought lacks tool call")

        # Factor 2: Check for vague or uncertain language
        uncertainty_markers = [
            "maybe",
            "possibly",
            "might",
            "unsure",
            "not sure",
            "unclear",
            "don't know",
            "uncertain",
            "perhaps",
        ]
        content_lower = thought.content.lower()
        if any(marker in content_lower for marker in uncertainty_markers):
            score *= 0.6
            reasons.append("Thought contains uncertainty markers")

        # Factor 3: Check execution history for repeated failures
        if self._require_escalation_on_errors:
            recent_steps = context.get("recent_steps", [])
            if isinstance(recent_steps, list):
                recent_failures = sum(
                    1
                    for step in recent_steps[-3:]
                    if isinstance(step, AgentStep) and step.result and not step.result.success
                )
                if recent_failures >= 2:
                    score *= 0.4
                    reasons.append(f"Multiple recent failures ({recent_failures})")

        # Factor 4: Missing tool arguments
        if thought.tool_call and not thought.tool_call.arguments:
            score *= 0.7
            reasons.append("Tool call has no arguments")

        # Factor 5: Very short thought content (may indicate confusion)
        if len(thought.content.strip()) < 10:
            score *= 0.8
            reasons.append("Very brief reasoning")

        # Determine confidence level
        if score >= 0.8:
            level = ConfidenceLevel.HIGH
        elif score >= 0.5:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        # Decide if escalation is needed
        should_escalate = score < self._escalation_threshold

        reasoning = "; ".join(reasons) if reasons else "No concerns detected"

        return ConfidenceAssessment(
            score=score,
            level=level,
            reasoning=reasoning,
            should_escalate=should_escalate,
        )

    def should_escalate(self, confidence: float) -> bool:
        """Determine if confidence score requires human escalation.

        Args:
            confidence: Confidence score between 0.0 and 1.0

        Returns:
            True if score is below escalation threshold
        """
        return confidence < self._escalation_threshold

    def analyze_execution_pattern(self, steps: list[AgentStep]) -> dict[str, Any]:
        """Analyze patterns in execution history that might indicate uncertainty.

        Args:
            steps: List of agent steps to analyze

        Returns:
            Dictionary with pattern analysis results
        """
        if not steps:
            return {
                "total_steps": 0,
                "failure_rate": 0.0,
                "repeated_tools": {},
                "concerns": [],
            }

        total_steps = len(steps)
        failures = sum(1 for step in steps if step.result and not step.result.success)
        failure_rate = failures / total_steps if total_steps > 0 else 0.0

        # Track repeated tool usage (might indicate stuck in loop)
        tool_counts: dict[str, int] = {}
        for step in steps:
            if step.thought.tool_call:
                tool_name = step.thought.tool_call.name
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # Identify concerns
        concerns: list[str] = []
        if failure_rate >= 0.5:
            concerns.append(f"High failure rate: {failure_rate:.1%}")

        for tool_name, count in tool_counts.items():
            if count >= 3:
                concerns.append(f"Tool '{tool_name}' used {count} times (possible loop)")

        # Check for alternating tools (another loop indicator)
        if len(steps) >= 4:
            last_tools = [
                step.thought.tool_call.name
                for step in steps[-4:]
                if step.thought.tool_call
            ]
            if len(last_tools) >= 4 and len(set(last_tools)) == 2:
                concerns.append("Alternating tool pattern detected (possible loop)")

        return {
            "total_steps": total_steps,
            "failure_rate": failure_rate,
            "repeated_tools": tool_counts,
            "concerns": concerns,
        }

    def generate_escalation_question(
        self, thought: Thought, confidence: ConfidenceAssessment
    ) -> str:
        """Generate a specific question to ask human for guidance.

        Args:
            thought: The thought with low confidence
            confidence: Assessment explaining why confidence is low

        Returns:
            Well-formed question for human guidance
        """
        question_parts = [
            f"I have low confidence ({confidence.score:.2f}) in my current reasoning.",
            f"Reason: {confidence.reasoning}",
            "",
            f"My current thought is: {thought.content}",
            "",
        ]

        if thought.tool_call:
            question_parts.append(f"I was planning to use tool: {thought.tool_call.name}")
            if thought.tool_call.arguments:
                question_parts.append(f"With arguments: {thought.tool_call.arguments}")
            question_parts.append("")

        question_parts.extend(
            [
                "Questions for guidance:",
                "1. Should I proceed with this action?",
                "2. Is there a better approach I should consider?",
                "3. What additional information would help me decide?",
            ]
        )

        return "\n".join(question_parts)

    def get_escalation_threshold(self) -> float:
        """Return the current escalation threshold."""
        return self._escalation_threshold

    def set_escalation_threshold(self, threshold: float) -> None:
        """Update the escalation threshold.

        Args:
            threshold: New threshold between 0.0 and 1.0
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Escalation threshold must be between 0.0 and 1.0")
        self._escalation_threshold = threshold
