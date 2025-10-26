# Phase 4: Agent Integration & Automation

**Status:** Planned  
**Dependencies:** Phase 1, 2, 3 (Full stack)  
**Estimated Effort:** 2-3 weeks

## Overview

Integrate the knowledge base pipeline with GitHub Copilot agents to enable automated, issue-driven knowledge extraction workflows. This phase creates the templates, workflows, and infrastructure that allow copilot agents to autonomously build and maintain knowledge bases.

---

## Objectives

1. Create issue templates for knowledge extraction tasks
2. Enable copilot agents to invoke extraction and KB tools
3. Build Model Context Protocol (MCP) server for advanced integration
4. Automate quality assurance and improvement workflows
5. Support human-in-the-loop refinement
6. Enable continuous knowledge base maintenance

---

## Architecture

### Integration Layers

```
GitHub Issues (Task Specification)
    ↓
Copilot Agent (Task Executor)
    ↓
┌─────────────────────────────────┐
│  Integration Layer              │
│  ├─ CLI Tools (current)         │
│  ├─ MCP Server (enhanced)       │
│  └─ Workflow Helpers            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  KB Engine + Extraction Tools   │
└─────────────────────────────────┘
    ↓
Knowledge Base Artifacts
    ↓
Pull Request (Review & Merge)
```

### Components

#### 1. Issue Templates

**.github/templates/kb-extract-source.md**
```markdown
---
title: "Extract knowledge from {{ source_name }}"
labels:
  - ready-for-copilot
  - kb-extraction
  - automated
---

## Task: Extract Knowledge from Source Material

**Source Path:** `{{ source_path }}`
**Source Type:** {{ source_type }}  
**Processing Date:** {{ date }}

### Extraction Requirements

- [ ] Extract concepts (min frequency: {{ min_concept_freq }})
- [ ] Extract entities (people, places, organizations)
- [ ] Build relationship graph
- [ ] Generate source document with references

### Output Requirements

**Target KB Root:** `knowledge-base/`

**Expected Artifacts:**
- Concept documents in `knowledge-base/concepts/`
- Entity documents in `knowledge-base/entities/`
- Source document in `knowledge-base/sources/{{ source_slug }}/`
- Updated indexes and navigation
- Quality report with metrics

### Quality Standards

- Minimum completeness: {{ min_completeness }}
- Minimum findability: {{ min_findability }}
- All documents must validate against IA schema
- All links must resolve

### Tools to Use

```bash
# 1. Process source material
python -m main kb process \
  --source {{ source_path }} \
  --kb-root knowledge-base/ \
  --mission config/mission.yaml \
  --extract concepts entities relationships structure \
  --validate

# 2. Check quality metrics
python -m main kb metrics \
  --kb-root knowledge-base/ \
  --output reports/quality-{{ issue_number }}.json

# 3. Fix any validation issues
python -m main kb validate \
  --kb-root knowledge-base/ \
  --check-links \
  --check-metadata \
  --auto-fix
```

### Success Criteria

- [ ] All extraction tools completed successfully
- [ ] Quality metrics meet thresholds
- [ ] Validation passes with no errors
- [ ] Quality report generated
- [ ] Changes committed to branch `kb-extract-{{ issue_number }}`

### Notes

{{ additional_instructions }}
```

**.github/templates/kb-improve-quality.md**
```markdown
---
title: "Improve quality of {{ kb_section }}"
labels:
  - ready-for-copilot
  - kb-quality
  - automated
---

## Task: Improve Knowledge Base Quality

**Target Section:** `{{ kb_section }}`
**Current Quality Score:** {{ current_score }}
**Target Quality Score:** {{ target_score }}

### Quality Issues Identified

{{ quality_issues }}

### Improvement Actions

- [ ] Fix incomplete metadata
- [ ] Add missing related links
- [ ] Improve summaries/definitions
- [ ] Validate taxonomy assignments
- [ ] Add source references

### Tools to Use

```bash
# 1. Analyze current quality
python -m main kb metrics \
  --kb-root knowledge-base/ \
  --section {{ kb_section }} \
  --detailed

# 2. Get improvement suggestions
python -m main kb improve \
  --kb-root knowledge-base/ \
  --section {{ kb_section }} \
  --suggest

# 3. Apply fixes
python -m main kb improve \
  --kb-root knowledge-base/ \
  --section {{ kb_section }} \
  --auto-fix \
  --rebuild-links
