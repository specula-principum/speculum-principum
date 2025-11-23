# Entity Extraction Guide

## Overview

This guide documents the entity extraction system for the knowledge base. The system currently supports extracting:
1.  **People**: Names of individuals.
2.  **Organizations**: Companies, institutions, governments, etc.
3.  **Concepts**: Key themes, ideas, and definitions.

## Architecture

### Components

1.  **CLI Interface** (`src/cli/commands/extraction.py`)
2.  **Extraction Engine** (`src/knowledge/extraction.py`)
3.  **Knowledge Graph Storage** (`src/knowledge/storage.py`)
4.  **Orchestration Toolkit** (`src/orchestration/toolkit/extraction.py`)

### Data Flow

```
Parsed Documents (evidence/parsed/)
    ↓
CLI or Orchestration Tool
    ↓
Extractor (Person/Organization/Concept)
    ↓
KnowledgeGraphStorage
    ↓
Knowledge Graph (knowledge-graph/{type}/)
```

## CLI Usage

### Entry Point

The main entry point is through `main.py`:

```bash
python -m main extract [options]
```

### Command Options

-   `--limit N`: Process only N documents (useful for testing)
-   `--force`: Reprocess documents even if already extracted
-   `--dry-run`: Preview what would be extracted without saving
-   `--kb-root PATH`: Override default knowledge graph root directory
-   `--config PATH`: Specify custom parsing configuration file
-   `--orgs` / `--organizations`: Extract organizations instead of people
-   `--concepts`: Extract concepts instead of people
-   `--associations`: Extract associations between entities (People, Organizations, Concepts)

### Examples

```bash
# Extract people from all unprocessed documents (default)
python -m main extract

# Extract organizations
python -m main extract --orgs

# Extract concepts
python -m main extract --concepts

# Extract associations
python -m main extract --associations

# Test concept extraction on first document only
python -m main extract --concepts --limit 1

# Reprocess all documents for people
python -m main extract --force
```

## Recommended Workflow

For the best results, especially when extracting associations, it is recommended to run extractions in the following order:

1.  **Entities**: Extract People and Organizations first.
2.  **Concepts**: Extract Concepts next.
3.  **Associations**: Extract Associations last.

This order allows the Association Extractor to utilize the previously extracted entities as "hints" to identify relationships more accurately.

```bash
# 1. Extract base entities
python -m main extract
python -m main extract --orgs

# 2. Extract concepts
python -m main extract --concepts

# 3. Extract associations (uses hints from above)
python -m main extract --associations
```

## Extraction Methodology

The extraction system uses an LLM-based approach with `gpt-4o-mini` via GitHub Models.

### Common Features

-   **Chunking**: Documents exceeding ~6000 tokens are automatically split into chunks at paragraph boundaries.
-   **Deduplication**: Results from chunks are merged and deduplicated (case-insensitive).
-   **Artifact Support**: Supports single files, page directories, and legacy directory structures.

### 1. Person Extraction

-   **Target**: Unique person names.
-   **Normalization**: 'First Last' format.
-   **Exclusions**: Titles (Mr., Dr.) unless necessary.

### 2. Organization Extraction

-   **Target**: Companies, institutions, governments, military units, formal groups.
-   **Normalization**: Standardized names (e.g., 'The World Bank').
-   **Inclusions**: Historical organizations.

### 3. Concept Extraction

-   **Target**: Key concepts, themes, definitions, abstract ideas.
-   **Focus**: Core ideas and terminology, not document summarization.
-   **Normalization**: Standard forms (e.g., 'Social Contract').

### 4. Association Extraction

-   **Target**: Relationships between entities (People, Organizations, Concepts).
-   **Fields**: Source, Target, Relationship, Evidence, Source Type, Target Type, Confidence.
-   **Hints**: Uses previously extracted people, organizations, and concepts as hints to guide the LLM.

## Storage Format

Extracted entities are stored in the `knowledge-graph/` directory, organized by entity type.

### Directory Structure

```
knowledge-graph/
  people/
    {checksum}.json
  organizations/
    {checksum}.json
  concepts/
    {checksum}.json
  associations/
    {checksum}.json
```

### Schema

All extraction types share a similar JSON schema:

```json
{
  "source_checksum": "1327a866df4a...",
  "people": [ ... ],        // OR "organizations": [...], OR "concepts": [...]
  "extracted_at": "2025-11-22T22:55:42.955422+00:00",
  "metadata": {}
}
```

For associations, the schema is:

```json
{
  "source_checksum": "1327a866df4a...",
  "associations": [
    {
      "source": "Niccolo Machiavelli",
      "target": "The Prince",
      "relationship": "Author of",
      "evidence": "...",
      "source_type": "Person",
      "target_type": "Concept",
      "confidence": 0.9
    }
  ],
  "extracted_at": "...",
  "metadata": {}
}
```

## Orchestration Integration

The extraction toolkit is registered in the orchestration system and exposes the following tools:

-   `extract_people_from_document`
-   `extract_organizations_from_document`
-   `extract_concepts_from_document`
-   `extract_associations_from_document`

Each tool accepts a `checksum` and returns the extracted list.

## Testing

Tests are located in `tests/parsing/test_extraction.py` (and potentially split into `tests/knowledge/`).

To run tests:

```bash
pytest tests/parsing/test_extraction.py
```

## Troubleshooting

### Common Issues

-   **"Payload Too Large"**: Chunking usually handles this, but extremely long paragraphs might still cause issues.
-   **Zero Results**: Check if the document artifact path is correct in the manifest.
-   **Missing GITHUB_TOKEN**: Ensure the environment variable is set.
