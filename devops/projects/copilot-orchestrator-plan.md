# Copilot Agentic Orchestrator Project Plan

## Vision
Build a **generative reasoning agent** that autonomously accomplishes repository management tasks by using CLI tools as its capabilities. The agent receives high-level goals, plans its approach, executes tools, observes results, and iterates until objectives are met—going far beyond simple command sequencing.

## Core Insight from Feedback
The original plan described a deterministic orchestrator that sequences CLI commands in a fixed order. This is insufficient. What we need is an **LLM-powered agent** that:
- **Reasons** about what needs to be done given a goal
- **Plans** a sequence of actions to achieve that goal
- **Executes** tools and observes outcomes
- **Adapts** its approach based on what it learns
- **Explains** its decisions for human oversight

This is the difference between a script and an intelligent agent.

## Working Principles
- **Agent-first design**: The system reasons about what to do, not just what commands to run in sequence.
- **Tool-based architecture**: All CLI commands become callable tools in the agent's toolkit.
- **Human-in-the-loop**: Critical decisions (policy, moderation, legal) require human approval.
- **Incremental deployment**: Start with simple missions, expand capabilities progressively.
- **Observability**: All agent reasoning, tool calls, and outcomes are logged for audit and learning.
- **Safety-first**: Guardrails prevent destructive actions; dry-run modes allow testing without side effects.

## Architecture Overview

### Core Components
1. **Agent Runtime** (`src/orchestration/agent.py`): LLM-based reasoning loop with tool calling, state management, and planning
2. **Tool Registry** (`src/orchestration/tools.py`): Exposes all CLI commands as structured tool definitions with schemas
3. **Mission Definitions** (`config/missions/`): High-level goal specifications that the agent can execute
4. **Safety Layer** (`src/orchestration/safety.py`): Guardrails, human approval gates, and action validation
5. **Observability** (`src/orchestration/logging.py`): Structured logging of reasoning traces and tool executions

### Agent Capabilities (Tools)
The agent has access to existing CLI functionality as tools:
- **GitHub Operations**: create/update issues, manage labels, post comments, search, assign, close
- **PR Management**: review PRs, approve, merge, check diffs
- **Knowledge Base**: extract, validate, generate reports, run automation workflows
- **Parsing**: parse documents (markdown, PDF, DOCX, web)
- **MCP Server**: expose KB tools to other agents

## Phase 0 – Agent Foundation
**Objectives**
- Build the core agent runtime with reasoning loop and tool calling
- Create the tool registry that wraps existing CLI commands
- Establish safety guardrails and human-in-the-loop patterns

**Implementation Tasks**

### 1. Agent Runtime (`src/orchestration/agent.py`)
Create the core reasoning engine:
```python
class AgentRuntime:
    """LLM-powered agent that accomplishes tasks using tools."""
    
    def execute_mission(self, mission: Mission) -> MissionOutcome:
        """Main reasoning loop: observe → think → plan → act → evaluate."""
        
    def _reason(self, context: Context) -> Thought:
        """Ask LLM to analyze situation and decide what to do next."""
        
    def _select_tool(self, thought: Thought) -> ToolCall:
        """Choose appropriate tool based on reasoning."""
        
    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool and capture result."""
        
    def _evaluate_progress(self, history: List[Step]) -> bool:
        """Determine if mission goal is achieved."""
```

Features:
- Multi-step planning with **GitHub Copilot integration via `src/integrations/copilot`** (primary approach)
- Fallback to GitHub Models API only if Copilot integration is unsuitable for specific use cases
- Conversation history and working memory
- Tool call parsing and validation
- Retry logic and error recovery
- Token/cost tracking
- Timeout protection

