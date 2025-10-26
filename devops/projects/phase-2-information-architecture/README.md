# Phase 2: Information Architecture Implementation

**Status:** Planned  
**Dependencies:** Phase 1 (Extraction Tooling)  
**Estimated Effort:** 3-4 weeks

## Overview

Implement **Information Architecture (IA)** as the foundational methodology for organizing knowledge extracted from source materials. This phase defines opinionated structures, conventions, and processes that guide how knowledge bases are built and maintained.

---

## What is Information Architecture?

Information Architecture is the practice of organizing, structuring, and labeling content to support **findability**, **understandability**, and **usability**. Originating from library science and refined through web design and content management, IA provides battle-tested patterns for organizing large knowledge collections.

### Core IA Principles

1. **Organization Systems** - How information is categorized (hierarchical, sequential, topical)
2. **Labeling Systems** - How information is represented (terminology, naming conventions)
3. **Navigation Systems** - How users browse and move through information
4. **Search Systems** - How users look for information
5. **Metadata Standards** - Descriptive information that enables discovery

### Why IA for This Project?

- **Proven methodology** used by libraries, documentation teams, and content platforms
- **Scalable** - works for 10 documents or 10,000 documents
- **Human-centered** - optimizes for how people actually search and browse
- **Tool-agnostic** - principles apply regardless of technology
- **Measurable** - clear success criteria (findability studies, search analytics)

---

## Architecture

### Knowledge Base Structure

Opinionated directory layout following IA principles:

```
knowledge-base/
├── index.md                          # Master navigation hub (Map of Content)
├── metadata.yaml                     # KB-level metadata
├── taxonomy.yaml                     # Controlled vocabulary definitions
│
├── concepts/                         # Organized by concept (topic-based)
│   ├── index.md                      # Concept directory
│   ├── statecraft/
│   │   ├── index.md
│   │   ├── virtue.md
│   │   ├── fortune.md
│   │   └── power.md
│   └── political-theory/
│       ├── index.md
│       └── republicanism.md
│
├── entities/                         # Organized by entity type
│   ├── index.md
│   ├── people/
│   │   ├── index.md
│   │   ├── cesare-borgia.md
│   │   └── pope-alexander-vi.md
│   ├── places/
│   │   ├── index.md
│   │   └── florence.md
│   └── organizations/
│       ├── index.md
│       └── medici-family.md
│
├── sources/                          # Organized by source material
│   ├── index.md
│   ├── the-prince/
│   │   ├── index.md
│   │   ├── metadata.yaml
│   │   ├── chapters/
│   │   │   ├── chapter-01.md
│   │   │   └── chapter-02.md
│   │   └── analysis/
│   │       └── key-themes.md
│   └── discourses/
│       └── index.md
│
├── relationships/                    # Graph-based connections
│   ├── index.md
│   ├── concept-graph.yaml
│   └── citation-network.yaml
│
└── meta/                            # About the knowledge base
    ├── methodology.md               # IA principles used
    ├── conventions.md               # Naming and formatting rules
    ├── quality-standards.md         # Quality criteria
    └── processing-history.yaml      # Transformation log
```

### Document Templates

Every document follows IA-informed frontmatter:

```markdown
---
# Identity
title: "Virtue in The Prince"
slug: virtue-in-the-prince
kb_id: concepts/statecraft/virtue
type: concept

# Classification (controlled vocabulary from taxonomy.yaml)
primary_topic: statecraft
secondary_topics:
  - political-theory
  - ethics
tags:
  - machiavelli
  - renaissance

# Discovery metadata
aliases:
  - virtù
  - political virtue
related_concepts:
  - fortune
  - power
  - necessity

# Provenance
sources:
  - kb_id: sources/the-prince/chapters/chapter-15
    pages: [15, 16, 17]
  - kb_id: sources/the-prince/chapters/chapter-25
    pages: [25]

# Quality metrics
completeness: 0.85
last_reviewed: 2025-10-25
reviewed_by: copilot-agent-v2

# Search optimization
keywords:
  - virtue
  - virtù
  - moral flexibility
  - pragmatic ethics
---

# Virtue (Virtù)

## Definition

In Machiavelli's *The Prince*, **virtù** refers to...

## Context

This concept appears primarily in chapters...

## Related Concepts

- [[fortune]] - Virtue's counterpart
- [[power]] - The goal virtue serves

## Source References

> "A prince must have the flexibility to change with circumstances..."
> — The Prince, Chapter 18, p. 15

## Analysis

[Generated summary from extraction tools]

## Backlinks

- Referenced in: [[cesare-borgia]]
- Discussed in: [[chapter-15-analysis]]
```

