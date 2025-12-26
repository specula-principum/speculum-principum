# Source Curator Agent - Planning Document

## Agent Overview

**Mission:** Identify, validate, and maintain a registry of authoritative sources.

**Status:** ✅ Implementation Complete (Discussions-First Workflow)

---

## Responsibilities

- Maintain the source registry anchored to the project's foundational `source_url` from `config/manifest.json`
- Evaluate source credibility using established criteria (authority, recency, accessibility)
- Assess proposed sources in GitHub Discussions ("Sources" category) with credibility analysis
- Create implementation Issues only after community consensus is reached in Discussions
- Implement approved sources by registering them and closing the implementation Issue

## Quality Standards

- **Primary Source**: The `source_url` from manifest is the foundational, approved source
- **Derived Sources**: Links discovered within primary source documents require Discussion consensus before Issue creation
- **Credibility Tracking**: All sources have accessibility status and last-verified timestamps
- **Transparency**: All source decisions are documented in Discussions (proposals) and Issues (implementation)

---

## Approval Workflow (Discussions-First)

### Key Principles

1. **Discussions for Proposals**: All source proposals start as Discussion topics in the "Sources" category
2. **Agent Assessment**: The agent posts credibility analysis as a reply to the Discussion
3. **Community Consensus**: Team discusses validity and reach agreement in the Discussion
4. **Issues for Implementation**: Only after consensus, an Issue is created with proper labels
5. **Copilot Assignment**: The Issue is assigned to copilot for automated implementation

### Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISCUSSIONS-FIRST WORKFLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PROPOSAL (Discussion)                                                   │
│     ┌─────────────────────────────────────┐                                │
│     │ User/Agent creates Discussion in    │                                │
│     │ "Sources" category with proposed    │                                │
│     │ URL and justification               │                                │
│     └─────────────────┬───────────────────┘                                │
│                       ▼                                                     │
│  2. ASSESSMENT (Discussion Reply)                                           │
│     ┌─────────────────────────────────────┐                                │
│     │ Agent posts credibility assessment  │                                │
│     │ as reply: score, domain type,       │                                │
│     │ accessibility, integrity indicators │                                │
│     └─────────────────┬───────────────────┘                                │
│                       ▼                                                     │
│  3. DELIBERATION (Discussion Thread)                                        │
│     ┌─────────────────────────────────────┐                                │
│     │ Community discusses validity,       │                                │
│     │ raises concerns, asks questions     │                                │
│     └─────────────────┬───────────────────┘                                │
│                       ▼                                                     │
│  4. CONSENSUS (Discussion → Issue)                                          │
│     ┌─────────────────────────────────────┐                                │
│     │ When approved: User comments        │                                │
│     │ `/approve-source` to trigger        │                                │
│     │ Issue creation                      │                                │
│     └─────────────────┬───────────────────┘                                │
│                       ▼                                                     │
│  5. IMPLEMENTATION (Issue)                                                  │
│     ┌─────────────────────────────────────┐                                │
│     │ Agent creates Issue with            │                                │
│     │ `source-approved` label,            │                                │
│     │ assigns to copilot                  │                                │
│     └─────────────────┬───────────────────┘                                │
│                       ▼                                                     │
│  6. REGISTRATION (Agent Action)                                             │
│     ┌─────────────────────────────────────┐                                │
│     │ Agent registers source, updates     │                                │
│     │ Discussion with status, closes      │                                │
│     │ Issue with summary                  │                                │
│     └─────────────────────────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Rejection Flow

```
Discussion → `/reject-source [reason]` comment → Agent marks Discussion as 
"Rejected" with reason → No Issue created → Discussion archived
```

---

## Implementation Plan

### 1. Source Registry Schema

Sources are tracked in both **local storage** (knowledge-graph/sources/) and **GitHub Discussions** ("Sources" category).

#### SourceEntry Data Model

Location: `src/knowledge/storage.py` (extend existing module)

