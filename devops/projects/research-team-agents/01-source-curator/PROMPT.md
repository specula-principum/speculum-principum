# Source Curator Agent - Implementation Prompt

Use this prompt to continue implementation work on the Source Curator Agent.

---

## Instructions for AI Agent

You are implementing the **Source Curator Agent** for the speculum-principum research platform. Your work is guided by the detailed plan in [PLAN.md](PLAN.md).

### Before Starting Work

1. **Read the current plan**: Review `PLAN.md` to understand the full scope
2. **Check progress**: Look at the Progress Tracker section below to see what's done
3. **Identify next task**: Pick the next uncompleted item in sequence
4. **Update status**: Mark the task as 🔄 In Progress before starting

### While Working

- Follow existing code patterns in the repository (see `src/knowledge/storage.py`, `src/orchestration/toolkit/`)
- Write tests alongside implementation (see `tests/` for patterns)
- Keep changes focused on one component at a time
- Commit logical units of work

### After Completing a Task

1. **Update this file**: Mark the task ✅ Complete with date
2. **Add notes**: Document any deviations or decisions in the Session Log
3. **Identify blockers**: Note any issues that need resolution

---

## Progress Tracker

### Phase 1: Storage Layer
| Task | Status | Notes |
|------|--------|-------|
| 1.1 Add `SourceEntry` dataclass to `storage.py` | ✅ Complete | 2025-12-24 |
| 1.2 Add `SourceRegistry` storage class | ✅ Complete | 2025-12-24 |
| 1.3 Create `knowledge-graph/sources/` directory structure | ✅ Complete | Created automatically by SourceRegistry |
| 1.4 Write unit tests for serialization | ✅ Complete | 23 tests in test_source_storage.py |

### Phase 2: Source Discovery
| Task | Status | Notes |
|------|--------|-------|
| 2.1 Create `src/knowledge/source_discovery.py` | ✅ Complete | 2025-12-24 |
| 2.2 Implement `SourceDiscoverer.extract_urls()` | ✅ Complete | Supports markdown links, angle brackets, bare URLs |
| 2.3 Implement `SourceDiscoverer.filter_candidates()` | ✅ Complete | Excludes social media, shorteners, registered |
| 2.4 Implement `SourceDiscoverer.score_candidate()` | ✅ Complete | Scores based on domain type, HTTPS |
| 2.5 Write unit tests for URL extraction | ✅ Complete | 35 tests in test_source_discovery.py |
| 2.6 Write unit tests for scoring | ✅ Complete | Included in test_source_discovery.py |

### Phase 3: CLI Commands
| Task | Status | Notes |
|------|--------|-------|
| 3.1 Create `src/cli/commands/sources.py` | ✅ Complete | 2025-12-24 |
| 3.2 Implement `discover-sources` command | ✅ Complete | Supports --dry-run, --limit, --domain-filter |
| 3.3 Implement `list-sources` command | ✅ Complete | Supports --status, --type, --json filters |
| 3.4 Register commands in main CLI | ✅ Complete | Added to main.py |
| 3.5 Write CLI integration tests | ⬜ Not Started | Deferred - manual testing complete |

### Phase 4: Orchestration Tools
| Task | Status | Notes |
|------|--------|-------|
| 4.1 Create `src/orchestration/toolkit/source_curator.py` | ✅ Complete | 2025-12-24 |
| 4.2 Implement `register_source` tool | ✅ Complete | REVIEW risk, requires approval for derived |
| 4.3 Implement `get_source` / `list_sources` tools | ✅ Complete | SAFE risk |
| 4.4 Implement `verify_source_accessibility` tool | ✅ Complete | HTTP HEAD/GET requests |
| 4.5 Implement `calculate_credibility_score` tool | ✅ Complete | Based on domain type |
| 4.6 Implement `propose_source` tool | ✅ Complete | 2025-12-24 - Creates Issues with credibility assessment |
| 4.7 Implement `process_source_approval` tool | ✅ Complete | 2025-12-24 - DESTRUCTIVE risk, handles approve/reject |
| 4.8 Implement `discover_sources` tool | ✅ Complete | Uses SourceDiscoverer |
| 4.9 Implement `sync_source_discussion` tool | ✅ Complete | 2025-12-24 - Creates/updates Discussions |
| 4.10 Write tool registration function | ✅ Complete | register_source_curator_tools() |
| 4.11 Write orchestration tool tests | ✅ Complete | 36 tests in test_source_curator_tools.py |

