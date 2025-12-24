# Research Team Agents - Multi-Project Plan

## Overview

This project collection implements a rigorous research team for analyzing state law, legislative process, and community feedback. The team is designed around the use case of assessing Department of Education policies, but the agent architecture is domain-agnostic.

## Agent Roster

| # | Agent | Purpose | Status |
|---|-------|---------|--------|
| 1 | [Source Curator](./01-source-curator/) | Identify, validate, and maintain authoritative sources | 🔲 Planning |
| 2 | [Monitor](./02-monitor/) | Track sources for new/updated content | 🔲 Planning |
| 3 | [Acquisition](./03-acquisition/) | Retrieve and preserve source documents | 🔲 Planning |
| 4 | [Extraction](./04-extraction/) | Extract structured entities and relationships | 🔲 Planning |
| 5 | [Synthesis](./05-synthesis/) | Aggregate and organize knowledge structures | 🔲 Planning |
| 6 | [Conflict Detection](./06-conflict-detection/) | Identify inconsistencies and contradictions | 🔲 Planning |
| 7 | [Quality Assurance](./07-quality-assurance/) | Verify accuracy and completeness | 🔲 Planning |
| 8 | [Report Generation](./08-report-generation/) | Produce structured deliverables | 🔲 Planning |

## Workflow Architecture

```
┌─────────────────┐
│  Source Curator │──────────────────────────────────┐
└────────┬────────┘                                  │
         │ registered sources                        │
         ▼                                           │
┌─────────────────┐                                  │
│  Monitor Agent  │                                  │
└────────┬────────┘                                  │
         │ change alerts                             │
         ▼                                           │
┌─────────────────┐                                  │
│ Acquisition Agt │                                  │
└────────┬────────┘                                  │
         │ parsed documents                          │
         ▼                                           │
┌─────────────────┐     ┌───────────────────┐       │
│ Extraction Agt  │────▶│  Synthesis Agent  │       │
└────────┬────────┘     └─────────┬─────────┘       │
         │                        │                  │
         │    ┌───────────────────┘                  │
         ▼    ▼                                      │
┌─────────────────┐     ┌───────────────────┐       │
│Conflict Detect. │◀───▶│   QA Agent        │◀──────┘
└────────┬────────┘     └─────────┬─────────┘
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────┐
│          Report Generation Agent        │
└─────────────────────────────────────────┘
```

## Implementation Approach

Each agent will be developed as an independent feature with:
- Mission YAML configuration (`config/missions/`)
- Agent-specific tools (`src/orchestration/toolkit/`)
- Test coverage (`tests/`)
- Documentation

## Quality Standards (All Agents)

- Primary sources preferred over secondary
- Full provenance tracking for all data
- Citation accuracy verification
- Human approval gates for critical decisions
- Conflict escalation procedures

## Progress Tracking

- [ ] Phase 1: Source Curator + Monitor (foundation)
- [ ] Phase 2: Acquisition + Extraction (data pipeline)
- [ ] Phase 3: Synthesis + Conflict Detection (knowledge building)
- [ ] Phase 4: QA + Report Generation (output quality)

---

*Created: 2025-12-24*