### 2. Tool Registry (`src/orchestration/tools.py`)
Expose CLI commands as agent tools:
```python
@dataclass(frozen=True)
class ToolDefinition:
    """Describes a tool the agent can use."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[[dict], ToolResult]
    risk_level: ActionRisk

class ToolRegistry:
    """Registry of all available tools."""
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """Add a tool to the registry."""
        
    def get_tool_schemas(self) -> list[dict]:
        """Return GitHub Models-compatible tool schema for all tools."""
        
    def execute_tool(self, name: str, args: dict) -> ToolResult:
        """Execute a tool by name with given arguments."""
```

Initial tools to implement:
- `search_github_issues(query, labels, state)` → list of issues
- `get_issue_details(number)` → full issue content
- `add_label(issue_number, label)` → success/failure
- `post_comment(issue_number, body)` → comment URL
- `extract_kb_knowledge(source_path, kb_root)` → extraction result
- `validate_kb(kb_root)` → validation report
- `parse_document(path, format)` → parsed content

### 3. Safety Layer (`src/orchestration/safety.py`)
Implement guardrails and approval gates:
```python
class ActionRisk(Enum):
    SAFE = "safe"  # Read-only operations
    REVIEW = "review"  # Modifications requiring approval
    DESTRUCTIVE = "destructive"  # Deletion, closing, locking

class SafetyValidator:
    """Validates and gates risky actions."""
    
    def check_action(self, tool: str, args: dict) -> ApprovalDecision:
        """Determine if action requires human approval."""
        
    def request_approval(self, action: ToolCall) -> bool:
        """Request human approval for risky action."""
        
    def audit_log(self, execution: ToolExecution) -> None:
        """Record all tool executions for audit trail."""
```

Features:
- Risk classification for every tool
- Approval request mechanism (CLI prompt, webhook, etc.)
- Dry-run simulation mode
- Audit logging of all actions

**Deliverables**
- Working agent runtime with LLM integration
- Tool registry with 5-10 essential tools
- Safety layer with approval gates
- Unit tests with mocked LLM responses
- Integration test demonstrating simple reasoning

**Guardrails**
- Start with read-only tools only
- All LLM calls have 30-second timeout and 4K token limit
- Agent must explain reasoning before each tool call
- Maximum 5 tool calls in initial phase

## Phase 1 – Simple Missions
**Objectives**
- Define and execute simple, bounded agent missions
- Validate that agent reasoning produces correct tool sequences
- Establish mission definition format and evaluation criteria

**Implementation Tasks**

### 1. Mission Framework (`src/orchestration/missions.py`)
Define how missions are specified:
```python
@dataclass(frozen=True)
class Mission:
    """Specification of a goal for the agent to accomplish."""
    id: str
    goal: str  # Natural language goal
    constraints: list[str]  # Things the agent must/must not do
    success_criteria: list[str]  # How to know when done
    max_steps: int  # Safety limit
    allowed_tools: list[str] | None  # Tool whitelist
    requires_approval: bool  # Human-in-the-loop flag

def load_mission(path: Path) -> Mission:
    """Load mission definition from YAML/JSON."""
```

Example mission YAML:
```yaml
id: triage-new-issue
goal: |
  Read the issue and determine its type. Apply appropriate labels
  based on content (kb-extraction, bug, feature-request, etc.).
  Do not close or assign the issue.
constraints:
  - Only read issue content and apply labels
  - Do not modify issue body or title
  - Do not close or assign the issue
success_criteria:
  - At least one relevant label has been applied
  - No errors occurred during label application
max_steps: 5
allowed_tools:
  - get_issue_details
  - add_label
requires_approval: false
```

### 2. Initial Missions (`config/missions/`)
Create simple missions to validate the agent:

**Mission 1**: `triage_new_issue.yaml`
- **Goal**: Classify an issue and apply appropriate labels
- **Tools**: `get_issue_details`, `add_label`
- **Success**: Correct label applied

**Mission 2**: `kb_extraction_check.yaml`
- **Goal**: Verify KB extraction issue has required template fields
- **Tools**: `get_issue_details`, `post_comment`
- **Success**: Comment posted listing missing fields (if any)

