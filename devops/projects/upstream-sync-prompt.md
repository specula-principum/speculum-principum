# Upstream Sync Implementation - Session Prompt

Copy and paste the following prompt to start or resume work on this project:

---

## Session Start Prompt

```
I'm continuing work on the upstream sync implementation for speculum-principum.

Context:
- This project is a template repo that gets cloned for research topics
- Cloned repos need to receive code updates from this base repo
- All operations must work on GitHub.com (no local git) using Actions and API
- Forks don't work (can't fork into same account multiple times)
- Templates don't maintain upstream relationship

Solution: GitHub Actions workflow that uses GitHub API to sync code directories from upstream

Plan document: devops/projects/upstream-sync-implementation.md

Please:
1. Read the plan document to see current progress
2. Check off any completed tasks
3. Continue with the next uncompleted task
4. Update the session log at the bottom of the plan when done
```

---

## Quick Reference

### Key Files
- Plan: `devops/projects/upstream-sync-implementation.md`
- Existing GitHub utils: `src/integrations/github/api.py`
- Setup mission: `config/missions/setup_repo.yaml`
- Setup workflow: `.github/workflows/setup-agent.yml`

### Directory Structure for Sync
**Sync FROM upstream (code):**
- `src/`
- `tests/`
- `.github/`
- `config/missions/`
- `docs/`
- `main.py`, `requirements.txt`, `pytest.ini`

**NEVER sync (research content):**
- `evidence/`
- `knowledge-graph/`
- `reports/`
- `dev_data/`

### Implementation Order
1. Create `sync-from-upstream.yml` workflow
2. Create `src/integrations/github/sync.py` utility
3. Update setup mission to store upstream URL
4. Add notification system (Phase 2)
5. Add conflict resolution (Phase 3)
6. Documentation (Phase 4)
