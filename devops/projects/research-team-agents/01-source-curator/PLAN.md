# Source Curator Agent - Planning Document

## Agent Overview

**Mission:** Identify, validate, and maintain a registry of authoritative sources.

**Status:** ✅ Planning Complete

---

## Responsibilities

- Maintain the source registry anchored to the project's foundational `source_url` from `config/manifest.json`
- Evaluate source credibility using established criteria (authority, recency, accessibility)
- Maintain source entries as Discussions in the "Sources" category with structured metadata
- Flag deprecated or unreliable sources via Issues for human review
- Propose new authoritative sources related to the project topic via Issues for approval

## Quality Standards

- **Primary Source**: The `source_url` from manifest is the foundational, approved source
- **Derived Sources**: Links discovered within primary source documents require Issue approval
- **Credibility Tracking**: All sources have accessibility status and last-verified timestamps
- **Transparency**: All source decisions are documented in Issues and Discussions

---

## Implementation Plan

### 1. Source Registry Schema

Sources are stored as GitHub Discussions in a **"Sources"** category, following the existing entity pattern used for People and Organizations.

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
    approval_issue: int | None        # Issue number that approved this source
    
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

Sources are discovered through three channels, all requiring explicit approval:

#### 2.1 Foundational Source (Automatic)

The `source_url` in `config/manifest.json` is automatically registered as the primary source during repository setup. This happens via the existing `setup_repo` mission.

**Integration Point**: Extend `configure_repository()` in `src/orchestration/toolkit/setup.py` to:
1. Register the `source_url` as a SourceEntry with `source_type="primary"`
2. Create the initial "Sources" Discussion

#### 2.2 Derived Source Discovery (Manual CLI Command)

A **manual CLI command** scans parsed documents for URLs and proposes new sources via Issues:

```bash
# Discover sources from all parsed documents
python -m main discover-sources

# Dry run - show what would be proposed without creating Issues
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
5. **Propose Phase**: Create Issue for each candidate (with `--limit` support)

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

**Issue Template for Discovered Sources**:
```markdown
## Discovered Source Proposal

**URL**: {url}
**Discovered in**: {source_document_checksum}
**Parent Source**: {parent_url}
**Discovery Method**: Automated scan via `discover-sources`

### Preliminary Assessment
**Credibility Score**: {score}/1.0
**Domain**: {domain}
**Domain Type**: {government|education|organization|commercial|unknown}

### Context
Found in document section:
> {surrounding_text_snippet}

### Integrity Indicators
- [ ] Official domain ({domain_assessment})
- [ ] Accessible (HTTP {status_code})
- [ ] Valid SSL certificate
- [ ] Content parseable

---
**To approve**: Comment with `/approve-source`
**To reject**: Comment with `/reject-source [reason]`

_Proposed by Source Curator Agent_
```

#### 2.3 Manual Source Addition (Human-Driven)

Humans can propose sources by creating Issues with the `source-proposal` label:

1. User creates Issue with source URL and justification
2. Agent validates URL accessibility
3. Agent posts credibility assessment as comment
4. Human approves via `/approve-source` command
5. Agent registers source and updates Discussion

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

#### 3.3 Human Review Thresholds

| Condition | Action |
|-----------|--------|
| New derived source | Always requires Issue approval |
| Credibility < 0.5 | Flag for human review |
| Source unreachable 3x | Create Issue, mark `pending_review` |
| Source deprecated | Create Issue for removal decision |

#### 3.4 Re-validation Schedule

- **Active sources**: Verify weekly (via Monitor Agent)
- **Pending sources**: Daily verification attempts
- **Deprecated sources**: No verification, retained for history

### 4. Tool Requirements

#### 4.1 Existing Tools (Reuse)

| Tool | Module | Purpose |
|------|--------|---------|
| `validate_url` | `toolkit/setup.py` | Basic URL validation |
| `get_issue_details` | `toolkit/github.py` | Read issue metadata |
| `get_issue_comments` | `toolkit/github.py` | Read approval commands |
| `post_comment` | `toolkit/github.py` | Post assessment/results |
| `create_discussion` | `toolkit/discussion_tools.py` | Create source Discussion |
| `update_discussion` | `toolkit/discussion_tools.py` | Update source metadata |
| `find_discussion_by_title` | `toolkit/discussion_tools.py` | Check existing sources |

#### 4.2 New Tools Required

Location: `src/orchestration/toolkit/source_curator.py`

| Tool | Description | Risk Level |
|------|-------------|------------|
| `register_source` | Add new source to registry, create Discussion | REVIEW |
| `get_source` | Retrieve source entry by URL | SAFE |
| `list_sources` | List all sources with optional filters | SAFE |
| `update_source_status` | Change source status (requires approval for deprecation) | REVIEW |
| `verify_source_accessibility` | Check if source URL is reachable | SAFE |
| `calculate_credibility_score` | Compute credibility based on rubric | SAFE |
| `propose_source` | Create Issue proposing new source | REVIEW |
| `process_source_approval` | Handle `/approve-source` command | DESTRUCTIVE |
| `sync_source_discussion` | Update Discussion from registry | REVIEW |
| `discover_sources` | Scan documents for new URLs, filter and rank | SAFE |

#### 4.3 New Modules Required

| Module | Purpose |
|--------|---------|
| `src/knowledge/source_discovery.py` | URL extraction and candidate scoring |
| `src/cli/commands/sources.py` | CLI commands for source management |

#### 4.4 Integration Points

1. **Setup Flow**: Hook into `setup_repo` mission to register primary source
2. **Discovery Flow**: Manual `discover-sources` CLI command triggers URL scan
3. **Discussion Sync**: Follow pattern from `sync_discussions` mission

### 5. Mission Configuration

Location: `config/missions/curate_sources.yaml`

```yaml
id: curate_sources
version: 1
metadata:
  owner: copilot-orchestrator
  created_at: 2025-12-24
  summary_tooling: source-curation

