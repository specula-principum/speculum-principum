# Source Curator Agent - Implementation Prompt

Use this prompt to continue implementation work on the Source Curator Agent.

---

## Instructions for AI Agent

You are implementing the **Source Curator Agent** for the speculum-principum research platform. Your work is guided by the detailed plan in [PLAN.md](PLAN.md).

### ⚠️ REFACTORING IN PROGRESS

The approval workflow has been restructured to use a **Discussions-first** approach:
- **OLD**: Issues for proposals → agent assesses → `/approve-source` → register
- **NEW**: Discussions for proposals → agent assesses → `/approve-source` → Issue created → register

See the "Approval Workflow (Discussions-First)" section in PLAN.md for the full diagram.

### Before Starting Work

1. **Read the current plan**: Review `PLAN.md` to understand the Discussions-first workflow
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

### Prior Implementation (Completed Before Refactor)
| Task | Status | Notes |
|------|--------|-------|
| `SourceEntry` dataclass | ✅ Complete | 2025-12-24 - Needs field updates |
| `SourceRegistry` storage class | ✅ Complete | 2025-12-24 |
| `SourceDiscoverer` class | ✅ Complete | 2025-12-24 |
| CLI commands (discover-sources, list-sources) | ✅ Complete | 2025-12-24 - Needs output updates |
| Basic orchestration tools | ✅ Complete | 2025-12-24 - Needs refactoring |
| Unit tests | ✅ Complete | 2025-12-24 - Needs updates |

---

### Phase 1: Refactor Storage Layer
| Task | Status | Notes |
|------|--------|-------|
| 1.1 Rename `approval_issue` → `implementation_issue` in SourceEntry | ✅ Complete | 2025-12-25 |
| 1.2 Add `proposal_discussion` field to SourceEntry | ✅ Complete | 2025-12-25 |
| 1.3 Update `to_dict()` / `from_dict()` methods | ✅ Complete | 2025-12-25 - Added backward compat for legacy field |
| 1.4 Update serialization tests | ✅ Complete | 2025-12-25 - Added legacy migration tests |
| 1.5 Migrate any existing source entries (if applicable) | ✅ Complete | 2025-12-25 - Auto-migration via from_dict() |

### Phase 2: Refactor Orchestration Tools
| Task | Status | Notes |
|------|--------|-------|
| 2.1 Rename `propose_source` → `propose_source_discussion` | ✅ Complete | 2025-12-25 |
| 2.2 Update proposal tool to create Discussion | ✅ Complete | 2025-12-25 |
| 2.3 Add `assess_source_proposal` tool | ✅ Complete | 2025-12-25 - Posts credibility reply |
| 2.4 Add `create_source_implementation_issue` tool | ✅ Complete | 2025-12-25 - Creates Issue w/ label + assignment |
| 2.5 Split `process_source_approval` for Discussion context | ✅ Complete | 2025-12-25 - Now _process_discussion_approval_handler |
| 2.6 Add `process_source_rejection` tool | ✅ Complete | 2025-12-25 |
| 2.7 Add `implement_approved_source` tool | ✅ Complete | 2025-12-25 - Tracks both discussion + issue |
| 2.8 Deprecate `sync_source_discussion` | ✅ Complete | 2025-12-25 - Marked deprecated, still registered |
| 2.9 Update tool tests | ✅ Complete | 2025-12-25 - 63 tests passing |

### Phase 3: New Mission Configurations
| Task | Status | Notes |
|------|--------|-------|
| 3.1 Create `assess_source.yaml` mission | ⬜ Not Started | Triggered by new Discussion in Sources |
| 3.2 Create `implement_source.yaml` mission | ⬜ Not Started | Triggered by Issue with `source-approved` |
| 3.3 Update `curate_sources.yaml` for Discussion commands | ⬜ Not Started | Handles `/approve-source` in Discussions |
| 3.4 Remove Issue-proposal triggers from missions | ⬜ Not Started | |

