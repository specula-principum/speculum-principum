# Phase 3: Knowledge Base Engine

**Status:** Planned  
**Dependencies:** Phase 1 (Extraction Tooling), Phase 2 (Information Architecture)  
**Estimated Effort:** 4-5 weeks

## Overview

Build the orchestration layer that combines extraction tools (Phase 1) with IA methodology (Phase 2) to automatically transform parsed source materials into structured knowledge bases. This engine implements workflows, pipelines, and quality assurance processes.

---

## Objectives

1. Orchestrate extraction tools to process parsed documents
2. Apply IA structure and conventions automatically
3. Build and maintain knowledge graphs
4. Ensure quality through validation and metrics
5. Support incremental updates and refinement
6. Enable mission-driven customization

---

## Architecture

### Workflow Engine

The KB engine follows a pipeline architecture:

```
Source Material (evidence/parsed/)
    ↓
[1. Analysis] - Understand source structure
    ↓
[2. Extraction] - Run extraction tools (concepts, entities, etc.)
    ↓
[3. Transformation] - Convert to KB documents
    ↓
[4. Organization] - Place in IA-compliant structure
    ↓
[5. Linking] - Create relationships and navigation
    ↓
[6. Validation] - Check quality and consistency
    ↓
Knowledge Base (knowledge-base/)
```

### Core Components

#### 1. Pipeline Orchestrator

**`src/kb_engine/pipeline.py`**

```python
class KBPipeline:
    """Orchestrates the full extraction-to-KB workflow."""
    
    def process_source(self, source_path: Path) -> KBProcessingResult:
        """Transform parsed source into KB artifacts."""
        # 1. Analyze source structure
        # 2. Run extraction tools
        # 3. Transform to KB documents
        # 4. Organize in IA structure
        # 5. Generate links
        # 6. Validate
        
    def update_existing(self, kb_id: str) -> KBUpdateResult:
        """Update existing KB entry with new data."""
        
    def rebuild_indexes(self) -> None:
        """Regenerate all navigation indexes."""
```

Supports:
- **Full processing** - New sources → complete KB generation
- **Incremental updates** - Refresh specific concepts/entities
- **Index rebuilding** - Regenerate navigation after changes
- **Quality refinement** - Re-run validation and improve quality scores

#### 2. Extraction Coordinator

**`src/kb_engine/extraction.py`**

```python
class ExtractionCoordinator:
    """Manages extraction tool execution and result aggregation."""
    
    def extract_all(self, text: str, config: ExtractionConfig) -> ExtractionBundle:
        """Run all configured extractors on input text."""
        
    def extract_selective(self, text: str, extractors: list[str]) -> ExtractionBundle:
        """Run only specified extractors."""
```

Features:
- Parallel extraction execution
- Result caching and reuse
- Error handling and fallbacks
- Progress reporting

#### 3. Transformation Layer

**`src/kb_engine/transform.py`**

```python
class KBTransformer:
    """Converts extraction results to KB documents."""
    
    def create_concept_document(
        self,
        concept: ExtractedConcept,
        context: TransformContext,
    ) -> KBDocument:
        """Generate a concept document from extracted data."""
        
    def create_entity_document(
        self,
        entity: ExtractedEntity,
        context: TransformContext,
    ) -> KBDocument:
        """Generate an entity document from extracted data."""
```

Responsibilities:
- Apply document templates
- Generate frontmatter metadata
- Format content sections
- Create source references
- Calculate initial quality scores

#### 4. Organization Manager

**`src/kb_engine/organize.py`**

```python
class KBOrganizer:
    """Places documents in IA-compliant directory structure."""
    
    def place_document(
        self,
        document: KBDocument,
        kb_root: Path,
    ) -> Path:
        """Determine correct location and write document."""
        
    def ensure_indexes(self, kb_root: Path) -> None:
        """Create or update index.md files."""
```

Features:
- Taxonomy-driven placement
- Automatic slug generation
- Collision detection and resolution
- Index file generation
- Breadcrumb management

#### 5. Link Builder

**`src/kb_engine/links.py`**

```python
class LinkBuilder:
    """Generates and maintains relationships between KB documents."""
    
    def build_concept_graph(self, kb_root: Path) -> ConceptGraph:
        """Create graph of concept relationships."""
        
    def generate_backlinks(self, kb_root: Path) -> None:
        """Add bidirectional links to all documents."""
        
    def suggest_related(self, kb_id: str) -> list[str]:
        """Recommend related content based on similarity."""
```

Algorithms:
- Co-occurrence analysis for concept relationships
- Citation network for source relationships
- Similarity scoring for recommendations
- Graph centrality for importance ranking

#### 6. Quality Assurance

**`src/kb_engine/quality.py`**

```python
class QualityAnalyzer:
    """Measures and improves KB quality metrics."""
    
    def calculate_completeness(self, document: KBDocument) -> float:
        """Score metadata and content completeness (0.0-1.0)."""
        
    def calculate_findability(self, kb_id: str, kb_root: Path) -> float:
        """Score how discoverable this document is."""
        
    def identify_gaps(self, kb_root: Path) -> list[QualityGap]:
        """Find missing links, incomplete metadata, orphaned docs."""
```

Metrics:
- **Completeness** - % of required fields populated
- **Findability** - Number of access paths, link depth
- **Consistency** - Adherence to naming/formatting conventions
- **Coverage** - % of source material represented
- **Connectivity** - Ratio of links to documents

---

## Workflows

### Workflow 1: Process New Source Material

```bash
# Full pipeline: evidence/parsed → knowledge-base
python -m main kb process \
  --source evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/ \
  --kb-root knowledge-base/ \
  --mission config/mission.yaml \
  --extract concepts entities relationships \
  --validate
```

