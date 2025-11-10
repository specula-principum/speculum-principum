"""GitHub Copilot CLI-based planner for agent missions."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .planner import Planner
from .safety import ActionRisk
from .tools import ToolDefinition, ToolResult, ToolRegistryError
from .types import AgentState, Thought, ThoughtType, ToolCall

if TYPE_CHECKING:
    from .tools import ToolRegistry


DEFAULT_COPILOT_MODEL = "claude-haiku-4.5"


@dataclass(frozen=True)
class CopilotCLIExecution:
    """Container for a single Copilot CLI invocation."""

    prompt: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class CopilotCLIPlannerError(Exception):
    """Error during Copilot CLI-based planning."""


class CopilotCLIPlanner(Planner):
    """Planner that uses GitHub Copilot CLI with workspace awareness.
    
    This planner runs the Copilot CLI and provides custom tools via an MCP server,
    giving the agent both workspace context and access to our GitHub/KB tools.
    """

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        copilot_command: str = "copilot",
        model: str | None = None,
        mcp_server_path: str | None = None,
    ):
        """Initialize Copilot CLI planner.
        
        Args:
            tool_registry: Registry of available tools for the mission.
            copilot_command: Path to copilot CLI executable.
            model: Optional model to use (e.g., "claude-sonnet-4").
            mcp_server_path: Path to orchestration MCP server script.
        """
        self._tool_registry = tool_registry
        self._copilot_command = copilot_command
        self._model = model or DEFAULT_COPILOT_MODEL
        
        # Default to our orchestration MCP server
        if mcp_server_path is None:
            mcp_server_path = str(
                Path(__file__).parent.parent / "mcp_server" / "orchestration_server.py"
            )
        self._mcp_server_path = mcp_server_path
        
        self._tool_name = "copilot_cli_session"
        self._has_run = False
        self._session_requested = False
        self._last_execution: CopilotCLIExecution | None = None
        self._register_cli_tool()

    @property
    def model(self) -> str:
        """Return the Copilot CLI model configured for this planner."""

        return self._model

    def plan_next(self, state: AgentState) -> Thought:
        """Use Copilot CLI to determine the next action or finish."""

        if self._has_run:
            return Thought(
                content="Copilot CLI session already completed.",
                type=ThoughtType.FINISH,
            )

        if not self._session_requested:
            prompt = self._build_prompt(state)
            self._session_requested = True
            return Thought(
                content="Executing mission via Copilot CLI session.",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(
                    name=self._tool_name,
                    arguments={
                        "prompt": prompt,
                    },
                ),
            )

        if not state.steps:
            self._has_run = True
            return Thought(
                content="Copilot CLI session did not record any actions.",
                type=ThoughtType.FINISH,
            )

        last_step = state.steps[-1]
        result = last_step.result
        self._has_run = True

        if result and result.success:
            message = "Copilot CLI session completed successfully."
            if isinstance(result.output, Mapping):
                summary = result.output.get("stderr") or ""
                summary = summary.strip()
                if not summary:
                    summary = str(result.output.get("stdout", "")).strip()
                if summary:
                    message = f"Copilot CLI session completed successfully: {summary[:200]}"  # noqa: E501
            return Thought(content=message, type=ThoughtType.FINISH)

        error_message = "Copilot CLI session reported a failure."
        if result and result.error:
            error_message = result.error
        elif self._last_execution:
            stderr = self._last_execution.stderr.strip()
            if stderr:
                error_message = f"Copilot CLI session failed: {stderr[:200]}"
        return Thought(content=error_message, type=ThoughtType.FINISH)

    def _register_cli_tool(self) -> None:
        """Expose a tool that runs a Copilot CLI session on demand."""

        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Mission prompt to provide to Copilot CLI.",
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 30,
                    "maximum": 900,
                    "description": "Optional timeout in seconds (default: 300).",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        }

        def handler(payload: Mapping[str, Any]) -> ToolResult:
            prompt = str(payload["prompt"])
            timeout_value = payload.get("timeout")
            timeout = 300
            if timeout_value is not None:
                try:
                    timeout = int(timeout_value)
                except (TypeError, ValueError):
                    return ToolResult(success=False, output=None, error="Invalid timeout value supplied to Copilot CLI session tool.")  # noqa: E501
                timeout = max(30, min(timeout, 900))

            try:
                execution = self._run_copilot_session(prompt=prompt, timeout=timeout)
            except CopilotCLIPlannerError as exc:
                self._last_execution = None
                return ToolResult(success=False, output=None, error=str(exc))

            self._last_execution = execution
            output = {
                "command": execution.command,
                "returncode": execution.returncode,
                "stdout": self._trim_output(execution.stdout),
                "stderr": self._trim_output(execution.stderr),
            }

            if execution.returncode == 0:
                return ToolResult(success=True, output=output, error=None)

            error_message = f"Copilot CLI exited with code {execution.returncode}"
            return ToolResult(success=False, output=output, error=error_message)

        definition = ToolDefinition(
            name=self._tool_name,
            description="Run a Copilot CLI session with mission context.",
            parameters=schema,
            handler=handler,
            risk_level=ActionRisk.SAFE,
        )

        try:
            self._tool_registry.register_tool(definition)
        except ToolRegistryError:
            # The tool might already be registered if multiple planners share the registry.
            pass

    def _build_prompt(self, state: AgentState) -> str:
        """Create prompt with mission context for Copilot CLI.
        
        Args:
            state: Current agent state.
            
        Returns:
            Formatted prompt string.
        """
        mission = state.mission
        
        lines = [
            f"MISSION: {mission.goal}",
            "",
        ]
        
        if mission.constraints:
            lines.append("CONSTRAINTS:")
            for constraint in mission.constraints:
                lines.append(f"  - {constraint}")
            lines.append("")
        
        if mission.success_criteria:
            lines.append("SUCCESS CRITERIA:")
            for criterion in mission.success_criteria:
                lines.append(f"  - {criterion}")
            lines.append("")
        
        if state.context.inputs:
            lines.append("INPUTS:")
            for key, value in state.context.inputs.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        lines.extend([
            "You have access to custom tools via the orchestration MCP server:",
            "  - GitHub issue/PR tools (get_issue_details, add_label, post_comment, etc.)",
            "  - Knowledge base tools",
            "  - Document parsing tools",
            "",
            "Complete the mission by satisfying ALL success criteria.",
            "Use the available tools to take concrete actions.",
            "Do NOT use git commands - focus on using the provided tools.",
        ])
        
        return "\n".join(lines)

    def _run_copilot_session(self, *, prompt: str, timeout: int) -> CopilotCLIExecution:
        """Execute Copilot CLI with MCP server for tools."""
        # Build Copilot CLI command
        command = [self._copilot_command]
        
        # Add model if specified
        if self._model:
            command.extend(["--model", self._model])
        
        # Enable our MCP server for custom tools
        # The format is: --allow-tool mcp-server-name(tool_pattern)
        # We'll use a temporary server name
        command.extend([
            "--allow-tool", "write",  # Allow file editing
            "--allow-tool", "github-mcp-server(web_search)",  # Allow web search
        ])
        
        # Add our orchestration MCP server
        # Note: This requires copilot CLI to support custom MCP servers
        # You may need to configure this via copilot config file instead
        
        # Add the prompt
        command.extend(["--prompt", prompt])
        
        # Prepare environment
        env = os.environ.copy()
        if "GH_TOKEN" not in env:
            github_token = env.get("GITHUB_TOKEN")
            if github_token:
                env["GH_TOKEN"] = github_token
        
        # Run Copilot CLI
        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CopilotCLIPlannerError(
                f"Copilot CLI timed out after {timeout} seconds"
            ) from exc
        except FileNotFoundError as exc:
            raise CopilotCLIPlannerError(
                f"Copilot CLI not found at '{self._copilot_command}'. "
                "Install with: npm install -g @githubnext/copilot-cli"
            ) from exc
        except OSError as exc:
            raise CopilotCLIPlannerError(f"Failed to execute Copilot CLI: {exc}") from exc

        return CopilotCLIExecution(
            prompt=prompt,
            command=command,
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    @staticmethod
    def _trim_output(text: str, limit: int = 2000) -> str:
        data = (text or "").strip()
        if len(data) <= limit:
            return data
        return f"{data[:limit]}... [truncated]"


__all__ = ["CopilotCLIPlanner", "CopilotCLIPlannerError"]
