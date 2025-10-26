# Phase 1: Extraction Tooling

**Status:** Completed  
**Dependencies:** None (foundational)  
**Estimated Effort:** 2-3 weeks

## Overview

Build isolated, reusable text extraction modules that transform parsed documents into structured data. These tools operate as pure functions with no dependencies on agents, GitHub integration, or knowledge base structure.

## Objectives

1. Create modular extraction libraries for common text analysis tasks (✅ delivered)
2. Provide CLI interfaces for use by copilot agents and humans (✅ delivered)
3. Ensure each module is independently testable and configurable (✅ delivered)
4. Establish data models for extraction results (✅ delivered)

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Run the extraction CLI via the single entry point: `python -m main extract segments --input <parsed.md>`
3. Benchmark extractors when tuning performance: `python -m main extract-benchmark --input <parsed.md>`
4. Execute the extraction-focused test suite: `pytest tests/extraction`

All commands assume the project root as the working directory and the default config at `config/extraction.yaml`.

## CLI Usage

`python -m main` exposes two production-ready commands registered under the `extract` namespace:

- `python -m main extract <extractor>` – Runs one extractor against a parsed document. Required `--input` argument accepts a file or directory. Optional flags:
  - `--config` (defaults to `config/extraction.yaml`) to override extractor settings.
  - `--output` to write serialized results to disk; omit to stream to stdout.
  - `--output-format {json,yaml,text}` to change serialization (default `json`).
  - `--dry-run` to validate config without executing the extractor.
- `python -m main extract-benchmark [extractor ...]` – Benchmarks one or many extractors over a single input. Flags mirror the extraction command with two additions:
  - `--iterations` positive integer controlling the repetition count (default `3`).
  - `--output-format {json,yaml}` for the summary metrics payload.

Both commands call into `src/extraction/cli.py` which ensures registry lookups, config loading, serialization, and structured error handling remain consistent across extractors.

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
class ExtractedRelationship:
  subject: str
  object: str
  relation_type: str
  evidence: str
  confidence: float
  metadata: dict[str, Any]

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

All extraction tools are accessible via `python -m main extract`. Example recipes:

```bash
# Extract concepts from a parsed document
python -m main extract concepts \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --output-format json

# Extract entities restricted to PERSON and ORG
python -m main extract entities \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --config config/extraction.yaml \
  --output outputs/entities.json

# Inspect document structure as YAML
python -m main extract structure \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/ \
  --output-format yaml

# Generate an abstract-style summary with highlights
python -m main extract summarization \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --output-format json \
  --output outputs/page-010-summary.json

# Benchmark tiers of extractors
python -m main extract-benchmark concepts summarization \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --iterations 5 \
  --output benchmarks/page-010.json

# Validate configuration only (no extraction)
python -m main extract entities \
  --input evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/page-010.md \
  --dry-run

extract-benchmark emits total, mean, median, min, and max durations per extractor in the requested format, enabling regression tracking in CI dashboards.
```

### Configuration

Each extractor supports configuration via:
1. Command-line arguments
2. `config/extraction.yaml`
3. Programmatic API

The shared loader in `src/extraction/config.py` normalizes keys, enforces that every extractor block is a mapping, and reports actionable errors through the CLI when misconfigured. Missing config files are treated as an empty mapping, while the default file (`config/extraction.yaml`) is loaded automatically when present.

Example config:
```yaml
# config/extraction.yaml
concepts:
  min_frequency: 2
  max_concepts: 50
  exclude_stopwords: true
  language: en

relationships:
  max_relationships: 100
  max_pairs_per_sentence: 6
  window_size: 3
  include_self_pairs: false

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
  max_sentences: 5
  min_sentence_length: 25
  include_highlights: true
  preserve_order: true
```

### Configuration Reference

Key configuration blocks and notable options:

- **concepts** – `min_frequency`, `max_concepts`, `exclude_stopwords`, `max_related_terms`, `window_size`, `min_term_length`.
- **entities** – `confidence_threshold`, `entity_types` (list or scalar), additional CLI `--entity-types` overrides the config.
- **relationships** – `max_relationships`, `max_pairs_per_sentence`, `window_size`, `include_self_pairs`, `keywords` vocabulary families.
- **metadata** – `include_quality_metrics`, `include_history`, `max_keywords`, `long_sentence_threshold` for readability scoring.
- **taxonomy** – `max_labels`, `min_score`, `bonus_weight` applied per keyword match.
- **linking** – `max_links`, `include_mentions`, `include_anchor_offsets` for provenance reporting.
- **summarization** – `default_max_length`, `style`, `max_sentences`, `include_highlights`, `preserve_order`.

Settings are merged with CLI-provided overrides, and every extractor automatically receives a `source_path` from CLI entry points to populate provenance metadata.

### Extractor API Surface

Every module exposes a single callable that returns an `ExtractionResult` dataclass. The registry in `src/extraction/cli.py` maps CLI keys to callables:

| CLI key        | Callable signature                                               | Notes |
| -------------- | ---------------------------------------------------------------- | ----- |
| `segments`     | `segment_text(text: str, *, config: Mapping[str, object] = None)` | Produces `DocumentSegment` tuples with heading/list/quote detection and count metadata. |
| `entities`     | `extract_entities(text: str, *, entity_types=None, config=None)`  | Provides PERSON/ORG/DATE heuristics with confidence filtering and deduplication. |
| `structure`    | `analyze_structure(text: str, *, config=None)`                    | Builds hierarchy metrics, cross-reference maps, and footnote listings. |
| `concepts`     | `extract_concepts(text: str, *, config=None)`                     | Outputs term frequencies, spans, and related-term mappings honoring stopword filters. |
| `relationships`| `extract_relationships(text: str, *, config=None)`                | Generates weighted relationship edges with provenance snippets and keyword tagging. |
| `metadata`     | `generate_metadata(text: str, *, config=None)`                    | Emits Dublin Core metadata, quality metrics, and processing history. |
| `taxonomy`     | `assign_taxonomy(text: str, *, config=None)`                      | Scores documents against hierarchical taxonomies producing scored label outputs. |
| `linking`      | `generate_links(text: str, *, config=None)`                       | Creates backlink suggestions, mention anchors, and related-document hints. |
| `summarization`| `summarize(text: str, *, config=None)`                             | Produces abstract-style summaries, highlights, and structured metadata. |

Extractors share hashing, timestamp generation, and metadata conventions so outputs remain interchangeable across downstream systems.

### Testing & Quality Gates

- Unit tests for every extractor live under `tests/extraction/` with >90% coverage.
- CLI integration tests exercise JSON/YAML serialization and error paths via `python -m main extract` and `extract-benchmark`.
- Performance regressions are caught by invoking `python -m main extract-benchmark` inside CI and tracking the emitted metric payloads.

### Performance & Observability

`extract-benchmark` metrics (total, mean, median, min, max) are deterministic, enabling comparison across runs. Each `ExtractionResult.metadata` block includes:

- `counts`/`segment_types` for segmentation analytics.
- Provenance fields (`source_path`, `checksum`) for traceability.
- Config snapshot to reproduce extractions and benchmark runs.

### Release Checklist

- [x] CLI entry points registered in `main.py`.
- [x] All extraction modules implemented and tested.
- [x] Configuration defaults documented and validated.
- [x] Benchmark workflow and metrics described for QA handoff.

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
- Performance benchmarks for large documents (extract-benchmark harness)
- Documentation covering API surface, CLI usage, config reference, and performance guidance

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
7. Documentation enables QA and code review to run extraction flows without additional context

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