```python
@dataclass(slots=True)
class SourceEntry:
    """Represents an authoritative source in the registry."""
    
    url: str                          # Canonical URL
    name: str                         # Human-readable name
    source_type: str                  # "primary" | "derived" | "reference"
    status: str                       # "active" | "deprecated" | "pending_review"
    last_verified: datetime           # Last successful access check
    added_at: datetime                # When source was registered
    added_by: str                     # GitHub username or "system"
    
    # Approval tracking (updated for Discussions-first)
    proposal_discussion: int | None   # Discussion number where proposed
    implementation_issue: int | None  # Issue number for implementation
    
    # Credibility metadata
    credibility_score: float          # 0.0-1.0, based on evaluation
    is_official: bool                 # Official/authoritative domain
    requires_auth: bool               # Requires authentication to access
    
    # Discovery metadata  
    discovered_from: str | None       # Checksum of document where discovered
    parent_source_url: str | None     # URL of source that referenced this
    
    # Content metadata
    content_type: str                 # "webpage" | "pdf" | "api" | "feed"
    update_frequency: str | None      # "daily" | "weekly" | "monthly" | "unknown"
    topics: List[str]                 # Related topics/keywords
    notes: str                        # Free-form notes

    def to_dict(self) -> dict[str, Any]: ...
    
    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceEntry": ...
```

#### Storage Structure

```
knowledge-graph/
├── sources/
│   ├── {url_hash}.json      # Individual source entry
│   └── registry.json        # Index of all sources
```

### 2. Discovery Mechanisms

Sources are discovered through three channels, all flowing through Discussions:

#### 2.1 Foundational Source (Automatic)

The `source_url` in `config/manifest.json` is automatically registered as the primary source during repository setup. This happens via the existing `setup_repo` mission.

**Integration Point**: Extend `configure_repository()` in `src/orchestration/toolkit/setup.py` to:
1. Register the `source_url` as a SourceEntry with `source_type="primary"`
2. Create the initial "Sources" Discussion documenting the primary source

#### 2.2 Derived Source Discovery (Manual CLI Command)

A **manual CLI command** scans parsed documents for URLs and proposes new sources via **Discussions**:

```bash
# Discover sources from all parsed documents
python -m main discover-sources

# Dry run - show what would be proposed without creating Discussions
python -m main discover-sources --dry-run

# Limit to specific document
python -m main discover-sources --checksum abc123

# Filter by domain pattern (e.g., only .gov or .edu)
python -m main discover-sources --domain-filter "\.gov$|\.edu$"
```

**Workflow:**

1. **Scan Phase**: Parse all documents in `evidence/parsed/` for external URLs
2. **Filter Phase**: Exclude already-registered sources, apply domain filters
3. **Score Phase**: Calculate preliminary credibility scores
4. **Rank Phase**: Sort by credibility score descending
5. **Propose Phase**: Create Discussion for each candidate (with `--limit` support)

**Implementation Components:**

| Component | Location | Purpose |
|-----------|----------|---------|
| `SourceDiscoverer` | `src/knowledge/source_discovery.py` | URL extraction from markdown |
| `discover-sources` CLI | `src/cli/commands/sources.py` | Manual trigger command |
| `discover_sources` tool | `src/orchestration/toolkit/source_curator.py` | Agent-callable version |

**URL Extraction Logic:**

```python
class SourceDiscoverer:
    """Discovers potential source URLs from parsed documents."""
    
    def extract_urls(self, markdown: str) -> List[DiscoveredUrl]:
        """Extract all URLs from markdown content."""
        # Pattern matches: [text](url), <url>, bare URLs
        # Excludes: internal anchors, relative paths, images
        ...
    
    def filter_candidates(
        self,
        urls: List[DiscoveredUrl],
        registered_sources: List[str],
        domain_filter: str | None = None,
    ) -> List[DiscoveredUrl]:
        """Filter to unregistered, high-integrity candidates."""
        ...
    
    def score_candidate(self, url: DiscoveredUrl) -> float:
        """Preliminary credibility score based on domain characteristics."""
        # Higher scores for: .gov, .edu, known official domains
        # Lower scores for: social media, URL shorteners, commercial
        ...
```

**Discussion Template for Proposed Sources**:
```markdown
## Source Proposal: {name}

**URL**: {url}
**Discovered in**: {source_document_checksum}
**Parent Source**: {parent_url}
**Discovery Method**: {automated_scan|manual_proposal}

### Why This Source?
{justification or context snippet}

---

### Agent Assessment
_Pending - agent will post credibility analysis as a reply_

---

### Commands
- **To approve**: Comment `/approve-source` after reaching consensus
- **To reject**: Comment `/reject-source [reason]`

_Proposed by {author}_
```

**Agent Assessment Reply Template**:
```markdown
## Credibility Assessment

**Credibility Score**: {score}/1.0
**Domain**: {domain}
**Domain Type**: {government|education|organization|commercial|unknown}

### Integrity Indicators
| Check | Status | Details |
|-------|--------|---------|
| Official domain | {✅/❌} | {domain_assessment} |
| Accessible | {✅/❌} | HTTP {status_code} |
| Valid SSL | {✅/❌} | {ssl_status} |
| Content parseable | {✅/❌} | {content_type} |

### Recommendation
{recommendation based on score and indicators}

---
_Assessment by Source Curator Agent_
```

