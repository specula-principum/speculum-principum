"""Utilities for deterministic multi-workflow deliverable naming."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

from .workflow_matcher import WorkflowPlan

_ALLOWED_STRATEGIES = {"suffix"}


class MultiWorkflowDeliverableNamer:
    """Resolve output filenames for multi-workflow execution plans."""

    def __init__(
        self,
        *,
        strategy: str = "suffix",
        separator: str = "--",
    ) -> None:
        if strategy not in _ALLOWED_STRATEGIES:
            raise ValueError(f"Unsupported conflict resolution strategy: {strategy}")
        if not separator:
            raise ValueError("Suffix separator must be a non-empty string")

        self.strategy = strategy
        self.separator = separator

    def build_manifest(
        self,
        *,
        issue_number: int,
        issue_title: str,
        plan: Optional[WorkflowPlan],
    ) -> Dict[str, Any]:
        """Return a manifest describing resolved deliverable filenames."""

        manifest: Dict[str, Any] = {
            "strategy": self.strategy,
            "separator": self.separator,
            "workflow_count": 0,
            "deliverable_count": 0,
            "workflows": [],
            "conflict_groups": [],
        }

        if plan is None or not plan.candidates:
            return manifest

        title_slug = self._slugify(issue_title)
        conflict_groups: Dict[str, List[Dict[str, Any]]] = {}
        workflow_entries: List[Dict[str, Any]] = []
        deliverable_total = 0

        for order, candidate in enumerate(plan.candidates):
            workflow_info = candidate.workflow_info
            workflow_slug = self._slugify(workflow_info.name)
            output_config = workflow_info.output or {}
            folder_template = output_config.get("folder_structure", "issue_{issue_number}")
            file_pattern = output_config.get("file_pattern", "{deliverable_name}.md")

            format_context = {
                "issue_number": issue_number,
                "title_slug": title_slug,
                "workflow_slug": workflow_slug,
                "workflow_name": workflow_info.name,
            }

            folder_path = self._format_value(
                folder_template,
                format_context,
                workflow_info.name,
                field_name="folder_structure",
            )

            workflow_entry: Dict[str, Any] = {
                "workflow_name": workflow_info.name,
                "workflow_slug": workflow_slug,
                "priority": candidate.priority,
                "order": order,
                "deliverables": [],
            }

            for deliverable in workflow_info.deliverables:
                deliverable_name = deliverable.get("name") or "deliverable"
                deliverable_slug = self._slugify(deliverable_name)

                file_context = dict(format_context)
                file_context["deliverable_name"] = deliverable_slug
                base_filename = self._format_value(
                    file_pattern,
                    file_context,
                    workflow_info.name,
                    field_name="file_pattern",
                )

                base_relative_path = self._build_relative_path(folder_path, base_filename)

                entry: Dict[str, Any] = {
                    "workflow_name": workflow_info.name,
                    "workflow_slug": workflow_slug,
                    "deliverable_name": deliverable_name,
                    "deliverable_slug": deliverable_slug,
                    "folder": folder_path,
                    "base_filename": base_filename,
                    "final_filename": base_filename,
                    "base_relative_path": base_relative_path,
                    "final_relative_path": base_relative_path,
                    "conflict_group": None,
                    "conflict_index": None,
                    "was_conflict": False,
                }

                workflow_entry["deliverables"].append(entry)
                conflict_groups.setdefault(base_relative_path, []).append(entry)
                deliverable_total += 1

            workflow_entries.append(workflow_entry)

        self._apply_conflict_resolution(conflict_groups)

        manifest["workflow_count"] = len(workflow_entries)
        manifest["deliverable_count"] = deliverable_total
        manifest["workflows"] = workflow_entries
        manifest["conflict_groups"] = self._summarize_conflicts(conflict_groups)

        return manifest

    def _apply_conflict_resolution(
        self,
        conflict_groups: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        if self.strategy != "suffix":
            return

        for group_key, entries in conflict_groups.items():
            if len(entries) <= 1:
                continue

            slug_occurrences: Dict[str, int] = {}
            for index, entry in enumerate(entries):
                slug = str(entry["workflow_slug"])
                slug_occurrences[slug] = slug_occurrences.get(slug, 0) + 1

                suffix = f"{self.separator}{slug}"
                occurrence_index = slug_occurrences[slug]
                if occurrence_index > 1:
                    suffix = f"{suffix}{self.separator}{occurrence_index}"

                final_filename = self._append_suffix(str(entry["base_filename"]), suffix)
                entry["final_filename"] = final_filename
                entry["final_relative_path"] = self._build_relative_path(str(entry["folder"]), final_filename)
                entry["conflict_group"] = group_key
                entry["conflict_index"] = index
                entry["was_conflict"] = True

    @staticmethod
    def _summarize_conflicts(
        conflict_groups: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for group_key, entries in conflict_groups.items():
            if len(entries) <= 1:
                continue

            summaries.append(
                {
                    "group": group_key,
                    "workflow_count": len(entries),
                    "resolved_paths": [str(entry["final_relative_path"]) for entry in entries],
                }
            )
        return summaries

    @staticmethod
    def _build_relative_path(folder: str, filename: str) -> str:
        path = PurePosixPath(folder) / filename
        return path.as_posix()

    @staticmethod
    def _append_suffix(filename: str, suffix: str) -> str:
        if "." not in filename:
            return f"{filename}{suffix}"
        pivot = filename.rfind(".")
        return f"{filename[:pivot]}{suffix}{filename[pivot:]}"

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", value.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-") or "workflow"

    @staticmethod
    def _format_value(
        template: str,
        context: Dict[str, Any],
        workflow_name: str,
        *,
        field_name: str,
    ) -> str:
        try:
            return template.format(**context)
        except KeyError as exc:  # pragma: no cover - defensive guard
            missing = exc.args[0]
            placeholder = "{" + str(missing) + "}"
            raise ValueError(
                f"Unknown placeholder '{placeholder}' in {field_name} for workflow '{workflow_name}'"
            ) from exc
