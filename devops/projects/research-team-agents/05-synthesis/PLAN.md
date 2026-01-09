# Synthesis Agent - Planning Document

## Agent Overview

**Mission:** Aggregate and organize extracted information into coherent knowledge structures by resolving entity duplicates, building canonical entity records, and computing corroboration scores.

**Status:** 📋 Planning Complete

**Prerequisites:**
- Extraction Agent (04-extraction) - ✅ Complete (provides extracted entities in `knowledge-graph/`)

---

## Problem Statement

### Current State

The Extraction Agent successfully extracts entities from parsed documents:
- **People:** `knowledge-graph/people/{checksum}.json` - List of person names
- **Organizations:** `knowledge-graph/organizations/{checksum}.json` - List of org names
- **Concepts:** `knowledge-graph/concepts/{checksum}.json` - List of concepts
- **Associations:** `knowledge-graph/associations/{checksum}.json` - Relationship objects

However, entities are stored **per-source** without consolidation:
- The same entity may appear in 10+ source files with minor variations
- "Denver Broncos" vs "Broncos" are treated as separate entities
- No way to know how many sources mention an entity (corroboration)
- No canonical entity records for downstream agents

### What Exists

| Component | Location | Status |
|-----------|----------|--------|
| Entity Storage | `src/knowledge/storage.py` | ✅ Per-source storage works |
| Aggregation Module | `src/knowledge/aggregation.py` | ✅ Basic aggregation, needs enhancement |
| Knowledge Aggregator | `KnowledgeAggregator` class | ✅ Reads all sources, basic dedup |
| Aggregated Entity | `AggregatedEntity` dataclass | ✅ Exists but underutilized |
| Entity Profiles | `knowledge-graph/profiles/` | ❌ Unused (empty in production) |
| Canonical Entities | - | ❌ Missing |
| Alias Resolution | - | ❌ Missing |
| Corroboration Scores | - | ❌ Missing |

### Observed Entity Patterns (from mirror-denver-broncos test repo)

Analysis of ~40 extracted source documents revealed these patterns:

| Pattern | Examples | Frequency |
|---------|----------|-----------|
| **Name variants** | "Denver Broncos" / "Broncos" | High |
| **Abbreviations** | "AFC West" / "AFC" | Medium |
| **Full vs short names** | "Los Angeles Chargers" / "Chargers" | High |
| **Cross-type leakage** | "Courtland Sutton" in both people AND concepts | Medium |
| **Org hierarchy** | "AFC" (parent) → "AFC West" (child) | Low |
| **Title variations** | "Sean Payton" / "Head Coach Sean Payton" | Medium |
| **Empty extractions** | Many sources yield `[]` for people | High (~30%) |

### Gap Analysis

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CURRENT GAP                                     │
└─────────────────────────────────────────────────────────────────────────┘

Per-Source Extraction              Missing Stages              Downstream Agents
┌──────────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ people/checksum1.json│       │                  │       │ Conflict Detect. │
│ people/checksum2.json│ ────▶ │   Synthesis?     │ ────▶ │ QA Agent         │
│ ...                  │       │                  │       │ Report Gen.      │
│ assoc/checksum1.json │       │                  │       │                  │
└──────────────────────┘       └──────────────────┘       └──────────────────┘

