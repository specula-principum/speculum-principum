"""Copilot integration helpers."""

from __future__ import annotations

from .accuracy import (
    AccuracyMetrics,
    AccuracyReport,
    AccuracyScenario,
    collect_kb_signatures,
    evaluate_accuracy,
    load_accuracy_scenario,
    render_accuracy_report,
)
from .client import (
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    CopilotClient,
    CopilotClientError,
    FunctionCall,
    ToolCall,
    Usage,
)
from .helpers import (
    ValidationReport,
    gather_kb_documents,
    generate_quality_report,
    prepare_kb_extraction_context,
    validate_kb_changes,
)

__all__ = [
    "AccuracyMetrics",
    "AccuracyReport",
    "AccuracyScenario",
    "ChatCompletionResponse",
    "ChatMessage",
    "Choice",
    "CopilotClient",
    "CopilotClientError",
    "FunctionCall",
    "ToolCall",
    "Usage",
    "collect_kb_signatures",
    "evaluate_accuracy",
    "load_accuracy_scenario",
    "render_accuracy_report",
    "ValidationReport",
    "gather_kb_documents",
    "generate_quality_report",
    "prepare_kb_extraction_context",
    "validate_kb_changes",
]