#### 2.3 Manual Source Addition (Human-Driven)

Humans can propose sources by creating Discussions in the "Sources" category:

1. User creates Discussion with source URL and justification
2. Agent posts credibility assessment as reply
3. Community discusses validity in the thread
4. When consensus reached, user comments `/approve-source`
5. Agent creates Issue with `source-approved` label, assigns to copilot
6. Agent registers source and closes Issue

### 3. Validation Procedures

#### 3.1 Credibility Scoring Rubric

Sources receive a credibility score (0.0-1.0) based on:

| Factor | Weight | Criteria |
|--------|--------|----------|
| Domain Authority | 0.3 | Official domains score higher |
| Accessibility | 0.2 | Consistently reachable, no auth barriers |
| Relationship | 0.2 | Distance from primary source |
| Recency | 0.15 | Last verified within threshold |
| Content Quality | 0.15 | Parseable, structured content |

**Scoring Implementation**: New function in `src/knowledge/` module.

#### 3.2 Automated Validation

Using existing `validate_url()` tool plus new checks:

- **Reachability**: HTTP HEAD request, status code check
- **Content Type**: Verify expected media type
- **SSL/TLS**: Valid certificate for HTTPS sources

#### 3.3 Discussion-Based Review

| Condition | Action |
|-----------|--------|
| New source proposal | Create Discussion in "Sources" category |
| Agent assessment | Post credibility analysis as Discussion reply |
| Community consensus | `/approve-source` triggers Issue creation |
| Rejection | `/reject-source [reason]` marks Discussion rejected |
| Credibility < 0.5 | Agent flags concerns in assessment reply |

#### 3.4 Re-validation Schedule

- **Active sources**: Verify weekly (via Monitor Agent)
- **Pending sources**: Daily verification attempts
- **Deprecated sources**: No verification, retained for history

### 4. Tool Requirements

#### 4.1 Existing Tools (Reuse)

| Tool | Module | Purpose |
|------|--------|---------|
| `validate_url` | `toolkit/setup.py` | Basic URL validation |
| `create_discussion` | `toolkit/discussion_tools.py` | Create source proposal Discussion |
| `update_discussion` | `toolkit/discussion_tools.py` | Update Discussion status |
| `add_discussion_comment` | `toolkit/discussion_tools.py` | Post assessment reply |
| `find_discussion_by_title` | `toolkit/discussion_tools.py` | Check existing proposals |
| `create_issue` | `toolkit/github.py` | Create implementation Issue |
| `close_issue` | `toolkit/github.py` | Close Issue after registration |
| `add_label_to_issue` | `toolkit/github.py` | Add `source-approved` label |

#### 4.2 New Tools Required

Location: `src/orchestration/toolkit/source_curator.py`

| Tool | Description | Risk Level |
|------|-------------|------------|
| `register_source` | Add new source to registry | REVIEW |
| `get_source` | Retrieve source entry by URL | SAFE |
| `list_sources` | List all sources with optional filters | SAFE |
| `update_source_status` | Change source status | REVIEW |
| `verify_source_accessibility` | Check if source URL is reachable | SAFE |
| `calculate_credibility_score` | Compute credibility based on rubric | SAFE |
| `propose_source_discussion` | Create Discussion proposing new source | REVIEW |
| `assess_source_proposal` | Post credibility assessment as Discussion reply | REVIEW |
| `create_source_implementation_issue` | Create Issue for approved source | REVIEW |
| `process_source_approval` | Handle `/approve-source` command from Discussion | DESTRUCTIVE |
| `process_source_rejection` | Handle `/reject-source` command from Discussion | REVIEW |
| `discover_sources` | Scan documents for new URLs, filter and rank | SAFE |

#### 4.3 New Modules Required

| Module | Purpose |
|--------|---------|
| `src/knowledge/source_discovery.py` | URL extraction and candidate scoring |
| `src/cli/commands/sources.py` | CLI commands for source management |

#### 4.4 Integration Points

1. **Setup Flow**: Hook into `setup_repo` mission to register primary source
2. **Discovery Flow**: Manual `discover-sources` CLI creates Discussions
3. **Assessment Flow**: Workflow triggers agent to assess new Discussions
4. **Approval Flow**: `/approve-source` creates Issue, triggers implementation

### 5. Mission Configuration

#### 5.1 Source Assessment Mission