```

### Success Criteria

- [ ] Quality score improved to >= {{ target_score }}
- [ ] All validation errors resolved
- [ ] Documentation updated
```

**.github/templates/kb-add-concept.md**
```markdown
---
title: "Add concept: {{ concept_name }}"
labels:
  - ready-for-copilot
  - kb-concept
  - manual
---

## Task: Add New Concept to Knowledge Base

**Concept:** {{ concept_name }}
**Primary Topic:** {{ primary_topic }}
**Source Material:** {{ source_material }}

### Requirements

Create a new concept document with:

1. **Clear definition** - What is this concept?
2. **Context** - Where does it appear in sources?
3. **Related concepts** - What other concepts connect to it?
4. **Source references** - Direct quotes and citations
5. **Analysis** - Interpretation and significance

### Document Location

`knowledge-base/concepts/{{ topic_path }}/{{ concept_slug }}.md`

### Metadata Requirements

```yaml
title: {{ concept_name }}
kb_id: concepts/{{ topic_path }}/{{ concept_slug }}
type: concept
primary_topic: {{ primary_topic }}
sources:
  - kb_id: sources/{{ source_slug }}
    pages: [...]
```

### Tools to Use

```bash
# Extract concept information from sources
python -m main extract concepts \
  --input {{ source_path }} \
  --focus "{{ concept_name }}" \
  --output-format json

# Create KB document
python -m main kb create-concept \
  --name "{{ concept_name }}" \
  --topic {{ primary_topic }} \
  --sources {{ source_path }} \
  --kb-root knowledge-base/

# Validate
python -m main kb validate \
  --kb-root knowledge-base/ \
  --document concepts/{{ topic_path }}/{{ concept_slug }}.md
```
```

#### 2. Copilot Workflow Helpers

**`src/integrations/copilot/helpers.py`**

```python
def prepare_kb_extraction_context(issue: IssueDetails) -> str:
    """Generate comprehensive context for KB extraction tasks."""
    # Parse issue body for source paths, requirements
    # Read source metadata
    # Check KB current state
    # Generate focused instructions for agent
    
def validate_kb_changes(kb_root: Path) -> ValidationReport:
    """Run all validation checks on KB changes."""
    # Check metadata completeness
    # Validate links
    # Calculate quality scores
    # Generate report
    
def generate_quality_report(kb_root: Path, issue_number: int) -> Path:
    """Create detailed quality report for issue."""
    # Run metrics
    # Format as markdown
    # Save to reports/
```

**`src/integrations/copilot/commands.py`**

```python
def register_copilot_commands(subparsers):
    """Add copilot-specific convenience commands."""
    
    # python -m main copilot kb-extract --issue 42
    # Wraps full extraction workflow
    
    # python -m main copilot kb-validate --issue 42
    # Validates changes for current issue
    
    # python -m main copilot kb-report --issue 42
    # Generates quality report
```

#### 3. Model Context Protocol (MCP) Server

**`src/mcp_server/kb_tools.py`**

Expose KB tools via MCP for native copilot integration:

```python
# MCP Tool: extract_concepts
{
  "name": "kb_extract_concepts",
  "description": "Extract key concepts from text",
  "inputSchema": {
    "type": "object",
    "properties": {
      "source_path": {"type": "string"},
      "min_frequency": {"type": "integer", "default": 2},
      "max_concepts": {"type": "integer", "default": 50}
    }
  }
}

# MCP Tool: create_kb_document
{
  "name": "kb_create_concept",
  "description": "Create a concept document in knowledge base",
  "inputSchema": {
    "type": "object",
    "properties": {
      "concept_name": {"type": "string"},
      "definition": {"type": "string"},
      "sources": {"type": "array"},
      "related_concepts": {"type": "array"}
    }
  }
}

# MCP Tool: validate_kb
{
  "name": "kb_validate",
  "description": "Validate knowledge base structure and quality",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kb_root": {"type": "string"},
      "section": {"type": "string", "optional": true}
    }
  }
}
```

**MCP Server Implementation:**

```bash
# Run MCP server
python -m src.mcp_server.kb_server

# Copilot connects via stdio
# Tools appear in agent's tool palette
# Type-safe invocation with schema validation
```

#### 4. Automation Workflows

