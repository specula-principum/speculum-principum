# Workflow Schema Versioning & Flexibility

The workflow validator now supports **schema profiles** so we can keep moving fast in
production without editing Python whenever requirements change.

## Quick facts

- Profiles are keyed by the **major** component of `workflow_version` (e.g. `2.4.1`
  → profile `"2"`).
- Configuration lives in `docs/workflow/schema-profile.yaml` by default.
- Override the file path with `WORKFLOW_SCHEMA_PROFILE_PATH=/path/to/custom.yaml`.
- Each profile can:
  - replace the list of required taxonomy fields,
  - add or swap required template stacks,
  - extend base entity requirements,
  - register new taxonomy categories or priority levels,
  - register brand-new typed workflow properties.
- Unknown versions gracefully fall back to the default profile.

## Adding a new profile

1. Duplicate the default profile block in `docs/workflow/schema-profile.yaml` and
   update the key to the new major version (for example `"2"`).
2. (Optional) Include `extends: "1"` to inherit the previous profile and only
   override the fields that changed.
3. Add any new required fields, templates, or base entity types.
4. If the new fields aren't already part of the schema, list them under
   `properties:` with a JSON Schema snippet describing them.
5. Commit the updated YAML alongside any new workflows or documentation.

## Runtime behavior

- The validator automatically loads profile files the first time it runs. This
  happens inside `WorkflowSchemaValidator.initialize_profiles()`.
- When a profile introduces new categories or priority levels, the JSON Schema
  enums are refreshed so downstream validations stay accurate.
- Profiles can be registered programmatically with
  `WorkflowSchemaValidator.register_schema_profile("beta", {...})` for
  integration tests or experiments.
- Additional workflow metadata should live under the `extensions` object when a
  formal schema entry isn't needed yet.

## Migration tips

- Treat new profiles like a migration plan: create the profile, land it with the
  validator, then roll out workflows that declare the new `workflow_version`.
- Keep `default_profile` pointing at the most widely deployed schema (usually the
  latest production version) so unexpected versions still validate.
- When deprecating fields, continue to accept them for at least one profile
  version to give existing workflows time to roll off.

## Testing

Use `pytest tests/unit/workflow/test_workflow_schema_profiles.py -v` to exercise
profile registration scenarios, including fallback behavior and schema
extensions. Update or add tests whenever requirements evolve.