Location: `config/missions/assess_source.yaml`

```yaml
id: assess_source
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-25
  summary_tooling: source-assessment

goal: |
  Assess source proposals in GitHub Discussions and post credibility analysis.
  
  Triggered by:
  1. New Discussions in "Sources" category
  2. Discussions updated with new information
  
  Actions:
  1. Read the Discussion to extract proposed URL
  2. Validate URL accessibility
  3. Calculate credibility score
  4. Post assessment as Discussion reply

constraints:
  - Only assess Discussions in "Sources" category
  - Do not create Issues - assessment only
  - Post assessment as reply, not edit to original

success_criteria:
  - All source proposals have credibility assessments
  - Assessments include score, domain type, integrity indicators

max_steps: 5
allowed_tools:
  - get_discussion
  - add_discussion_comment
  - verify_source_accessibility
  - calculate_credibility_score
  - get_source
requires_approval: false
```

#### 5.2 Source Implementation Mission

Location: `config/missions/implement_source.yaml`

```yaml
id: implement_source
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-25
  summary_tooling: source-implementation

goal: |
  Implement approved sources by registering them and closing implementation Issues.
  
  Triggered by:
  1. Issues with `source-approved` label assigned to copilot
  
  Actions:
  1. Read Issue to extract source URL and Discussion reference
  2. Register source in knowledge-graph/sources/
  3. Update Discussion with "Approved" status
  4. Close Issue with implementation summary

constraints:
  - Only process Issues with `source-approved` label
  - Verify Discussion consensus before registration
  - Update Discussion to reflect final status

success_criteria:
  - Approved sources appear in registry
  - Discussion updated with approval status
  - Issue closed with summary

max_steps: 8
allowed_tools:
  - get_issue_details
  - close_issue
  - post_comment
  - register_source
  - get_source
  - update_discussion
  - get_discussion
requires_approval: false
```

#### 5.3 Source Approval Command Mission

Location: `config/missions/curate_sources.yaml`

```yaml
id: curate_sources
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-25
  summary_tooling: source-curation

goal: |
  Process approval and rejection commands in source proposal Discussions.
  
  Triggered by:
  1. Discussion comments containing `/approve-source`
  2. Discussion comments containing `/reject-source`
  
  Actions:
  1. For approval commands:
     - Verify Discussion is a source proposal
     - Create Issue with `source-approved` label
     - Assign Issue to copilot
     - Update Discussion with Issue link
  
  2. For rejection commands:
     - Mark Discussion as rejected
     - Post rejection summary with reason
     - Archive/close Discussion

constraints:
  - Never register sources directly - create Issue for implementation
  - Require explicit `/approve-source` or `/reject-source` command
  - Maintain audit trail in Discussion

success_criteria:
  - Approved sources have implementation Issues created
  - Rejected sources are documented with reasons
  - All decisions transparent in Discussion thread

max_steps: 10
allowed_tools:
  - get_discussion
  - get_discussion_comments
  - add_discussion_comment
  - update_discussion
  - create_issue
  - add_label_to_issue
  - get_source
  - list_sources
  - process_source_approval
  - process_source_rejection
requires_approval: false
```

### 6. Test Cases

Location: `tests/orchestration/test_source_curator.py`

#### 6.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_source_entry_serialization` | SourceEntry to_dict/from_dict round-trip |
| `test_source_entry_tracks_discussion` | SourceEntry has proposal_discussion field |
| `test_source_entry_tracks_issue` | SourceEntry has implementation_issue field |
| `test_credibility_score_calculation` | Scoring rubric produces expected values |
| `test_url_hash_generation` | Consistent hashing for registry keys |
| `test_register_source_creates_entry` | Registration writes to storage |
| `test_url_extraction_from_markdown` | Extracts URLs from various markdown formats |
| `test_domain_filter_regex` | Domain filter patterns match correctly |
| `test_candidate_scoring_gov_domains` | .gov domains receive high scores |

#### 6.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_proposal_creates_discussion` | Source proposal creates Discussion |
| `test_assessment_posts_reply` | Agent posts credibility reply to Discussion |
| `test_approval_creates_issue` | `/approve-source` creates implementation Issue |
| `test_issue_has_approved_label` | Created Issue has `source-approved` label |
| `test_issue_assigned_to_copilot` | Created Issue assigned to copilot |
| `test_implementation_registers_source` | Processing Issue registers source |
| `test_implementation_closes_issue` | Processing Issue closes it with summary |
| `test_rejection_marks_discussion` | `/reject-source` marks Discussion rejected |
| `test_primary_source_from_manifest` | Setup flow registers source_url |
| `test_discover_sources_creates_discussions` | CLI creates Discussions not Issues |