**Mission 3**: `pr_safety_check.yaml`
- **Goal**: Review PR and verify it only modifies KB files
- **Tools**: `get_pr_details`, `get_pr_diff`, `post_comment`
- **Success**: Safety assessment comment posted

### 3. Evaluation Framework (`src/orchestration/evaluation.py`)
Test and measure mission outcomes:
```python
class MissionEvaluator:
    """Evaluates whether a mission succeeded."""
    
    def evaluate(self, mission: Mission, outcome: MissionOutcome) -> Evaluation:
        """Check if success criteria were met."""
        
    def generate_report(self, evaluation: Evaluation) -> str:
        """Create markdown report of mission execution."""
```

**Deliverables**
- Mission definition format and loader
- 3 working simple missions
- Evaluation framework with success/failure detection
- Test harness with mocked tools
- CLI command: `python -m main agent run --mission triage_new_issue --issue 123`

**Guardrails**
- Missions execute in read-only mode by default (override with `--allow-writes`)
- Maximum 10 tool calls per mission
- All missions require explicit termination conditions
- Failed missions must log reasoning trace

## Phase 2 – GitHub Workflow Missions
**Objectives**
- Enable agent to autonomously handle common GitHub workflows
- Implement human approval for destructive actions
- Create mission templates for issue triage, PR review, and KB processing

**Implementation Tasks**

### 1. Extended GitHub Tools
Add mutation operations:
- `remove_label(issue_number, label)` → success/failure
- `update_issue_body(issue_number, body)` → success/failure
- `close_issue(issue_number, reason)` → success/failure [REQUIRES APPROVAL]
- `lock_issue(issue_number, reason)` → success/failure [REQUIRES APPROVAL]
- `assign_issue(issue_number, assignee)` → success/failure
- `approve_pr(pr_number, comment)` → success/failure
- `merge_pr(pr_number, method)` → success/failure [REQUIRES APPROVAL]
- `request_pr_changes(pr_number, comments)` → success/failure

### 2. Workflow Missions (`config/missions/workflows/`)

**Mission**: `issue_triage_complete.yaml`
```yaml
goal: |
  Classify the issue, apply appropriate labels, and either:
  - Assign to Copilot if it's a KB extraction task
  - Request more information if template is incomplete
  - Assign to admin if it requires human judgment
allowed_tools:
  - get_issue_details
  - add_label
  - remove_label
  - assign_issue
  - post_comment
max_steps: 15
```

**Mission**: `kb_extraction_full.yaml`
```yaml
goal: |
  Execute the full KB extraction workflow:
  1. Validate issue has source path and requirements
  2. Run extraction from specified source
  3. Validate extracted knowledge base
  4. Generate quality report
  5. Post report as comment
  6. Apply completion label if successful
allowed_tools:
  - get_issue_details
  - extract_kb_knowledge
  - validate_kb
  - generate_kb_report
  - post_comment
  - add_label
max_steps: 25
requires_approval: false  # Safe workflow
```

**Mission**: `pr_auto_merge_kb.yaml`
```yaml
goal: |
  Review PR and automatically approve/merge if:
  - All changed files are in knowledge-base/
  - Changes are additive (no deletions except frontmatter)
  - Validation passes
  Otherwise, explain why auto-merge is not safe.
allowed_tools:
  - get_pr_details
  - get_pr_diff
  - validate_kb
  - post_comment
  - approve_pr
  - merge_pr
max_steps: 20
requires_approval: true  # Merging requires approval
```

**Mission**: `moderation_response.yaml`
```yaml
goal: |
  Detect policy violations and respond appropriately:
  - Post policy-aligned response explaining issue
  - Hide inappropriate comments if needed
  - Lock thread if hostile
  - Close issue with explanation
allowed_tools:
  - get_issue_details
  - post_comment
  - hide_comment
  - lock_issue
  - close_issue
max_steps: 10
requires_approval: true  # Always require human review
```