**Steps:**
1. Read source index and metadata
2. For each page/section:
   - Run extraction tools
   - Transform results to KB documents
   - Organize in IA structure
3. Build cross-document links
4. Generate navigation indexes
5. Validate quality
6. Report results

**Output:**
```
Processing: The Prince (150 pages)
├─ Extracted: 247 concepts
├─ Extracted: 89 entities (53 people, 24 places, 12 orgs)
├─ Extracted: 156 relationships
├─ Created: 247 concept documents
├─ Created: 89 entity documents
├─ Created: 12 source documents
├─ Generated: 2,341 cross-links
├─ Updated: 34 index files
└─ Quality: avg 0.78 completeness, 0.82 findability

Knowledge base: knowledge-base/
└─ Ready for review
```

### Workflow 2: Incremental Update

```bash
# Update specific concept with new analysis
python -m main kb update \
  --kb-id concepts/statecraft/virtue \
  --source evidence/parsed/2025/prince01mach-1-pdf-1327a866df4a/ \
  --reextract \
  --rebuild-links
```

**Steps:**
1. Load existing KB document
2. Re-run extractors on source material
3. Merge new data with existing
4. Recalculate quality scores
5. Update related documents
6. Rebuild affected indexes

### Workflow 3: Quality Improvement Pass

```bash
# Find and fix quality issues
python -m main kb improve \
  --kb-root knowledge-base/ \
  --min-completeness 0.75 \
  --fix-links \
  --suggest-tags
```

**Steps:**
1. Scan all documents
2. Identify quality gaps
3. Suggest improvements
4. Optionally auto-fix issues
5. Generate improvement report

### Workflow 4: Knowledge Graph Export

```bash
# Export relationships for visualization
python -m main kb export-graph \
  --kb-root knowledge-base/ \
  --format graphml \
  --output knowledge-graph.xml
```

Supported formats:
- GraphML (Cypher, Neo4j)
- DOT (Graphviz)
- JSON (D3.js)
- CSV (edge list)

---

## Configuration

### Processing Configuration

```yaml
# config/kb-processing.yaml
pipeline:
  extraction:
    enabled_tools:
      - concepts
      - entities
      - structure
      - relationships
    
    parallel_execution: true
    cache_results: true
    cache_ttl: 86400  # 24 hours
  
  transformation:
    templates_dir: config/templates/
    apply_quality_filters: true
    min_concept_frequency: 2
    min_entity_confidence: 0.7
  
  organization:
    auto_slug: true
    slug_format: kebab-case
    collision_strategy: append_hash
    index_generation: auto
  
  linking:
    build_concept_graph: true
    generate_backlinks: true
    max_related_items: 10
    similarity_threshold: 0.6
  
  quality:
    validate_on_creation: true
    auto_fix_simple_issues: true
    required_completeness: 0.7
    required_findability: 0.6

monitoring:
  log_level: INFO
  progress_updates: true
  metrics_output: reports/kb-metrics.json
```

---

## Deliverables

### Code Structure

```
src/kb_engine/
├── __init__.py           # Core models and exceptions
├── pipeline.py           # Main orchestration
├── extraction.py         # Extraction coordination
├── transform.py          # KB document generation
├── organize.py           # IA-compliant placement
├── links.py              # Relationship building
├── quality.py            # Quality metrics
└── cli.py                # CLI handlers

src/cli/commands/
└── kb_engine.py          # Register engine commands

config/
├── kb-processing.yaml    # Pipeline configuration
└── templates/            # KB document templates
    ├── concept.md.j2
    ├── entity.md.j2
    └── source.md.j2

reports/                  # Generated quality reports
└── .gitkeep

tests/kb_engine/
├── test_pipeline.py
├── test_extraction.py
├── test_transform.py
├── test_organize.py
├── test_links.py
└── test_quality.py
```

### Documentation

- **Pipeline Architecture** - How components interact
- **Workflow Guide** - Step-by-step for each workflow
- **Configuration Reference** - All options explained
- **Quality Metrics** - How scores are calculated
- **Troubleshooting** - Common issues and solutions

---

## Integration Points

### With Phase 1 (Extraction Tooling)
- Calls extraction CLIs programmatically
- Parses JSON/YAML output
- Handles extraction errors gracefully

### With Phase 2 (Information Architecture)
- Uses KB structure definitions
- Applies taxonomy classifications
- Follows metadata schemas
- Validates against IA standards

### With Phase 4 (Agent Integration)
- Provides CLI for copilot agents
- Generates issues for quality gaps
- Reports progress for monitoring

---

## Success Criteria

1. **Automation**: Full source → KB with single command
2. **Quality**: Average KB completeness >0.75
3. **Performance**: Process 100-page document in <5 minutes
4. **Reliability**: Handle extraction failures gracefully
5. **Incremental**: Update existing KB without full rebuild
6. **Validation**: Catch and report structural issues

---

## Future Enhancements

- **Active Learning** - Improve extraction models based on KB feedback
- **Conflict Resolution** - Handle contradictory information from sources
- **Multi-Source Synthesis** - Merge information from multiple sources
- **Temporal Tracking** - Track how concepts evolve across time
- **Collaborative Editing** - Support human refinement of auto-generated content
- **Real-time Processing** - Stream processing for live document ingestion

---

## Notes

- This engine is the "brain" that combines Phase 1 tools with Phase 2 methodology
- Configuration allows project-specific customization without code changes
- Quality metrics make iterative improvement measurable
- Designed to be run by copilot agents or human operators
