# Agent Triage Mission - Analysis and Improvements

## Problem Summary

The `triage_new_issue` mission was completing successfully but not performing any meaningful actions. Analysis of the execution transcript revealed several root causes:

### Root Causes

1. **Missing Tool Registration**
   - The mission configuration listed `add_label`, `remove_label`, and `post_comment` as allowed tools
   - However, these mutation tools were **not registered** in the `ToolRegistry` during agent initialization
   - Only read-only tools (like `get_issue_details`) were available to the agent
   - Result: The agent could only fetch issue data but couldn't take any actions

2. **Unclear Mission Expectations**
   - The mission goal was vague: "synthesize a short summary and determine which workflow should handle it"
   - Success criteria were passive: "A summary with recommended next steps has been produced"
   - No explicit requirement to **add labels** or **post comments**
   - Result: The agent completed by just reading the issue and finishing

3. **Inadequate Output Visibility**
   - The console output only showed: "Mission completed: succeeded" and "Steps executed: 1"
   - The transcript JSON didn't clearly show the agent's reasoning process
   - Result: Operators couldn't easily see what the agent analyzed or decided

## Changes Made

### 1. Tool Registration Fix

**File: `src/orchestration/toolkit/__init__.py`**
```python
# Added export of mutation tools registration function
from .github import (
    register_github_mutation_tools,  # NEW
    register_github_pr_tools,
    register_github_read_only_tools,
)
```

**File: `src/cli/commands/agent.py`**
```python
# Now registers mutation tools during agent setup
from src.orchestration.toolkit import (
    register_github_mutation_tools,  # NEW
    ...
)

register_github_read_only_tools(registry)
register_github_mutation_tools(registry)  # NEW - enables add_label, post_comment, etc.
register_github_pr_tools(registry)
```

**Impact:** The agent now has access to `add_label`, `remove_label`, and `post_comment` tools as intended.

### 2. Mission Configuration Improvements

**File: `config/missions/triage_new_issue.yaml`**

**Changed the goal** to be explicit about required actions:
```yaml
goal: |
  Read the incoming GitHub issue, synthesize a short summary, and determine
  which workflow should handle it...
  
  Actions Required:
  1. Fetch the issue details and analyze the content
  2. Classify the issue type based on its content:
     - Documentation bug: reports errors in docs
     - Feature request: proposes new functionality
     - Bug report: describes unexpected behavior
     - Other: needs human review
  3. Add appropriate label(s) to the issue
  4. Post a comment summarizing your analysis and recommended next steps
```

**Updated success criteria** to require concrete actions:
```yaml
success_criteria:
  - Issue metadata has been retrieved successfully.
  - Issue type has been classified (documentation, enhancement, bug, or needs-triage).
  - At least one appropriate label has been added to the issue.
  - A comment has been posted summarizing the analysis and recommended next steps.
  - The transcript contains a clear summary of the classification decision and reasoning.
```

**Updated constraints** to remove read-only restriction:
```yaml
constraints:
  - Only add labels that actually exist in the repository.
  - Cite specific evidence from the issue body when explaining classification.
  - If classification is uncertain, use "needs-triage" label and explain why.
  - Keep comments professional and constructive.
```

**Increased max_steps:** From 7 to 10 to allow for multiple actions.

**Impact:** The agent now has clear, actionable requirements and will not complete until it has added labels and posted a comment.

### 3. Enhanced Console Output

**File: `src/cli/commands/agent.py`**

Added detailed execution trace to console output:
```python
# Show step-by-step breakdown
if outcome.steps:
    print("\nExecution trace:")
    for i, step in enumerate(outcome.steps, 1):
        thought = step.thought
        result = step.result
        print(f"\n  Step {i}:")
        if thought.content:
            print(f"    Reasoning: {thought.content}")
        if thought.tool_call:
            print(f"    Tool: {thought.tool_call.name}")
            print(f"    Arguments: {json.dumps(thought.tool_call.arguments, indent=6)}")
        if result:
            if result.success:
                print(f"    Result: ✓ Success")
            else:
                print(f"    Result: ✗ Failed")
```

**Impact:** Operators can now see each step the agent takes, including:
- The agent's reasoning for each action
- Which tool was called and with what arguments
- Whether the action succeeded or failed
- A clear execution trace for debugging

## Expected Behavior After Changes

When running `agent run --mission config/missions/triage_new_issue.yaml --input issue_number=118`, the agent should now:

1. **Fetch issue #118** using `get_issue_details`
2. **Analyze the content** to classify it as a bug report (based on "Error in..." and the stack trace)
3. **Add the "bug" label** using `add_label`
4. **Post a comment** using `post_comment` with:
   - Summary of what the issue is about
   - Classification as bug report
   - Recommended next steps (e.g., "This will be prioritized for the next sprint")
5. **Complete successfully** with all success criteria met

The console output will show:
```
Mission completed: succeeded
Steps executed: 3-4

Execution trace:

  Step 1:
    Reasoning: Fetching issue details to analyze content
    Tool: get_issue_details
    Arguments: {"issue_number": 118}
    Result: ✓ Success

  Step 2:
    Reasoning: Issue describes unexpected behavior and includes error logs - classifying as bug
    Tool: add_label
    Arguments: {"issue_number": 118, "labels": ["bug"]}
    Result: ✓ Success

  Step 3:
    Reasoning: Posting analysis summary for team visibility
    Tool: post_comment
    Arguments: {
      "issue_number": 118,
      "body": "..."
    }
    Result: ✓ Success

Summary: Successfully triaged issue #118 as bug report
```

## Testing Recommendations

1. **Run the updated mission:**
   ```bash
   python -m main agent run --mission triage_new_issue --input issue_number=118
   ```

2. **Verify on GitHub that:**
   - The issue has a new label (e.g., "bug")
   - A comment was posted with the agent's analysis

3. **Check the transcript JSON** to ensure it captures:
   - All steps taken
   - The reasoning for each action
   - The final summary

4. **Monitor for edge cases:**
   - Issues that are ambiguous in classification
   - Issues with unusual formatting or missing content
   - Rate limiting from GitHub API

## Additional Improvements to Consider

1. **Mission-specific tool registration:** Instead of registering all tools globally, have missions declare their required tools and only register those.

2. **Approval workflow for mutations:** For sensitive operations, add `requires_approval: true` and implement interactive approval prompts.

3. **Label validation:** Before adding labels, query GitHub to ensure they exist in the repository.

4. **Better error handling:** If label addition fails (e.g., label doesn't exist), fall back to "needs-triage" and explain in the comment.

5. **Structured output:** Have the agent output a structured classification result that can be consumed by downstream automation.

6. **Metrics and monitoring:** Track classification accuracy, average triage time, and manual override frequency.

## Related Files

- Mission config: `config/missions/triage_new_issue.yaml`
- Tool registration: `src/orchestration/toolkit/github.py`
- Agent CLI: `src/cli/commands/agent.py`
- LLM Planner: `src/orchestration/llm.py`
- GitHub issues API: `src/integrations/github/issues.py`

## References

- Agent operations guide: `docs/guides/agent-operations.md`
- Mission schema: `config/mission.schema.yaml`
- Original issue: GitHub #118