### 3. Human-in-the-Loop (`src/orchestration/approval.py`)
Implement approval workflow:
```python
class ApprovalGate:
    """Requests human approval for risky actions."""
    
    def request_approval(
        self,
        action: ToolCall,
        context: ExecutionContext,
    ) -> ApprovalDecision:
        """Present action to human and await decision."""
        
    def record_decision(self, decision: ApprovalDecision) -> None:
        """Audit log approval/rejection."""
```

Methods:
- CLI prompt (interactive mode)
- GitHub comment (post pending action, await reply)
- Webhook (POST to external approval service)
- Timeout/escalation after 4 hours

**Deliverables**
- 12+ GitHub mutation tools
- 4 complete workflow missions
- Human approval system
- CLI: `python -m main agent run --mission pr_auto_merge_kb --pr 456 --interactive`
- Integration tests with approval mocks

**Guardrails**
- Closing/locking/merging requires approval by default
- Agent cites specific evidence for all classification decisions
- Maximum 25 tool calls per workflow mission
- All destructive actions logged to audit trail

## Phase 3 – Advanced Reasoning
**Objectives**
- Enable multi-step planning and goal decomposition
- Implement learning from past mission executions
- Support complex decision-making with uncertainty handling

**Implementation Tasks**

### 1. Planning System (`src/orchestration/planner.py`)
Add hierarchical planning:
```python
class Planner:
    """Creates and validates multi-step plans."""
    
    def create_plan(self, goal: str, context: Context) -> Plan:
        """Generate step-by-step plan to achieve goal."""
        
    def validate_plan(self, plan: Plan) -> list[PlanIssue]:
        """Check plan for safety and feasibility."""
        
    def revise_plan(self, plan: Plan, feedback: str) -> Plan:
        """Update plan based on new information."""
```

Features:
- Hierarchical goal decomposition
- Plan validation before execution
- Plan revision based on intermediate results
- Plan visualization for debugging

### 2. Memory & Learning (`src/orchestration/memory.py`)
Store and retrieve mission history:
```python
class MissionMemory:
    """Stores past mission executions for learning."""
    
    def record_execution(self, outcome: MissionOutcome) -> None:
        """Save mission execution details."""
        
    def find_similar(self, mission: Mission) -> list[MissionOutcome]:
        """Retrieve similar past missions."""
        
    def extract_patterns(self) -> list[SuccessPattern]:
        """Identify successful tool sequences."""
```

Use cases:
- "Show me how similar issues were handled"
- "What labels are typically applied to KB extraction issues?"
- "Which tool sequences failed in the past?"

### 3. Uncertainty Handling
Teach agent to ask for help:
```python
class UncertaintyDetector:
    """Identifies when agent needs human guidance."""
    
    def assess_confidence(self, thought: Thought) -> float:
        """Score confidence in current reasoning."""
        
    def should_escalate(self, confidence: float) -> bool:
        """Decide if human input is needed."""
```

New tool: `request_human_guidance(question: str) -> str`
- Agent explains situation
- Asks specific question
- Waits for human response
- Continues with new information

**Deliverables**
- Hierarchical planner with validation
- Mission memory storage and retrieval
- Uncertainty detection and escalation
- `request_human_guidance` tool
- Complex missions using planning

**Guardrails**
- Agent declares uncertainty when confidence < 0.7
- Complex missions require initial plan approval
- Learning system is read-only (no autonomous retraining)
- Maximum 50 tool calls per complex mission

## Phase 4 – Production Deployment
**Objectives**
- Deploy agent for continuous repository management
- Implement monitoring and alerting
- Create runbooks for common failure modes

**Implementation Tasks**

### 1. Deployment Infrastructure
Enable continuous operation:
- Scheduled execution (GitHub Actions workflow runs every hour)
- Mission queue with priority system
- Circuit breaker (pause after 3 consecutive failures)
- Health check endpoint
- Graceful shutdown and resume

