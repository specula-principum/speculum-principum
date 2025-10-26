# Speculum Principum: Project Roadmap

**Mission:** Build an automated, agent-driven system for extracting and organizing knowledge from source materials into structured, discoverable knowledge bases.

**Core Methodology:** Information Architecture (IA)

---

## Vision

Transform the process of building knowledge bases from manual curation to automated extraction and organization. Enable GitHub Copilot agents to autonomously process source materials (PDFs, documents, web content) and generate high-quality, IA-compliant knowledge repositories.

### Key Principles

1. **Methodology-Driven** - Ground the system in established Information Architecture practices
2. **Modular & Reusable** - Build isolated tools that work independently
3. **Agent-First** - Design for autonomous copilot execution
4. **Quality-Focused** - Measurable metrics and continuous improvement
5. **Mission-Configurable** - Adaptable to different domains via configuration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Issues                             │
│              (Task specification & orchestration)                │
└──────────────────────────┬───────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Copilot Agent Layer                           │
│         (Autonomous execution via CLI tools & MCP server)        │
└──────────────────────────┬───────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: Agent Integration                                      │
│  ├─ Issue templates                                              │
│  ├─ Workflow helpers                                             │
│  ├─ MCP server                                                   │
│  └─ Automation workflows                                         │
└──────────────────────────┬───────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: Knowledge Base Engine                                  │
│  ├─ Pipeline orchestration                                       │
│  ├─ Extraction coordination                                      │
│  ├─ Transformation layer                                         │
│  ├─ Organization manager                                         │
│  ├─ Link builder                                                 │
│  └─ Quality assurance                                            │
└──────────────────┬──────────────────────┬────────────────────────┘
                   ↓                      ↓
┌──────────────────────────────┐  ┌─────────────────────────────┐
│  Phase 1: Extraction Tooling │  │  Phase 2: Information       │
│  ├─ Text segmentation        │  │           Architecture      │
│  ├─ Entity extraction        │  │  ├─ KB structure            │
│  ├─ Concept extraction       │  │  ├─ Taxonomy system         │
│  ├─ Relationship mapping     │  │  ├─ Metadata schemas        │
│  ├─ Metadata generation      │  │  ├─ Navigation patterns     │
│  └─ Link generation          │  │  └─ Quality standards       │
└──────────────────────────────┘  └─────────────────────────────┘
                   ↓                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Source Material (evidence/parsed/)            │
│              (PDFs, DOCX, Web content → Markdown)                │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│               Knowledge Base (knowledge-base/)                   │
│       (Structured, validated, IA-compliant artifacts)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Development Phases

### Phase 1: Extraction Tooling
**Status:** Planned  
**Duration:** 2-3 weeks  
**Dependencies:** None  

**Objective:** Build isolated, reusable text extraction modules.

**Deliverables:**
- Segmentation, entity, concept, relationship extraction modules
- CLI interfaces for each tool
- Comprehensive test coverage
- Configuration system

**Key Files:**
- `src/extraction/*.py` - Core extraction logic
- `src/cli/commands/extraction.py` - CLI registration
- `config/extraction.yaml` - Default configuration
- `tests/extraction/` - Test suite

**Success Criteria:**
- All modules independently testable
- CLI tools usable by copilot agents
- >90% test coverage

**Documentation:** [`phase-1-extraction-tooling/`](./phase-1-extraction-tooling/)

---

### Phase 2: Information Architecture
**Status:** Planned  
**Duration:** 3-4 weeks  
**Dependencies:** Phase 1  

**Objective:** Implement IA methodology with opinionated structure and guidelines.

**Deliverables:**
- KB directory structure and conventions
- Taxonomy system
- Metadata schemas (Dublin Core + custom)
- Document templates
- Validation framework

**Key Files:**
- `src/knowledge_base/*.py` - IA implementation
- `config/mission.yaml` - IA decisions and goals
- `config/taxonomy.yaml` - Controlled vocabulary
- `knowledge-base/meta/` - Methodology documentation

