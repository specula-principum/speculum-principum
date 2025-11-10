"""LLM-based planner using GitHub Models API for autonomous agent reasoning."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.integrations.copilot import CopilotClient, CopilotClientError

from .planner import Planner
from .types import AgentState, Thought, ThoughtType, ToolCall

if TYPE_CHECKING:
    from .tools import ToolRegistry


class LLMPlannerError(Exception):
    """Error during LLM-based planning."""


class LLMPlanner(Planner):
    """Planner powered by GitHub Models API for autonomous reasoning.

    This planner uses an LLM to analyze the mission state and decide what
    action to take next, enabling true autonomous agent behavior rather than
    following predetermined scripts.
    """

    def __init__(
        self,
        *,
        copilot_client: CopilotClient,
        tool_registry: ToolRegistry,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ):
        """Initialize LLM planner with Copilot client.

        Args:
            copilot_client: GitHub Models API client for LLM calls.
            tool_registry: Registry of available tools for function calling.
            max_tokens: Token limit per LLM call.
            temperature: Sampling temperature (0.0-1.0).
        """
        self._copilot = copilot_client
        self._tool_registry = tool_registry
        self._max_tokens = max_tokens
        self._temperature = temperature

    def plan_next(self, state: AgentState) -> Thought:
        """Use LLM to determine the next action based on mission state.

        Args:
            state: Current mission execution state.

        Returns:
            Thought containing either a tool call or finish signal.

        Raises:
            LLMPlannerError: If LLM call fails or response is invalid.
        """
        system_prompt = self._build_system_prompt(state)

        tools = self._tool_registry.get_openai_tool_schemas()
        if state.mission.allowed_tools is not None:
            allowed = set(state.mission.allowed_tools)
            tools = [
                tool
                for tool in tools
                if tool["function"]["name"] in allowed
            ]

        messages = self._build_messages(system_prompt, state)

        try:
            response = self._copilot.chat_completion(
                messages=messages,
                tools=tools if tools else None,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )
        except CopilotClientError as exc:
            raise LLMPlannerError(f"LLM call failed: {exc}") from exc

        thought = self._parse_response(response, state)

        return thought

    def _build_system_prompt(self, state: AgentState) -> str:
        """Create system prompt with mission context and instructions."""
        mission = state.mission

        tool_names = [tool.name for tool in self._tool_registry]

        if mission.allowed_tools is not None:
            tool_names = [t for t in tool_names if mission.is_tool_allowed(t)]

        can_post_comment = "post_comment" in tool_names
        label_tools = {"add_label", "add_labels", "remove_label"}
        can_modify_labels = any(tool in label_tools for tool in tool_names)
        mutation_tools = {
            "close_issue",
            "reopen_issue",
            "lock_issue",
            "unlock_issue",
            "update_issue_title",
            "update_issue_body",
            "merge_pr",
            "request_review",
        }
        has_mutation_tools = (
            can_post_comment
            or can_modify_labels
            or any(tool in mutation_tools for tool in tool_names)
        )

        available_tools_str = ", ".join(tool_names) if tool_names else "None"

        prompt_parts = [
            "You are an autonomous GitHub repository management agent.",
            "",
            f"Mission Goal: {mission.goal}",
            "",
        ]

        if mission.constraints:
            prompt_parts.append("Constraints:")
            for constraint in mission.constraints:
                prompt_parts.append(f"- {constraint}")
            prompt_parts.append("")

        if mission.success_criteria:
            prompt_parts.append("Success Criteria:")
            for criterion in mission.success_criteria:
                prompt_parts.append(f"- {criterion}")
            prompt_parts.append("")

        prompt_parts.extend([
            f"Available Tools: {available_tools_str}",
            "",
            "Instructions:",
        ])

        instruction_lines = [
            "Analyze the current state and mission goal carefully",
            "Review all success criteria - you must complete ALL of them, not just some",
            "Take concrete actions with available tools to satisfy each criterion",
        ]

        if can_modify_labels:
            instruction_lines.append(
                "For triage missions: categorize issues by adding appropriate labels"
            )
        else:
            instruction_lines.append(
                "For triage missions without label tools: note recommended labels in your final response"
            )

        if can_post_comment:
            instruction_lines.append(
                "Document your analysis by posting comments when that will help collaborators"
            )
        else:
            instruction_lines.append(
                "Document your analysis in the final mission report; do not attempt to post comments"
            )

        instruction_lines.append(
            "Only respond with FINISH when ALL success criteria are demonstrably met"
        )

        for index, instruction in enumerate(instruction_lines, start=1):
            prompt_parts.append(f"{index}. {instruction}")
        prompt_parts.append("")

        prompt_parts.append("IMPORTANT:")

        important_lines = ["- Retrieving information is just the first step"]

        if has_mutation_tools:
            important_lines.extend([
                "- You must analyze AND take action (add labels, post recommendations, etc.)",
                "- Don't just describe what you would do - actually do it using the available tools",
            ])
        else:
            important_lines.extend([
                "- Stay within the mission's read-only constraints",
                "- Provide clear recommendations in your final response instead of modifying GitHub artifacts",
            ])

        prompt_parts.extend(important_lines)
        prompt_parts.append("")

        prompt_parts.extend([
            f"You have a maximum of {mission.max_steps} steps to complete this mission.",
            f"Current step: {len(state.steps) + 1} of {mission.max_steps}",
        ])

        return "\n".join(prompt_parts)

    def _build_messages(self, system_prompt: str, state: AgentState) -> list[dict]:
        """Build message history in OpenAI format from state.

        Args:
            system_prompt: System-level instructions.
            state: Current mission state with execution history.

        Returns:
            List of messages formatted for OpenAI chat completions API.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if not state.steps:
            # First interaction - just provide inputs
            inputs_str = json.dumps(state.context.inputs, indent=2) if state.context.inputs else "{}"
            messages.append({
                "role": "user",
                "content": f"Begin mission. Inputs:\n{inputs_str}\n\nWhat's your first action?"
            })
            return messages

        # Add initial user message
        inputs_str = json.dumps(state.context.inputs, indent=2) if state.context.inputs else "{}"
        messages.append({
            "role": "user",
            "content": f"Begin mission. Inputs:\n{inputs_str}\n\nWhat's your first action?"
        })

        # Add each step as assistant tool call + tool result
        for i, step in enumerate(state.steps, 1):
            thought = step.thought
            result = step.result

            if thought.tool_call:
                # Assistant made a tool call
                tool_call_id = f"call_{i}"
                message_dict = {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": thought.tool_call.name,
                            "arguments": json.dumps(thought.tool_call.arguments),
                        },
                    }],
                }
                if thought.content:
                    message_dict["content"] = thought.content
                messages.append(message_dict)

                # Tool result message
                if result:
                    if result.success:
                        tool_output = json.dumps(result.output) if result.output else "Success"
                    else:
                        tool_output = result.error or "Error executing tool"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_output,
                    })

        # Final user prompt asking for next action
        messages.append({
            "role": "user",
            "content": "What's your next action?"
        })

        return messages

    def _build_user_prompt(self, state: AgentState) -> str:
        """Create user prompt with execution history and context."""
        if not state.steps:
            # First step - provide mission inputs
            inputs_str = json.dumps(state.context.inputs, indent=2) if state.context.inputs else "{}"
            return f"Begin mission. Inputs:\n{inputs_str}\n\nWhat's your first action?"

        # Subsequent steps - summarize progress
        prompt_parts = ["Progress so far:"]

        for i, step in enumerate(state.steps, 1):
            thought = step.thought
            result = step.result

            # Describe the action taken
            if thought.tool_call:
                action_desc = f"Step {i}: Called {thought.tool_call.name}"
                if thought.content and thought.content != f"Calling {thought.tool_call.name}":
                    action_desc = f"{action_desc} ({thought.content})"
            else:
                action_desc = f"Step {i}: {thought.content}"

            prompt_parts.append(action_desc)

            # Describe the result
            if result:
                if result.success:
                    if result.output:
                        output_preview = str(result.output)[:200]
                        if len(str(result.output)) > 200:
                            output_preview += "..."
                        prompt_parts.append(f"  Result: {output_preview}")
                    else:
                        prompt_parts.append("  Result: Success")
                else:
                    error_msg = result.error or "Unknown error"
                    prompt_parts.append(f"  Error: {error_msg}")

        prompt_parts.extend(["", "What's your next action?"])

        return "\n".join(prompt_parts)

    def _parse_response(self, response, state: AgentState) -> Thought:
        """Convert LLM response to a Thought.

        Args:
            response: ChatCompletionResponse from the API.
            state: Current mission state for validation.

        Returns:
            Thought with either a tool call or finish signal.

        Raises:
            LLMPlannerError: If response cannot be parsed or is invalid.
        """
        if not response.choices:
            raise LLMPlannerError("LLM response contains no choices")

        message = response.choices[0].message

        # Check for function/tool call
        if message.tool_calls and len(message.tool_calls) > 0:
            tool_call_data = message.tool_calls[0]
            function = tool_call_data.function

            # Parse arguments
            try:
                arguments = json.loads(function.arguments)
            except json.JSONDecodeError as exc:
                raise LLMPlannerError(
                    f"Invalid JSON in tool arguments: {function.arguments}"
                ) from exc

            # Validate tool is allowed
            if not state.mission.is_tool_allowed(function.name):
                raise LLMPlannerError(
                    f"Tool '{function.name}' is not allowed for this mission"
                )

            # Create thought with tool call
            content = message.content or f"Calling {function.name}"
            return Thought(
                content=content,
                type=ThoughtType.ACTION,
                tool_call=ToolCall(
                    name=function.name,
                    arguments=arguments,
                ),
            )

        # No tool call - should be a finish signal
        content = message.content or "Mission complete"
        return Thought(
            content=content,
            type=ThoughtType.FINISH,
        )
