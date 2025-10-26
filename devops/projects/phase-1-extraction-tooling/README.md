# Phase 1: Extraction Tooling

**Status:** Planned  
**Dependencies:** None (foundational)  
**Estimated Effort:** 2-3 weeks

## Overview

Build isolated, reusable text extraction modules that transform parsed documents into structured data. These tools operate as pure functions with no dependencies on agents, GitHub integration, or knowledge base structure.

## Objectives

1. Create modular extraction libraries for common text analysis tasks
2. Provide CLI interfaces for use by copilot agents and humans
3. Ensure each module is independently testable and configurable
4. Establish data models for extraction results

## Architecture

### Core Modules

All modules live in `src/extraction/` with shared data models in `src/extraction/__init__.py`.

#### Tier 1: Text Analysis (Pure Functions)

**`src/extraction/segments.py`**
- Segment text into logical units (paragraphs, sentences, sections)
- Detect heading hierarchy
- Extract quoted passages
- Identify list structures

**`src/extraction/entities.py`**
- Extract named entities (people, places, organizations)
- Identify dates and temporal references
- Parse citations and references
- Detect technical terms and proper nouns

**`src/extraction/structure.py`**
- Analyze document hierarchy (chapters → sections → paragraphs)
- Detect and parse tables of contents
- Build cross-reference maps
- Identify footnotes and annotations

#### Tier 2: Semantic Analysis

**`src/extraction/concepts.py`**
- Extract key phrases and concepts
- Calculate term frequency and co-occurrence
- Detect concept definitions
- Identify domain-specific terminology

**`src/extraction/relationships.py`**
- Map citation networks
- Discover concept relationships
- Detect temporal sequences
- Identify comparisons and contrasts

#### Tier 3: Metadata & Organization

**`src/extraction/metadata.py`**
- Generate Dublin Core metadata fields
- Calculate quality metrics (completeness, readability)
- Track provenance and processing history
- Support custom taxonomy assignment

**`src/extraction/taxonomy.py`**
- Assign topics to documents
- Support hierarchical categorization
- Suggest tags based on content
- Manage controlled vocabularies

#### Tier 4: Output Generation

**`src/extraction/linking.py`**
- Generate backlinks between documents
- Build knowledge graphs
- Create navigation indexes
- Suggest related content

**`src/extraction/summarization.py`**
- Generate page summaries
- Create section abstracts
- Extract concept definitions
- Build tables of contents

### Data Models

```python
# src/extraction/__init__.py

@dataclass(frozen=True)
class ExtractedEntity:
    text: str
    entity_type: str  # PERSON, PLACE, ORG, DATE, etc.
    start_offset: int
    end_offset: int
    confidence: float
    metadata: dict[str, Any]

@dataclass(frozen=True)
class ExtractedConcept:
    term: str
    frequency: int
    positions: tuple[int, ...]
    related_terms: tuple[str, ...]
    definition: str | None

@dataclass(frozen=True)
class DocumentSegment:
    segment_type: str  # paragraph, heading, quote, list
    text: str
    level: int  # hierarchy level
    start_offset: int
    end_offset: int

@dataclass(frozen=True)
class ExtractionResult:
    source_path: str
    checksum: str
    extractor_name: str
    data: Any  # Type varies by extractor
    metadata: dict[str, Any]
    created_at: datetime
```

### CLI Interface

All extraction tools are accessible via `python -m main extract`:

```bash
# Extract concepts from a parsed document
python -m main extract concepts \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --output-format json \
  --min-frequency 2

# Extract entities
python -m main extract entities \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --entity-types PERSON ORG \
  --output concepts/entities.json

# Extract document structure
python -m main extract structure \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/ \
  --recursive \
  --output-format yaml

# Generate summaries
python -m main extract summarize \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --max-length 200 \
  --style abstract
```

### Configuration

Each extractor supports configuration via:
1. Command-line arguments
2. `config/extraction.yaml`
3. Programmatic API

Example config:
```yaml
# config/extraction.yaml
concepts:
  min_frequency: 2
  max_concepts: 50
  exclude_stopwords: true
  language: en

entities:
  confidence_threshold: 0.7
  entity_types:
    - PERSON
    - ORG
    - GPE
    - DATE

summarization:
  default_max_length: 250
  style: abstract
  preserve_formatting: true
```

## Deliverables

### Code Structure
```
src/extraction/
├── __init__.py          # Shared data models
├── segments.py          # Text segmentation
├── entities.py          # Named entity extraction
├── structure.py         # Document structure analysis
├── concepts.py          # Concept extraction
├── relationships.py     # Relationship mapping
├── metadata.py          # Metadata enrichment
├── taxonomy.py          # Classification system
├── linking.py           # Link generation
├── summarization.py     # Summary generation
└── cli.py               # CLI handlers

src/cli/commands/
└── extraction.py        # Register extraction commands

config/
└── extraction.yaml      # Default extraction settings

tests/extraction/
├── test_segments.py
├── test_entities.py
├── test_structure.py
├── test_concepts.py
├── test_relationships.py
├── test_metadata.py
├── test_taxonomy.py
├── test_linking.py
├── test_summarization.py
└── test_cli.py
```

### Testing Requirements

- Unit tests for each extraction module (>90% coverage)
- Integration tests for CLI commands
- Fixture data from real parsed documents
- Performance benchmarks for large documents

### Documentation

- API documentation for each module
- CLI usage examples
- Configuration reference
- Performance characteristics

## Dependencies

### Python Libraries

- `spacy` - NLP pipeline for entity recognition and linguistic analysis
- `nltk` - Natural language processing utilities
- `scikit-learn` - TF-IDF and clustering for concept extraction
- `networkx` - Graph analysis for relationships and linking
- `pyyaml` - Configuration file parsing

### Optional Enhancements

- `transformers` - Advanced NLP models for better extraction
- `keybert` - Keyword extraction using BERT embeddings
- `textstat` - Readability and quality metrics

## Success Criteria

1. All extraction modules have clean, documented APIs
2. CLI tools can be invoked by copilot agents
3. Each module is independently testable
4. Configuration system supports project-specific customization
5. Output formats (JSON, YAML, text) are well-defined and stable
6. Performance is acceptable for documents up to 1000 pages

## Future Enhancements

- Multilingual support
- Custom entity types via training
- Graph database integration for relationships
- Real-time extraction streaming for large documents
- Machine learning model fine-tuning per domain

## Notes

- These tools are **methodology-agnostic** - they extract data without imposing structure
- Phase 2 will opinionated how these tools are used within the Information Architecture methodology
- Tools should be usable outside this project (consider packaging as separate library)
