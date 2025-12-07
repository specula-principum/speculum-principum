# Repository Setup Workflow Implementation Plan

**Goal:** Implement an interactive "Onboarding Issue" workflow where an agent guides the user through configuring the repository after cloning. This replaces static documentation with an active setup mission.

## Phase 0: Repository Hygiene (Pre-requisite)
- [x] **Isolate Data from Code**
  - Move existing "seed" data (e.g., `evidence/Agriculture...`, `knowledge-graph/associations/...`) to a new directory `dev_data/`.
  - Place `.gitkeep` files in `evidence/`, `knowledge-graph/`, and `reports/` to preserve directory structure.
  - **Crucial:** Do *not* add these to `.gitignore`. The user needs to track their own data here.
  - **Why:** By keeping the upstream `main` branch empty of data files, we avoid merge conflicts when users pull updates, while still allowing them to commit their own evidence and knowledge graph.

## Phase 1: Mission Definition
- [x] **Create Setup Mission Configuration**
  - Create `config/missions/setup_repo.yaml`.
  - Define the goal: Gather configuration details (Source URL, Topic, Frequency) from the user via Issue comments.
  - Define success criteria: A Pull Request is created with the generated configuration.
  - Define allowed tools: `get_issue_comments`, `validate_url` (needs creation), `create_pull_request`, `commit_file`.

## Phase 2: CLI & Backend Logic
- [x] **Implement Bootstrap Command**
  - Add a `setup` subcommand to `src/cli/commands/`.
  - Implement the handler to create the initial "Project Configuration & Setup" issue.
  - Post the initial "Welcome" comment from the agent.
- [x] **Implement Configuration Tools**
  - Ensure the agent has a tool to validate a URL (e.g., `src/orchestration/tools.py` or `src/integrations/copilot/validation.py`).
  - Ensure the agent has a tool to generate the specific config files (likely `config/manifest.json` and `config/missions/*.yaml` updates).
- [x] **Implement Workspace Cleanup Logic**
  - Create a utility to clear `evidence/`, `knowledge-graph/`, and `reports/` (preserving `.gitkeep` or directory structure).
  - Expose this as a tool `clean_workspace` for the agent to call during setup.

## Phase 3: GitHub Action
- [x] **Create Workflow File**
  - Create `.github/workflows/initialize-repo.yml`.
  - Trigger: `workflow_dispatch` (Manual run by user after clone).
  - Steps:
    - Checkout code.
    - Setup Python environment.
    - Run `python -m main setup --repo ${{ github.repository }}`.
  - **(Added)** Create `.github/workflows/setup-agent.yml` to trigger the agent on issue comments.

## Phase 4: Agent Logic & Refinement
- [x] **Refine Agent Instructions**
  - Ensure the agent knows how to parse the user's natural language replies into structured JSON for the config.
  - Handle error cases (e.g., user provides an invalid URL).
- [x] **End-to-End Testing**
  - Verify the flow: Trigger Action -> Issue Created -> User Replies -> Agent Validates -> PR Created.
  - (Verified via code review and unit test simulation).