NEEDED:
1. Deduplicate entities across sources (resolve "Broncos" = "Denver Broncos")
2. Build canonical entity records (one record per real-world entity)
3. Compute corroboration scores (N sources mention this entity)
4. Track provenance (which sources contributed to this entity)
5. Merge associations (combine relationships from all sources)
```

---

## Design Decisions

### Decision 1: Copilot-Native Resolution (No CLI Intermediary)

**Decision:** **Copilot directly resolves entities** using its native tools. No CLI layer calling GitHub Models.

**Rationale:**
- Copilot IS the LLM - no need to call another LLM via CLI
- Copilot has native tools: read files, search, create/edit files, create PRs
- Adding CLI → GitHub Models is redundant complexity
- Direct Copilot work = simpler architecture, easier debugging
- PR-based output = natural review workflow

**Copilot's Native Capabilities:**
- `read_file` - Read canonical store, alias maps, extracted entities
- `semantic_search` - Find related entities across knowledge graph
- `grep_search` - Search for exact entity names
- `create_file` / `replace_string_in_file` - Update canonical entities
- Creates PR automatically with all changes

**What Copilot Decides:**
- All entity matching (abbreviations, variants, nicknames)
- Cross-type disambiguation (person vs concept)
- Hierarchical relationships (parent/child orgs)
- Confidence levels and review flags

### Decision 2: Detailed Issue Instructions (Copilot Works Directly)

**Decision:** Issues contain **complete instructions** for Copilot to work autonomously using its tools.

**Rationale:**
- Copilot reads Issue body, understands task, uses tools, creates PR
- No intermediary CLI or orchestration layer needed
- Issue body = the "prompt" with all context Copilot needs
- PR = the output, ready for human review
- Simple workflow: Issue → Copilot → PR → Review → Merge

**Issue Types:**

| Issue Type | Label | Purpose |
|------------|-------|---------|
| Synthesis Batch | `synthesis-batch` | Process a batch of raw entities |
| Objection Review | `synthesis-objection` | Human-raised objection from Discussions |
| Full Rebuild | `synthesis-rebuild` | Regenerate entire canonical store |

**Issue Body Contains:**
- Explicit file paths to read (entities, canonical store, alias map)
- Clear decision criteria for matching
- Expected output format with examples
- Instructions to create PR with changes

### Decision 3: Issue-Based State (Each Issue = One Batch)

**Decision:** Each Issue is a **self-contained batch** with state tracked via Issue labels and comments.

**Batch Structure:**
- Maximum 50 entities per Issue (configurable)
- Issue body contains all entities to process
- Issue labels track status: `pending`, `in-progress`, `complete`
- Copilot comments progress as it works
- PR linked to Issue contains all changes

**State Tracking (via Issue):**
```markdown
## Progress

- [x] Read canonical store (15 existing entities)
- [x] Processed: "Denver Broncos" → matched to `denver-broncos`
- [x] Processed: "Broncos" → added as alias to `denver-broncos`
- [ ] Pending: "AFC West", "AFC", "Kansas City Chiefs"...

## Summary

Processed 8/12 entities. Creating PR with changes.
```

**Rate Limit Handling:**
- If Copilot hits rate limit, Issue remains open with progress comment
- Re-assign Copilot to continue (it reads previous comments)
- Or: Close Issue and create new one for remaining entities

### Decision 4: Discussion-Based Objection Workflow

**Decision:** Allow humans to **raise objections via GitHub Discussions**, which create synthesis Issues for Copilot review.

**Workflow:**
1. User sees incorrect entity resolution in Discussion/knowledge-graph
2. User creates Discussion with category "Objection" 
3. Discussion body includes entity IDs and proposed correction
4. Workflow detects new objection Discussion
5. Creates Issue with label `synthesis-objection`
6. Copilot reviews objection, updates canonical entities
7. Comments resolution on original Discussion

**Discussion Template:**
```markdown
---
title: "Objection: [Entity Name] incorrectly merged"
labels: ["objection"]
---

## Entity Objection

**Canonical Entity:** `denver-broncos`
**Issue:** The alias "Denver" should NOT be included - it's ambiguous (city vs team)

## Proposed Resolution

Remove "Denver" from aliases for `denver-broncos`.

## Evidence

- Source document abc123 refers to "Denver" as the city, not the team
- See line 45: "The meeting was held in Denver..."

