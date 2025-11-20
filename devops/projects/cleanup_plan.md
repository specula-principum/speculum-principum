# Project Cleanup Plan

This document tracks components identified for removal to streamline the project and remove dependencies on tools incompatible with the target environment (GitHub Actions).

## 1. Copilot CLI Planner & Integration

**Rationale:**
The `CopilotCLIPlanner` relies on the `gh copilot` CLI tool. This tool is designed for interactive local use and is not suitable for automated environments like GitHub Actions. The project should rely on the `LLMPlanner` which uses the GitHub Models API directly.

**Components to Remove:**

*   **Source Code:**
    *   `src/orchestration/copilot_cli_planner.py`: The planner implementation wrapping the CLI.
    *   `src/mcp_server/`: The Model Context Protocol server used solely by the CLI planner to access local tools.
    *   `src/integrations/github/assign_copilot.py`: Integration for assigning Copilot agents (if confirmed unused by other parts).
    *   `devops/scripts/setup_copilot_cli.py`: Setup script for the CLI integration.

*   **CLI Commands:**
    *   Remove `--planner copilot-cli` option from `src/cli/commands/agent.py`.
    *   Remove `--copilot-bin` option from `src/cli/commands/agent.py`.
    *   Remove `assign-copilot` (or similar) command from `src/cli/commands/github.py` and its usage of `run_issue_with_local_copilot`.

*   **Tests:**
    *   Any tests specifically targeting `CopilotCLIPlanner` or `mcp_server`.

*   **Documentation:**
    *   `docs/guides/copilot-cli-implementation-summary.md`
    *   `docs/guides/copilot-cli-integration.md`
    *   `docs/guides/transcript-format-updates.md` (Contains references to `copilot-cli` planner types)
    *   References in `README.md` or other guides.

## 2. Deterministic Planner

**Rationale:**
The `DeterministicPlanner` is primarily a testing utility that executes a fixed sequence of steps. It is not used for dynamic, AI-driven decision making and adds unnecessary code surface area to the production runtime.

**Components to Remove:**

*   **Source Code:**
    *   `src/orchestration/planner.py`: Remove `DeterministicPlanner`, `DeterministicPlan`, `PlanStep`, and `load_deterministic_plan`. (Keep the base `Planner` interface).

*   **CLI Commands:**
    *   Remove `--planner deterministic` option from `src/cli/commands/agent.py`.

*   **Tests:**
    *   Tests relying solely on `DeterministicPlanner` (e.g., parts of `tests/orchestration/test_agent_runtime.py`).

## 3. Strict Mission YAML Requirement (Refactor)

**Rationale:**
Requiring a pre-defined YAML file for every mission is a barrier to simple, ad-hoc tasks. While not a component removal per se, removing this strict requirement allows for a more flexible "script mode" where goals can be passed directly.

**Changes:**
*   Refactor `src/cli/commands/agent.py` to accept a goal string directly instead of requiring a mission file.
*   Refactor `src/orchestration/missions.py` to allow creating ephemeral `Mission` objects from arguments.
