---
title: Quality Standards
slug: quality-standards
kb_id: meta/quality-standards
type: meta
primary_topic: political-philosophy-knowledge-base
tags:
- meta
- quality
- standards
- documentation
sources: []
---

# Quality Standards

## Overview
This document defines the quality standards for the Political Philosophy Knowledge Base, aligned with the mission goals in `config/mission.yaml`.

## Minimum Quality Thresholds

### Completeness
- **Minimum:** 0.7 (70%)
- **Measurement:** Ratio of populated required metadata fields to total required fields
- **Required fields:** title, type, primary_topic, sources, tags, aliases

### Findability
- **Minimum:** 0.6 (60%)
- **Measurement:** Combination of:
  - Navigation paths available (taxonomy breadcrumbs)
  - Related content links (concepts, entities, sources)
  - Backlinks from other documents
  - Tag coverage

### Content Quality
- **Minimum body length:** 10 characters
- **Link depth:** Maximum 3 levels for relationship traversal
- **Metadata validation:** All documents must have valid YAML front matter

## Document Types

### Concepts
Concepts represent ideas, themes, and topics extracted from source materials.
- Required: definition, related terms, frequency data
- Recommended: historical context, usage examples

### Entities
Entities represent people, places, organizations, and dates.
- Required: entity type, confidence score, occurrence data
- Recommended: biographical/historical context, relationships

### Sources
Sources represent the original materials from which knowledge is extracted.
- Required: citation information, page ranges, document structure
- Recommended: summary, key themes, related sources

## Validation

Documents are validated against these standards during:
1. Initial processing (`kb process --validate`)
2. Quality reporting (`kb quality-report`)
3. Improvement workflows (`kb improve`)

## Continuous Improvement

Quality gaps are categorized by severity:
- **Error:** Critical issues that prevent proper functionality (e.g., missing front matter)
- **Warning:** Issues that reduce quality but don't break functionality (e.g., short content)
- **Info:** Suggestions for enhancement (e.g., missing backlinks)
