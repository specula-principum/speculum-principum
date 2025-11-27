# Discussion Sync Guide

## Overview

The Discussion Sync feature allows you to automatically synchronize entities from the knowledge graph to GitHub Discussions. This creates a collaborative, browsable interface for exploring extracted entities and their relationships.

## Quick Start

```bash
# List entities in the knowledge graph
python -m main list-entities

# Dry run - preview what would be synced
python -m main sync-discussions --dry-run

# Sync all entities to discussions
python -m main sync-discussions

# Sync only a specific entity type
python -m main sync-discussions --entity-type Person

# Sync a single entity
python -m main sync-discussions --entity-name "Niccolo Machiavelli"
```

## Prerequisites

### 1. GitHub Token

You need a GitHub token with the following permissions:
- `repo` - Full repository access
- `discussions` - Read and write access to discussions

Set the token in your environment:

```bash
export GITHUB_TOKEN="ghp_your_token_here"
# or
export GH_TOKEN="ghp_your_token_here"
```

### 2. Repository Configuration

Set the target repository:

```bash
export GITHUB_REPOSITORY="owner/repo"
# or
export GH_REPOSITORY="owner/repo"
```

### 3. Discussion Categories

Before syncing, you must create the following discussion categories in your GitHub repository settings:

1. **People** - For person entity profiles
2. **Organizations** - For organization entity profiles

To create categories:
1. Go to your repository's Settings → Features → Discussions
2. Enable Discussions if not already enabled
3. Click "Set up discussions"
4. Add the "People" and "Organizations" categories

## CLI Commands

### `list-entities`

List all entities in the knowledge graph.

```bash
python -m main list-entities [OPTIONS]

Options:
  --entity-type {Person,Organization,all}  Type to list (default: all)
  --knowledge-graph PATH                   Knowledge graph directory
  --format {table,json}                    Output format (default: table)
```

Example output:
```
Found 35 entities:

Name                                     Type            Sources    Associations
-----------------------------------------------------------------------------
Niccolo Machiavelli                      Person          5          12
Cesare Borgia                            Person          3          8
Florence                                 Organization    2          5
...
```

### `sync-discussions`

Sync knowledge graph entities to GitHub Discussions.

```bash
python -m main sync-discussions [OPTIONS]

Options:
  --entity-type {Person,Organization,all}  Type to sync (default: all)
  --entity-name NAME                       Sync only this entity
  --knowledge-graph PATH                   Knowledge graph directory
  --repository OWNER/REPO                  Target repository
  --token TOKEN                            GitHub token
  --dry-run                                Preview without making changes
  --output PATH                            Write JSON report to file
```

## Sync Behavior

### Idempotent Operations

The sync process is designed to be safe to run multiple times:

1. **New entities** → Creates a new discussion
2. **Unchanged entities** → Skips (no API call)
3. **Updated entities** → Updates discussion body and adds changelog comment

### Content Change Detection

The sync compares the generated discussion body with the existing discussion. Updates only occur when:
- Entity profile information changes
- New associations are discovered
- Source documents are added or modified

### Changelog Comments

When a discussion is updated, a changelog comment is automatically added:

```markdown
**Updated:** 2025-11-27 14:30 UTC

Discussion body updated to reflect current knowledge graph state.
```

## Discussion Format

Each synced discussion follows a consistent format:

```markdown
# Entity Name

**Type:** Person
**Confidence:** 95%

## Summary

[Entity summary from knowledge graph]

## Attributes

| Attribute | Value |
|-----------|-------|
| birth_year | 1469 |
| death_year | 1527 |

## Associations

### As Source
- [Relationship] → Target Entity (Confidence: 90%)
  - Evidence: "Quote from source document"

### As Target
- Source Entity → [Relationship] (Confidence: 85%)

## Source Documents

- `abc123...` (2 mentions)
- `def456...` (1 mention)

---
*Generated from knowledge graph on 2025-11-27*
```

## Agent Mission

The sync functionality is also available as an agent mission:

```bash
python -m main agent run --mission sync_discussions
```

The agent will:
1. List all entities in the knowledge graph
2. Check each entity's discussion status
3. Create, update, or skip as needed
4. Report on all actions taken

### Mission Configuration

See `config/missions/sync_discussions.yaml` for the mission definition:

```yaml
id: sync_discussions
max_steps: 100
allowed_tools:
  - list_discussion_categories
  - find_discussion_by_title
  - create_discussion
  - update_discussion
  - list_knowledge_entities
  - get_entity_profile
  - sync_entity_discussion
```

## Reports

Generate a detailed JSON report of sync operations:

```bash
python -m main sync-discussions --output reports/sync-report.json
```

Report structure:
```json
{
  "timestamp": "2025-11-27T14:30:00Z",
  "repository": "owner/repo",
  "knowledge_graph": "knowledge-graph",
  "entity_types": ["Person", "Organization"],
  "dry_run": false,
  "results": [
    {
      "entity": "Niccolo Machiavelli",
      "type": "Person",
      "action": "created",
      "discussion_number": 42,
      "url": "https://github.com/owner/repo/discussions/42"
    }
  ],
  "errors": [],
  "summary": {
    "created": 10,
    "updated": 5,
    "unchanged": 20,
    "error_count": 0
  }
}
```

## Troubleshooting

### "Category not found" Error

```
error: Category 'People' not found. Please create it manually in repository settings.
```

**Solution:** Create the required discussion categories in your GitHub repository settings.

### "Token not found" Error

```
error: GitHub token not found
```

**Solution:** Set `GITHUB_TOKEN` or `GH_TOKEN` environment variable.

### "Repository not found" Error

```
error: GitHub repository not found
```

**Solution:** Set `GITHUB_REPOSITORY` or `GH_REPOSITORY` environment variable, or use `--repository` flag.

### Rate Limiting

If you encounter rate limits:
1. Wait for the rate limit to reset (usually 1 hour)
2. Use `--entity-type` to sync one type at a time
3. Use `--entity-name` to sync individual entities

### Debugging

Run with dry-run and output to inspect what would happen:

```bash
python -m main sync-discussions --dry-run --output debug-report.json
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer                                │
│   main.py sync-discussions                                       │
│   src/cli/commands/discussions.py                                │
└─────────────────┬───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    Knowledge Layer                               │
│   src/knowledge/aggregation.py - Entity aggregation              │
│   src/knowledge/storage.py - Knowledge graph storage             │
└─────────────────┬───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    Integration Layer                             │
│   src/integrations/github/discussions.py - GitHub GraphQL API   │
└─────────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Entity Extraction Guide](entity-extraction.md) - How entities are extracted
- [Agent Operations Guide](agent-operations.md) - Running agent missions
- [GitHub Discussions API](https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions)
