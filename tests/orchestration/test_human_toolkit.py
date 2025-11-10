"""Tests for human interaction toolkit."""

from unittest.mock import patch

import pytest

from src.orchestration.toolkit.human import (
    _request_human_guidance_handler,
    register_human_interaction_tools,
)
from src.orchestration.tools import ToolRegistry


@pytest.fixture
def registry():
    """Provide a tool registry with human interaction tools."""
    reg = ToolRegistry()
    register_human_interaction_tools(reg)
    return reg


def test_register_human_interaction_tools(registry):
    """Test that human interaction tools are registered correctly."""
    tools = list(registry.get_tool_schemas())

    tool_names = [tool["name"] for tool in tools]
    assert "request_human_guidance" in tool_names


def test_request_human_guidance_tool_schema(registry):
    """Test that request_human_guidance has correct schema."""
    definition = registry._tools["request_human_guidance"]

    assert definition.name == "request_human_guidance"
    assert "uncertain" in definition.description.lower()
    assert definition.parameters["required"] == ["question"]
    assert "question" in definition.parameters["properties"]
    assert definition.parameters["properties"]["question"]["minLength"] == 10


def test_request_human_guidance_non_interactive():
    """Test requesting guidance in non-interactive mode."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=False):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=False):
            result = _request_human_guidance_handler(
                {
                    "question": "Should I proceed with this action?",
                    "context": {"issue": 123},
                    "options": ["Approve", "Reject"],
                }
            )

            assert result.success
            assert result.output is not None
            assert result.output["mode"] == "non-interactive"
            assert "Human guidance required" in result.output["response"]
            assert result.output["question"] == "Should I proceed with this action?"
            assert result.output["context"] == {"issue": 123}
            assert result.output["options"] == ["Approve", "Reject"]


def test_request_human_guidance_interactive_text_response():
    """Test requesting guidance with text response in interactive mode."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", return_value="Yes, proceed carefully"):
                result = _request_human_guidance_handler(
                    {"question": "Should I proceed with this action?"}
                )

                assert result.success
                assert result.output is not None
                assert result.output["response"] == "Yes, proceed carefully"


def test_request_human_guidance_interactive_skip():
    """Test skipping guidance request in interactive mode."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", return_value="skip"):
                result = _request_human_guidance_handler(
                    {"question": "Need help?"}
                )

                assert result.success
                assert result.output is not None
                assert result.output["skip"] is True
                assert "agent's judgment" in result.output["response"].lower()


def test_request_human_guidance_interactive_option_selection():
    """Test selecting an option by number in interactive mode."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", return_value="2"):
                result = _request_human_guidance_handler(
                    {
                        "question": "Which approach?",
                        "options": ["Option A", "Option B", "Option C"],
                    }
                )

                assert result.success
                assert result.output is not None
                assert result.output["response"] == "Option B"
                assert result.output["selected_option"] == 2


def test_request_human_guidance_interactive_invalid_option():
    """Test that invalid option number falls back to text response."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", return_value="99"):
                result = _request_human_guidance_handler(
                    {
                        "question": "Which approach?",
                        "options": ["Option A", "Option B"],
                    }
                )

                assert result.success
                # Falls back to treating "99" as text response
                assert result.output is not None
                assert result.output["response"] == "99"


def test_request_human_guidance_interactive_empty_input():
    """Test that empty input is treated as error."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", return_value=""):
                result = _request_human_guidance_handler(
                    {"question": "Need help?"}
                )

                assert not result.success
                assert result.error is not None
                assert "No guidance provided" in result.error


def test_request_human_guidance_interactive_keyboard_interrupt():
    """Test handling of KeyboardInterrupt during input."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                result = _request_human_guidance_handler(
                    {"question": "Need help?"}
                )

                assert not result.success
                assert result.error is not None
                assert "cancelled" in result.error.lower()


def test_request_human_guidance_interactive_eof():
    """Test handling of EOFError during input."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=True):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=True):
            with patch("builtins.input", side_effect=EOFError):
                result = _request_human_guidance_handler(
                    {"question": "Need help?"}
                )

                assert not result.success
                assert result.error is not None
                assert "cancelled" in result.error.lower()


def test_request_human_guidance_with_context():
    """Test that context is properly handled."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=False):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=False):
            result = _request_human_guidance_handler(
                {
                    "question": "How to proceed?",
                    "context": {
                        "issue_number": 456,
                        "current_step": "validation",
                        "error_count": 2,
                    },
                }
            )

            assert result.success
            assert result.output is not None
            assert result.output["context"]["issue_number"] == 456
            assert result.output["context"]["current_step"] == "validation"


def test_request_human_guidance_registry_integration(registry):
    """Test executing the tool through registry."""
    with patch("src.orchestration.toolkit.human.sys.stdin.isatty", return_value=False):
        with patch("src.orchestration.toolkit.human.sys.stdout.isatty", return_value=False):
            result = registry.execute_tool(
                "request_human_guidance",
                {"question": "This is a test question for validation purposes."},
            )

            assert result.success
            assert result.output is not None
            assert "Human guidance required" in result.output["response"]


def test_request_human_guidance_validation_error(registry):
    """Test that invalid arguments are rejected."""
    # Question too short - should fail validation
    result = registry.execute_tool(
        "request_human_guidance",
        {"question": "Short"},  # Less than 10 characters
    )
    
    # Validation error should be returned as a failed result
    assert not result.success
    assert "validation failed" in result.error.lower()
