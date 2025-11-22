# Entity Extraction Guide

## Overview

This guide documents the entity extraction system for the knowledge base, starting with person name extraction. The architecture is designed to be extensible for additional entity types (organizations, locations, etc.).

## Architecture

### Components

1. **CLI Interface** (`src/cli/commands/extraction.py`)
2. **Extraction Engine** (`src/knowledge/extraction.py`)
3. **Knowledge Graph Storage** (`src/knowledge/storage.py`)
4. **Orchestration Toolkit** (`src/orchestration/toolkit/extraction.py`)

### Data Flow

```
Parsed Documents (evidence/parsed/)
    ↓
CLI or Orchestration Tool
    ↓
PersonExtractor (LLM-based)
    ↓
KnowledgeGraphStorage
    ↓
Knowledge Graph (knowledge-graph/people/)
```

## CLI Usage

### Entry Point

The main entry point is through `main.py`:

```bash
python -m main extract [options]
```

### Command Options

- `--limit N`: Process only N documents (useful for testing)
- `--force`: Reprocess documents even if already extracted
- `--dry-run`: Preview what would be extracted without saving
- `--kb-root PATH`: Override default knowledge graph root directory
- `--config PATH`: Specify custom parsing configuration file

### Examples

```bash
# Extract from all unprocessed documents
python -m main extract

# Test extraction on first document only
python -m main extract --limit 1

# Reprocess all documents
python -m main extract --force

# Preview extraction without saving
python -m main extract --dry-run
```

## Person Extraction Methodology

### Current Implementation

The `PersonExtractor` class in `src/knowledge/extraction.py` uses an LLM-based approach with the following characteristics:

#### Prompting Strategy

```python
system_prompt = (
    "You are an expert entity extractor. Your task is to extract all unique person names "
    "from the provided text. Return ONLY a JSON array of strings. "
    "Do not include titles (Mr., Dr.) unless necessary for disambiguation. "
    "Normalize names to 'First Last' format where possible. "
    "If no people are found, return an empty array []."
)
```

**Key aspects:**
- Structured output (JSON array)
- Name normalization
- Title handling rules
- Empty result handling

#### Chunking for Large Documents

Documents exceeding ~6000 tokens are automatically split into chunks:

1. **Chunk Size**: 6000 tokens (~24,000 characters)
2. **Splitting Strategy**: Split on paragraph boundaries (`\n\n`) to preserve context
3. **Processing**: Each chunk processed independently
4. **Deduplication**: Results merged and deduplicated (case-insensitive)

This prevents token limit errors and enables processing of large documents like books.

#### LLM Configuration

- **Model**: `gpt-4o-mini` (via GitHub Models API)
- **Temperature**: 0.1 (low for deterministic output)
- **Max Tokens**: 2000 (for response)

### Handling Parsed Document Artifacts

The system supports multiple artifact types:

1. **Page Directory** (most common for PDFs):
   - Manifest points to `index.md`
   - Actual content in `page-NNN.md` files
   - Detection: `metadata['artifact_type'] == 'page-directory'`
   - Processing: Read all `*.md` files except `index.md` from parent directory

2. **Single File**:
   - Manifest points directly to the file
   - Processing: Read file content directly

3. **Legacy Directory**:
   - Manifest points to directory
   - Processing: Read all `*.md` files except `index.md`

**Critical Implementation Detail:**
```python
is_page_directory = entry.metadata.get("artifact_type") == "page-directory"

if is_page_directory:
    directory = artifact_path.parent
    pages = sorted([p for p in directory.glob("*.md") if p.name != "index.md"])
    full_text = "\n\n".join([p.read_text(encoding="utf-8") for p in pages])
```

## Storage Format

### File Location

Extracted entities are stored in:
```
knowledge-graph/
  people/
    {checksum}.json
```

### Schema

```json
{
  "source_checksum": "1327a866df4a...",
  "people": [
    "Niccolo Machiavelli",
    "Luigi Ricci",
    "Lorenzo de' Medici"
  ],
  "extracted_at": "2025-11-22T22:55:42.955422+00:00",
  "metadata": {}
}
```

**Fields:**
- `source_checksum`: Links to parsed document manifest entry
- `people`: Array of extracted person names
- `extracted_at`: ISO 8601 timestamp
- `metadata`: Extensible field for additional information

## Orchestration Integration

### Tool Registration

The extraction toolkit is registered in the orchestration system:

```python
from src.orchestration.toolkit.extraction import register_extraction_tools

register_extraction_tools(registry)
```

### Available Tools

#### `extract_people_from_document`

Extracts person names from a parsed document.

**Parameters:**
- `checksum` (string, required): Document checksum from manifest

**Returns:**
```json
{
  "status": "success",
  "extracted_count": 81,
  "people": ["Name 1", "Name 2", ...]
}
```