### Phase 4: CLI Updates
| Task | Status | Notes |
|------|--------|-------|
| 4.1 Update `discover-sources` output text (Discussion not Issue) | ⬜ Not Started | |
| 4.2 Add `--propose` flag to create Discussions | ⬜ Not Started | Dry-run by default |
| 4.3 Update help text and docstrings | ⬜ Not Started | |

### Phase 5: GitHub Workflow Updates
| Task | Status | Notes |
|------|--------|-------|
| 5.1 Create `2-op-assess-source.yml` workflow | ⬜ Not Started | Triggers on Discussion created |
| 5.2 Update `2-op-curate-sources.yml` workflow | ⬜ Not Started | Triggers on Discussion comment |
| 5.3 Create `2-op-implement-source.yml` workflow | ⬜ Not Started | Triggers on Issue with label |
| 5.4 Remove or update Issue template | ⬜ Not Started | May need Discussion template instead |

### Phase 6: Testing & Validation
| Task | Status | Notes |
|------|--------|-------|
| 6.1 Update integration tests for Discussion-first flow | ⬜ Not Started | |
| 6.2 Add tests for new tools | ⬜ Not Started | |
| 6.3 End-to-end workflow testing | ⬜ Not Started | Requires live GitHub |

---

## Session Log

Record implementation sessions here for continuity.

### Session: 2025-12-25 (Phase 1: Storage Layer Refactoring)
**Tasks Completed**:
- Renamed `approval_issue` → `implementation_issue` in SourceEntry dataclass
- Added `proposal_discussion` field to SourceEntry for Discussion-first workflow
- Updated `to_dict()` / `from_dict()` methods with backward compatibility
- Updated all test fixtures (test_source_storage.py, test_source_curator_tools.py, test_setup_toolkit.py)
- Updated CLI commands/sources.py to display new fields
- Updated setup.py primary source registration
- Updated source_curator.py tool definitions and handlers
- Updated curate_sources.yaml mission constraints
- Added 3 new tests for legacy field migration (backward compatibility)
- All 83 tests passing (25 storage + 58 orchestration)

**Decisions Made**:
- Implemented backward compatibility: `from_dict()` reads legacy `approval_issue` and maps to `implementation_issue`
- New fields use None as default (not required in JSON)
- CLI now shows both `Proposal Discussion` and `Implementation Issue` when present

**Blockers/Issues**:
- None

**Next Steps**:
- Phase 2: Refactor orchestration tools (rename propose_source, add new tools)

### Session: 2025-12-25 (Phase 2: Orchestration Tools Refactoring)
**Tasks Completed**:
- Renamed `propose_source` → `propose_source_discussion` (creates Discussion instead of Issue)
- Added `assess_source_proposal` tool (posts credibility assessment as Discussion reply)
- Added `create_source_implementation_issue` tool (creates Issue with `source-approved` label, assigns to copilot)
- Refactored `process_source_approval` to `_process_discussion_approval_handler` (Discussion-first workflow)
- Added `process_source_rejection` tool (marks Discussion as rejected)
- Added `implement_approved_source` tool (registers source with both discussion and issue, closes Issue)
- Deprecated `sync_source_discussion` (marked deprecated but still registered for backward compat)
- Updated all tests for new Discussion-first tools
- All 63 tests passing (38 source curator + 25 storage)

**Decisions Made**:
- New tools follow Discussion-first workflow: Discussion → Assessment → Approval → Issue → Implementation
- `implement_approved_source` is the final step that registers source with both `proposal_discussion` and `implementation_issue` tracked
- Legacy `_propose_source_handler` kept for backward compatibility but not registered as a tool
- Used `github_discussions.get_discussion()` for Discussion lookup by number

**Blockers/Issues**:
- None

**Next Steps**:
- Phase 3: Create new mission configurations (assess_source.yaml, implement_source.yaml)
- Phase 4: Update CLI commands