**`.github/workflows/kb-quality-check.yml`**
```yaml
name: Knowledge Base Quality Check

on:
  pull_request:
    paths:
      - 'knowledge-base/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Validate KB structure
        run: |
          python -m main kb validate \
            --kb-root knowledge-base/ \
            --check-links \
            --check-metadata \
            --strict
      
      - name: Calculate quality metrics
        run: |
          python -m main kb metrics \
            --kb-root knowledge-base/ \
            --output reports/quality.json
      
      - name: Post quality report
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('reports/quality.json'));
            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Knowledge Base Quality Report\n\n${formatReport(report)}`
            });
```

**`.github/workflows/kb-auto-improve.yml`**
```yaml
name: Auto-improve KB Quality

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday 2am
  workflow_dispatch:

jobs:
  improve:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
      
      - name: Find quality gaps
        run: |
          python -m main kb improve \
            --kb-root knowledge-base/ \
            --min-completeness 0.75 \
            --suggest > gaps.json
      
      - name: Create improvement issues
        uses: actions/github-script@v7
        with:
          script: |
            const gaps = require('./gaps.json');
            for (const gap of gaps) {
              await github.rest.issues.create({
                title: `Improve: ${gap.section}`,
                body: gap.description,
                labels: ['ready-for-copilot', 'kb-quality', 'automated']
              });
            }
```

---

## Agent Workflows

### Workflow A: Automated Extraction

1. **Human creates issue** from template `kb-extract-source.md`
2. **GitHub Action** applies `ready-for-copilot` label
3. **Agent assignment task** picks up issue:
   ```bash
   python -m main assign-copilot --label ready-for-copilot
   ```
4. **Copilot agent** receives issue context:
   - Reads source material
   - Invokes extraction tools via CLI or MCP
   - Processes results
   - Creates KB documents
   - Validates quality
   - Commits changes
5. **Agent creates PR** with quality report
6. **Human reviews** and merges

### Workflow B: Quality Improvement

1. **Scheduled job** runs quality analysis
2. **Script creates issues** for sections below threshold
3. **Agent picks up issue**
4. **Agent runs improvement tools**:
   - Analyzes gaps
   - Adds missing metadata
   - Suggests related links
   - Improves summaries
5. **Agent commits improvements**
6. **PR created** for review

### Workflow C: Human-Initiated Concept Addition

1. **Human creates issue** with concept details
2. **Agent extracts** information from sources
3. **Agent drafts** concept document
4. **Human reviews draft** in PR
5. **Human refines** content
6. **Merge** when satisfied

---

## Deliverables

### Code Structure

```
.github/
├── templates/
│   ├── kb-extract-source.md
│   ├── kb-improve-quality.md
│   ├── kb-add-concept.md
│   └── kb-add-entity.md
└── workflows/
    ├── kb-quality-check.yml
    └── kb-auto-improve.yml

src/integrations/copilot/
├── __init__.py
├── helpers.py            # Context preparation, validation
└── commands.py           # Copilot-specific CLI commands

src/mcp_server/
├── __init__.py
├── kb_server.py          # MCP server implementation
└── kb_tools.py           # Tool definitions

src/cli/commands/
└── copilot.py            # Register copilot commands

tests/integrations/copilot/
└── [comprehensive tests]
```

### Documentation

- **Agent Workflow Guide** - How copilot agents use KB tools
- **Issue Template Reference** - How to create KB tasks
- **MCP Integration Guide** - Setting up MCP server
- **Automation Playbook** - Configuring automated workflows

---

## Success Criteria

1. **Agent Success Rate**: >90% of extraction tasks complete successfully
2. **Quality Improvement**: Automated improvements increase scores by >10%
3. **Human Effort**: <10% of KB content requires manual intervention
4. **Cycle Time**: Source → KB in <1 hour for 100-page documents
5. **Validation Pass Rate**: >95% of PRs pass quality checks

---

## Future Enhancements

- **Multi-agent collaboration** - Parallel processing of large sources
- **Conflict resolution** - Agent negotiation for contradictory data
- **Interactive refinement** - Agent asks clarifying questions via comments
- **Learning feedback** - Improve extraction based on human edits
- **Scheduled maintenance** - Auto-refresh stale content

---

## Notes

- This phase makes the full system autonomous and scalable
- Human oversight remains critical for quality and accuracy
- Issue templates encode best practices and requirements
- MCP server provides richer integration than CLI alone
- Automation workflows reduce maintenance burden