<!-- objection:synthesis -->
```

### Decision 5: Canonical Entity Store Structure

**Decision:** Create new storage structure for deduplicated entities.

**Directory:** `knowledge-graph/canonical/`
```
knowledge-graph/canonical/
├── people/
│   └── sean-payton.json
├── organizations/
│   └── denver-broncos.json
├── concepts/
│   └── afc-west.json
├── index.json
└── alias-map.json
```

**Canonical Entity Schema:**
```json
{
  "canonical_id": "denver-broncos",
  "canonical_name": "Denver Broncos",
  "entity_type": "Organization",
  "aliases": ["Denver Broncos", "Broncos", "The Broncos"],
  "source_checksums": ["abc123...", "def456...", "..."],
  "corroboration_score": 15,
  "first_seen": "2026-01-08T04:31:00+00:00",
  "last_updated": "2026-01-08T04:37:00+00:00",
  "resolution_history": [
    {
      "action": "created",
      "by": "copilot",
      "issue_number": 42,
      "timestamp": "2026-01-08T04:31:00+00:00"
    },
    {
      "action": "alias_added",
      "alias": "The Broncos",
      "by": "copilot",
      "issue_number": 45,
      "timestamp": "2026-01-08T05:00:00+00:00"
    }
  ],
  "attributes": {},
  "associations": [],
  "metadata": {
    "needs_review": false,
    "confidence": 0.95
  }
}
```

**Alias Map:** `knowledge-graph/canonical/alias-map.json`
```json
{
  "version": 1,
  "last_updated": "2026-01-08T05:00:00+00:00",
  "aliases": {
    "denver broncos": "denver-broncos",
    "broncos": "denver-broncos",
    "the broncos": "denver-broncos",
    "sean payton": "sean-payton",
    "head coach sean payton": "sean-payton"
  }
}
```

---

## Architecture

### Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     SYNTHESIS PIPELINE (Copilot-Native)                          │
└─────────────────────────────────────────────────────────────────────────────────┘

TRIGGERS                          ISSUE                         OUTPUT
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│ Post-Extraction  │         │                  │         │                  │
│ Workflow         │────────▶│  Issue with      │         │  Pull Request    │
└──────────────────┘         │  detailed        │         │                  │
                             │  instructions    │         │  - Canonical     │
┌──────────────────┐         │                  │         │    entities      │
│ Scheduled Daily  │────────▶│  ┌────────────┐  │────────▶│  - Alias map     │
│ (cron)           │         │  │ @copilot   │  │         │  - Resolution    │
└──────────────────┘         │  │  assigned  │  │         │    history       │
                             │  └────────────┘  │         │                  │
┌──────────────────┐         │                  │         └────────┬─────────┘
│ Discussion       │────────▶│  Copilot reads,  │                  │
│ Objection        │         │  searches,       │                  ▼
└──────────────────┘         │  decides,        │         ┌──────────────────┐
                             │  writes files,   │         │  Human Review    │
┌──────────────────┐         │  creates PR      │         │  Merge PR        │
│ Manual Trigger   │────────▶│                  │         └──────────────────┘
│ (workflow_dispatch)        └──────────────────┘
└──────────────────┘

NO CLI LAYER - Copilot uses native tools directly
```

### Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ENTITY RESOLUTION FLOW (Copilot-Native)                      │
└─────────────────────────────────────────────────────────────────────────────────┘

Issue Contains                        Copilot Reads & Decides
Entity List                           (using native tools)
     │                                      │
     ▼                                      ▼
┌──────────────┐                     ┌──────────────────────────────────────────┐
│ "Sean Payton"│                     │ 1. Read alias-map.json                   │
│ "Broncos"    │────────────────────▶│ 2. Check if entity already exists       │
│ "AFC"        │                     │ 3. If exists: add alias, update sources  │
│ "Denver..."  │                     │ 4. If new: create canonical entity       │
└──────────────┘                     │ 5. Update alias-map.json                 │
                                     │ 6. Add reasoning to resolution_history   │
                                     └──────────────────┬───────────────────────┘
                                                        │
                                                        ▼
                                     ┌──────────────────────────────────────────┐
                                     │  Create PR with:                         │
                                     │  - New/updated canonical entity files    │
                                     │  - Updated alias-map.json                │
                                     └──────────────────────────────────────────┘
```

No deterministic matching layer - Copilot handles ALL entity resolution decisions.

---

## Implementation Plan

### Phase 1: Canonical Storage (2 days)

**Goal:** Build canonical entity storage with dataclasses and file I/O.

**Deliverables:**

| File | Purpose |
|------|---------|
| `src/knowledge/canonical.py` | Canonical entity storage |
| `tests/knowledge/test_canonical.py` | Storage tests |

**Canonical Entity Dataclass:**

```python
@dataclass(slots=True)
class CanonicalEntity:
    """A deduplicated entity with all source references."""
    
    canonical_id: str  # Slug: "sean-payton"
    canonical_name: str  # Display: "Sean Payton"
    entity_type: str  # "Person" | "Organization" | "Concept"
    aliases: List[str]  # All known names for this entity
    source_checksums: List[str]  # Which documents mention this
    corroboration_score: int  # len(source_checksums)
    first_seen: datetime
    last_updated: datetime
    resolution_history: List[ResolutionEvent]  # Audit trail
    attributes: dict[str, Any]  # Merged attributes
    associations: List[CanonicalAssociation]  # Merged relationships
    metadata: dict[str, Any]  # Confidence, review flags
