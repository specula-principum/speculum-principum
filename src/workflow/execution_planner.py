"""Execution planning for multi-workflow processing.

This module converts a ``WorkflowPlan`` into execution stages that respect
workflow priority, declared dependencies, and conflict metadata. The resulting
``WorkflowExecutionPlan`` captures deterministic ordering information that the
issue processor can consume in later phases of the multi-workflow rollout.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .workflow_matcher import WorkflowCandidate, WorkflowPlan


@dataclass(frozen=True)
class WorkflowRunSpec:
    """Describes the execution requirements for a workflow candidate."""

    candidate: WorkflowCandidate
    sandbox_slug: str
    git_branch: Optional[str] = None

    @property
    def name(self) -> str:
        return self.candidate.name

    @property
    def conflict_keys(self) -> frozenset[str]:
        return self.candidate.conflict_keys

    @property
    def dependencies(self) -> Tuple[str, ...]:
        return self.candidate.dependencies

    @property
    def priority(self) -> int:
        return self.candidate.priority


@dataclass(frozen=True)
class ExecutionStage:
    """Represents one ordered execution stage composed of one or more workflows."""

    index: int
    run_mode: str
    workflows: Tuple[WorkflowRunSpec, ...]
    blocking_conflicts: frozenset[str] = field(default_factory=frozenset)

    def is_parallel(self) -> bool:
        return self.run_mode == "parallel"

    def workflow_names(self) -> Tuple[str, ...]:
        return tuple(run_spec.name for run_spec in self.workflows)


@dataclass(frozen=True)
class WorkflowExecutionPlan:
    """Execution-ready plan returned by the ``WorkflowExecutionPlanner``."""

    plan_id: str
    stages: Tuple[ExecutionStage, ...]
    allow_partial_success: bool
    overall_timeout_seconds: Optional[int] = None
    selection_reason: Optional[str] = None
    selection_message: Optional[str] = None

    def is_empty(self) -> bool:
        return not self.stages

    def stage_count(self) -> int:
        return len(self.stages)

    def workflow_count(self) -> int:
        return sum(len(stage.workflows) for stage in self.stages)

    def to_summary(self) -> Dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "stage_count": self.stage_count(),
            "workflow_count": self.workflow_count(),
            "stages": [
                {
                    "index": stage.index,
                    "run_mode": stage.run_mode,
                    "workflows": list(stage.workflow_names()),
                    "blocking_conflicts": sorted(stage.blocking_conflicts),
                }
                for stage in self.stages
            ],
        }


class WorkflowPlanningError(RuntimeError):
    """Raised when execution planning fails due to invalid input."""


class WorkflowExecutionPlanner:
    """Generate deterministic execution plans for ``WorkflowPlan`` objects."""

    def __init__(
        self,
        *,
        allow_parallel_stages: bool = True,
        max_parallel_workflows: Optional[int] = None,
        allow_partial_success: bool = True,
        overall_timeout_seconds: Optional[int] = None,
    ) -> None:
        self.allow_parallel_stages = allow_parallel_stages
        self.max_parallel_workflows = max_parallel_workflows
        self.allow_partial_success = allow_partial_success
        self.overall_timeout_seconds = overall_timeout_seconds

    def build_execution_plan(self, workflow_plan: WorkflowPlan) -> WorkflowExecutionPlan:
        """Create a ``WorkflowExecutionPlan`` from the provided ``WorkflowPlan``."""

        if not workflow_plan.candidates:
            return WorkflowExecutionPlan(
                plan_id=self._generate_plan_id(),
                stages=(),
                allow_partial_success=self.allow_partial_success,
                overall_timeout_seconds=self.overall_timeout_seconds,
                selection_reason=workflow_plan.selection_reason,
                selection_message=workflow_plan.selection_message,
            )

        candidates = list(workflow_plan.candidates)
        name_to_candidate: Dict[str, WorkflowCandidate] = {
            candidate.name: candidate for candidate in candidates
        }

        self._validate_dependencies(name_to_candidate)

        adjacency: Dict[str, List[str]] = {name: [] for name in name_to_candidate}
        in_degree: Dict[str, int] = {name: 0 for name in name_to_candidate}

        for candidate in candidates:
            for dependency in candidate.dependencies:
                adjacency.setdefault(dependency, []).append(candidate.name)
                in_degree[candidate.name] = in_degree.get(candidate.name, 0) + 1

        sort_key = {
            name: (cand.priority, cand.name.lower())
            for name, cand in name_to_candidate.items()
        }

        available: List[str] = sorted(
            [name for name, degree in in_degree.items() if degree == 0],
            key=lambda item: sort_key[item],
        )

        stages: List[ExecutionStage] = []
        processed: List[str] = []

        while available:
            stage_names, deferred = self._select_stage_members(available, name_to_candidate)

            if not stage_names:
                raise WorkflowPlanningError(
                    "Unable to select workflows for execution stage; check conflicts and dependencies",
                )

            stage_conflicts = self._collect_conflicts(stage_names, name_to_candidate)
            stage_workflows = tuple(
                WorkflowRunSpec(
                    candidate=name_to_candidate[name],
                    sandbox_slug=self._slugify_name(name),
                )
                for name in stage_names
            )

            stage_index = len(stages)
            run_mode = (
                "parallel"
                if self.allow_parallel_stages and len(stage_workflows) > 1
                else "sequential"
            )
            stages.append(
                ExecutionStage(
                    index=stage_index,
                    run_mode=run_mode,
                    workflows=stage_workflows,
                    blocking_conflicts=stage_conflicts,
                )
            )

            processed.extend(stage_names)

            for name in stage_names:
                for dependent in adjacency.get(name, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        deferred.append(dependent)

            available = sorted(set(deferred), key=lambda item: sort_key[item])

        if len(processed) != len(name_to_candidate):
            unresolved = set(name_to_candidate) - set(processed)
            raise WorkflowPlanningError(
                f"Unresolved workflows after planning: {sorted(unresolved)}",
            )

        return WorkflowExecutionPlan(
            plan_id=self._generate_plan_id(),
            stages=tuple(stages),
            allow_partial_success=self.allow_partial_success,
            overall_timeout_seconds=self.overall_timeout_seconds,
            selection_reason=workflow_plan.selection_reason,
            selection_message=workflow_plan.selection_message,
        )

    def _select_stage_members(
        self,
        available: Sequence[str],
        name_to_candidate: Dict[str, WorkflowCandidate],
    ) -> Tuple[List[str], List[str]]:
        stage_members: List[str] = []
        deferred: List[str] = []
        stage_conflicts: set[str] = set()

        for name in available:
            candidate = name_to_candidate[name]

            if not stage_members:
                stage_members.append(name)
                stage_conflicts.update(candidate.conflict_keys)
                continue

            if not self.allow_parallel_stages:
                deferred.append(name)
                continue

            if self.max_parallel_workflows and len(stage_members) >= self.max_parallel_workflows:
                deferred.append(name)
                continue

            if candidate.conflict_keys & stage_conflicts:
                deferred.append(name)
                continue

            stage_members.append(name)
            stage_conflicts.update(candidate.conflict_keys)

        return stage_members, deferred

    @staticmethod
    def _collect_conflicts(
        stage_names: Iterable[str],
        name_to_candidate: Dict[str, WorkflowCandidate],
    ) -> frozenset[str]:
        conflicts: set[str] = set()
        for name in stage_names:
            conflicts.update(name_to_candidate[name].conflict_keys)
        return frozenset(conflicts)

    @staticmethod
    def _validate_dependencies(name_to_candidate: Dict[str, WorkflowCandidate]) -> None:
        unknown_dependencies: Dict[str, List[str]] = {}
        for name, candidate in name_to_candidate.items():
            for dependency in candidate.dependencies:
                if dependency not in name_to_candidate:
                    unknown_dependencies.setdefault(name, []).append(dependency)
                if dependency == name:
                    raise WorkflowPlanningError(
                        f"Workflow '{name}' declares a circular dependency on itself",
                    )

        if unknown_dependencies:
            messages = [
                f"{workflow} -> {sorted(deps)}"
                for workflow, deps in sorted(unknown_dependencies.items())
            ]
            raise WorkflowPlanningError(
                "Unknown workflow dependencies detected: " + ", ".join(messages)
            )

    @staticmethod
    def _slugify_name(value: str) -> str:
        import re

        slug = re.sub(r"[^\w\s-]", "", value.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    @staticmethod
    def _generate_plan_id() -> str:
        return f"multiwf-{uuid.uuid4().hex}"


def build_plan_created_event(
    plan: WorkflowExecutionPlan,
    *,
    issue_number: Optional[int] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, object]:
    """Draft telemetry payload for ``multi_workflow.plan_created`` events."""

    summary = plan.to_summary()

    payload = {
        "event_type": "multi_workflow.plan_created",
        "plan_id": summary.get("plan_id", plan.plan_id),
        "issue_number": issue_number,
        "batch_id": batch_id,
        "stage_count": summary.get("stage_count", plan.stage_count()),
        "workflow_count": summary.get("workflow_count", plan.workflow_count()),
        "allow_partial_success": plan.allow_partial_success,
    }

    if plan.overall_timeout_seconds is not None:
        payload["overall_timeout_seconds"] = plan.overall_timeout_seconds

    stages = summary.get("stages")
    if stages is not None:
        payload["stages"] = stages
    else:
        payload["stages"] = [
            {
                "index": stage.index,
                "run_mode": stage.run_mode,
                "workflows": list(stage.workflow_names()),
                "blocking_conflicts": sorted(stage.blocking_conflicts),
            }
            for stage in plan.stages
        ]

    return payload
