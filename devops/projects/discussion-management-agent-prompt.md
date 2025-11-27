# Discussion Management Agent - Session Prompt

Use this prompt to resume work on the Discussion Management Agent project.

---

## Prompt

```
I'm working on the Discussion Management Agent feature for this repository. Please review the project plan at `devops/projects/discussion-management-agent.md` and:

1. Check off any completed tasks in the plan
2. Identify the next open checkpoint/phase
3. Implement the next incomplete task

The project creates an orchestration agent that syncs knowledge graph entities (people and organizations) to GitHub Discussions, with their associations and concepts as content.

Key files to reference:
- Project plan: `devops/projects/discussion-management-agent.md`
- GitHub API patterns: `src/integrations/github/issues.py`
- Knowledge storage: `src/knowledge/storage.py`
- Orchestration tools: `src/orchestration/tools.py`

Continue from where we left off.
```

---

## Quick Status Check

Before starting, verify current state:

```bash
# Check if discussions.py exists
ls -la src/integrations/github/discussions.py 2>/dev/null || echo "Phase 1 not started"

# Check if aggregation.py exists  
ls -la src/knowledge/aggregation.py 2>/dev/null || echo "Phase 2 not started"

# Check if discussion_tools.py exists
ls -la src/orchestration/toolkit/discussion_tools.py 2>/dev/null || echo "Phase 3 not started"

# Check if mission config exists
ls -la config/missions/sync_discussions.yaml 2>/dev/null || echo "Phase 4 not started"
```