### 2. Monitoring (`src/orchestration/monitoring.py`)
Track agent performance:
```python
class AgentMonitor:
    """Tracks agent performance and health."""
    
    def record_mission(self, outcome: MissionOutcome) -> None:
        """Log mission metrics."""
        
    def check_health(self) -> HealthStatus:
        """Assess agent health (error rate, latency, etc.)."""
        
    def generate_report(self, period: timedelta) -> Report:
        """Create performance report."""
```

Metrics:
- Mission success/failure rate
- Tool execution latency
- LLM token usage and cost
- Approval request frequency
- Anomaly detection (unexpected tool usage patterns)

### 3. CLI Integration
Complete command suite:
```bash
# Run a specific mission
python -m main agent run --mission issue_triage --issue 789

# Dry-run mode (no mutations)
python -m main agent run --mission pr_auto_merge_kb --pr 101 --dry-run

# List available missions
python -m main agent list-missions

# Check agent status
python -m main agent status

# Explain past execution
python -m main agent explain --mission-id abc-123

# View mission history
python -m main agent history --limit 10
```

### 4. VS Code Task Integration
Update tasks to use agent:
```json
{
  "label": "agent: triage unlabeled issues",
  "type": "shell",
  "command": "python -m main agent run --mission triage_unlabeled_batch"
}
```

**Deliverables**
- Scheduled execution in GitHub Actions
- Monitoring dashboard
- Complete CLI command suite
- VS Code tasks
- Runbook for common failure modes
- Cost tracking and budgets

**Guardrails**
- Agent operates in dry-run mode for first week
- Rate limits: max 100 GitHub API calls/hour
- Automatic pause after 5 consecutive failures
- Human review of all outcomes for first 2 weeks
- Daily cost reports

## Phase 5 – Feedback & Evolution
**Objectives**
- Establish continuous improvement process
- Expand mission library based on usage patterns
- Optimize agent performance and reliability

**Implementation Tasks**

### 1. Performance Analysis
Analyze agent behavior:
- Mission success rate by type
- Common failure modes
- Tool usage distribution
- Cost per mission (tokens + API calls)
- Time to completion by mission

### 2. Mission Library Expansion
Grow capabilities:
- Extract new missions from manual workflows
- Create mission variants for edge cases
- Implement mission composition (chain simple missions)
- Build mission recommendation: "Based on this issue, I suggest running mission X"

### 3. Agent Optimization
Improve efficiency:
- Fine-tune system prompts based on success patterns
- Optimize tool selection (reduce unnecessary calls)
- Implement caching for repeated queries
- Reduce token usage through prompt compression
- A/B test different reasoning strategies

### 4. Documentation
Create user guides:
- Mission authoring guide
- Tool development guide
- Troubleshooting guide
- Best practices for agent interaction

**Deliverables**
- Performance analytics dashboard
- 20+ mission templates
- Optimization results (token reduction, faster execution)
- Comprehensive documentation
- Community contribution guidelines

**Guardrails**
- Changes to core agent behavior require review
- New missions start in supervised mode
- Performance degradation triggers rollback
- Human-in-the-loop for mission design

## Success Criteria

### Phase 0
- [ ] Agent can reason about a simple task and select appropriate tools
- [ ] Tool registry exposes 5-10 CLI commands
- [ ] Safety layer blocks unapproved destructive actions
- [ ] Integration test shows agent completing 3-step task

### Phase 1
- [ ] Agent successfully executes 3 simple missions
- [ ] Missions correctly identify success/failure
- [ ] Test harness validates agent behavior
- [ ] CLI accepts mission definitions

### Phase 2
- [ ] Agent triages 10 real issues correctly
- [ ] KB extraction mission runs end-to-end
- [ ] PR review mission correctly approves/rejects
- [ ] Human approval gates function correctly

