"""Utilities for generating unified specialist and Copilot handoff sections.

This module assembles the standardized issue body sections defined by the
workflow refactor initiative. It pulls context from workflow metadata,
AI assessment output, and generated deliverables so that the issue processor
can emit consistent guidance for specialists and Copilot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import re

from .workflow_matcher import WorkflowInfo
from .specialist_workflow_config import (
    SpecialistWorkflowConfig,
    SpecialistWorkflowConfigManager,
    SpecialistType,
)
from ..utils.markdown_sections import extract_section

DEFAULT_COPILOT_ASSIGNEE = "github-copilot[bot]"
DEFAULT_DUE_HOURS = 48


@dataclass
class AIInsights:
    """Structured representation of the AI assessment section."""

    summary: Optional[str] = None
    recommended_workflows: Optional[List[str]] = None
    key_topics: Optional[List[str]] = None
    indicators: Optional[List[str]] = None
    urgency: Optional[str] = None
    content_type: Optional[str] = None

    def __post_init__(self) -> None:
        if self.recommended_workflows is None:
            self.recommended_workflows = []
        if self.key_topics is None:
            self.key_topics = []
        if self.indicators is None:
            self.indicators = []


@dataclass
class IssueHandoffPayload:
    """Rendered sections and metadata for updating an issue."""

    specialist_guidance: str
    copilot_assignment: str
    copilot_assignee: str
    copilot_due_iso: str
    summary_comment: str


class IssueHandoffBuilder:
    """Builds standardized specialist guidance and Copilot handoff content."""

    def __init__(
        self,
        *,
        config_path: str = "config.yaml",
        workflow_directory: str = "docs/workflow/deliverables",
        default_due_hours: int = DEFAULT_DUE_HOURS,
    ) -> None:
        self._default_due_hours = default_due_hours
        self._logger = logging.getLogger(__name__)
        self._config_manager: Optional[SpecialistWorkflowConfigManager]
        try:
            self._config_manager = SpecialistWorkflowConfigManager(
                config_path, workflow_directory
            )
            self._config_manager.load_configurations()
        except Exception as exc:  # noqa: BLE001
            # If specialist configs cannot be loaded we fall back to defaults.
            self._logger.warning("Unable to load specialist workflow configs: %s", exc)
            self._config_manager = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build_handoff(
        self,
        *,
        issue_title: str,
        issue_url: Optional[str],
        issue_body: str,
        workflow_info: WorkflowInfo,
        labels: Sequence[str],
        created_files: Sequence[str],
        metadata: Optional[Dict[str, Any]] = None,
        due_hours: Optional[int] = None,
    ) -> IssueHandoffPayload:
        """Return rendered specialist and Copilot sections for an issue."""

        insights = self._parse_ai_insights(issue_body)
        discovery_metadata = self._parse_discovery_metadata(issue_body)
        specialist_config = self._locate_specialist_config(labels, workflow_info)

        branch_name = self._extract_branch_from_metadata(metadata)
        relative_files = [self._format_file_path(path) for path in created_files]

        due_hours = due_hours or self._default_due_hours
        due_at = datetime.now(timezone.utc) + timedelta(hours=due_hours)
        due_iso = due_at.isoformat(timespec="seconds")

        specialist_section = self._render_specialist_guidance(
            issue_title=issue_title,
            issue_url=issue_url or discovery_metadata.get("URL"),
            workflow_info=workflow_info,
            specialist_config=specialist_config,
            insights=insights,
            discovery_metadata=discovery_metadata,
            created_files=relative_files,
            branch_name=branch_name,
        )

        copilot_section = self._render_copilot_assignment(
            issue_title=issue_title,
            workflow_info=workflow_info,
            specialist_config=specialist_config,
            insights=insights,
            created_files=relative_files,
            branch_name=branch_name,
            due_iso=due_iso,
        )

        summary_comment = self._render_summary_comment(
            workflow_info=workflow_info,
            relative_files=relative_files,
            branch_name=branch_name,
            due_iso=due_iso,
        )

        return IssueHandoffPayload(
            specialist_guidance=specialist_section,
            copilot_assignment=copilot_section,
            copilot_assignee=DEFAULT_COPILOT_ASSIGNEE,
            copilot_due_iso=due_iso,
            summary_comment=summary_comment,
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_branch_from_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        if not metadata:
            return None
        for key in ("git_branch", "branch", "branch_name"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _format_file_path(path: str) -> str:
        try:
            resolved = Path(path)
            cwd = Path.cwd()
            rel = resolved.relative_to(cwd)
            return rel.as_posix()
        except (ValueError, OSError):
            return Path(path).as_posix()

    def _locate_specialist_config(
        self,
        labels: Sequence[str],
        workflow_info: WorkflowInfo,
    ) -> Optional[SpecialistWorkflowConfig]:
        if not self._config_manager:
            return None

        specialist_label = next(
            (
                label.split("::", 1)[1]
                for label in labels
                if label.lower().startswith("specialist::") and "::" in label
            ),
            None,
        )

        # Fallback to workflow metadata if specialist label missing
        if not specialist_label:
            potential = (
                workflow_info.processing.get("specialist_type")
                if isinstance(workflow_info.processing, dict)
                else None
            )
            if isinstance(potential, str):
                specialist_label = potential

        if not specialist_label:
            return None

        normalised = specialist_label.strip().lower()
        try:
            specialist_type = SpecialistType(normalised)
        except ValueError:
            # Attempt with hyphen/underscore normalisation
            try:
                specialist_type = SpecialistType(normalised.replace("_", "-"))
            except ValueError:
                return None

        return self._config_manager.get_specialist_config(specialist_type)

    def _parse_ai_insights(self, issue_body: str) -> AIInsights:
        section = extract_section(issue_body or "", "AI Assessment")
        if not section:
            return AIInsights()

        current_block: Optional[str] = None
        summary_lines: List[str] = []
        recommended: List[str] = []
        topics: List[str] = []
        indicators: List[str] = []
        urgency: Optional[str] = None
        content_type: Optional[str] = None

        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            header_match = re.fullmatch(r"\*\*(.+?)\*\*", line)
            if header_match:
                current_block = header_match.group(1).strip().lower()
                continue
            if not line.startswith("-"):
                continue
            value = line[1:].strip()

            if current_block == "summary":
                summary_lines.append(value)
            elif current_block == "recommended workflows":
                recommended.append(value)
            elif current_block == "key topics":
                topics.append(value)
            elif current_block == "indicators":
                indicators.append(value)
            elif current_block == "classification":
                if value.lower().startswith("urgency:"):
                    urgency = value.split(":", 1)[1].strip()
                elif value.lower().startswith("content type:"):
                    content_type = value.split(":", 1)[1].strip()

        summary_text = " ".join(summary_lines) if summary_lines else None
        return AIInsights(
            summary=summary_text,
            recommended_workflows=recommended,
            key_topics=topics,
            indicators=indicators,
            urgency=urgency,
            content_type=content_type,
        )

    @staticmethod
    def _parse_discovery_metadata(issue_body: str) -> Dict[str, str]:
        section = extract_section(issue_body or "", "Discovery")
        if not section:
            return {}

        metadata: Dict[str, str] = {}
        pattern = re.compile(r"- \*\*(.+?)\*\*: (.+)")
        for line in section.splitlines():
            match = pattern.search(line)
            if match:
                metadata[match.group(1).strip()] = match.group(2).strip()
        return metadata

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_specialist_guidance(
        self,
        *,
        issue_title: str,
        issue_url: Optional[str],
        workflow_info: WorkflowInfo,
        specialist_config: Optional[SpecialistWorkflowConfig],
        insights: AIInsights,
        discovery_metadata: Dict[str, str],
        created_files: Sequence[str],
        branch_name: Optional[str],
    ) -> str:
        persona_name = specialist_config.name if specialist_config else "Specialist"
        role = self._resolve_role(specialist_config, workflow_info)
        objective = self._resolve_objective(specialist_config, workflow_info)

        insight_lines = self._build_insight_highlights(insights)
        insight_lines.insert(0, f"Issue focus: {issue_title}")
        if issue_url or discovery_metadata.get("URL"):
            source_url = issue_url or discovery_metadata.get("URL")
            insight_lines.append(f"Primary source: {source_url}")
        if discovery_metadata.get("Detected"):
            insight_lines.append(f"Detection timestamp: {discovery_metadata['Detected']}")
        insights_block = "\n".join(f"- {line}" for line in (insight_lines or [
            "AI assessment not available; review discovery details manually."
        ]))

        required_actions = self._build_required_actions(
            workflow_info=workflow_info,
            specialist_config=specialist_config,
            branch_name=branch_name,
            created_files=created_files,
        )
        actions_block = "\n".join(required_actions)

        deliverable_lines = self._build_deliverable_lines(
            workflow_info,
            created_files,
        )
        deliverables_block = "\n".join(deliverable_lines or [
            "- [ ] Confirm deliverable scope with the workflow lead."
        ])

        collaboration_lines = self._build_collaboration_notes(branch_name)
        collaboration_block = "\n".join(collaboration_lines)

        return (
            f"### Persona: {persona_name}\n"
            f"- **Role**: {role}\n"
            f"- **Objective**: {objective}\n\n"
            "### Key Insights from AI Assessment\n"
            f"{insights_block}\n\n"
            "### Required Actions\n"
            f"{actions_block}\n\n"
            "### Deliverables\n"
            f"{deliverables_block}\n\n"
            "### Collaboration Notes\n"
            f"{collaboration_block}\n"
        )

    def _render_copilot_assignment(
        self,
        *,
        issue_title: str,
        workflow_info: WorkflowInfo,
        specialist_config: Optional[SpecialistWorkflowConfig],
        insights: AIInsights,
        created_files: Sequence[str],
        branch_name: Optional[str],
        due_iso: str,
    ) -> str:
        acceptance = self._build_acceptance_criteria(workflow_info, created_files)
        validation_steps = self._build_validation_steps(branch_name, created_files)
        persona_hint = specialist_config.name if specialist_config else "the specialist"
        summary_snippet = insights.summary or (
            f"Execute deliverables for \"{issue_title}\" using the specialist guidance."
        )

        acceptance_block = "\n".join(acceptance)
        validation_block = "\n".join(validation_steps)

        return (
            f"**Assignee**: @{DEFAULT_COPILOT_ASSIGNEE}\n"
            f"**Due**: {due_iso}\n\n"
            f"**Summary**: {summary_snippet}\n\n"
            "**Acceptance Criteria**:\n"
            f"{acceptance_block}\n\n"
            "**Validation Steps**:\n"
            f"{validation_block}\n\n"
            f"**Notes**: Collaborate with {persona_hint} if scope changes or additional sources are required.\n"
        )

    @staticmethod
    def _render_summary_comment(
        *,
        workflow_info: WorkflowInfo,
        relative_files: Sequence[str],
        branch_name: Optional[str],
        due_iso: str,
    ) -> str:
        files_line = ", ".join(relative_files) if relative_files else "No files generated yet"
        branch_line = branch_name or "(branch not created)"
        return (
            "🚀 **Unified Issue Processing Update**\n\n"
            f"Workflow: **{workflow_info.name}**\n"
            f"Branch: `{branch_line}`\n"
            f"Deliverables: {files_line}\n"
            f"Assigned to: @{DEFAULT_COPILOT_ASSIGNEE} (due {due_iso})\n\n"
            "Specialist guidance and Copilot assignment sections have been updated in the issue body."
        )

    # ------------------------------------------------------------------
    # Section building helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_insight_highlights(insights: AIInsights) -> List[str]:
        highlights: List[str] = []
        if insights.summary:
            highlights.append(f"Summary: {insights.summary}")
        if insights.recommended_workflows:
            formatted = [IssueHandoffBuilder._format_recommended_workflow(value) for value in insights.recommended_workflows]
            highlights.extend(formatted)
        if insights.key_topics:
            highlights.append("Key topics: " + ", ".join(insights.key_topics[:3]))
        if insights.indicators:
            highlights.append("Indicators: " + ", ".join(insights.indicators[:3]))
        if insights.urgency:
            highlights.append(f"Urgency: {insights.urgency}")
        if insights.content_type:
            highlights.append(f"Content type: {insights.content_type}")
        return highlights

    @staticmethod
    def _format_recommended_workflow(value: str) -> str:
        text = value.strip()
        if not text:
            return "Recommended workflow: (unspecified)"

        pattern = re.compile(
            r"^(?P<name>[^—-]+?)"
            r"(?:\s+[—-]\s+(?:Confidence:?\s*)?(?P<confidence>[0-9]+%|[0-9]+\.[0-9]+%?))?"
            r"(?:\s+[—-]\s+Rationale:\s*(?P<rationale>.+?))?"
            r"(?:\s+\(assigned\))?$",
            re.IGNORECASE,
        )

        match = pattern.match(text)
        if not match:
            return f"Recommended workflow: {text}"

        name = match.group("name").strip()
        confidence = match.group("confidence")
        rationale = match.group("rationale")

        details: List[str] = []
        if confidence:
            details.append(confidence.strip())
        if rationale:
            details.append(rationale.strip())

        if details:
            return f"Recommended workflow: {name} ({'; '.join(details)})"

        return f"Recommended workflow: {name}"

    def _build_deliverable_lines(
        self,
        workflow_info: WorkflowInfo,
        created_files: Sequence[str],
    ) -> List[str]:
        lines: List[str] = []
        referenced_files = list(dict.fromkeys(created_files))

        for deliverable in workflow_info.deliverables:
            title = deliverable.get("title") or deliverable.get("name") or "Deliverable"
            description = deliverable.get("description", "")
            filename_hint = deliverable.get("filename") or deliverable.get("template")
            suffix = []
            if filename_hint:
                suffix.append(f"Target: `{filename_hint}`")
            if description:
                suffix.append(description)
            detail = " — ".join(suffix)
            line = f"- [ ] {title}"
            if detail:
                line += f" — {detail}"
            lines.append(line)

        for file_path in referenced_files:
            lines.append(f"- [ ] Verify output stored at `{file_path}`")

        return lines

    def _build_required_actions(
        self,
        *,
        workflow_info: WorkflowInfo,
        specialist_config: Optional[SpecialistWorkflowConfig],
        branch_name: Optional[str],
        created_files: Sequence[str],
    ) -> List[str]:
        base_actions: List[str] = [
            "Review the discovery context and AI assessment to confirm scope.",
            "Prioritize workflow objectives using the specialist guidance template.",
        ]

        if workflow_info.deliverables:
            deliverable_titles = [
                str(item.get("title") or item.get("name"))
                for item in workflow_info.deliverables
                if item.get("title") or item.get("name")
            ]
            if deliverable_titles:
                base_actions.append(
                    f"Develop deliverables: {', '.join(deliverable_titles)}."
                )

        if created_files:
            base_actions.append(
                f"Validate generated files: {', '.join(created_files)}."
            )
        elif branch_name:
            base_actions.append(f"Stage updates on branch `{branch_name}` for Copilot.")

        if specialist_config and specialist_config.quality_requirements.require_source_references:
            base_actions.append("Document source citations and note confidence levels.")

        return [f"{idx}. {text}" for idx, text in enumerate(base_actions, start=1)]

    @staticmethod
    def _build_collaboration_notes(branch_name: Optional[str]) -> List[str]:
        notes = [
            "- Coordinate with Workflow Assignment if label adjustments are needed.",
            "- Escalation if blocked: Workflow Modernization Lead.",
        ]
        if branch_name:
            notes.insert(0, f"- Reference branch `{branch_name}` for in-progress commits.")
        return notes

    @staticmethod
    def _resolve_role(
        specialist_config: Optional[SpecialistWorkflowConfig],
        workflow_info: WorkflowInfo,
    ) -> str:
        if specialist_config and specialist_config.persona:
            return specialist_config.persona.split(".")[0].strip()
        if specialist_config and specialist_config.description:
            return specialist_config.description.split(".")[0].strip()
        if workflow_info.description:
            return workflow_info.description.split(".")[0].strip()
        return "Domain expert supporting the workflow"

    @staticmethod
    def _resolve_objective(
        specialist_config: Optional[SpecialistWorkflowConfig],
        workflow_info: WorkflowInfo,
    ) -> str:
        if workflow_info.description:
            return workflow_info.description.split(".")[0].strip()
        if specialist_config and specialist_config.description:
            return specialist_config.description.split(".")[0].strip()
        return f"Advance the {workflow_info.name} workflow outcomes"

    @staticmethod
    def _build_acceptance_criteria(
        workflow_info: WorkflowInfo,
        created_files: Sequence[str],
    ) -> List[str]:
        deliverable_titles = [
            str(deliverable.get("title") or deliverable.get("name"))
            for deliverable in workflow_info.deliverables
            if deliverable.get("title") or deliverable.get("name")
        ]

        criteria = [
            "1. Deliver all specialist-requested artifacts with the updated analysis.",
            "2. Reflect specialist guidance directly in the committed files.",
        ]
        if deliverable_titles:
            criteria.insert(
                0,
                "1. Produce: " + ", ".join(deliverable_titles),
            )
        if created_files:
            criteria.append(
                "3. Confirm files are updated: " + ", ".join(created_files)
            )
        else:
            criteria.append(
                "3. Commit deliverables to the designated branch when ready."
            )

        return criteria

    @staticmethod
    def _build_validation_steps(
        branch_name: Optional[str],
        created_files: Sequence[str],
    ) -> List[str]:
        steps = []
        if branch_name:
            steps.append(f"- Checkout branch `{branch_name}` for updates.")
        if created_files:
            steps.append(
                "- Review updated files: " + ", ".join(created_files)
            )
        steps.append("- Run project linters and pytest critical suites.")
        steps.append("- Post completion summary with any blockers or open questions.")
        return steps