goal: |
  Manage the source registry by processing source proposals and maintaining
  source metadata in GitHub Discussions.
  
  Triggered by:
  1. Issues with `source-proposal` label (new source proposals)
  2. Issues with `source-review` label (re-validation requests)
  3. Comments containing `/approve-source` or `/reject-source`
  
  Actions:
  1. For new proposals:
     - Validate URL accessibility
     - Calculate credibility score
     - Post assessment as Issue comment
     - Await human approval
  
  2. For approval commands:
     - Register source in knowledge-graph/sources/
     - Create or update Discussion in "Sources" category
     - Close the proposal Issue with summary
  
  3. For rejection commands:
     - Add rejection note to registry (for history)
     - Close Issue with rejection reason

constraints:
  - Never register sources without explicit human approval
  - Always create Issues for transparency
  - Maintain audit trail in Issue comments

success_criteria:
  - Source proposals have credibility assessments
  - Approved sources appear in registry and Discussions
  - Rejected sources are documented with reasons

max_steps: 10
allowed_tools:
  - get_issue_details
  - get_issue_comments
  - post_comment
  - close_issue
  - verify_source_accessibility
  - calculate_credibility_score
  - register_source
  - propose_source
  - process_source_approval
  - create_discussion
  - update_discussion
  - find_discussion_by_title
  - sync_source_discussion
  - get_source
  - list_sources
requires_approval: false
```

### 6. Test Cases

Location: `tests/orchestration/test_source_curator.py`

#### 6.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_source_entry_serialization` | SourceEntry to_dict/from_dict round-trip |
| `test_credibility_score_calculation` | Scoring rubric produces expected values |
| `test_url_hash_generation` | Consistent hashing for registry keys |
| `test_register_source_creates_entry` | Registration writes to storage |
| `test_register_source_requires_approval_issue` | Blocks without issue reference |
| `test_url_extraction_from_markdown` | Extracts URLs from various markdown formats |
| `test_domain_filter_regex` | Domain filter patterns match correctly |
| `test_candidate_scoring_gov_domains` | .gov domains receive high scores |

#### 6.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_source_proposal_workflow` | Issue → Assessment → Approval → Registration |
| `test_source_rejection_workflow` | Issue → Assessment → Rejection → Closure |
| `test_discussion_sync_creates_source` | New source creates Discussion |
| `test_discussion_sync_updates_source` | Changed metadata updates Discussion |
| `test_primary_source_from_manifest` | Setup flow registers source_url |
| `test_discover_sources_cli_dry_run` | CLI shows candidates without creating Issues |
| `test_discover_sources_creates_issues` | CLI creates proposal Issues |

#### 6.3 Edge Cases

| Test | Description |
|------|-------------|
| `test_duplicate_source_proposal` | Handles existing source gracefully |
| `test_unreachable_source_handling` | Marks status, creates review Issue |
| `test_malformed_url_rejection` | Validates URL format before processing |
| `test_approval_without_proposal` | Rejects orphaned approval commands |
| `test_discover_excludes_registered` | Already-registered URLs not proposed again |
| `test_discover_excludes_internal_links` | Anchor links and relative paths filtered |

---

## GitHub Workflow Integration

### Source Curation Workflow

Location: `.github/workflows/curate-sources.yml`

```yaml
name: "Source Curation"

on:
  issues:
    types: [opened, labeled]
  issue_comment:
    types: [created]

jobs:
  curate:
    if: |
      (github.event_name == 'issues' && contains(github.event.issue.labels.*.name, 'source-proposal')) ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '/approve-source')) ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '/reject-source'))
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
| `src/orchestration/toolkit/source_curator.py` | New toolkit for source tools |
| `src/orchestration/toolkit/setup.py` | Integration for primary source |
| `src/integrations/github/discussions.py` | Discussion management |
| `config/missions/curate_sources.yaml` | Mission definition |

---

## Implementation Sequence

1. **Phase 1: Storage Layer**
   - Add `SourceEntry` to `storage.py`
   - Add `SourceRegistry` storage class
   - Unit tests for serialization

2. **Phase 2: Tools**
   - Create `toolkit/source_curator.py`
   - Implement core tools (register, get, list, verify)
   - Integration with existing validation

3. **Phase 3: Mission**
   - Create `curate_sources.yaml`
   - Implement approval/rejection flow
   - Add Discussion sync

4. **Phase 4: Setup Integration**
   - Extend setup flow to register primary source
   - Create "Sources" category in Discussions

5. **Phase 5: Workflow**
   - Add GitHub Actions workflow
   - End-to-end testing

---

*Last Updated: 2025-12-24*
