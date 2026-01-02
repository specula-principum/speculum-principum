# Research Team Agents - Multi-Project Plan

## Overview

This project collection implements a rigorous research team for analyzing state law, legislative process, and community feedback. The team is designed around the use case of assessing Department of Education policies, but the agent architecture is domain-agnostic.

## Agent Roster

| # | Agent | Purpose | Status |
|---|-------|---------|--------|
| 1 | [Source Curator](./01-source-curator/) | Identify, validate, and maintain authoritative sources | ✅ Planning Complete |
| 2 | [Monitor](./02-monitor/) | Queue sources for acquisition via change detection | ✅ Complete (merged into #9) |
| 3 | ~~[Acquisition](./03-acquisition/)~~ | ~~Retrieve and preserve source documents~~ | ⏭️ Merged into #3 |
| 3 | [Crawler](./03-crawler/) | Site-wide content acquisition within scope | ✅ Complete (merged into #9) |
| 4 | [Extraction](./04-extraction/) | Extract structured entities and relationships | 📋 Planning Complete |
| 5 | [Synthesis](./05-synthesis/) | Aggregate and organize knowledge structures | 🔲 Planning |
| 6 | [Conflict Detection](./06-conflict-detection/) | Identify inconsistencies and contradictions | 🔲 Planning |
| 7 | [Quality Assurance](./07-quality-assurance/) | Verify accuracy and completeness | 🔲 Planning |
| 8 | [Report Generation](./08-report-generation/) | Produce structured deliverables | 🔲 Planning |
| 9 | [Content Pipeline](./09-content-pipeline/) | Unified monitor + acquire (LLM-free) | ✅ Complete |

## Workflow Architecture

```
┌─────────────────┐
│  Source Curator │──────────────────────────────────┐
└────────┬────────┘                                  │
         │ registered sources                        │
         ▼                                           │
┌─────────────────────────────────────────┐          │
│     Content Pipeline (LLM-free)         │          │
│  ┌─────────────┐   ┌─────────────────┐  │          │
│  │  Monitor    │──▶│  Crawler/Acquire │  │          │
│  │  (detect)   │   │  (fetch/store)   │  │          │
│  └─────────────┘   └─────────────────┘  │          │
└────────┬────────────────────────────────┘          │
         │ parsed documents                          │
         ▼                                           │
┌─────────────────┐                                  │
│ Extraction Agt  │◀─────────────────────────────────┘
│  (filter→extract) │     source context
└────────┬────────┘
         │ entities, associations
         ▼
┌─────────────────┐     ┌───────────────────┐
│  Synthesis Agt  │────▶│ Conflict Detect.  │
└────────┬────────┘     └─────────┬─────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐     ┌───────────────────┐
│   QA Agent      │◀────│  Human Review     │
└────────┬────────┘     └───────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│          Report Generation Agent        │
└─────────────────────────────────────────┘
```

## Implementation Approach

Each agent will be developed as an independent feature with:
- Mission YAML configuration (`config/missions/`) - for LLM-orchestrated agents
- Programmatic pipeline (`src/knowledge/pipeline/`) - for LLM-free execution
- Agent-specific tools (`src/orchestration/toolkit/`)
- Test coverage (`tests/`)
- Documentation

**Key Insight:** Following the Content Pipeline refactor, we prefer **LLM-free programmatic execution** for deterministic workflows (monitoring, acquisition, extraction) and reserve LLM orchestration for tasks requiring judgment (source curation, conflict resolution, report generation).

## Quality Standards (All Agents)

- Primary sources preferred over secondary
- Full provenance tracking for all data
- Citation accuracy verification
- Human approval gates for critical decisions
- Conflict escalation procedures

## Progress Tracking

- [x] Phase 1: Source Curator + Monitor (foundation)
- [x] Phase 2: Content Pipeline (unified monitor + acquire, LLM-free)
- [ ] Phase 3: Extraction (knowledge pipeline) — *Planning Complete*
- [ ] Phase 4: Synthesis + Conflict Detection (knowledge building)
- [ ] Phase 5: QA + Report Generation (output quality)

---

*Created: 2025-12-24*
*Updated: 2026-01-02*
