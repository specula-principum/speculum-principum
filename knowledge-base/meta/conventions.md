# Information Architecture Conventions

## Purpose
These conventions translate mission policies and taxonomy rules into practical authoring standards. Follow them whenever creating or updating content under `knowledge-base/` to preserve consistency, automation compatibility, and search reliability.

## Directory and File Layout
- `knowledge-base/index.md` is the authoritative map of content. Every subdirectory must supply its own `index.md`.
- Concepts live under `knowledge-base/concepts/`, entities under `knowledge-base/entities/`, sources under `knowledge-base/sources/`, and relationship manifests under `knowledge-base/relationships/`.
- Keep directory depth aligned with taxonomy breadcrumbs. Avoid introducing ad-hoc nesting that is not represented in `config/taxonomy.yaml`.
- Each markdown file name must equal its slug (for example `virtue.md` -> slug `virtue`).

## Naming Rules
- Use kebab-case for all identifiers (`kb_id` segments, filenames, directory names, relationship IDs).
- Limit slugs and filenames to 80 characters, matching the mission `labeling_conventions.max_length`.
- Reserve ASCII characters for identifiers; escape accented terms through the `aliases` array instead of filenames.
- Prefix knowledge base identifiers according to document type:
  - Concepts: `concepts/<primary-topic>/<slug>`
  - Entities: `entities/<entity-type>/<slug>`
  - Sources: `sources/<collection>/<slug>`
  - Relationships: `relationships/<graph>/<slug>`

## Front Matter Requirements
- Always begin documents with YAML front matter produced by `metadata_payload` to guarantee parity with runtime models.
- Required keys (in order): `title`, `slug`, `kb_id`, `type`, `primary_topic`, `secondary_topics`, `tags`, `aliases`, `related_concepts`, `sources`, `dublin_core`, `ia`.
- Populate `sources` with `kb_id` references plus page ranges. Do not cite raw page numbers without the containing source ID.
- Ensure Dublin Core `identifier` matches `kb_id`, and `language` defaults to `en` unless justified.
- Set IA metadata fields:
  - `findability_score` and `completeness` must meet or exceed mission thresholds.
  - `navigation_path` should mirror taxonomy breadcrumbs returned by `assign_topics`.
  - `related_by_topic` and `related_by_entity` contain `kb_id` references only.

## Content Authoring Guidelines
- Start body content with an `#` heading matching the document title.
- Use secondary headings (`##`) to introduce sections: Definition, Context, Analysis, References, Backlinks.
- Reference other artifacts with double bracket wiki-style links (`[[concepts/statecraft/fortune]]`) or direct markdown links when pointing outside the knowledge base.
- Quote primary sources with block quotes and cite supporting `sources` entries inline.
- Keep paragraphs short and scannable; favor bullet lists for enumerations of relationships, themes, or takeaways.

## Relationship and Metadata Updates
- When adding a `KBRelationship`, update the corresponding adjacency manifest under `knowledge-base/relationships/` and run `pytest tests/knowledge_base/test_linking.py`.
- Maintain reciprocal edges by respecting the taxonomy inverse definitions; the `RelationshipGraph` helper will enforce this during tests.
- Recalculate quality metrics with `calculate_quality_metrics` after large batches of document changes.

## Submission Checklist
- [ ] Slugs, filenames, and `kb_id` segments are kebab-case and under 80 characters.
- [ ] Front matter validates via `validate_documents` and `assert_quality_thresholds`.
- [ ] Taxonomy assignments run through `assign_topics`; navigation breadcrumbs updated.
- [ ] Unit tests under `tests/knowledge_base/` pass locally (`pytest tests/knowledge_base`).
- [ ] `devops/projects/phase-2-information-architecture/PROGRESS.md` reflects newly completed tasks and decisions.
