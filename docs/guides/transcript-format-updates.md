# Updated Transcript Format

## Changes

The mission transcript now includes planner information showing which planner and model were used.

### New Field: `planner`

```json
{
  "mission_id": "triage_new_issue_20251106_143052",
  "mission": {
    "id": "triage_new_issue",
    "goal": "Read the incoming GitHub issue..."
  },
  "planner": {
    "type": "copilot-cli",
    "model": "claude-sonnet-4"
  },
  "status": "succeeded",
  "duration_seconds": 12.34,
  "steps": [...],
  "summary": "Successfully triaged issue #118"
}
```

## Examples

### Copilot CLI with Custom Model
```json
"planner": {
  "type": "copilot-cli",
  "model": "claude-sonnet-4"
}
```

### Copilot CLI with Default Model
```json
"planner": {
  "type": "copilot-cli",
  "model": "copilot-default"
}
```

### GitHub Models API (LLM)
```json
"planner": {
  "type": "llm",
  "model": "gpt-4o-mini"
}
```

### Deterministic Planner
```json
"planner": {
  "type": "deterministic",
  "model": null
}
```

## Benefits

1. **Debugging**: Easily see which planner was used for a mission
2. **Analysis**: Compare performance between planners
3. **Reproducibility**: Know exactly what model/planner to use for reruns
4. **Auditing**: Track which AI model made decisions

## Example Commands & Outputs

### Command:
```bash
python -m main agent run \
  --mission triage_new_issue \
  --planner copilot-cli \
  --model claude-sonnet-4
```

### Transcript:
```json
{
  "mission_id": "triage_new_issue_20251106_143052",
  "planner": {
    "type": "copilot-cli",
    "model": "claude-sonnet-4"
  },
  ...
}
```

---

### Command:
```bash
python -m main agent run \
  --mission triage_new_issue \
  --planner llm
```

### Transcript:
```json
{
  "mission_id": "triage_new_issue_20251106_143152",
  "planner": {
    "type": "llm",
    "model": "gpt-4o-mini"
  },
  ...
}
```

## Backward Compatibility

Old transcripts without the `planner` field will still work. The field is additive and doesn't break existing tooling.