**Success Criteria:**
- Clear IA principles documented
- Findability: any concept in ≤3 clicks
- Consistent document structure
- Validated metadata compliance

**Documentation:** [`phase-2-information-architecture/`](./phase-2-information-architecture/)

---

### Phase 3: Knowledge Base Engine
**Status:** Planned  
**Duration:** 4-5 weeks  
**Dependencies:** Phase 1, Phase 2  

**Objective:** Orchestrate extraction tools and IA to build knowledge bases.

**Deliverables:**
- Pipeline orchestrator
- Extraction coordinator
- Transformation layer
- Organization manager
- Link builder
- Quality analyzer

**Key Files:**
- `src/kb_engine/*.py` - Engine components
- `config/kb-processing.yaml` - Pipeline configuration
- `config/templates/*.md.j2` - Document templates
- `reports/` - Quality metrics

**Success Criteria:**
- Single-command source → KB transformation
- Average quality score >0.75
- Process 100-page doc in <5 minutes
- Graceful error handling

**Documentation:** [`phase-3-knowledge-base-engine/`](./phase-3-knowledge-base-engine/)

---

### Phase 4: Agent Integration
**Status:** Planned  
**Duration:** 2-3 weeks  
**Dependencies:** Phase 1, 2, 3  

**Objective:** Enable copilot agents to autonomously build knowledge bases.

**Deliverables:**
- Issue templates for KB tasks
- Copilot workflow helpers
- MCP server for tool integration
- Automation workflows
- Quality monitoring

**Key Files:**
- `.github/templates/kb-*.md` - Issue templates
- `.github/workflows/kb-*.yml` - Automation
- `src/integrations/copilot/*.py` - Helpers
- `src/mcp_server/*.py` - MCP server

**Success Criteria:**
- >90% agent task success rate
- Source → KB in <1 hour automated
- >95% PR validation pass rate
- <10% manual intervention needed

**Documentation:** [`phase-4-agent-integration/`](./phase-4-agent-integration/)

---

## Timeline

```
Month 1          Month 2          Month 3          Month 4
│                │                │                │
├─ Phase 1 ──────┤                │                │
│   Extraction   │                │                │
│   Tooling      │                │                │
│                ├─ Phase 2 ──────┤                │
│                │   Information  │                │
│                │   Architecture │                │
│                │                ├─ Phase 3 ──────┤
│                │                │   KB Engine    │
│                │                │                ├─ Phase 4 ──┤
│                │                │                │   Agent    │
│                │                │                │   Integ.   │
└────────────────┴────────────────┴────────────────┴────────────┘
```

**Total Duration:** 11-15 weeks (3-4 months)

---

## Current State

### Completed ✓
- Document parsing (PDF, DOCX, Web, Markdown)
- GitHub issue creation and search
- Local copilot agent integration
- Branch/PR automation

### In Progress 🔄
- Project planning and architecture design
- Methodology selection and documentation

### Planned 📋
- All four development phases above

---

## Technology Stack

### Core Dependencies
- **Python 3.11+** - Primary language
- **spaCy** - NLP pipeline for extraction
- **nltk** - Text processing utilities
- **scikit-learn** - TF-IDF, clustering
- **networkx** - Graph analysis
- **pyyaml** - Configuration
- **pypdf** - PDF parsing (existing)

### Development Tools
- **pytest** - Testing framework
- **black/ruff** - Code formatting
- **mypy** - Type checking

### Integration
- **GitHub API** - Issue/PR management (existing)
- **GitHub Copilot CLI** - Agent execution (existing)
- **MCP (Model Context Protocol)** - Tool integration (new)

---

## Configuration Philosophy

The system is designed to be **mission-driven** and **domain-agnostic**:

### Project-Specific Configuration
```
config/
├── mission.yaml          # Goals, audience, IA decisions
├── taxonomy.yaml         # Domain-specific vocabulary
├── extraction.yaml       # Extraction parameters
└── kb-processing.yaml    # Pipeline configuration
```

