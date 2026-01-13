# Synthesis Agent QA Response

**Date:** January 12, 2026  
**Issue:** Missing concept content, associations, and cross-type entity leakage

---

## Issues Identified

Based on QA feedback on the first batch of synthesized concepts:

### 1. Cross-Type Leakage ❌
- **Problem:** Person names appearing in Concepts (e.g., "Joe Lombardi", "Vance Joseph")
- **Problem:** Organization names appearing in Concepts (e.g., "Los Angeles Chargers")
- **Root Cause:** Extraction agent's concept extraction prompt was too vague and didn't explicitly exclude people/organizations

### 2. Missing Concept Content ❌
- **Problem:** Concepts had no description/definition - just metadata (timestamps, sources, etc.)
- **Example:** "creating turnovers" had no explanation of what this concept means
- **Root Cause:** Synthesis agent only copied raw entity names without enriching attributes

### 3. Missing Associations ❌
- **Problem:** All concepts had empty `associations` arrays
- **Root Cause:** Extracted associations exist in `knowledge-graph/associations/{checksum}.json` but synthesis agent wasn't loading and merging them

---

## Fixes Implemented

### Fix 1: Improved Extraction Prompt ✅

**File:** `src/knowledge/extraction.py`

Updated `ConceptExtractor` prompt to explicitly exclude people and organizations:

```python
system_prompt = (
    "You are an expert entity extractor. Extract all key concepts, themes, "
    "definitions, and abstract ideas from the text. "
    "Return ONLY a JSON array of strings. "
    "Focus on capturing the core ideas and terminology used in the text. "
    "DO NOT include person names, organization names, or team names - these are separate entity types. "
    "Examples of valid concepts: 'home-field advantage', 'defensive strategy', 'leadership', 'innovation'. "
    "Examples of INVALID concepts (wrong type): 'John Smith' (person), 'Denver Broncos' (organization). "
    "Avoid summarizing the entire document; instead, list specific concepts. "
    "Normalize concepts to a standard form where possible (e.g., 'The Social Contract' -> 'Social Contract'). "
    "If no concepts are found, return []."
)
```

**Impact:** Future extractions will not misclassify people/orgs as concepts.

---

### Fix 2: Cross-Type Detection in Synthesis ✅

**File:** `config/missions/synthesize_batch.yaml`

Added cross-type detection logic to synthesis mission:

```yaml
- **CROSS-TYPE CHECK:** Detect if entity should be in a different type:
  * If entity_type is Concept and name looks like a person (e.g., "Joe Lombardi", "Vance Joseph"), 
    set needs_review=true and add note in reasoning
  * If entity_type is Concept and name looks like an organization (e.g., "Los Angeles Chargers"), 
    set needs_review=true and add note in reasoning
  * Person indicators: proper names with first+last, titles like "Coach", "Director"
  * Org indicators: team names, company names, "LLC", "Inc", "Foundation"
```

**Impact:** 
- Synthesis agent will detect misclassified entities and flag them with `needs_review=true`
- Lower confidence scores (< 0.8) for these entities
- QA reviewers can easily find and reclassify them

---

### Fix 3: Concept Enrichment Tool ✅

**File:** `src/orchestration/toolkit/synthesis.py`

Added new tool `enrich_concept_attributes` to extract descriptions from source documents:

```python
def _enrich_concept_attributes_handler(args: Mapping[str, Any]) -> ToolResult:
    """Extract description/definition for a concept from its source document."""
    raw_name = args["raw_name"]
    source_checksum = args["source_checksum"]
    
    # Reads parsed markdown from evidence/parsed/{checksum}.md
    # Extracts sentences mentioning the concept
    # Returns attributes dict with 'description' field
```

**Tool Parameters:**
- `raw_name`: The concept name (e.g., "creating turnovers")
- `source_checksum`: Checksum of source document

**Tool Output:**
```json
{
  "attributes": {
    "description": "Creating turnovers: The defensive strategy focuses on forcing turnovers through aggressive play...",
    "enrichment_status": "extracted"
  }
}
```

**Mission Integration:**
```yaml
- **FOR CONCEPTS:** Call enrich_concept_attributes to get a description/definition for the concept
  * Pass raw_name and source_checksum
  * The tool will read the source document and extract concept meaning
  * This populates the attributes.description field
```

**Impact:** All concepts will now have meaningful descriptions explaining what they are.

---

### Fix 4: Association Merging Tool ✅

**File:** `src/orchestration/toolkit/synthesis.py`

Added new tool `get_source_associations` to load extracted relationships:

```python
def _get_source_associations_handler(args: Mapping[str, Any]) -> ToolResult:
    """Retrieve extracted associations for a source document."""
    source_checksum = args["source_checksum"]
    
    # Loads from knowledge-graph/associations/{checksum}.json
    # Returns list of associations involving entities from this source
```

**Tool Output:**
```json
{
  "source_checksum": "abc123...",
  "associations": [
    {
      "source": "Vance Joseph",
      "target": "Denver Broncos",
      "relationship": "defensive coordinator for",
      "evidence": "Vance Joseph, Denver's defensive coordinator...",
      "source_type": "Person",
      "target_type": "Organization",
      "confidence": 0.95
    }
  ],
  "count": 1
}
```

