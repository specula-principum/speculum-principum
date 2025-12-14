"""Tests for the CopilotClient GitHub Models API integration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.copilot.client import (
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    CopilotClient,
    CopilotClientError,
    FunctionCall,
    ToolCall,
    Usage,
)


def test_copilot_client_requires_api_key():
    """CopilotClient raises error if no API key is provided."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(CopilotClientError, match="GitHub token required"):
            CopilotClient()


def test_copilot_client_uses_env_token():
    """CopilotClient reads GITHUB_TOKEN from environment."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token", "GH_TOKEN": ""}, clear=True):
        client = CopilotClient()
        assert client.api_key == "test_token"


def test_copilot_client_explicit_token():
    """CopilotClient accepts explicit API key parameter."""
    client = CopilotClient(api_key="explicit_token")
    assert client.api_key == "explicit_token"


def test_copilot_client_defaults():
    """CopilotClient sets appropriate defaults."""
    client = CopilotClient(api_key="test")
    assert client.model == "gpt-4o"
    assert client.max_tokens == 4000
    assert client.temperature == 0.7
    assert client.timeout == 60


def test_copilot_client_custom_values():
    """CopilotClient accepts custom configuration."""
    client = CopilotClient(
        api_key="test",
        model="gpt-4o",
        max_tokens=8000,
        temperature=0.5,
        timeout=120,
    )
    assert client.model == "gpt-4o"
    assert client.max_tokens == 8000
    assert client.temperature == 0.5
    assert client.timeout == 120


def test_chat_completion_simple_message():
    """CopilotClient can handle a simple chat completion."""
    mock_response = {
        "id": "chatcmpl-123",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18,
        },
    }
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        client = CopilotClient(api_key="test")
        response = client.chat_completion([
            {"role": "user", "content": "Hello"}
        ])
        
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4o-mini"
        assert len(response.choices) == 1
        assert response.choices[0].message.content == "Hello! How can I help you?"
        assert response.usage is not None
        assert response.usage.total_tokens == 18


def test_chat_completion_with_tool_call():
    """CopilotClient parses tool/function calls correctly."""
    mock_response = {
        "id": "chatcmpl-456",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_issue_details",
                                "arguments": '{"issue_number": 42}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        client = CopilotClient(api_key="test")
        response = client.chat_completion(
            messages=[{"role": "user", "content": "Get issue 42"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "get_issue_details",
                    "description": "Fetch issue details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_number": {"type": "integer"},
                        },
                    },
                },
            }],
        )
        
        assert len(response.choices) == 1
        message = response.choices[0].message
        assert message.tool_calls is not None
        assert len(message.tool_calls) == 1
        
        tool_call = message.tool_calls[0]
        assert tool_call.id == "call_abc123"
        assert tool_call.type == "function"
        assert tool_call.function.name == "get_issue_details"
        assert tool_call.function.arguments == '{"issue_number": 42}'


def test_chat_completion_sends_correct_payload():
    """CopilotClient sends properly formatted request."""
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "id": "test",
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
        }
        mock_post.return_value.raise_for_status = MagicMock()
        
        client = CopilotClient(api_key="test_token", model="gpt-4o")
        
        tools = [{
            "type": "function",
            "function": {"name": "test_tool", "description": "Test"},
        }]
        
        client.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
            max_tokens=2000,
            temperature=0.9,
        )
        
        # Verify the request was made correctly
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        
        assert call_kwargs["headers"]["Authorization"] == "Bearer test_token"
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        
        payload = call_kwargs["json"]
        assert payload["model"] == "gpt-4o"
        assert payload["messages"] == [{"role": "user", "content": "test"}]
        assert payload["max_tokens"] == 2000
        assert payload["temperature"] == 0.9
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"


def test_chat_completion_handles_http_error():
    """CopilotClient raises error on HTTP failure."""
    import requests
    
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.RequestException("HTTP 401")
        mock_post.return_value = mock_response
        
        client = CopilotClient(api_key="test")
        
        with pytest.raises(CopilotClientError, match="GitHub Models API request failed"):
            client.chat_completion([{"role": "user", "content": "test"}])


def test_chat_completion_handles_json_decode_error():
    """CopilotClient raises error on invalid JSON response."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("bad", "", 0)
        mock_post.return_value = mock_response
        
        client = CopilotClient(api_key="test")
        
        with pytest.raises(CopilotClientError, match="Invalid JSON response"):
            client.chat_completion([{"role": "user", "content": "test"}])


def test_parse_response_handles_missing_fields():
    """CopilotClient handles API responses with missing optional fields."""
    client = CopilotClient(api_key="test")
    
    # Minimal response
    minimal_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                }
            }
        ]
    }
    
    result = client._parse_response(minimal_response)
    
    assert result.id == ""
    assert result.model == ""
    assert len(result.choices) == 1
    assert result.choices[0].message.content == ""
    assert result.choices[0].message.tool_calls is None
    assert result.usage is None
