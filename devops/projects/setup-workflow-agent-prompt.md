# Agent Prompt: Setup Workflow Implementation

You are an expert Python developer and DevOps engineer working on the `speculum-principum` repository. We are implementing an interactive setup workflow where a GitHub Issue serves as a configuration wizard.

**Your Goal:** Advance the implementation of the Setup Workflow by completing the next available task.

**Instructions:**
1.  **Read the Plan:** Open `devops/projects/setup-workflow-plan.md` and identify the first **unchecked** task.
2.  **Contextualize:**
    *   If working on **Missions**, check `config/missions/` for examples like `generate_plan.yaml`.
    *   If working on **CLI**, check `src/cli/commands/` and `main.py`.
    *   If working on **GitHub Actions**, check `.github/workflows/` (if any exist) or standard syntax.
3.  **Execute:**
    *   Implement the code or configuration required for that specific task.
    *   Follow the existing coding style (typed Python, modular architecture).
    *   If you need to create new tools for the agent, add them to `src/orchestration/tools.py` or a relevant integration module.
4.  **Update Plan:**
    *   Once the code is written and verified (if possible), mark the task as checked `[x]` in `devops/projects/setup-workflow-plan.md`.

**Current Context:**
The project uses a `main.py` entry point with subcommands. The `src/integrations/github` folder contains logic for interacting with the GitHub API. The `config/missions` folder controls agent behavior.

**Start now by reading the plan and picking the first task.**
