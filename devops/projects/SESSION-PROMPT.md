# Project Session Prompt: Speculum Principum Development

Use this prompt to start or continue work on the Speculum Principum knowledge base extraction system.

---

## Session Initialization Prompt

```
I'm working on Speculum Principum, an automated knowledge base extraction system 
that uses GitHub Copilot agents to transform source materials into structured, 
IA-compliant knowledge repositories.

### Current Project State

**Repository:** terrence-giggy/speculum-principum
**Branch:** parse_the_prince
**Project Documentation:** devops/projects/

The project is divided into 4 development phases:

1. **Phase 1: Extraction Tooling** (devops/projects/phase-1-extraction-tooling/)
   - Isolated text extraction modules (concepts, entities, relationships)
   - Status: [Check PROGRESS.md]

2. **Phase 2: Information Architecture** (devops/projects/phase-2-information-architecture/)
   - IA methodology implementation with opinionated KB structure
   - Status: [Check PROGRESS.md]

3. **Phase 3: Knowledge Base Engine** (devops/projects/phase-3-knowledge-base-engine/)
   - Pipeline orchestration combining extraction + IA
   - Status: [Check PROGRESS.md]

4. **Phase 4: Agent Integration** (devops/projects/phase-4-agent-integration/)
   - Copilot agent workflows, MCP server, automation
   - Status: [Check PROGRESS.md]

### Session Instructions

1. **Read current phase documentation:**
   - Review the README.md for the phase I'm working on
   - Check PROGRESS.md to see what's already completed
   - Identify the next task in the sprint plan

2. **Today's work focus:**
   [SPECIFY: Which phase and which specific task/sprint you want to work on]
   
   Example: "I want to start Phase 1, Sprint 1: Foundation & Core Models"
   Example: "Continue Phase 2, Sprint 3: Structure & Metadata implementation"

3. **Development guidelines:**
   - Follow the architecture defined in the phase README
   - Write comprehensive tests (target >90% coverage)
   - Update PROGRESS.md when completing tasks
   - Document architectural decisions in PROGRESS.md Notes section
   - Create code in the locations specified in the phase documentation

4. **Session completion checklist:**
   - [ ] Code implemented and tested
   - [ ] Tests passing with good coverage
   - [ ] PROGRESS.md updated with:
     - Completed tasks checked off
     - New blockers/issues noted
     - Metrics updated
     - Architectural decisions documented
   - [ ] Code committed with descriptive message
   - [ ] Ready for next session or handoff

5. **End of session:**
   When this work session is complete, update PROGRESS.md with a summary of 
   what was accomplished and what should be done next. This allows the next 
   session (or another developer) to pick up where we left off.

### Key Principles

- **Modular:** Each phase builds on previous phases but maintains clean boundaries
- **Testable:** All code should have comprehensive unit tests
- **Documented:** Update PROGRESS.md as you complete tasks
- **IA-Driven:** Phase 2's Information Architecture methodology guides all decisions
- **Agent-Ready:** Build CLI tools that copilot agents can invoke

### Questions to Answer

Before starting, help me answer:
1. What is the current state of the phase I want to work on?
2. What dependencies are needed (check requirements.txt)?
3. What's the next logical task to complete?
4. Are there any blockers or design decisions needed?

Let's begin!
```

---

## Quick Start Templates

### Starting a New Phase

```
I'm starting [Phase X: Name] of Speculum Principum.

Please:
1. Read devops/projects/phase-X-[name]/README.md
2. Review devops/projects/phase-X-[name]/PROGRESS.md
3. Show me Sprint 1 tasks
4. Help me set up the initial directory structure
5. Guide me through the first implementation task

When we complete Sprint 1, update PROGRESS.md with completed tasks and metrics.
```

### Continuing Work on a Phase

```
I'm continuing work on [Phase X: Name] of Speculum Principum.

Please:
1. Read devops/projects/phase-X-[name]/PROGRESS.md
2. Show me what's completed and what's next
3. Check for any blockers or issues
4. Help me implement the next uncompleted task in the current sprint

When we complete this task, update PROGRESS.md with progress.
```

### Debugging or Refactoring

```
I need to debug/refactor [specific component] in [Phase X: Name] of Speculum Principum.

Context:
- Issue: [describe the problem]
- Location: [file/module path]
- Related phase: devops/projects/phase-X-[name]/

Please help me:
1. Understand the current implementation
2. Identify the issue
3. Fix it while maintaining test coverage
4. Update PROGRESS.md if this reveals new blockers or requires architectural changes
```

### Code Review / Quality Check

```
I want to review the quality of [Phase X: Name] implementation in Speculum Principum.

Please:
1. Check test coverage for phase X modules
2. Review code against the phase README specifications
3. Verify PROGRESS.md metrics are accurate
4. Identify any gaps or improvements needed
5. Update PROGRESS.md with findings
```

---

## PROGRESS.md Update Template

When completing work, update the relevant phase's PROGRESS.md:

```markdown
## Completed Tasks

### [Date] - [Sprint Name]
- ✅ [Task description]
  - Implementation: [brief notes]
  - Tests added: [test files]
  - Files changed: [list]
  
### Notes & Decisions

**[Date]**: [Architectural decision or important note]
- Rationale: [why]
- Impact: [what this affects]
- Alternatives considered: [other options]

## Blockers & Issues

**[Date]**: [Issue description]
- Status: [open/resolved]
- Impact: [high/medium/low]
- Resolution: [if resolved, what was done]

## Metrics

- **Test Coverage:** [updated percentage]
- **Modules Completed:** [X/total]
- **[Other relevant metrics]**
```

---

## Tips for Effective Sessions

1. **Start Small:** Pick one sprint or task per session
2. **Test as You Go:** Write tests alongside implementation
3. **Document Decisions:** Use PROGRESS.md Notes section for important choices
4. **Update Metrics:** Keep metrics current for tracking
5. **Commit Frequently:** Small, focused commits with clear messages
6. **End Clean:** Leave PROGRESS.md updated for next session

---

## Common Session Goals

- **Implementation Session:** Complete 1-2 modules with tests
- **Testing Session:** Improve coverage for existing code
- **Integration Session:** Connect multiple modules together
- **Documentation Session:** Improve docs, examples, guides
- **Refactoring Session:** Improve code quality without changing behavior
- **Bug Fix Session:** Address issues from testing or usage

---

## File Quick Reference

- **Phase Specs:** `devops/projects/phase-X-[name]/README.md`
- **Progress Tracking:** `devops/projects/phase-X-[name]/PROGRESS.md`
- **Master Roadmap:** `devops/projects/README.md`
- **Main CLI:** `main.py`
- **Current Parsing:** `src/parsing/`
- **Tests:** `tests/`
- **Config:** `config/` (to be created per phase)

---

**Remember:** The goal is incremental progress with clear documentation. Each session 
should leave the project in a state where someone else (or future you) can easily 
continue the work.
