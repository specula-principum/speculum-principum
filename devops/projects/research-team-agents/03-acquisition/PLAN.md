# Acquisition Agent - Planning Document

## Agent Overview

**Mission:** Retrieve and preserve source documents in structured format.

**Status:** ⏭️ Merged into Monitor Agent (02-monitor)

---

## Disposition

This agent's responsibilities have been fully absorbed into the Monitor Agent implementation:

| Original Responsibility | Implemented In |
|------------------------|----------------|
| Download documents | `src/parsing/runner.py` → `parse_single_target()` |
| Parse into structured content | `src/parsing/` (WebParser, PDF, DOCX parsers) |
| Store with provenance metadata | `src/parsing/storage.py` → `ParseStorage` |
| Handle rate limits | `src/knowledge/monitoring.py` → `PolitenessPolicy` |
| Document versioning | Manifest checksums in `evidence/parsed/` |

**Execution Flow:**
1. Monitor Agent detects changes → creates Issue with `initial-acquisition` or `content-update` label
2. Agent picks up Issue → runs `acquire_source` mission (`config/missions/acquire_source.yaml`)
3. Mission uses existing parsing infrastructure to fetch, parse, and store content

No separate Acquisition Agent is needed.

---

## Original Responsibilities (Archived)

- Download documents from detected updates
- Parse documents into structured content (using existing parsing infrastructure)
- Store with full provenance metadata (source URL, retrieval date, document hash)
- Handle access barriers (rate limits, authentication, format variations)
- Maintain document versioning for changed content

## Quality Standards

- Preserve original document alongside parsed version
- Verify document integrity via checksums
- Flag incomplete or corrupted retrievals for retry

---

## Implementation Plan

> ⚠️ **TODO: This section requires detailed planning**
>
> The following areas need to be defined:
>
> ### 1. Retrieval Strategies
> - HTTP client configuration
> - Authentication handling
> - Retry and backoff policies
>
> ### 2. Document Storage Schema
> - File organization structure
> - Metadata format and location
> - Version control approach
>
> ### 3. Parser Integration
> - Mapping document types to parsers
> - Fallback strategies for unknown formats
> - Error handling and partial success
>
> ### 4. Tool Requirements
> - List of tools needed for this agent
> - Integration with existing modules
> - New capabilities to build
>
> ### 5. Mission Configuration
> - YAML mission definition
> - Input/output specifications
> - Success criteria
>
> ### 6. Test Cases
> - Unit test scenarios
> - Integration test scenarios
> - Edge cases and failure modes

---

## Dependencies

- Upstream: Monitor Agent (provides change alerts)
- Downstream: Extraction Agent

## Related Modules

- `src/parsing/` (PDF, DOCX, web, markdown parsers)

---

*Last Updated: 2025-12-24*
