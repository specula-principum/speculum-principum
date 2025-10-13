"""Sandbox execution helper stubs for multi-workflow processing.

These helpers provide placeholder objects that future phases can extend with
real filesystem and execution logic. The current implementation intentionally
performs minimal work so callers can integrate the interfaces without worrying
about side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .execution_planner import WorkflowRunSpec


@dataclass(frozen=True)
class SandboxContext:
    """Metadata describing a sandbox prepared for workflow execution."""

    workflow_name: str
    sandbox_root: Path
    workspace_path: Path
    git_branch: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class SandboxExecutionResult:
    """Placeholder result representing a pending sandbox execution."""

    workflow_name: str
    status: str
    sandbox_path: Path
    message: Optional[str] = None


def prepare_sandbox(root: Path, run_spec: WorkflowRunSpec) -> SandboxContext:
    """Return a sandbox context without performing filesystem mutations."""

    sandbox_root = root / run_spec.sandbox_slug
    return SandboxContext(
        workflow_name=run_spec.name,
        sandbox_root=sandbox_root,
        workspace_path=sandbox_root,
        git_branch=run_spec.git_branch,
        notes="Sandbox preparation stub executed with no side effects.",
    )


def execute_workflow_in_sandbox(context: SandboxContext) -> SandboxExecutionResult:
    """Return a stub execution result indicating the workflow is pending."""

    return SandboxExecutionResult(
        workflow_name=context.workflow_name,
        status="pending",
        sandbox_path=context.sandbox_root,
        message="Sandbox execution not implemented yet; returning placeholder result.",
    )
