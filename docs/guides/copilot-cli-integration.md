# Integrating GitHub Copilot CLI with Agent Missions

This guide explains how to use GitHub Copilot CLI instead of GitHub Models API for agent missions, giving you workspace awareness and file access while still using custom tools.

## Architecture Overview

### Current Setup (GitHub Models API)
```
Agent Mission
    ↓
LLM Planner → GitHub Models API (gpt-4o-mini)
    ↓
Tool Registry (GitHub API tools only)
    ↓
No workspace context
```

### New Setup (GitHub Copilot CLI)
```
Agent Mission
    ↓
Copilot CLI Planner → GitHub Copilot CLI
    ↓                      ↓
    ↓                  Workspace Context
    ↓                  File System Access
    ↓                      ↓
MCP Server (Custom Tools) → Tool Registry
    ↓
GitHub API, KB, Parsing tools
```

## Key Benefits

### Copilot CLI Advantages:
1. **Workspace Awareness**: Can see and edit project files
2. **Git Integration**: Understands repository structure
3. **File System Access**: Can read/write files directly
4. **Better Context**: Full VS Code-like experience
5. **Interactive Mode**: Can ask clarifying questions

### Custom Tools via MCP:
- GitHub issue/PR operations (add_label, post_comment, etc.)
- Knowledge base tools
- Document parsing
- Any custom tools you build

## Setup Instructions

### 1. Install GitHub Copilot CLI

```bash
# Install via npm
npm install -g @githubnext/github-copilot-cli

# Authenticate
copilot auth login

# Verify installation
copilot --version
```

### 2. Configure MCP Server

The orchestration MCP server is already created at:
```
src/mcp_server/orchestration_server.py
```

Test it:
```bash
# List available tools
python -m src.mcp_server.orchestration_server --list-tools

# Should show: get_issue_details, add_label, post_comment, etc.
```

### 3. Configure Copilot CLI to Use MCP Server

Create/edit `~/.copilot/config.json`:
```json
{
  "mcp_servers": {
    "orchestration": {
      "command": "python",
      "args": ["-m", "src.mcp_server.orchestration_server"],
      "cwd": "/path/to/speculum-principum"
    }
  }
}
```

Or set up per-project in `.copilot/config.json` in the workspace.

### 4. Run Agent with Copilot CLI

```bash
# Use Copilot CLI planner instead of Models API
python -m main agent run \
  --mission config/missions/triage_new_issue.yaml \
  --input issue_number=118 \
  --planner copilot-cli \
  --copilot-bin copilot
```

## Implementation Status

### ✅ Completed:
- [x] Created `OrchestrationMCPServer` (`src/mcp_server/orchestration_server.py`)
- [x] Created `CopilotCLIPlanner` (`src/orchestration/copilot_cli_planner.py`)
- [x] Exposes all GitHub, KB, and parsing tools via MCP

### 🚧 TODO:
- [ ] Update `src/cli/commands/agent.py` to add `copilot-cli` planner option
- [ ] Configure MCP server in Copilot CLI config
- [ ] Parse Copilot CLI output to create proper transcripts
- [ ] Add integration tests

## Usage Examples

### Example 1: Triage an Issue with Copilot CLI

```bash
python -m main agent run \
  --mission triage_new_issue \
  --input issue_number=118 \
  --planner copilot-cli
```

**What happens:**
1. Copilot CLI receives mission prompt with goal and success criteria
2. It can see the project files (unlike Models API)
3. It calls `get_issue_details` via MCP to fetch issue #118
4. It analyzes the content with full workspace context
5. It calls `add_label` to categorize the issue
6. It calls `post_comment` to post analysis
7. Mission completes

### Example 2: Interactive Mode

```bash
# Run in interactive mode (Copilot can ask questions)
python -m main agent run \
  --mission triage_new_issue \
  --input issue_number=118 \
  --planner copilot-cli \
  --interactive
```

### Example 3: Custom Model

```bash
# Use Claude Sonnet instead of default
python -m main agent run \
  --mission triage_new_issue \
  --input issue_number=118 \
  --planner copilot-cli \
  --model claude-sonnet-4
```

## How It Works

### Mission Flow:

