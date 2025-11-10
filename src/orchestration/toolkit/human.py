"""Human interaction tools for the orchestration runtime."""

from __future__ import annotations

import sys
from typing import Any, Mapping

from ..safety import ActionRisk
from ..tools import ToolDefinition, ToolRegistry
from ..types import ToolResult


def register_human_interaction_tools(registry: ToolRegistry) -> None:
    """Register tools for human guidance and interaction."""

    registry.register_tool(
        ToolDefinition(
            name="request_human_guidance",
            description=(
                "Ask a human operator for guidance when uncertain about how to proceed. "
                "Use this when confidence is low or when encountering ambiguous situations "
                "that require human judgment."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "minLength": 10,
                        "description": (
                            "Specific question or situation requiring human guidance. "
                            "Should clearly explain the uncertainty and what help is needed."
                        ),
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context information to help human understand the situation.",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of possible approaches being considered.",
                    },
                },
                "required": ["question"],
                "additionalProperties": False,
            },
            handler=_request_human_guidance_handler,
            risk_level=ActionRisk.SAFE,  # Asking for help is always safe
        )
    )


def _request_human_guidance_handler(arguments: Mapping[str, Any]) -> ToolResult:
    """Handle request for human guidance.

    In interactive mode, prompts the human and waits for response.
    In non-interactive mode, returns a default escalation message.
    """
    question = arguments["question"]
    context = arguments.get("context", {})
    options = arguments.get("options", [])

    # Check if running in interactive mode (TTY available)
    is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if not is_interactive:
        # Non-interactive mode: return escalation message
        return ToolResult(
            success=True,
            output={
                "response": "Human guidance required - agent paused for manual review",
                "question": question,
                "context": context,
                "options": options,
                "mode": "non-interactive",
            },
        )

    # Interactive mode: prompt for human input
    print("\n" + "=" * 70)
    print("AGENT REQUESTING HUMAN GUIDANCE")
    print("=" * 70)
    print(f"\n{question}\n")

    if context:
        print("Context:")
        for key, value in context.items():
            print(f"  {key}: {value}")
        print()

    if options:
        print("Possible options:")
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print()

    print("Please provide guidance (or type 'skip' to let agent proceed):")
    print("-" * 70)

    try:
        response = input("> ").strip()

        if not response:
            return ToolResult(
                success=False,
                error="No guidance provided",
            )

        if response.lower() == "skip":
            return ToolResult(
                success=True,
                output={
                    "response": "Proceed with agent's judgment",
                    "skip": True,
                },
            )

        # If user selected an option number, return that option
        if options and response.isdigit():
            option_index = int(response) - 1
            if 0 <= option_index < len(options):
                return ToolResult(
                    success=True,
                    output={
                        "response": options[option_index],
                        "selected_option": option_index + 1,
                    },
                )

        return ToolResult(
            success=True,
            output={
                "response": response,
            },
        )

    except (EOFError, KeyboardInterrupt):
        print("\n\nGuidance request cancelled by user.")
        return ToolResult(
            success=False,
            error="User cancelled guidance request",
        )