### Metadata Schema (Dublin Core + Custom)

Every knowledge artifact includes:

```yaml
# Dublin Core (standard library metadata)
dc:
  title: string
  creator: string
  subject: string[]
  description: string
  publisher: string
  contributor: string[]
  date: ISO8601
  type: string
  format: string
  identifier: string
  source: string
  language: string
  relation: string[]
  coverage: string

# Custom IA metadata
ia:
  findability_score: float        # 0.0-1.0
  completeness: float              # 0.0-1.0
  depth: int                       # 1-5 (surface to deep)
  audience: string[]               # target reader types
  navigation_path: string[]        # breadcrumb trail
  related_by_topic: string[]       # KB IDs
  related_by_entity: string[]      # KB IDs
  last_updated: ISO8601
  update_frequency: string         # static, monthly, etc.
```

### Taxonomy Structure

Controlled vocabulary in `knowledge-base/taxonomy.yaml`:

```yaml
version: "1.0.0"
methodology: information-architecture

# Topic taxonomy (hierarchical)
topics:
  political-theory:
    label: "Political Theory"
    definition: "Theories of governance and political organization"
    children:
      - republicanism
      - monarchy
      - democracy
  
  statecraft:
    label: "Statecraft"
    definition: "The art of conducting state affairs"
    children:
      - virtue
      - fortune
      - power
      - necessity

# Entity types (faceted)
entity_types:
  person:
    label: "Person"
    properties:
      - birth_date
      - death_date
      - nationality
      - roles
  
  place:
    label: "Place"
    properties:
      - coordinates
      - time_period
      - political_entity

# Relationship types
relationship_types:
  influences:
    label: "Influences"
    inverse: "influenced_by"
  
  contradicts:
    label: "Contradicts"
    inverse: "contradicted_by"
  
  exemplifies:
    label: "Exemplifies"
    inverse: "exemplified_by"

# Controlled vocabulary terms
vocabulary:
  statecraft:
    preferred_term: "statecraft"
    alternate_terms:
      - "art of government"
      - "political craft"
    related_terms:
      - "governance"
      - "political strategy"
```

### Navigation Systems

**1. Hierarchical Navigation (index.md files)**
- Every directory has an index.md
- Provides context and links to children
- Shows breadcrumb trail

**2. Faceted Navigation (multiple classification paths)**
- Same concept accessible via topic, entity, or source
- Each path provides different context

**3. Associative Navigation (related links)**
- "See also" links based on relationships
- Bidirectional linking
- Graph-based recommendations

**4. Search Enhancement**
- Full-text search via tags and keywords
- Metadata-based filtering
- Controlled vocabulary for precision

---

## Implementation Components

### Core Modules

**`src/knowledge_base/__init__.py`**
- Core data models for KB artifacts
- Document templates
- Metadata schemas

**`src/knowledge_base/structure.py`**
- Create opinionated directory structures
- Generate index files
- Maintain navigation hierarchies

**`src/knowledge_base/taxonomy.py`**
- Load and validate taxonomy definitions
- Assign controlled vocabulary terms
- Suggest classifications based on content

**`src/knowledge_base/metadata.py`**
- Generate IA-compliant metadata
- Calculate quality metrics
- Track provenance

**`src/knowledge_base/linking.py`**
- Create bidirectional links
- Build concept graphs
- Generate "related content" recommendations

