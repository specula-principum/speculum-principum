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
    gather_kb_documents,
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
    "gather_kb_documents",
]