```

**Alias Map Functions:**

```python
def load_alias_map(canonical_dir: Path) -> dict[str, str]:
    """Load alias-map.json mapping normalized names to canonical IDs."""
    
def save_alias_map(canonical_dir: Path, alias_map: dict[str, str]) -> None:
    """Save alias-map.json."""

def normalize_name(name: str) -> str:
    """Normalize name for alias map lookup (lowercase, strip, collapse spaces)."""
```

### Phase 2: (Removed)

*Copilot handles all matching directly - no separate matching layer needed.*

### Phase 3: Issue Creation Workflow (2 days)

**Goal:** Workflow creates Issues with detailed instructions for Copilot.

**Deliverables:**

| File | Purpose |
|------|---------|
| `.github/workflows/synthesis-queue.yml` | Create synthesis batch Issues |
| `src/cli/commands/synthesis.py` | Simple CLI for Issue creation only |
| `tests/cli/test_synthesis.py` | CLI tests |

**Workflow: Issue Creation**

```yaml
# .github/workflows/synthesis-queue.yml
name: "Synthesis: Create Batch Issue 📋"

on:
  # After extraction completes
  workflow_run:
    workflows: ["Extraction: Process Document 🧠"]
    types: [completed]
    
  # Scheduled daily
  schedule:
    - cron: '0 7 * * *'  # 7 AM UTC
    
  # Manual trigger
  workflow_dispatch:
    inputs:
      full_rebuild:
        description: "Full rebuild (reprocess all entities)"
        type: boolean
        default: false

jobs:
  create-synthesis-issue:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          
      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Create synthesis Issue
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
        run: |
          # CLI only gathers data and creates Issue - no LLM work
          python main.py synthesis create-issue \
            --repository ${{ github.repository }} \
            ${{ inputs.full_rebuild == 'true' && '--full' || '' }}
```

**CLI Role (Minimal):**

The CLI only:
1. Scans `knowledge-graph/` for extracted entities
2. Compares against `knowledge-graph/canonical/` to find new entities
3. Creates GitHub Issue with entity list and instructions
4. Assigns Issue to Copilot

The CLI does **NOT**:
- Call any LLM/GitHub Models
- Make resolution decisions
- Update canonical entities

All intelligent work is done by Copilot directly.

**Issue Template (Detailed Instructions for Copilot):**

```markdown
---
title: "Synthesis: Resolve Organization Entities (Batch 3)"
labels: ["synthesis-batch", "copilot"]
assignees: ["copilot"]
---

## Task: Entity Resolution

Resolve the following organization names to canonical entities.

## Entities to Process

| Raw Name | Source File |
|----------|-------------|
| Denver Broncos | `knowledge-graph/organizations/abc123.json` |
| Broncos | `knowledge-graph/organizations/def456.json` |
| The Broncos | `knowledge-graph/organizations/ghi789.json` |
| AFC West | `knowledge-graph/organizations/jkl012.json` |
| AFC | `knowledge-graph/organizations/mno345.json` |

## Current Canonical Store

Read existing entities from:
- `knowledge-graph/canonical/organizations/` (all `.json` files)
- `knowledge-graph/canonical/alias-map.json`

## Resolution Rules

For each entity above:

1. **Check alias map** - If normalized name exists in alias map, it's already resolved
2. **Search canonical entities** - Look for semantic match (abbreviation, nickname, variant)
3. **Decide:**
   - **MATCH** → Add as alias to existing canonical entity
   - **NEW** → Create new canonical entity file
   - **AMBIGUOUS** → Add `"needs_review": true` to metadata

## Output Format

### For existing canonical entity (add alias):

Edit `knowledge-graph/canonical/organizations/denver-broncos.json`:
- Add new name to `aliases` array
- Add source checksum to `source_checksums`
- Increment `corroboration_score`
- Add entry to `resolution_history`

### For new canonical entity:

Create `knowledge-graph/canonical/organizations/[slug].json`:
```json
{
  "canonical_id": "[slug]",
  "canonical_name": "[Primary Name]",
  "entity_type": "Organization",
  "aliases": ["[name]"],
  "source_checksums": ["[checksum]"],
  "corroboration_score": 1,
  "first_seen": "[ISO timestamp]",
  "last_updated": "[ISO timestamp]",
  "resolution_history": [
    {
      "action": "created",
      "timestamp": "[ISO timestamp]",
      "issue_number": [this issue number],
      "reasoning": "[why this is a new entity]"
    }
  ],
  "metadata": {"needs_review": false, "confidence": 0.95}
}
```

### Update alias map:

Edit `knowledge-graph/canonical/alias-map.json`:
- Add normalized name → canonical_id mapping

## Completion

1. Create a PR with all changes
2. Comment summary: how many matched, how many new, any ambiguous
3. Close this Issue

---
<!-- copilot:synthesis-batch -->
```

### Phase 4: Copilot Assignment (1 day)

**Goal:** Ensure Copilot is assigned to synthesis Issues.

**Approach:** The Issue creation (Phase 3) already assigns Copilot. This workflow is a fallback for manually created Issues.

**Deliverables:**

| File | Purpose |
|------|---------|
| `.github/workflows/synthesis-assign.yml` | Assign Copilot to labeled Issues |

**Workflow: Assign Copilot**

```yaml
# .github/workflows/synthesis-assign.yml
name: "Synthesis: Assign Copilot 🤖"

on:
  issues:
    types: [labeled]

permissions:
  issues: write

jobs:
  assign-copilot:
    if: github.event.label.name == 'synthesis-batch' || github.event.label.name == 'synthesis-objection'
    runs-on: ubuntu-latest
    
    steps:
      - name: Assign Copilot
        uses: actions/github-script@v7
        with:
          script: |
            const issue = context.payload.issue;
            const assignees = issue.assignees.map(a => a.login);
            
            if (!assignees.includes('copilot')) {
              await github.rest.issues.addAssignees({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: issue.number,
                assignees: ['copilot']
              });
              
              console.log(`Assigned Copilot to Issue #${issue.number}`);
            }
```

**No Mission Configuration Needed:**

The Issue body contains all instructions. Copilot reads the Issue and works directly - no separate mission YAML required.

### Phase 5: Objection Workflow (1 day)

**Goal:** Process human objections from Discussions.

**Deliverables:**

| File | Purpose |
|------|---------|
| `.github/workflows/synthesis-objection.yml` | Create Issue from Discussion objection |

**Workflow: Objection → Issue (No CLI)**

```yaml
# .github/workflows/synthesis-objection.yml
name: "Synthesis: Objection from Discussion 🗣️"

on:
  discussion:
    types: [created]

permissions:
  discussions: read
  issues: write

jobs:
  create-objection-issue:
    if: contains(github.event.discussion.body, '<!-- objection:synthesis -->')
    runs-on: ubuntu-latest
    
    steps:
      - name: Create Objection Issue
        uses: actions/github-script@v7
        with:
          script: |
            const discussion = context.payload.discussion;
            
            const issueBody = `## Synthesis Objection

**From Discussion:** #${discussion.number}
**Author:** @${discussion.user.login}

## Original Objection

${discussion.body}

## Instructions

@copilot Please review this objection:

1. Read the objection above
2. Find the canonical entity mentioned in \`knowledge-graph/canonical/\`
3. Evaluate if the objection is valid
4. If valid: Update the canonical entity (remove/add alias, fix error)
5. If invalid: Explain why in a comment
6. Create PR with any changes
7. Comment on original Discussion #${discussion.number} with resolution
8. Close this Issue

---
<!-- objection-discussion:${discussion.number} -->
<!-- copilot:synthesis-objection -->
`;
            
            const issue = await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Objection: ${discussion.title}`,
              body: issueBody,
              labels: ['synthesis-objection', 'copilot'],
              assignees: ['copilot']
            });
            
            console.log(`Created Issue #${issue.data.number} for objection`);
```

**No separate processing workflow needed** - the Issue assignment workflow (Phase 4) handles Copilot assignment.

**Objection Issue Template (for manual creation):**

```markdown
---
title: "Objection: [Entity/Issue Summary]"
labels: ["synthesis-objection"]
assignees: ["copilot"]
---

## Synthesis Objection

**Entity ID:** `[canonical-id]`

## Objection

[Describe what is wrong with the current entity resolution]

## Proposed Fix

[What should be changed]

## Evidence