### Phase 5: Mission Configuration
| Task | Status | Notes |
|------|--------|-------|
| 5.1 Create `config/missions/curate_sources.yaml` | ✅ Complete | 2025-12-24 - Updated with new tools |
| 5.2 Create `config/missions/discover_sources.yaml` | ⬜ Not Started | May not be needed - CLI serves this purpose |
| 5.3 Test mission execution | ⬜ Not Started | Requires GitHub integration |

### Phase 6: Setup Integration
| Task | Status | Notes |
|------|--------|-------|
| 6.1 Extend `configure_repository()` to register primary source | ✅ Complete | 2025-12-24 - Modified setup.py |
| 6.2 Add "Sources" category check to validate-setup | ✅ Complete | 2025-12-24 - Warns if missing (manual creation required) |
| 6.3 Test setup integration | ✅ Complete | 16 tests in test_setup_toolkit.py, 10 tests in test_setup_commands.py |

### Phase 7: GitHub Workflow
| Task | Status | Notes |
|------|--------|-------|
| 7.1 Create `.github/workflows/curate-sources.yml` | ✅ Complete | 2025-12-24 - 3 jobs: assess, approve, review |
| 7.2 Create `.github/ISSUE_TEMPLATE/source-proposal.md` | ✅ Complete | 2025-12-24 |
| 7.3 End-to-end workflow testing | ⬜ Not Started | Requires live GitHub environment |

---

## Session Log

Record implementation sessions here for continuity.

### Session: 2025-12-24 (Phase 4 Completion)
**Tasks Completed**:
- Phase 4.6: Implemented `propose_source` tool
- Phase 4.7: Implemented `process_source_approval` tool  
- Phase 4.9: Implemented `sync_source_discussion` tool
- Added 10 new tests (36 total in test_source_curator_tools.py)
- Updated curate_sources.yaml mission with new tools

**Decisions Made**:
- `propose_source`: Creates GitHub Issues with `source-proposal` label, includes credibility assessment
- `process_source_approval`: DESTRUCTIVE risk (closes issues), registers sources on approval
- `sync_source_discussion`: Checks source exists before resolving credentials, creates/updates Discussions
- Added `_resolve_github_credentials()` helper for consistent credential handling
- Issue body includes credibility score, domain type, and approval instructions

**Implementation Details**:
- Tools use existing `github_issues` and `github_discussions` modules
- `process_source_approval` handles both approve and reject flows
- `sync_source_discussion` searches for "Sources" category by name (case-insensitive)
- All new tools follow existing error handling patterns

**Blockers/Issues**: None

**Next Steps**:
- Complete Phase 5.3: Mission execution testing (requires GitHub environment)
- Complete Phase 7.3: End-to-end workflow testing

### Session: 2025-12-24 (Phase 7)
**Tasks Completed**:
- Phase 7.1: Created `.github/workflows/2-op-curate-sources.yml`
- Phase 7.2: Created `.github/ISSUE_TEMPLATE/source-proposal.md`

**Decisions Made**:
- Workflow has 3 jobs: `assess-source-proposal`, `process-source-approval`, `review-source`
- Triggers on `source-proposal` and `source-review` labels
- Approval/rejection via `/approve-source` and `/reject-source` comment commands
- Bot comments excluded via `<!-- agent-response -->` marker pattern
- Issue template includes checkboxes for source type selection

**Blockers/Issues**:
- Phase 7.3 (e2e testing) requires live GitHub environment

**Next Steps**:
- Implement remaining tools: propose_source, process_source_approval, sync_source_discussion
- Test workflow in actual repository

### Session: 2025-12-24 (Phase 6.2 - Validate Setup)
**Tasks Completed**:
- Phase 6.2: Added "Sources" discussion category check to `validate_setup()`
- Updated workflow job summary to include "Sources" category in next steps
- Added 2 new tests for discussion category validation

**Decisions Made**:
- Category check is a **warning** not an error (source curation optional)
- Uses existing `github_discussions.get_category_by_name()` function
- Gracefully handles Discussions API errors (e.g., Discussions not enabled)
- Clear warning message directs users to repository Settings > Discussions
- GitHub API does not support programmatic category creation - must be manual

**Implementation Details**:
- Added import: `from src.integrations.github import discussions as github_discussions`
- New validation check (Check 7) after repository details checks
- Updated `.github/workflows/1-setup-initialize-repo.yml` next steps section