### Phase 3
- [ ] Agent creates and validates multi-step plans
- [ ] Mission memory retrieves similar past executions
- [ ] Agent requests human guidance when uncertain
- [ ] Complex missions (20+ steps) complete successfully

### Phase 4
- [ ] Agent runs continuously via GitHub Actions
- [ ] Monitoring detects and alerts on failures
- [ ] Cost tracking prevents budget overruns
- [ ] Zero unauthorized destructive actions

### Phase 5
- [ ] Mission library contains 20+ reusable missions
- [ ] Token usage reduced by 30% through optimization
- [ ] 95% mission success rate
- [ ] Documentation enables community contributions

## LLM Planner Implementation Guide

### Overview
The transition from demo scaffolding (deterministic planner) to production LLM-based planning is the critical step that unlocks true autonomous agent capabilities.

### Current State (Demo Scaffolding)
Location: `src/cli/commands/agent.py` lines 236-239

```python
planner = DeterministicPlanner(
    steps=[],  # Empty steps = immediate finish
    default_finish="Mission planning not yet implemented - use demo mode"
)
```

This placeholder verifies infrastructure works but performs no real reasoning.

### Target State (LLM Planner)

Create `src/orchestration/llm.py` implementing the `Planner` interface using GitHub Copilot.

#### Priority 1: GitHub Copilot Integration (REQUIRED)

**Use existing infrastructure**: `src/integrations/copilot/`

```python
"""LLM-based planner using GitHub Copilot (primary) with Models fallback."""

from src.integrations.copilot import CopilotClient  # Use existing integration
from .planner import Planner
from .types import AgentState, Thought, ThoughtType, ToolCall


class LLMPlanner(Planner):
    """Planner powered by GitHub Copilot for autonomous reasoning."""
    
    def __init__(
        self,
        *,
        copilot_client: CopilotClient,  # Leverage existing Copilot utilities
        available_tools: list[dict],
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ):
        """Initialize LLM planner with Copilot client.
        
        Args:
            copilot_client: Existing Copilot integration client from src/integrations/copilot
            available_tools: Tool schemas for function calling
            max_tokens: Token limit per LLM call
            temperature: Sampling temperature
        """
        self._copilot = copilot_client
        self._tools = available_tools
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._conversation_history: list[dict] = []
    
    def plan_next(self, state: AgentState) -> Thought:
        """Use GitHub Copilot to determine next action."""
        
        # Build prompt from mission context
        system_prompt = self._build_system_prompt(state)
        user_prompt = self._build_user_prompt(state)
        
        # Call Copilot via existing integration
        response = self._copilot.chat_completion(
            system=system_prompt,
            messages=self._conversation_history + [
                {"role": "user", "content": user_prompt}
            ],
            tools=self._tools,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        
        # Parse into Thought
        thought = self._parse_response(response)
        
        # Update history
        self._conversation_history.append({
            "role": "assistant",
            "content": thought.content,
        })
        
        return thought
    
    def _build_system_prompt(self, state: AgentState) -> str:
        """Create system prompt with mission context."""
        mission = state.mission
        
        return f'''You are an autonomous GitHub repository management agent.

Mission Goal: {mission.goal}

Constraints:
{chr(10).join(f"- {c}" for c in mission.constraints)}

Success Criteria:
{chr(10).join(f"- {c}" for c in mission.success_criteria)}

Available Tools: {", ".join(t["function"]["name"] for t in self._tools)}

Instructions:
1. Analyze the current state
2. Choose the most appropriate next action
3. Call tools to gather information or make changes
4. When goal is achieved, indicate FINISH

You have {mission.max_steps} steps maximum.'''
    
    def _build_user_prompt(self, state: AgentState) -> str:
        """Create prompt with execution history."""
        if not state.steps:
            return f"Begin mission. Inputs: {state.context.inputs}"
        
        # Summarize execution so far
        steps_summary = []
        for i, step in enumerate(state.steps, 1):
            tool = step.thought.tool_call.name if step.thought.tool_call else "none"
            success = step.result.success if step.result else "pending"
            steps_summary.append(f"Step {i}: {tool} - {success}")
        
        return f"Progress:\n{chr(10).join(steps_summary)}\n\nWhat's next?"
    
    def _parse_response(self, response: dict) -> Thought:
        """Convert Copilot response to Thought."""
        message = response["choices"][0]["message"]
        
        # Check for tool call
        if "tool_calls" in message and message["tool_calls"]:
            tool_call = message["tool_calls"][0]
            function = tool_call["function"]
            
            return Thought(
                content=message.get("content") or f"Calling {function['name']}",
                type=ThoughtType.ACTION,
                tool_call=ToolCall(
                    name=function["name"],
                    arguments=json.loads(function["arguments"]),
                ),
            )
        
        # Otherwise, finish
        return Thought(
            content=message["content"],
            type=ThoughtType.FINISH,
        )
```