#### 6.3 Edge Cases

| Test | Description |
|------|-------------|
| `test_duplicate_source_proposal` | Handles existing source gracefully |
| `test_approval_without_assessment` | Warns if approving without assessment |
| `test_unreachable_source_handling` | Posts warning in assessment |
| `test_malformed_url_rejection` | Validates URL format in Discussion |
| `test_approval_from_non_sources_category` | Ignores commands in wrong category |
| `test_discover_excludes_registered` | Already-registered URLs not proposed again |

---

## GitHub Workflow Integration

### Source Assessment Workflow

Location: `.github/workflows/2-op-assess-source.yml`

```yaml
name: "Assess Source Proposal"

on:
  discussion:
    types: [created, edited]

jobs:
  assess:
    if: github.event.discussion.category.name == 'Sources'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt
      - run: |
          python -m main agent \
            --mission assess_source \
            --discussion ${{ github.event.discussion.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

### Source Approval Workflow

Location: `.github/workflows/2-op-curate-sources.yml`

```yaml
name: "Process Source Commands"

on:
  discussion_comment:
    types: [created]

jobs:
  process-approval:
    if: |
      github.event.discussion.category.name == 'Sources' &&
      contains(github.event.comment.body, '/approve-source')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt
      - run: |
          python -m main agent \
            --mission curate_sources \
            --discussion ${{ github.event.discussion.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}

  process-rejection:
    if: |
      github.event.discussion.category.name == 'Sources' &&
      contains(github.event.comment.body, '/reject-source')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt
      - run: |
          python -m main agent \
            --mission curate_sources \
            --discussion ${{ github.event.discussion.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

### Source Implementation Workflow

Location: `.github/workflows/2-op-implement-source.yml`

```yaml
name: "Implement Approved Source"

on:
  issues:
    types: [opened, labeled]

jobs:
  implement:
    if: |
      contains(github.event.issue.labels.*.name, 'source-approved') &&
      contains(github.event.issue.assignees.*.login, 'copilot')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt
      - run: |
          python -m main agent \
            --mission implement_source \
            --issue ${{ github.event.issue.number }}
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

---

## Dependencies

- **Upstream**: None (foundational agent)
- **Downstream**: Monitor Agent, Acquisition Agent, QA Agent

## Related Modules

| Module | Purpose |
|--------|---------|
| `src/knowledge/storage.py` | SourceEntry data model, storage |
| `src/orchestration/toolkit/source_curator.py` | Toolkit for source tools |
| `src/orchestration/toolkit/setup.py` | Integration for primary source |
| `src/integrations/github/discussions.py` | Discussion management |
| `config/missions/assess_source.yaml` | Assessment mission |
| `config/missions/curate_sources.yaml` | Approval command mission |
| `config/missions/implement_source.yaml` | Implementation mission |

---

## Implementation Sequence

### Phase 1: Refactor Storage Layer ✅
- ✅ Update `SourceEntry` to use `proposal_discussion` and `implementation_issue` fields
- ✅ Migrate from `approval_issue` to new field names
- ✅ Update unit tests

### Phase 2: Refactor Tools ✅
- ✅ Rename `propose_source` → `propose_source_discussion`
- ✅ Add `assess_source_proposal` tool
- ✅ Add `create_source_implementation_issue` tool
- ✅ Split `process_source_approval` into approve/reject tools
- ✅ Update tool tests

### Phase 3: New Missions ✅
- ✅ Create `assess_source.yaml` mission
- ✅ Create `implement_source.yaml` mission
- ✅ Update `curate_sources.yaml` for Discussion commands
- ✅ Remove Issue-first workflow from missions

### Phase 4: CLI Updates ✅
- ✅ Update `discover-sources` to create Discussions instead of Issues
- ✅ Add `--propose` flag to actually create Discussions (vs dry-run)
- ✅ Update help text and documentation

### Phase 5: Workflow Updates ✅
- ✅ Replace Issue-triggered workflows with Discussion-triggered
- ✅ Add new workflow for Implementation Issues
- ✅ Update Issue template or remove if not needed
- N/A Discussion category template (not supported by GitHub Actions)

### Phase 6: Testing ✅
- ✅ Update integration tests for Discussions-first flow
- ✅ End-to-end workflow testing (548 tests passing)
- ✅ Migration testing for existing sources (backward compatibility)

---

*Last Updated: 2025-12-25*
