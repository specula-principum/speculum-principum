# Information Architecture Methodology

## Purpose
This guide codifies how the Speculum Principum team applies information architecture (IA) to the political philosophy knowledge base. It translates `config/mission.yaml` into day-to-day practices so that every artifact advances the mission to connect Machiavellian concepts across works while remaining discoverable to students, researchers, and political scientists.

## Mission Alignment
- **Mission title:** Political Philosophy Knowledge Base
- **Audience focus:** students, researchers, political scientists
- **Primary goals:**
	- Make Machiavelli's ideas accessible and discoverable.
	- Connect concepts that span multiple works and historical figures.
	- Track intellectual influences and relationships across the corpus.
- **Quality floor:** completeness >= 0.70, findability >= 0.60, relationship link depth <= 3.

Mission statements are treated as living directives. Any proposed content addition or structural change should explicitly cite which mission goal it advances and how it protects the documented quality floor.

## IA Pillars
### Organization systems
- Use the hybrid organization scheme mandated by the mission: topical first (concepts), alphabetical when navigating entities, and chronological when traversing sources.
- Keep topic trees in `config/taxonomy.yaml` authoritative; directories and navigation indexes must mirror that structure.
- Apply progressive disclosure so that every directory index introduces context before exposing deep analysis.

### Labeling systems
- Follow mission-defined labeling conventions: kebab-case identifiers, maximum length 80 characters, English labels sourced from the taxonomy.
- Maintain consistent `kb_id`, `slug`, and filename triplets so bidirectional linking and automation remain stable.
- Reject ad-hoc terminology that is not sanctioned in the taxonomy vocabulary section.

### Navigation systems
- Ensure every directory includes an `index.md` that communicates role, scope, and next steps.
- Surface multiple entry points (concept, entity, source) for the same knowledge object to satisfy faceted exploration.
- Use associative navigation via `related_concepts`, relationship manifests, and inline cross-links to reinforce concept graph cohesion.

### Search systems
- Honor mission search configuration: enable full text, metadata indexing, synonym expansion, and related content suggestions.
- Consider search impact whenever front matter changes; keywords, aliases, and controlled vocabulary terms should keep queries predictable.

### Metadata and quality
- Author front matter with the full Dublin Core plus IA extensions emitted by `metadata_payload`.
- Run `pytest tests/knowledge_base` after metadata-heavy updates to ensure quality gate assertions stay green.
- Leverage `src/knowledge_base/validation.py` to calculate completeness and findability before publishing.

## Operating Lifecycle
1. **Intake and triage** – Evaluate new sources or concepts against mission goals and confirm taxonomy coverage.
2. **Model alignment** – Map artifacts to existing topics, entity types, and relationship definitions. Update taxonomy only when governed changes are approved.
3. **Structure scaffolding** – Generate directory blueprints with `python -m main kb init --root knowledge-base` optionally overriding context with mission metadata.
4. **Authoring and enrichment** – Draft markdown using the concept/entity/source templates, populate metadata, and cite sources by `kb_id`.
5. **Quality review** – Validate documents (`validate_documents`) and relationships (`validate_relationships`) while enforcing mission thresholds.
6. **Publication and monitoring** – Merge approved changes, run quality metrics, and schedule review reminders according to the documented cadence.

## Governance and Roles
- **IA curator** – Owns taxonomy evolution, approves mission amendments, and ensures labeling conventions remain coherent.
- **Content author** – Drafts documents, maintains metadata accuracy, and submits relationship proposals with supporting evidence.
- **Automation steward** – Maintains CLI tooling, schemas, and tests that guarantee IA contracts remain enforceable.

### Taxonomy change workflow
1. Propose updates referencing concrete gaps or new mission goals.
2. Draft modifications in `config/taxonomy.yaml` and update associated tests.
3. Run `python -m main kb validate-taxonomy --taxonomy config/taxonomy.yaml` to surface schema violations.
4. Secure curator approval before merging.

### Mission configuration updates
1. Capture rationale tying changes to audience or goal shifts.
2. Modify `config/mission.yaml` and adjust schemas if necessary.
3. Run `pytest tests/knowledge_base/test_config.py` to confirm validation logic.
4. Communicate plan adjustments to downstream phases (extraction, parsing).

## Toolchain Integration
- `python -m main kb init` merges mission context with optional overrides when scaffolding structures.
- `python -m main kb validate-taxonomy` guarantees controlled vocabulary integrity before publishing.
- `src/knowledge_base/metadata.py` renders canonical front matter, preserving consistency between documentation and runtime models.
- Automated tests in `tests/knowledge_base/` safeguard mission rules, taxonomy relationships, structure planning, and quality metrics.

## Metrics and Review Cadence
- **Weekly:** Run `pytest tests/knowledge_base` to catch regression drift early.
- **Bi-weekly:** Produce quality reports using `validate_documents` and `calculate_quality_metrics`, logging results in `meta/quality-standards.md` (future work).
- **Quarterly:** Revisit mission assumptions with stakeholders; adjust audiences, goals, or thresholds only after curator approval.

## Dependencies and Future Work
- Integration tests will exercise cross-package flows (extraction -> parsing -> knowledge base) to guarantee IA contracts survive upstream changes.
- Continuing documentation will expand `meta/quality-standards.md` and capture governance retrospectives once integration coverage is complete.
