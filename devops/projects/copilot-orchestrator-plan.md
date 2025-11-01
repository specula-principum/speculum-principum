# Copilot Orchestrator Project Plan

## Working Principles
- Favor incremental automation over comprehensive refactors. Ship the smallest slice that delivers value, then iterate.
- Keep human administrators in the loop for subjective decisions (tone, policy, or legal calls).
- Prefer existing helpers in `src/integrations/github` and knowledge base modules rather than reinventing clients.
- Document assumptions and open questions in the progress log before expanding scope.
- Stop and request guidance if requirements conflict or if a feature exceeds the current phase objectives.

## Phase 0 – Orientation & Constraints
**Objectives**
- Review current GitHub integration helpers, Copilot tooling, and knowledge base pipeline capabilities.
- Confirm required environment variables, tokens, and GitHub repository settings.
- Capture any policy, moderation, or content guidelines relevant to repository interactions.

**Agent Instructions**
1. Read `README.md`, `.github/copilot-instructions.md`, and existing CLI command modules.
2. Inventory the GitHub REST actions already implemented; note gaps for labeling, commenting, closing, locking, or triage support.
3. Record constraints, unanswered questions, and risks in the progress document.

**Guardrails**
- Do not alter code in this phase; information gathering only.
- Do not design new sub-systems without explicit requirements.

## Phase 1 – GitHub Workflow Extensions
**Objectives**
- Expand the GitHub integration layer to cover missing issue and pull-request mutations required by the orchestrator.

**Agent Instructions**
1. Add lightweight wrappers for: applying/removing labels, posting issue comments, updating issue bodies, locking/closing issues, fetching unlabeled issue lists, and reviewing/merging PRs.
2. Follow existing module patterns (`assign_copilot`, `issues`, `search_issues`) for error handling and token resolution.
3. Introduce unit tests with mocked HTTP responses to prevent live API calls.

**Guardrails**
- Keep helpers narrowly focused; avoid generic GitHub clients or SDK abstractions.
- Skip OAuth/device flow implementations—reuse PAT-based auth expectations.

## Phase 2 – Issue Orchestration Core
**Objectives**
- Implement the core orchestrator responsible for triaging unlabeled issues and routing them down defined paths.

**Agent Instructions**
1. Create a new package under `src/orchestration/` (or similarly named) to host orchestration logic, keeping integrations separate.
2. Implement classifiers that tag issues as: document ingestion, admin review, moderation response, or Copilot-ready. Document heuristics and keep them simple (keywords, templates, or label hints).
3. Provide handler functions per path:
   - Document ingestion → apply KB-related labels, create/update structured issue templates, and notify responsible parties.
   - Admin review → assign to configured maintainer and leave a summary comment.
   - Moderation → post calm, policy-aligned responses, hide or lock when required, then close.
   - Copilot-ready → ensure template compliance, add `ready-for-copilot`, and optionally queue for automation.
4. Ensure actions are idempotent: re-running should not duplicate comments or labels.
5. Log each decision (stdout or structured result) for auditability.

**Guardrails**
- Avoid machine-learning classifiers; rely on deterministic checks that are easy to adjust.
- Do not roll out automatic assignment to humans without configuration flags.

## Phase 3 – Pull Request Automation
**Objectives**
- Automatically approve and merge PRs that only add knowledge-base content.

**Agent Instructions**
1. Use GitHub API endpoints to list open PRs and fetch file diffs.
2. Verify all modified files live within `knowledge-base/` and contain additive Markdown changes (no deletions outside front matter updates).
3. When criteria are met, post an approval review and merge using the repository’s preferred strategy (default: squash).
4. Record actions in logs and the progress tracker.

**Guardrails**
- Abort if diff parsing detects binary changes or non-Markdown files.
- Never force merge; respect branch protection errors and emit a warning instead.

## Phase 4 – CLI & Task Integration
**Objectives**
- Expose orchestrator capabilities via the CLI and VS Code task runner.

**Agent Instructions**
1. Add `copilot orchestrate` subcommand beneath `python -m main`, accepting options for dry runs, explicit issue/PR targets, and classification overrides.
2. Compose a VS Code task that initializes MCP tooling (e.g., `python -m main copilot mcp-serve --list-tools`) and then runs the orchestrator loop followed by the existing `run-agent` command targeting `ready-for-copilot` issues.
3. Provide concise CLI help text and examples.

**Guardrails**
- Keep task commands serial and human-readable; avoid introducing background daemons unless requested.
- Ensure the orchestrator dry-run mode does not mutate GitHub state.

## Phase 5 – Validation & Feedback Loop
**Objectives**
- Confirm orchestrator reliability and capture improvement ideas.

**Agent Instructions**
1. Add integration-style tests using fixtures or fake clients for classification and action sequencing.
2. Document manual verification steps (e.g., running in dry-run mode against a test repository).
3. Update the progress tracker with outcomes, open questions, and follow-up tasks.

**Guardrails**
- Focus on core flows; defer edge-case handling to future phases.
- Keep feedback actionable and tied to user value.
