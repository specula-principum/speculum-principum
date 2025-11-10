# Orchestration Examples

This directory contains example scripts demonstrating key features of the Copilot Agentic Orchestrator.

## Available Examples

### `approval_gate_demo.py`

Demonstrates the Phase 2 approval gate system with two modes:

1. **Auto-Approve Mode** - For testing, automatically approves all destructive actions
2. **Interactive Mode** - Prompts for human approval before executing destructive operations

**Usage:**
```bash
python src/orchestration/examples/approval_gate_demo.py
```

**Key Features Demonstrated:**
- Approval gate integration with agent runtime
- Safety validator with risk classification
- CLI-based approval prompts
- Audit logging of approval decisions
- Destructive action handling (close_issue, lock_issue, merge_pr)

## Purpose

These examples serve as:
- **Learning resources** for understanding orchestration patterns
- **Integration tests** demonstrating end-to-end workflows
- **Reference implementations** for mission designers

## Running Examples

All examples can be run directly as Python scripts:

```bash
# Make sure your Python environment is activated
source .venv/bin/activate  # or your environment path

# Run an example
python src/orchestration/examples/<example_name>.py
```

## Contributing

When adding new examples:
1. Include clear docstrings explaining what the example demonstrates
2. Use realistic but safe mock data (no actual GitHub API calls)
3. Add the example to this README with usage instructions
4. Follow the existing code style and patterns