**`src/knowledge_base/validation.py`**
- Validate document structure
- Check metadata completeness
- Verify taxonomy compliance
- Identify broken links

### CLI Interface

```bash
# Initialize a new knowledge base with IA structure
python -m main kb init \
  --root knowledge-base/ \
  --taxonomy config/taxonomy.yaml \
  --mission-statement config/mission.yaml

# Validate knowledge base structure
python -m main kb validate \
  --root knowledge-base/ \
  --check-links \
  --check-metadata

# Generate navigation indexes
python -m main kb build-indexes \
  --root knowledge-base/

# Calculate quality metrics
python -m main kb metrics \
  --root knowledge-base/ \
  --output reports/quality.json
```

### Configuration

Mission statement defines IA decisions:

```yaml
# config/mission.yaml
mission:
  title: "Political Philosophy Knowledge Base"
  description: "Extracting and organizing knowledge from Renaissance political texts"
  audience:
    - students
    - researchers
    - political scientists
  
  goals:
    - "Make Machiavelli's ideas accessible and discoverable"
    - "Connect concepts across multiple works"
    - "Track intellectual influences and relationships"

information_architecture:
  methodology: information-architecture
  version: "1.0"
  
  organization_scheme: hybrid
  organization_types:
    - topical          # Primary: by concept/topic
    - alphabetical     # Secondary: by entity name
    - chronological    # Tertiary: by source date
  
  depth_strategy: progressive_disclosure
  # Level 1: Overview/summary
  # Level 2: Key details
  # Level 3: Deep analysis
  # Level 4: Source references
  # Level 5: Academic commentary
  
  labeling_conventions:
    case: kebab-case
    max_length: 80
    preferred_language: en
    terminology_source: taxonomy.yaml
  
  navigation_priority:
    - concept_based     # Primary: browse by topic
    - entity_based      # Secondary: browse by person/place
    - source_based      # Tertiary: browse by original text
  
  search_optimization:
    - full_text_enabled: true
    - metadata_indexing: true
    - synonym_expansion: true
    - related_content_suggestions: true
  
  quality_standards:
    min_completeness: 0.7
    min_findability: 0.6
    required_metadata:
      - title
      - type
      - primary_topic
      - sources
    link_depth: 3  # Maximum clicks from index
```

---

## Deliverables

### Code Structure
```
src/knowledge_base/
├── __init__.py           # Core data models
├── structure.py          # Directory and file management
├── taxonomy.py           # Controlled vocabulary
├── metadata.py           # Metadata generation
├── linking.py            # Link management
├── validation.py         # Quality assurance
└── cli.py                # CLI handlers

src/cli/commands/
└── knowledge_base.py     # Register kb commands

config/
├── mission.yaml          # Project-specific IA decisions
└── taxonomy.yaml         # Controlled vocabulary

knowledge-base/           # Generated KB (in .gitignore)
└── [opinionated structure]

tests/knowledge_base/
└── [comprehensive tests]
```

### Documentation

**`knowledge-base/meta/methodology.md`** - Comprehensive guide to IA principles used

**`knowledge-base/meta/conventions.md`** - Naming, formatting, and structural rules

**`knowledge-base/meta/quality-standards.md`** - Quality criteria and metrics

### Templates

`.github/templates/kb-concept.md` - Issue template for adding concepts
`.github/templates/kb-entity.md` - Issue template for adding entities
`.github/templates/kb-source.md` - Issue template for processing sources

---

## Success Criteria

1. **Findability**: Users can locate any concept in ≤3 clicks
2. **Consistency**: All documents follow templates and conventions
3. **Quality**: Average completeness score >0.75
4. **Navigation**: No dead-end pages (all have related links)
5. **Validation**: All links resolve, all metadata complete
6. **Scalability**: Structure supports 1000+ documents without reorganization

---

## Notes

- **This phase is opinionated** - it makes specific IA decisions
- Decisions are documented in mission.yaml for transparency
- Different projects can use different taxonomies while keeping the tooling
- The methodology is clearly declared in every generated KB
- Quality metrics make IA principles measurable