#### Priority 2: GitHub Models Fallback (ONLY IF NEEDED)

**Only implement if**: Copilot integration lacks required capabilities (e.g., specific model, fine-tuning)

```python
class GitHubModelsPlanner(Planner):
    """Fallback planner using direct GitHub Models API.
    
    NOTE: Only use when Copilot integration is insufficient.
    Document reason for not using Copilot in code comments.
    """
    
    def __init__(self, *, model: str = "gpt-4o-mini", api_key: str, ...):
        """Initialize with GitHub Models API.
        
        WARNING: This bypasses Copilot integration. Justify in comments.
        """
        # Implementation using direct API calls
        pass
```

#### Implementation Steps

**Week 1-2: Copilot Integration**
1. Review `src/integrations/copilot/` existing utilities
2. Implement `LLMPlanner` using Copilot client
3. Add tool schema export to `ToolRegistry.get_tool_schemas()`
4. Write tests with mocked Copilot responses

**Week 3: Integration & Testing**
1. Update `src/cli/commands/agent.py` to use `LLMPlanner`
2. Add `--planner` CLI flag for A/B testing: `--planner copilot` vs `--planner deterministic`
3. Run all missions with both planners, compare transcripts
4. Validate reasoning quality and tool selection

**Week 4: Rollout**
1. Make Copilot planner default for all missions
2. Archive deterministic planner to tests-only
3. Monitor performance metrics and costs
4. Document any Copilot limitations discovered

**Week 5+: Optimization**
1. Fine-tune system prompts based on success patterns
2. Optimize token usage through prompt engineering
3. Consider GitHub Models fallback only if Copilot proves insufficient
4. Document decision rationale in progress log

### Integration Checklist

- [ ] Review existing `src/integrations/copilot/` utilities
- [ ] Implement `LLMPlanner` class using Copilot client
- [ ] Add `ToolRegistry.get_tool_schemas()` method
- [ ] Write unit tests with mocked responses
- [ ] Update CLI to instantiate `LLMPlanner` instead of `DeterministicPlanner`
- [ ] Add `--planner` flag for A/B testing
- [ ] Run regression tests comparing both planners
- [ ] Monitor first 100 missions for quality/cost
- [ ] Document any limitations of Copilot approach
- [ ] Only implement GitHub Models fallback if Copilot insufficient
- [ ] Update documentation with planner architecture

### Success Metrics for LLM Planner

- [ ] 90%+ missions complete successfully with Copilot planner
- [ ] Average mission time < 30 seconds
- [ ] Token usage < 5K tokens per mission
- [ ] Cost < $0.05 per mission
- [ ] Zero unauthorized mutations (safety layer works)
- [ ] Copilot integration meets all requirements (no fallback needed)

## Key Differences from Original Plan