### Session: 2025-12-25 (Refactoring Plan)
**Tasks Completed**:
- Updated PLAN.md with Discussions-first workflow
- Updated PROMPT.md with new implementation phases

**Decisions Made**:
- Workflow restructured per management feedback:
  - Proposals happen in Discussions (Sources category)
  - Agent posts credibility assessment as Discussion reply
  - `/approve-source` command triggers Issue creation
  - Issue has `source-approved` label and assigned to copilot
  - Agent implements source and closes Issue
- Split into 3 missions: assess_source, curate_sources, implement_source
- SourceEntry fields renamed: `approval_issue` → `implementation_issue`, added `proposal_discussion`

**Blockers/Issues**:
- Prior implementation needs refactoring (not removal)
- GitHub Discussion workflows may have API limitations

**Next Steps**:
- Phase 1: Refactor SourceEntry storage layer
- Phase 2: Refactor orchestration tools

### Session: 2025-12-24 (Prior Implementation - Pre-Refactor)
**Tasks Completed**: 
- Phase 1: Storage Layer (SourceEntry, SourceRegistry) - 23 tests
- Phase 2: Source Discovery (SourceDiscoverer, URL extraction, scoring) - 35 tests  
- Phase 3: CLI Commands (discover-sources, list-sources) - registered in main.py
- Phase 4: Orchestration Tools (7 tools with proper risk levels) - 36 tests
- Phase 5: Mission Configuration (curate_sources.yaml)
- Phase 6: Setup Integration (primary source registration)
- Phase 7: GitHub Workflow (curate-sources.yml, issue template)

**Note**: This implementation used Issue-first workflow which is now deprecated. The components are still valid but need refactoring for Discussion-first workflow.

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

### Key Files to Modify

| File | Change Required |
|------|-----------------|
| `src/knowledge/storage.py` | Update SourceEntry fields |
| `src/orchestration/toolkit/source_curator.py` | Refactor tools for Discussion flow |
| `src/cli/commands/sources.py` | Update CLI output and flags |
| `config/missions/curate_sources.yaml` | Update for Discussion triggers |
| `config/missions/assess_source.yaml` | NEW - Create this file |
| `config/missions/implement_source.yaml` | NEW - Create this file |
| `.github/workflows/2-op-*.yml` | Update/create workflow files |

### Key Files to Understand
- `src/knowledge/storage.py` - Entity storage patterns (EntityProfile, KnowledgeGraphStorage)
- `src/orchestration/toolkit/discussion_tools.py` - Discussion sync patterns
- `src/integrations/github/discussions.py` - Discussion API integration
- `config/missions/sync_discussions.yaml` - Mission YAML patterns

### Test Commands
```bash
# Run specific test file
python -m pytest tests/knowledge/test_source_storage.py -v

# Run source curator tool tests
python -m pytest tests/orchestration/test_source_curator_tools.py -v

# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src
```

### Code Patterns to Follow

**SourceEntry with new fields:**
```python
@dataclass(slots=True)
class SourceEntry:
    url: str
    name: str
    source_type: str
    status: str
    # ...
    proposal_discussion: int | None   # Discussion number where proposed
    implementation_issue: int | None  # Issue number for implementation
    # ...
```

**Discussion-first tool pattern:**
```python
def _propose_source_discussion_handler(args: Mapping[str, Any]) -> ToolResult:
    """Create a Discussion proposing a new source."""
    # 1. Validate URL
    # 2. Create Discussion in "Sources" category
    # 3. Return Discussion URL for agent assessment
    ...
```

**Assessment tool pattern:**
```python
def _assess_source_proposal_handler(args: Mapping[str, Any]) -> ToolResult:
    """Post credibility assessment as Discussion reply."""
    # 1. Read Discussion to extract URL
    # 2. Calculate credibility score
    # 3. Post assessment as reply
    ...
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

*Last Updated: 2025-12-25*