### Cloned Repository Pattern
Different projects fork/clone this repository and provide their own:
- `mission.yaml` - Specific goals and methodology choices
- `taxonomy.yaml` - Domain taxonomy and vocabulary
- `.github/templates/` - Project-specific issue templates

**Example Projects:**
- Political philosophy knowledge base (current: "Speculum Principum")
- Legal document analysis
- Technical documentation organization
- Historical text corpus analysis

---

## Success Metrics

### System Performance
- **Processing Speed:** <5 min per 100-page document
- **Quality Score:** Average >0.75 completeness
- **Validation Pass Rate:** >95% on first attempt
- **Error Recovery:** <5% processing failures

### Agent Effectiveness
- **Task Success:** >90% of agent tasks complete autonomously
- **Human Intervention:** <10% of content requires manual review
- **Cycle Time:** Source → merged KB in <2 hours
- **Quality Improvement:** Automated improvements increase scores >10%

### Knowledge Base Quality
- **Findability:** Any concept reachable in ≤3 clicks
- **Completeness:** >90% of required metadata populated
- **Connectivity:** >80% of documents have related links
- **Consistency:** 100% adherence to naming conventions

---

## Risk Assessment

### Technical Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| NLP extraction quality | High | Multiple extraction strategies, human review |
| Performance at scale | Medium | Caching, parallel processing, incremental updates |
| Taxonomy complexity | Medium | Start simple, iterative refinement |

### Operational Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent failure rate | High | Robust error handling, fallbacks, monitoring |
| Quality drift | Medium | Automated validation, scheduled reviews |
| Configuration complexity | Low | Sensible defaults, clear documentation |

---

## Future Vision

### Beyond Phase 4

**Multi-Source Synthesis**
- Merge knowledge from multiple documents
- Resolve contradictions and conflicts
- Track concept evolution over time

**Active Learning**
- Improve extraction models from human corrections
- Fine-tune for specific domains
- Collaborative human-agent refinement

**Advanced Analytics**
- Trend analysis in concept usage
- Citation network analysis
- Knowledge gap identification
- Semantic similarity search

**Integration Expansion**
- Web scraping pipelines
- Database integration (Neo4j, PostgreSQL)
- Export to documentation platforms
- API for external consumption

---

## Getting Started

### For Developers

1. **Read methodology:** Start with Phase 2 documentation
2. **Understand extraction:** Review Phase 1 tools
3. **Study pipeline:** Examine Phase 3 orchestration
4. **Review workflows:** Check Phase 4 agent integration

### For Users (Forking for New Project)

1. **Clone repository**
2. **Define mission:** Create `config/mission.yaml`
3. **Build taxonomy:** Create `config/taxonomy.yaml`
4. **Configure extraction:** Adjust `config/extraction.yaml`
5. **Create templates:** Customize `.github/templates/`
6. **Run pipeline:** Process source materials

---

## Contributing

See individual phase documentation for:
- Architecture decisions
- Code structure
- Testing requirements
- Documentation standards

---

## Project Metadata

**Repository:** terrence-giggy/speculum-principum  
**Current Branch:** parse_the_prince  
**License:** [To be determined]  
**Maintainers:** [To be updated]

**Project Name Origin:**  
*Speculum Principum* (Latin: "Mirror for Princes") - A medieval and Renaissance literary genre offering advice for rulers. Fitting for a project extracting knowledge from political philosophy texts.

---

## Resources

### Information Architecture References
- *Information Architecture for the World Wide Web* (Rosenfeld & Morville)
- *How to Make Sense of Any Mess* (Abby Covert)
- IA Institute: https://www.iainstitute.org/

### Technical Documentation
- spaCy: https://spacy.io/
- Model Context Protocol: https://modelcontextprotocol.io/
- GitHub Copilot: https://docs.github.com/copilot

### Domain Knowledge
- Machiavelli's *The Prince* (source material)
- Renaissance political theory
- Digital humanities methodologies