| Original Plan | Agentic Redesign |
|---------------|------------------|
| Deterministic classification rules | LLM-based reasoning about issue content |
| Fixed command sequences | Dynamic tool selection based on goal |
| Hardcoded workflow paths | Adaptive planning with goal decomposition |
| Simple script orchestration | True agent with memory and learning |
| No uncertainty handling | Confidence scoring and human escalation |
| Limited to predefined flows | Generalizes to new situations |

## Technology Stack

### LLM Integration (Priority Order)

1. **PRIMARY: GitHub Copilot via `src/integrations/copilot`**
   - Leverages existing Copilot integration infrastructure
   - Native tool calling and function execution support
   - Built-in rate limiting and cost management
   - Seamless integration with GitHub ecosystem
   - **This should be the default choice for all LLM-powered planning**

2. **FALLBACK ONLY: GitHub Models API**
   - Direct inference when Copilot integration is unsuitable
   - Use cases: specialized models, fine-tuned variants, specific latency requirements
   - Models: gpt-4o, gpt-4o-mini, Claude 3 on GitHub
   - **Only use when Copilot cannot meet specific technical requirements**

3. **DEVELOPMENT/TESTING: Local models via Ollama**
   - For offline development and unit testing
   - Cost-free experimentation
   - Not for production use

**Implementation Strategy**: All LLM planner implementations MUST first attempt to use `src/integrations/copilot` utilities. GitHub Models API should only be considered after documenting why Copilot is insufficient for the use case.

### Agent Framework Options
1. **Custom** (full control, aligned with existing architecture)
2. **LangChain** (mature ecosystem, many tools)
3. **AutoGPT/BabyAGI** (proven agent patterns)
4. **CrewAI** (multi-agent support for future)

**Recommendation**: Start with custom implementation using existing MCP patterns, migrate to framework if complexity grows.

### Storage
- Mission definitions: YAML files in `config/missions/`
- Execution history: SQLite database
- Audit logs: JSON lines format
- Metrics: Time-series database (optional)

## Cost Estimation

### LLM Costs (GitHub Copilot Primary)
**Note**: Costs based on GitHub Copilot usage. GitHub Models API costs apply only if Copilot fallback is needed.

Using GitHub Copilot (estimated):
- Simple mission (5 tool calls): ~2K tokens ≈ $0.005-0.01
- Workflow mission (20 tool calls): ~8K tokens ≈ $0.02-0.04
- Complex mission (50 tool calls): ~20K tokens ≈ $0.05-0.10

Estimated monthly cost (100 missions/day via Copilot):
- 70% simple + 25% workflow + 5% complex = ~$40-75/month

**GitHub Models API fallback costs** (if needed):
- gpt-4o-mini: ~$0.01 per simple mission
- gpt-4o: ~$0.04 per workflow mission
- Similar monthly range if fully on GitHub Models: ~$75/month

### Development Time
- Phase 0: 2 weeks (agent foundation)
- Phase 1: 1 week (simple missions)
- Phase 2: 2 weeks (GitHub workflows)
- Phase 3: 2 weeks (advanced reasoning)
- Phase 4: 1 week (deployment)
- Phase 5: Ongoing

**Total initial implementation**: ~8 weeks

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent makes incorrect decisions | High | Human approval for destructive actions, dry-run mode |
| LLM costs exceed budget | Medium | Token limits, caching, budget alerts |
| Agent gets stuck in loops | Medium | Maximum step limits, circuit breakers |
| GitHub API rate limits | Low | Rate limiting, backoff/retry logic |
| Security: leaked tokens in logs | High | Token redaction, secure storage |
| Agent becomes unpredictable | Medium | Extensive logging, rollback capability |

## Next Steps

1. **Review this plan** with stakeholders and advisors
2. **Prototype Phase 0** with minimal agent runtime
3. **Test with simple mission** (issue triage)
4. **Iterate based on results** and expand capabilities
5. **Document learnings** to inform subsequent phases

This is a true agentic system that reasons, plans, and adapts—not just a command sequencer.
