# Speculum Principum Session Prompts

Use these ready-to-paste prompts with the current phase `README.md` and `PROGRESS.md` attached so the assistant has full context.

---

## Project Snapshot

- **Repository:** terrence-giggy/speculum-principum (branch `parse_the_prince`)
- **Phases:** Extraction Tooling, Information Architecture, Knowledge Base Engine, Agent Integration
- **Phase Status:** All phases planned, sprint backlogs defined in each `PROGRESS.md`
- **Primary Goal:** Automated IA-driven knowledge base extraction with >90% test coverage expectations per phase

---

## Prompt 1: Build Session (Start or Continue Work)

```
I'm working on Speculum Principum, the IA-driven knowledge base extraction project.

Attachments:
- Current phase README (devops/projects/phase-3-knowledge-base-engine/README.md)
- Current phase PROGRESS log (devops/projects/phase-3-knowledge-base-engine/PROGRESS.md)

Please:
1. Summarize the attached phase README and PROGRESS files so I understand scope, status, and outstanding sprint items.
2. Confirm the most relevant next task for the current sprint backlog and outline a step-by-step plan to deliver it with tests (target >90% coverage where practical).
3. Highlight any prerequisites, dependencies, or open design decisions pulled from the docs.
4. Walk me through implementing the task, including code locations (e.g., src/, tests/, config/), test strategy, and validation steps.
5. When work is complete, draft the PROGRESS.md updates (checked tasks, notes/decisions, metrics) and summarize recommended git commit contents.
6. Call out remaining risks, blockers, or follow-up tasks for the next session.

Throughout the session, enforce the architectural guidance from the README and keep PROGRESS.md synchronized with actual changes.
```

---

## Prompt 2: Code Review Session

```
I need a focused code review for the Speculum Principum project.

Attachments:
- Relevant phase README (devops/projects/phase-3-knowledge-base-engine/README.md)
- Relevant phase PROGRESS log (devops/projects/phase-3-knowledge-base-engine/PROGRESS.md)
- Any recent PR diff or list of changed files (if available)

Please:
1. Summarize the phase objectives and current sprint commitments from the attachments.
2. Review the provided code changes against the phase architecture and sprint goals, identifying correctness issues, regressions, test gaps, or guideline violations.
3. Check that PROGRESS.md metrics and checkboxes reflect the actual implementation; note discrepancies.
4. Recommend fixes or improvements, ordered by severity, and point to precise files/lines or modules.
5. Suggest additional tests, documentation updates, or follow-up tasks needed before sign-off.
6. Provide a concise handoff note capturing overall quality, outstanding risks, and next actions.

Keep the feedback specific, actionable, and aligned with the IA and automation goals.
```

---

**Tip:** Always attach the matching phase README and PROGRESS files so the assistant can ground its guidance in the latest plan and metrics.