**Error Handling:**
- Document not found in manifest
- Document parsing not completed
- Extraction failures (with error message)

## Testing

### Test Coverage

Location: `tests/parsing/test_extraction.py`

**Test Cases:**
1. Basic extraction with mocked LLM
2. Empty response handling
3. Markdown-wrapped JSON handling
4. Full document processing (page-directory structure)
5. Storage persistence

### Running Tests

```bash
# Run extraction tests only
pytest tests/parsing/test_extraction.py -v

# Run with coverage
pytest tests/parsing/test_extraction.py --cov=src.knowledge
```

## Extending for Organization Extraction

### Recommended Approach

1. **Create `OrganizationExtractor` class** (similar to `PersonExtractor`)
   - Location: `src/knowledge/extraction.py`
   - Use similar LLM prompting strategy
   - Reuse chunking logic

2. **Update Storage**
   - Add `knowledge-graph/organizations/` directory
   - Create `ExtractedOrganizations` dataclass
   - Extend `KnowledgeGraphStorage` with organization methods

3. **Add CLI Command**
   - Extend `src/cli/commands/extraction.py`
   - Add `--extract-orgs` flag or separate subcommand
   - Follow same pattern as people extraction

4. **Register Orchestration Tool**
   - Add `extract_organizations_from_document` to toolkit
   - Update `src/orchestration/toolkit/extraction.py`

### Prompting Considerations for Organizations

```python
system_prompt = (
    "You are an expert entity extractor. Extract all organization names "
    "from the text including: companies, institutions, governments, "
    "military units, and other formal groups. Return ONLY a JSON array. "
    "Normalize names (e.g., 'The World Bank' not 'the world bank'). "
    "Include historical organizations. If none found, return []."
)
```

### Shared Infrastructure

**Reusable components:**
- Chunking logic (`_extract_chunked` pattern)
- Document artifact handling (`process_document` structure)
- Storage patterns (atomic writes, JSON serialization)
- CLI argument parsing structure
- Test fixtures and mocking patterns

## Environment Requirements

### Required Environment Variables

- `GITHUB_TOKEN`: GitHub Models API token for LLM access

### Dependencies

```python
from src.integrations.copilot import CopilotClient
from src.knowledge.storage import KnowledgeGraphStorage
from src.parsing.storage import ParseStorage
```

## Performance Considerations

### Token Usage

- Small documents (<6000 tokens): 1 LLM call
- Large documents: Multiple calls (document_size / 6000 tokens)
- Example: 150-page book ≈ 25-30 LLM calls

### Rate Limiting

Currently no rate limiting implemented. Consider adding:
- Exponential backoff for API errors
- Configurable delay between chunks
- Batch processing limits

### Optimization Opportunities

1. **Caching**: Cache extraction results by content hash
2. **Parallel Processing**: Process multiple documents concurrently
3. **Incremental Updates**: Only process new/changed documents
4. **Selective Extraction**: Extract from specific page ranges

## Troubleshooting

### Common Issues

**Issue**: "Payload Too Large" error
- **Cause**: Document exceeds token limit without chunking
- **Solution**: Chunking now automatic; check implementation

**Issue**: No people extracted (0 count)
- **Cause**: Reading wrong artifact path (e.g., only index.md)
- **Solution**: Verify `artifact_type` handling in `process_document`

**Issue**: Duplicate names in results
- **Cause**: Deduplication not case-insensitive
- **Solution**: Normalize before comparison (`.lower()`)

**Issue**: Missing GITHUB_TOKEN
- **Cause**: Environment variable not set
- **Solution**: Export token or add to `.env` file

### Debug Mode

Enable verbose output:
```python
# In extraction.py, add logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Entity Linking

Link extracted entities to knowledge bases:
- Wikidata IDs
- DBpedia URIs
- Custom entity resolution

### Relationship Extraction

Extract relationships between entities:
- Person-Organization affiliations
- Person-Person relationships
- Organization hierarchies

### Confidence Scores

Add confidence metrics:
- Per-entity extraction confidence
- Ambiguity detection
- Multi-pass verification

### Cross-Reference Validation

Validate extractions across documents:
- Name variant detection
- Co-reference resolution
- Entity consolidation

## References

### Related Documentation

- [Agent Operations Guide](./agent-operations.md)
- [Parsing System](../src/parsing/README.md) (if exists)

### Key Files

- CLI: `src/cli/commands/extraction.py`
- Extraction: `src/knowledge/extraction.py`
- Storage: `src/knowledge/storage.py`
- Toolkit: `src/orchestration/toolkit/extraction.py`
- Tests: `tests/parsing/test_extraction.py`
- Config: `config/missions/parse_and_extract.yaml`
