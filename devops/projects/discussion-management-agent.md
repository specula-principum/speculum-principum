# Discussion Management Agent Project Plan

**Project Start Date:** 2025-11-27  
**Status:** Complete  
**Branch:** `feature/discussion-management-agent`

## Overview

Implement a GitHub Discussions management agent that populates repository discussions with extracted knowledge base content. Each person and organization from the knowledge graph will have a dedicated discussion containing their associated concepts and relationships.

## Problem Statement

The extracted knowledge base currently stores profiles, associations, and concepts in JSON files under `knowledge-graph/`. This data is not easily discoverable or browsable. GitHub Discussions provides a natural interface for collaborative exploration and annotation of this knowledge.

## Architecture

### Discussion Structure

```
Discussion Category: "People" or "Organizations"
Discussion Title: Entity name (e.g., "Niccolo Machiavelli")
Discussion Body: Markdown-formatted analysis document
  - Entity summary
  - Attributes table
  - Associations list (with relationship type and evidence)
  - Related concepts
  - Source mentions
  - Confidence score
Comment: Changelog entry for each update
```

### Component Map

```
src/integrations/github/
├── discussions.py          # NEW: GitHub Discussions GraphQL client
├── issues.py               # Existing: Reference for API patterns

src/orchestration/
├── toolkit/
│   └── discussion_tools.py # NEW: Tool definitions for agent
├── agent.py                # Existing: AgentRuntime

config/missions/
├── sync_discussions.yaml   # NEW: Mission configuration

tests/integrations/github/
├── test_discussions.py     # NEW: Unit tests for discussions module
tests/orchestration/
├── test_discussion_tools.py # NEW: Tool registration tests
```

## Implementation Phases

### Phase 1: GitHub Discussions API Client

**Goal:** Create a robust GraphQL client for GitHub Discussions CRUD operations.

**Tasks:**

1. [x] **Create `src/integrations/github/discussions.py`**
   - Repository ID resolution via GraphQL
   - Category CRUD: list, get, create
   - Discussion CRUD: list, search, get, create, update
   - Comment operations: list, create
   - Data classes: `DiscussionCategory`, `Discussion`, `DiscussionComment`

2. [x] **GraphQL Queries to Implement**
   - `repositoryId` - Get repository node ID
   - `discussionCategories` - List available categories
   - `createDiscussionCategory` - Create new category (requires admin)
   - `discussions` - Search/filter discussions
   - `discussion` - Get single discussion by number
   - `createDiscussion` - Create new discussion
   - `updateDiscussion` - Update discussion body
   - `addDiscussionComment` - Add comment to discussion

3. [x] **Unit Tests**
   - Mock GraphQL responses
   - Test error handling for API failures
   - Test data class serialization

**Estimated Effort:** 4-6 hours

### Phase 2: Knowledge Graph Reader

**Goal:** Create utilities to aggregate knowledge from multiple source checksums into unified entity views.

**Tasks:**

1. [x] **Create `src/knowledge/aggregation.py`**
   - `list_all_checksums()` - Enumerate all source documents
   - `get_all_profiles()` - Aggregate profiles across sources
   - `get_profiles_by_entity(name, entity_type)` - Find all profiles for an entity
   - `get_associations_for_entity(name)` - Find associations where entity is source/target
   - `build_entity_discussion_content(name, entity_type)` - Generate markdown body

2. [x] **Markdown Generation**
   - Template for discussion body
   - Format associations with evidence
   - Format attributes as tables
   - Include confidence scores
   - Reference source checksums

3. [x] **Unit Tests**
   - Test profile aggregation
   - Test markdown generation
   - Test empty knowledge graph handling

**Estimated Effort:** 3-4 hours

### Phase 3: Discussion Tools for Agent

**Goal:** Register discussion operations as orchestration tools.

**Tasks:**

1. [x] **Create `src/orchestration/toolkit/discussion_tools.py`**
   - `ensure_category_exists` - Find or create discussion category
   - `find_discussion_by_title` - Search for existing discussion
   - `create_discussion` - Create new discussion
   - `update_discussion` - Update discussion body
   - `add_changelog_comment` - Post update notification
   - `sync_entity_discussion` - Composite: full sync for one entity

2. [x] **Tool Risk Classifications**
   - `find_*`, `get_*` → `SAFE`
   - `create_*`, `update_*`, `add_*` → `REVIEW`

3. [x] **Register Tools**
   - Add to tool registry in `src/orchestration/tools.py`
   - Define parameter schemas

4. [x] **Unit Tests**
   - Mock knowledge graph and GitHub API
   - Test tool invocation flow

**Estimated Effort:** 4-5 hours

### Phase 4: Mission Configuration

**Goal:** Define the autonomous agent mission for syncing discussions.

**Tasks:**