[Links or references supporting your objection]

---
<!-- copilot:synthesis-objection -->
```

### Phase 6: Testing & Documentation (2 days)

**Goal:** Testing and documentation.

**Deliverables:**

| File | Purpose |
|------|---------|
| `tests/knowledge/test_canonical.py` | Canonical storage tests |
| `tests/cli/test_synthesis.py` | CLI tests (Issue creation only) |
| `docs/guides/synthesis.md` | User documentation |

**Test Scenarios:**

| Category | Test Case |
|----------|-----------|
| Canonical | Save and retrieve entity |
| Canonical | Add alias to existing entity |
| Canonical | Update corroboration score |
| Canonical | Resolution history tracking |
| Canonical | Load alias map |
| CLI | Create synthesis Issue |
| CLI | Detect new entities vs existing |
| CLI | Generate Issue body with instructions |
| Workflow | Issue creation workflow triggers |
| Workflow | Objection → Issue workflow |
| Workflow | Copilot assignment workflow |

---

## Entry Points Summary

### Automated Entry Points

| Entry Point | Trigger | Creates |
|-------------|---------|---------|
| Post-Extraction | Extraction workflow completes | Synthesis batch Issue |
| Scheduled Daily | Cron at 7 AM UTC | Synthesis batch Issue |
| Discussion Objection | User creates Discussion with marker | Objection Issue |

### Human-Initiated Entry Points

| Entry Point | Trigger | Creates |
|-------------|---------|---------|
| Manual Workflow | `workflow_dispatch` on synthesis-queue | Synthesis batch Issue |
| Direct Issue | User creates Issue with `synthesis-batch` label | Copilot assignment |
| Full Rebuild | Manual workflow with `full_rebuild: true` | Issue for all entities |

---

## Rate Limiting Strategy

### How It Works

Copilot naturally handles rate limits:
- If rate limited mid-Issue, Copilot stops working
- Issue remains open with partial progress in comments
- When rate limit clears, re-assign Copilot or create new Issue for remaining entities

### Recovery Options

**Option 1: Re-assign Copilot**
- Remove Copilot from assignees
- Re-add Copilot
- Copilot reads Issue + previous comments, continues work

**Option 2: New Issue for Remaining**
- Close current Issue with comment noting partial completion
- Create new Issue with only the remaining entities
- Assign Copilot to new Issue

**Option 3: Manual Intervention**
- Human reviews partial PR (if created)
- Human completes remaining entities manually
- Merge PR and close Issue

### No Complex State File Needed

Progress is tracked in:
- Issue comments (what Copilot completed)
- PR changes (what files were modified)
- Canonical store itself (which entities exist)

The next synthesis run automatically skips already-resolved entities by checking the alias map.

---

## Storage Schema

### Canonical Entity File

Path: `knowledge-graph/canonical/organizations/denver-broncos.json`

```json
{
  "canonical_id": "denver-broncos",
  "canonical_name": "Denver Broncos",
  "entity_type": "Organization",
  "aliases": [
    "Denver Broncos",
    "Broncos",
    "The Broncos"
  ],
  "source_checksums": [
    "28d5e6d8d542d36d528a8a2021d61e8dc26e73589ca9518b6c82b4698b61f994",
    "bcc19baa247a7930dc518c968fb9230b9eb09c889f18943475ab341c8b17b271",
    "8706a743c7e389daad160306dd3ea9f1bb81c14622c4e6c851b386ac8b7992db"
  ],
  "corroboration_score": 3,
  "first_seen": "2026-01-08T04:31:00+00:00",
  "last_updated": "2026-01-08T05:15:00+00:00",
  "resolution_history": [
    {
      "action": "created",
      "by": "copilot",
      "issue_number": 42,
      "timestamp": "2026-01-08T04:31:00+00:00",
      "reasoning": "First occurrence from source 28d5e6..."
    },
    {
      "action": "alias_added",
      "alias": "Broncos",
      "by": "copilot",
      "issue_number": 45,
      "timestamp": "2026-01-08T05:00:00+00:00",
      "reasoning": "Short name for Denver Broncos NFL team"
    }
  ],
  "attributes": {},
  "associations": [
    {
      "target_id": "sean-payton",
      "target_type": "Person",
      "relationships": [
        {"type": "employs", "count": 2},
        {"type": "coached by", "count": 1}
      ],
      "source_checksums": ["abc...", "def..."]
    }
  ],
  "metadata": {
    "needs_review": false,
    "confidence": 0.95
  }
}
```

### Alias Map

Path: `knowledge-graph/canonical/alias-map.json`

```json
{
  "version": 1,
  "last_updated": "2026-01-08T05:15:00+00:00",
  "by_type": {
    "Person": {
      "sean payton": "sean-payton",
      "head coach sean payton": "sean-payton",
      "courtland sutton": "courtland-sutton"
    },
    "Organization": {
      "denver broncos": "denver-broncos",
      "broncos": "denver-broncos",
      "the broncos": "denver-broncos",
      "afc west": "afc-west"
    },
    "Concept": {
      "home-field advantage": "home-field-advantage"
    }
  }
}
```

### State Tracking (No Separate File)

State is derived from existing artifacts:

| State Question | How to Determine |
|---------------|------------------|
| Which entities are resolved? | Check `alias-map.json` |
| Which sources are processed? | Check `source_checksums` in canonical entities |
| Is there pending work? | Compare extracted entities vs alias map |
| What Issues are active? | Query GitHub Issues with `synthesis-batch` label |

**No `synthesis/state.json` needed** - the canonical store IS the state.

---

## Dependencies

### Upstream

| Agent/Module | Provides |
|--------------|----------|
| Extraction Agent | Per-source entity files in `knowledge-graph/` |
| Knowledge Storage | `KnowledgeGraphStorage` for reading extractions |

### Downstream

| Agent/Module | Consumes |
|--------------|----------|
| Conflict Detection Agent | Canonical entities for inconsistency analysis |
| Report Generation Agent | Corroborated entities for report synthesis |
| QA Agent | Entity provenance chains for verification |

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Canonical Storage | 2 days | - |
| Phase 2: (Removed - Copilot does matching) | - | - |
| Phase 3: Issue Creation Workflow | 2 days | Phase 1 |
| Phase 4: Copilot Assignment | 1 day | Phase 3 |
| Phase 5: Objection Workflow | 1 day | Phase 4 |
| Phase 6: Testing & Documentation | 2 days | All |
| **Total** | **8 days** | |

---

## Success Criteria

1. **Entity Resolution Quality:** Copilot correctly matches 90%+ of entity variants
2. **PR-Based Review:** All changes come via PRs for human review
3. **Audit Trail:** Every resolution decision has reasoning in `resolution_history`
4. **Objection Handling:** Discussion objections create Issues and get resolved
5. **Simplicity:** No complex state management - canonical store IS the state
6. **Idempotency:** Re-running synthesis skips already-resolved entities

---

## Open Questions

1. **Batch Size Tuning:** Start with 50, adjust based on rate limit patterns
2. **LLM Prompt Refinement:** May need iteration on resolution prompts
3. **Hierarchical Entities:** Track parent/child relationships (future enhancement)
4. **Association Normalization:** Merge relationship types via LLM? (future)

---

## Related Modules

### Existing (Reuse/Extend)

- `src/knowledge/aggregation.py` - Reference for aggregation patterns
- `src/knowledge/storage.py` - Existing storage utilities
- `src/integrations/github/storage.py` - GitHub API persistence
- `src/integrations/github/issues.py` - Issue creation utilities

### New (Create)

- `src/knowledge/canonical.py` - Canonical entity storage (dataclasses + file I/O)
- `src/cli/commands/synthesis.py` - CLI for Issue creation only (no LLM work)
- `.github/workflows/synthesis-queue.yml` - Create batch Issues
- `.github/workflows/synthesis-assign.yml` - Assign Copilot to Issues
- `.github/workflows/synthesis-objection.yml` - Discussion → Issue
- `docs/guides/synthesis.md` - User documentation

**NOT Needed (Copilot-native approach):**
- ~~`src/knowledge/synthesis_state.py`~~ - State tracked in Issues/comments
- ~~`src/knowledge/matching.py`~~ - Copilot does all matching
- ~~`config/missions/synthesize_batch.yaml`~~ - Instructions in Issue body
- ~~`.github/workflows/synthesis-process.yml`~~ - No processing workflow
- ~~`.github/workflows/synthesis-resume.yml`~~ - No complex resume

---

*Last Updated: 2026-01-07*
