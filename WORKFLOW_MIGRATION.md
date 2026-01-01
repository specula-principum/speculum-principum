# Workflow Reorganization - December 31, 2025

## Summary

Reorganized all 15 GitHub workflow files from a numbered prefix system to a functional category system for improved clarity and discoverability.

## File Renames

| Old Filename | New Filename | New Display Name |
|--------------|--------------|------------------|
| `test.yml` | `ci-test.yml` | CI: Test Suite |
| `1-setup-initialize-repo.yml` | `template-initialize.yml` | Template: Initialize Clone |
| `1-setup-sync-from-upstream.yml` | `template-sync-downstream.yml` | Template: Sync from Upstream |
| `3-mgmt-notify-downstream.yml` | `template-notify-clones.yml` | Template: Notify Downstream Clones |
| `4-auto-merge-sync-prs.yml` | `template-validate-sync-pr.yml` | Template: Validate & Auto-Merge Sync PRs |
| `2-op-parse-and-extract.yml` | `content-parse-extract.yml` | Content: Parse & Extract Entities |
| `2-op-assess-source.yml` | `content-assess-source.yml` | Content: AI Assessment |
| `2-op-curate-sources.yml` | `content-curate-approve.yml` | Content: Curate & Approve |
| `2-op-implement-source.yml` | `content-implement-source.yml` | Content: Implement Approved Source |
| `5-op-content-pipeline.yml` | `content-monitor-acquire.yml` | Content: Monitor & Acquire |
| `2-op-sync-discussions.yml` | `content-sync-to-discussions.yml` | Content: Sync to GitHub Discussions |
| `2-op-answer-question.yml` | `agent-answer-question.yml` | Agent: Answer Questions |
| `2-op-generate-plan.yml` | `agent-generate-plan.yml` | Agent: Generate Research Plan |
| `2-op-setup-agent.yml` | `agent-interactive-setup.yml` | Agent: Interactive Setup |
| `copilot-setup-steps.yml` | `infra-copilot-dependencies.yml` | Infrastructure: Copilot Dependencies |

## New Categorization System

Workflows are now organized into 5 functional categories:

### 1. CI (`ci-*`)
- **ci-test.yml**: Run pytest suite on PRs and main branch pushes

### 2. Template Management (`template-*`)
- **template-initialize.yml**: Initialize new research repository clones
- **template-sync-downstream.yml**: Sync code updates from template to clones
- **template-notify-clones.yml**: Notify downstream clones of new releases
- **template-validate-sync-pr.yml**: Validate and auto-merge upstream sync PRs

### 3. Content Processing (`content-*`)
- **content-parse-extract.yml**: Parse documents and extract entities
- **content-assess-source.yml**: AI assessment of source proposals
- **content-curate-approve.yml**: Handle source approval/rejection commands
- **content-implement-source.yml**: Implement approved sources into knowledge graph
- **content-monitor-acquire.yml**: Monitor sources and acquire new content
- **content-sync-to-discussions.yml**: Sync entities to GitHub Discussions

### 4. Interactive Agents (`agent-*`)
- **agent-answer-question.yml**: AI-powered question answering
- **agent-generate-plan.yml**: Generate research plans
- **agent-interactive-setup.yml**: Interactive setup assistance

### 5. Infrastructure (`infra-*`)
- **infra-copilot-dependencies.yml**: Pre-install dependencies for Copilot agent

## Files Updated

### Workflow Files (15 files)
- All workflow files renamed and display names updated

### Issue Templates (2 files)
- `.github/ISSUE_TEMPLATE/parse-and-extract.md`: Updated workflow name reference
- `.github/ISSUE_TEMPLATE/source-proposal.md`: Updated workflow name reference

### Documentation (4 files)
- `README.md`: Updated workflow name references
- `docs/guides/upstream-sync.md`: Updated workflow name references
- `docs/guides/content-pipeline.md`: Updated workflow file path
- `docs/guides/crawler-agent.md`: Updated workflow file path with migration note
- `docs/guides/monitor-agent.md`: Updated workflow file path with migration note

### Self-References (1 file)
- `infra-copilot-dependencies.yml`: Updated path trigger to reference new filename

## Benefits

1. **Clear Functional Grouping**: Workflows appear in logical categories when sorted alphabetically
2. **Improved Discoverability**: New contributors can understand purpose at a glance
3. **Eliminated Confusion**: Removed misleading numeric prefixes (8 workflows sharing "2. Op:")
4. **Future-Proof**: Easy to add new workflows within existing categories
5. **Consistent Naming**: Category prefix + descriptive name pattern

## Validation

- ✅ All 15 workflow YAML files validated successfully
- ✅ All cross-references updated
- ✅ No workflow triggers affected
- ✅ Job names preserved (especially `copilot-setup-steps` requirement)

## Migration Notes

- Historical workflow runs will still show old names
- Alphabetical sorting now groups workflows by category
- No functional changes to workflow behavior
- All triggers, permissions, and jobs remain unchanged
