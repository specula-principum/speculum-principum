# Issue Template Reference

This reference outlines the Copilot-ready issue templates introduced in Phase 4, the parameters each template expects, and how agents consume the rendered content.

## Template Index

| File | Purpose | Labels | Automation Hooks |
| --- | --- | --- | --- |
| `.github/templates/kb-extract-source.md` | Run end-to-end extraction for new source material | `ready-for-copilot`, `kb-extraction`, `automated` | Drives `assign-copilot`, `copilot kb-automation`, `kb-quality-check.yml` |
| `.github/templates/kb-improve-quality.md` | Raise quality scores for an existing KB section | `ready-for-copilot`, `kb-quality`, `automated` | Feeds scheduled quality-improvement workflow |
| `.github/templates/kb-add-concept.md` | Add a concept document with curated metadata | `ready-for-copilot`, `kb-concept`, `manual` | Supports human-in-the-loop reviews |
| `.github/templates/kb-add-entity.md` | Add or enrich entity coverage | `ready-for-copilot`, `kb-entity`, `manual` | Aligns relationship metadata expectations |

## Template Anatomy

Each template begins with a YAML front-matter block used by GitHub Issue Forms. Parameters render into the Markdown body via `{{ placeholders }}` and are parsed by Copilot helpers.

### `kb-extract-source.md`

Key fields consumed by `prepare_kb_extraction_context`:

- **Source Path** (`{{ source_path }}`): File-system location processed by `copilot kb-automation`.
- **Source Type** (`{{ source_type }}`): A hint for extractor selection (`pdf`, `markdown`, etc.).
- **Processing Date** (`{{ date }}`): Logged in context for traceability.
- **Target KB Root** (`knowledge-base/` by default): Passed to validation and report commands.
- **Extraction Requirements**: Checkbox list (concepts, entities, relationships, structure) becomes “Required Actions” in the context block.

CLI mapping:
```bash
python -m main copilot kb-extract --issue <number>
python -m main copilot kb-automation --source <source_path> --kb-root <target_root>
python -m main copilot kb-validate --kb-root <target_root>
```

### `kb-improve-quality.md`

Fields:
- **Target Section** (`{{ kb_section }}`): Path or slug passed to quality metrics.
- **Current/Target Quality Score**: Captured in the context block; agents use them to assert improvements before PR.
- **Quality Issues Identified** (`{{ quality_issues }}`): Free-form description surfaced to agents.

Suggested command sequence from template body:
```bash
python -m main kb metrics --kb-root knowledge-base/ --section <kb_section> --detailed
python -m main kb improve --kb-root knowledge-base/ --section <kb_section> --suggest
python -m main kb improve --kb-root knowledge-base/ --section <kb_section> --auto-fix --rebuild-links
```

### `kb-add-concept.md`

Fields:
- **Concept Name / Primary Topic / Source Material**: Populate metadata for `kb create-concept`.
- **Requirements checklist**: Forces agents to include definition, context, related concepts, references, and analysis.
- **Metadata block**: Provides the YAML structure for the final document front matter.

Recommended commands:
```bash
python -m main extract concepts --input <source_path> --focus "<Concept>" --output-format json
python -m main kb create-concept --name "<Concept>" --topic <primary_topic> --sources <source_path> --kb-root knowledge-base/
python -m main kb validate --kb-root knowledge-base/ --document concepts/<topic_path>/<concept_slug>.md
```

### `kb-add-entity.md`

Mirrors `kb-add-concept` but emphasises relationship metadata:
- Requires entity definition, roles, relationships, and supporting evidence.
- Encourages linking to related entities/concepts using `related_concepts` and `tags`.
- Validation command ensures schema compliance.

## Template Usage Workflow

1. Author fills out template on GitHub Issue creation.
2. Template-provided labels trigger automation (assignment tasks, scheduled workflows).
3. Copilot helpers parse the issue body to build actionable prompts for agents.
4. Agent or automation follows CLI instructions embedded in the template to complete extraction or enrichment.

## Testing Templates

- `tests/integrations/github/test_templates.py` validates template rendering and required tokens.
- `tests/integrations/copilot/test_helpers.py` confirms context parsing picks up fields/tasks correctly.
- For manual smoke tests, run:
  ```bash
  python -m main github create-issue --template .github/templates/kb-extract-source.md --dry-run
  ```

## Maintenance Guidelines

- Update template labels if workflow naming changes to keep assignment tasks aligned.
- Keep command snippets in sync with CLI flag changes (`main.py` is the only entry point).
- Reflect new MCP tools or automation outputs in template checklists to steer agents toward current best practices.