**Files Modified**:
- `src/cli/commands/setup.py` - Added category check to `validate_setup()`
- `.github/workflows/1-setup-initialize-repo.yml` - Added step 5 about Sources category
- `tests/cli/test_setup_commands.py` - Added 2 tests, updated existing 8 with mock

**Blockers/Issues**: None

**Next Steps**:
- Phase 5.3: Mission execution testing (requires live GitHub)
- Phase 7.3: End-to-end workflow testing (requires live GitHub)

### Session: 2025-12-24 (Phase 6)
**Tasks Completed**:
- Phase 6.1: Extended `configure_repository()` to register primary source
- Phase 6.3: Created 16 unit tests in `test_setup_toolkit.py`

**Decisions Made**:
- Added `_calculate_primary_source_score()` and `_is_official_domain()` helpers to setup.py
- Primary sources auto-set to "active" status, don't require approval_issue
- Source name derived from topic: "{topic} - Primary Source"
- Credibility scores: .gov=0.95, .edu=0.90, .org=0.80, other=0.70
- Official domains: .gov, .gov.uk, .edu, .mil

**Blockers/Issues**:
- Phase 6.2 deferred - requires Discussion category API integration

**Next Steps**:
- Phase 7: GitHub Workflow (curate-sources.yml, issue template)

### Session: 2025-12-24 (Phases 1-5)
**Tasks Completed**: 
- Phase 1: Storage Layer (SourceEntry, SourceRegistry) - 23 tests
- Phase 2: Source Discovery (SourceDiscoverer, URL extraction, scoring) - 35 tests  
- Phase 3: CLI Commands (discover-sources, list-sources) - registered in main.py
- Phase 4: Orchestration Tools (7 tools with proper risk levels) - 26 tests
- Phase 5: Mission Configuration (curate_sources.yaml)

**Decisions Made**: 
- Added `_url_hash()` helper function to generate 16-character hex hashes for URL-based filenames
- `SourceRegistry` automatically creates `sources/` directory and maintains a `registry.json` index
- Registry index maps URL hashes to full URLs for efficient listing/lookup
- All file writes are atomic (write to .tmp then rename)
- Read tools marked SAFE, write tools marked REVIEW
- Derived sources require `approval_issue` reference
- Primary sources auto-set to "active" status, derived to "pending_review"

**Blockers/Issues**: 
- Phase 4.6-4.7 (propose_source, process_source_approval) deferred - need GitHub Issue integration patterns
- Phase 4.9 (sync_source_discussion) deferred - need Discussion category setup
- Two pre-existing test failures unrelated to this work

**Next Steps**: 
- Phase 6: Setup Integration (extend configure_repository to register primary source)
- Phase 7: GitHub Workflow (curate-sources.yml)
- Implement remaining tools (propose_source, process_source_approval, sync_source_discussion)

### Session Template
```
### Session: YYYY-MM-DD
**Tasks Completed**: 
**Decisions Made**: 
**Blockers/Issues**: 
**Next Steps**: 
```

---

## Quick Reference

### Key Files to Understand
- `src/knowledge/storage.py` - Entity storage patterns (EntityProfile, KnowledgeGraphStorage)
- `src/orchestration/toolkit/discussion_tools.py` - Discussion sync patterns
- `src/orchestration/toolkit/setup.py` - Setup tool patterns
- `src/cli/commands/extraction.py` - CLI command patterns
- `config/missions/sync_discussions.yaml` - Mission YAML patterns

### Test Commands
```bash
# Run specific test file
python -m pytest tests/knowledge/test_source_curator.py -v

# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src
```

### Code Patterns to Follow

**Dataclass with serialization:**
```python
@dataclass(slots=True)
class SourceEntry:
    url: str
    name: str
    # ... fields
    
    def to_dict(self) -> dict[str, Any]:
        return { ... }
    
    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceEntry":
        return cls(...)
```

**Tool registration:**
```python
def register_source_curator_tools(registry: ToolRegistry) -> None:
    registry.register_tool(
        ToolDefinition(
            name="tool_name",
            description="...",
            parameters={...},
            handler=_handler_function,
            risk_level=ActionRisk.SAFE,
        )
    )
```

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not Started |
| 🔄 | In Progress |
| ✅ | Complete |
| ⏸️ | Blocked |
| ❌ | Cancelled |

---

*Last Updated: 2025-12-24*