1. [x] **Create `config/missions/sync_discussions.yaml`**
   ```yaml
   name: sync_discussions
   description: Sync knowledge graph entities to GitHub Discussions
   objective: |
     For each person and organization in the knowledge graph,
     ensure a corresponding GitHub Discussion exists with
     up-to-date content reflecting associations and concepts.
   max_steps: 100  # Allow processing many entities
   success_criteria:
     - All entities have corresponding discussions
     - Discussion bodies reflect current knowledge graph state
   available_tools:
     - ensure_category_exists
     - find_discussion_by_title
     - create_discussion
     - update_discussion
     - add_changelog_comment
     - list_entities  # Read from knowledge graph
   ```

2. [x] **Add CLI Entry Point**
   - `main.py sync-discussions` command
   - Options: `--entity-type`, `--entity-name`, `--dry-run`
   - Also added `main.py list-entities` utility command

3. [x] **Integration Tests**
   - Test mission loading
   - Test CLI command registration
   - Test sync workflow (dry-run, create, update, skip unchanged)

**Estimated Effort:** 2-3 hours

### Phase 5: End-to-End Testing & Documentation

**Goal:** Validate the complete workflow and document usage.

**Tasks:**

1. [x] **Integration Testing**
   - Test against real GitHub API (with test repo)
   - Verify idempotent behavior (run twice → no duplicate discussions)
   - Test update detection (only comment when content changes)

2. [x] **Documentation**
   - Update `README.md` with discussions feature
   - Add `docs/guides/discussion-sync.md`
   - Document required GitHub permissions (discussions:write)

3. [x] **Error Handling**
   - Rate limiting recovery
   - Network failure retry
   - Partial failure reporting

**Estimated Effort:** 3-4 hours

## GitHub Discussions GraphQL API Reference

### Key Mutations

```graphql
# Create category (requires admin)
mutation {
  createDiscussionCategory(input: {
    repositoryId: "...",
    name: "People",
    format: OPEN,
    description: "Profiles of historical figures"
  }) {
    category { id name }
  }
}

# Create discussion
mutation {
  createDiscussion(input: {
    repositoryId: "...",
    categoryId: "...",
    title: "Niccolo Machiavelli",
    body: "..."
  }) {
    discussion { id number url }
  }
}

# Update discussion
mutation {
  updateDiscussion(input: {
    discussionId: "...",
    body: "..."
  }) {
    discussion { id }
  }
}

# Add comment
mutation {
  addDiscussionComment(input: {
    discussionId: "...",
    body: "Updated: 2025-11-27..."
  }) {
    comment { id }
  }
}
```

### Key Queries

```graphql
# Get repository ID and categories
query {
  repository(owner: "terrence-giggy", name: "speculum-principum") {
    id
    discussionCategories(first: 20) {
      nodes { id name slug }
    }
  }
}

# Search discussions by title
query {
  repository(owner: "terrence-giggy", name: "speculum-principum") {
    discussions(first: 10, categoryId: "...", query: "Machiavelli") {
      nodes { id number title }
    }
  }
}
```

## Dependencies

### Existing Components (No Changes Needed)
- `src/integrations/github/issues.py` - GraphQL patterns to follow
- `src/knowledge/storage.py` - Knowledge graph data access
- `src/orchestration/agent.py` - Agent runtime
- `src/orchestration/tools.py` - Tool registration

### New Dependencies
- None (uses stdlib `urllib` like existing GitHub integration)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Category creation requires admin | High | Pre-create categories manually or document admin setup |
| API rate limiting | Medium | Add retry logic with exponential backoff |
| Large knowledge graphs | Medium | Batch processing with progress tracking |
| Duplicate detection failure | Medium | Use consistent title format for reliable search |

## Success Metrics

1. ✅ All persons/organizations have corresponding discussions
2. ✅ Discussion content matches knowledge graph state
3. ✅ Idempotent execution (safe to run repeatedly)
4. ✅ Changelog comments track update history
5. ✅ Agent can run autonomously without manual intervention

## Session Checkpoints

Use these checkpoints to resume work across sessions:

- [x] **Checkpoint 1:** `discussions.py` client complete with tests
- [x] **Checkpoint 2:** `aggregation.py` knowledge reader complete with tests
- [x] **Checkpoint 3:** `discussion_tools.py` registered with tests
- [x] **Checkpoint 4:** Mission YAML and CLI entry point working
- [x] **Checkpoint 5:** End-to-end sync tested with integration tests, documentation complete

## Notes

- GitHub Discussions uses **GraphQL only** (no REST API)
- Category format options: `OPEN`, `ANNOUNCEMENT`, `POLL`
- Discussion search is full-text, title-specific search uses `in:title` qualifier
- The agent should detect content changes to avoid unnecessary updates