1. **Agent CLI** loads mission config and creates `CopilotCLIPlanner`
2. **Planner** builds prompt from mission goal, constraints, success criteria
3. **Copilot CLI** is invoked with:
   - The mission prompt
   - Access to orchestration MCP server (custom tools)
   - Access to workspace files (read/write)
4. **Copilot** executes the mission:
   - Reads project files as needed
   - Calls MCP tools (get_issue_details, add_label, etc.)
   - Makes decisions with full context
5. **Planner** captures output and returns FINISH thought
6. **Agent runtime** records completion

### Tool Invocation:

```
Copilot CLI
    ↓
"I need issue details"
    ↓
MCP Request: tools/call
    {
      "name": "get_issue_details",
      "arguments": {"issue_number": 118}
    }
    ↓
OrchestrationMCPServer
    ↓
ToolRegistry.execute_tool("get_issue_details", {...})
    ↓
GitHub API Call
    ↓
Returns issue data to Copilot
```

## Comparison: Models API vs Copilot CLI

| Feature | GitHub Models API | GitHub Copilot CLI |
|---------|-------------------|-------------------|
| Workspace access | ❌ No | ✅ Yes |
| File reading | ❌ No | ✅ Yes |
| File editing | ❌ No | ✅ Yes |
| Custom tools | ✅ Via function calling | ✅ Via MCP |
| GitHub API access | ✅ Via tools | ✅ Via tools + MCP |
| Interactive mode | ❌ No | ✅ Yes |
| Cost | ✅ Free (Models API) | 💰 Copilot subscription |
| Speed | ⚡ Fast API calls | 🐌 Slower (subprocess) |
| Programmatic control | ✅ Excellent | 🤔 Limited |
| Context window | 📊 API limits | 📊 Better with workspace |

## Current Limitations

### Copilot CLI Integration Challenges:

1. **MCP Configuration**: Copilot CLI MCP support is evolving. You may need to:
   - Use latest Copilot CLI version
   - Configure MCP servers properly
   - Check Copilot CLI documentation for current MCP support

2. **Output Parsing**: Copilot CLI output is designed for humans, not machines. The current implementation:
   - Doesn't capture individual tool calls
   - Can't create detailed transcripts
   - Returns a single FINISH thought

3. **Tool Approval**: Copilot CLI may prompt for confirmation before calling tools. This breaks automation. Solutions:
   - Pre-approve all tools in config
   - Use `--allow-tool orchestration-mcp-server(*)` pattern

## Recommended Approach

### For Development/Testing:
**Use Copilot CLI** - You get workspace context and can iterate quickly

### For Production Automation:
**Use Models API** - More reliable, programmable, and cost-effective

### Hybrid Approach:
- Use Copilot CLI for complex missions requiring code understanding
- Use Models API for simple GitHub API automation
- Switch via `--planner` flag

## Next Steps

1. **Test MCP Server**:
   ```bash
   python -m src.mcp_server.orchestration_server --list-tools
   ```

2. **Verify Copilot CLI**:
   ```bash
   copilot --version
   copilot --help
   ```

3. **Run Simple Test**:
   ```bash
   copilot --prompt "List the files in this directory"
   ```

4. **Enable MCP in Copilot**: Check Copilot CLI docs for current MCP configuration

5. **Try Agent Mission**: Once MCP is configured, run a mission with `--planner copilot-cli`

## Troubleshooting

### "Copilot CLI not found"
```bash
npm install -g @githubnext/github-copilot-cli
```

### "MCP server not responding"
- Check `~/.copilot/config.json` has correct path
- Test MCP server standalone: `python -m src.mcp_server.orchestration_server --list-tools`
- Check Copilot logs: `~/.copilot/logs/`

### "Tools not available"
- Verify MCP server is registered in Copilot config
- Use `--allow-tool orchestration-mcp-server(*)` in command
- Check that tools are listed when running with `--list-tools`

## References

- GitHub Copilot CLI: https://githubnext.com/projects/copilot-cli
- Model Context Protocol: https://modelcontextprotocol.io/
- Our MCP implementation: `src/mcp_server/orchestration_server.py`
- Copilot CLI planner: `src/orchestration/copilot_cli_planner.py`