**Mission Integration:**
```yaml
- **FOR ALL ENTITIES:** Use get_source_associations tool to retrieve associations for this source_checksum
  * Extract any associations where this entity is the source or target
  * These will be used to populate the associations field in the canonical entity
```

**Updated resolve_entity Parameters:**
```yaml
- attributes: Optional entity-specific attributes (e.g., for Concepts: {'description': '...'})
- associations: Optional list of association objects from source data
```

**Impact:** Canonical entities will now include relationships to other entities.

---

### Fix 5: Batch Save with Attributes & Associations ✅

**File:** `src/orchestration/toolkit/synthesis.py`

Updated `_resolve_entity_handler` to accept and store attributes/associations:

```python
def _resolve_entity_handler(args: Mapping[str, Any]) -> ToolResult:
    # ... existing params ...
    attributes = args.get("attributes", {})
    associations = args.get("associations", [])
    
    _batch_pending_changes.append({
        # ... existing fields ...
        "attributes": attributes,
        "associations": associations,
    })
```

Updated `_save_synthesis_batch_handler` to merge associations into canonical entities:

```python
# Convert associations to CanonicalAssociation objects
canonical_associations = []
for assoc in associations:
    canonical_associations.append(CanonicalAssociation(
        target_id=assoc.get("target_id", ""),
        target_type=assoc.get("target_type", "Unknown"),
        relationships=[{"type": assoc.get("relationship", "related"), "count": 1}],
        source_checksums=[source_checksum],
    ))

entity = CanonicalEntity(
    # ... existing fields ...
    attributes=attributes,  # Now populated with description for concepts
    associations=canonical_associations,  # Now populated with relationships
)
```

**Impact:** Canonical entities will have rich metadata and relationship graphs.

---

## Expected Output Format (After Fixes)

### Example: Concept with Content

```json
{
  "canonical_id": "creating-turnovers",
  "canonical_name": "creating turnovers",
  "entity_type": "Concept",
  "aliases": ["creating turnovers"],
  "source_checksums": ["ccdf59cd..."],
  "corroboration_score": 1,
  "first_seen": "2026-01-13T01:36:56.855449+00:00",
  "last_updated": "2026-01-13T01:36:56.855449+00:00",
  "resolution_history": [
    {
      "action": "created",
      "timestamp": "2026-01-13T01:36:56.855449+00:00",
      "by": "synthesis-agent",
      "reasoning": "New concept derived from the action description"
    }
  ],
  "attributes": {
    "description": "Creating turnovers: The defensive strategy focuses on forcing turnovers through aggressive play and opportunistic positioning. This approach emphasizes pressure on the quarterback and tight coverage to generate interceptions and fumble recoveries.",
    "enrichment_status": "extracted"
  },
  "associations": [
    {
      "target_id": "denver-broncos",
      "target_type": "Organization",
      "relationships": [{"type": "employed_by", "count": 1}],
      "source_checksums": ["ccdf59cd..."]
    },
    {
      "target_id": "vance-joseph",
      "target_type": "Person",
      "relationships": [{"type": "coordinated_by", "count": 1}],
      "source_checksums": ["ccdf59cd..."]
    }
  ],
  "metadata": {
    "synthesis_complete": true,
    "synthesis_batch_id": "20260113-013602",
    "confidence": 0.95,
    "needs_review": false
  }
}
```

### Example: Cross-Type Issue Flagged

```json
{
  "canonical_id": "joe-lombardi",
  "canonical_name": "Joe Lombardi",
  "entity_type": "Concept",
  "aliases": ["Joe Lombardi"],
  "attributes": {
    "description": "Joe Lombardi serves as offensive coordinator...",
    "enrichment_status": "extracted"
  },
  "metadata": {
    "synthesis_complete": true,
    "synthesis_batch_id": "20260113-013602",
    "confidence": 0.65,  // LOW - flagged for review
    "needs_review": true  // TRUE - QA must review
  },
  "resolution_history": [
    {
      "action": "created",
      "reasoning": "New concept BUT appears to be a person name (first+last). Set needs_review=true for manual reclassification."
    }
  ]
}
```

---

## Testing Status

- ✅ Canonical storage tests: 35/35 passing
- ✅ Mission configuration: Updated with new tools and enrichment steps
- ✅ Toolkit tools: `get_source_associations` and `enrich_concept_attributes` implemented
- ⚠️ **Pending:** Run on real data to validate (waiting for next extraction run)

---

## Next Steps for QA

1. **Trigger new extraction** on a test document to generate fresh concept extractions with improved prompt
2. **Run synthesis agent** on the new concepts to verify:
   - ✅ Concepts have `attributes.description` populated
   - ✅ Concepts have `associations` array populated with relationships
   - ✅ Cross-type issues (people/orgs in concepts) are flagged with `needs_review=true`
3. **Review flagged entities** - Check entities with `needs_review=true` in metadata
4. **Manually reclassify** any remaining cross-type entities (move from concepts to people/organizations)

---

## Long-Term Improvements

1. **LLM-Based Enrichment:** Replace heuristic concept description extraction with LLM call for better quality
2. **Automated Reclassification:** Instead of just flagging, automatically move cross-type entities to correct category
3. **Association Deduplication:** When merging associations across sources, deduplicate by relationship type
4. **Entity Linking:** Link concepts to external knowledge bases (Wikipedia, domain ontologies)

---

**Status:** Ready for QA validation with next synthesis batch
