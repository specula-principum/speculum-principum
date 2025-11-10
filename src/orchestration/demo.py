"""Demonstration helpers for executing Phase 0 missions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from .agent import AgentRuntime
from .evaluation import SimpleMissionEvaluator, TriageMissionEvaluator, successful_tool_execution
from .missions import Mission, load_mission
from .planner import DeterministicPlan, DeterministicPlanner, PlanStep, load_deterministic_plan
from .safety import SafetyValidator
from .toolkit import register_github_read_only_tools, register_parsing_tools
from .tools import ToolRegistry
from .types import ExecutionContext, MissionOutcome, MissionStatus


_DEFAULT_PREVIEW_PLAN_PATH = Path("devops/projects/kb-source-preview.plan.yaml")
_DEFAULT_PREVIEW_MISSION_PATH = Path("config/missions/kb_source_preview.yaml")


@dataclass(frozen=True)
class IssueSummary:
    """Concise summary of a GitHub issue produced by the demo mission."""

    number: int
    title: str
    state: str
    labels: tuple[str, ...]
    url: str

    def as_text(self) -> str:
        label_text = ", ".join(self.labels) if self.labels else "no labels"
        return f"Issue #{self.number} ({self.state}): {self.title} — Labels: {label_text} — {self.url}"


@dataclass(frozen=True)
class TriageRecommendation:
    """Simple heuristic classification for issue triage."""

    classification: str
    rationale: str
    suggested_labels: tuple[str, ...]

    def as_text(self) -> str:
        labels = ", ".join(self.suggested_labels) if self.suggested_labels else "no labels"
        return f"Recommendation: {self.classification} ({labels}) — {self.rationale}"


@dataclass(frozen=True)
class IssueInsights:
    """Aggregated insights derived from issue metadata."""

    summary: IssueSummary
    recommendation: TriageRecommendation | None
    payload: Mapping[str, Any]

    def render(self, *, include_recommendation: bool) -> str:
        lines = [self.summary.as_text()]
        if include_recommendation and self.recommendation is not None:
            lines.append(self.recommendation.as_text())
        return "\n".join(lines)


def run_issue_detail_demo(
    *,
    issue_number: int,
    repository: str | None = None,
    token: str | None = None,
    plan_override: Sequence[PlanStep] | None = None,
    default_finish: str | None = None,
    context_inputs: Mapping[str, object] | None = None,
    triage_mode: bool = False,
    interactive: bool = False,
) -> tuple[MissionOutcome, IssueSummary | None, TriageRecommendation | None]:
    """Execute the Phase 0 demo mission that fetches and summarizes a GitHub issue."""

    registry = ToolRegistry()
    register_github_read_only_tools(registry)

    mission = Mission(
        id="issue-detail-demo",
        goal="Fetch a GitHub issue and synthesize a short status summary.",
        max_steps=3,
        constraints=(
            "Only read information from GitHub; do not attempt mutations.",
        ),
        success_criteria=(
            "Issue details retrieved successfully.",
            "Summary generated for operator review.",
        ),
        allowed_tools=("get_issue_details",),
    )

    if plan_override is not None:
        deterministic_plan = DeterministicPlan(
            steps=tuple(plan_override),
            default_finish=default_finish or "Mission complete.",
        )
    else:
        deterministic_plan = DeterministicPlan(
            steps=(
                PlanStep(
                    description="Retrieve issue details",
                    tool_name="get_issue_details",
                    arguments={
                        "issue_number": issue_number,
                        **(_optional_arg("repository", repository)),
                        **(_optional_arg("token", token)),
                    },
                ),
            ),
            default_finish=default_finish or "Mission complete.",
        )

    planner = DeterministicPlanner(steps=deterministic_plan.steps, default_finish=deterministic_plan.default_finish)

    context_payload: dict[str, Any] = {
        "issue_number": issue_number,
        "repository": repository,
        "token": token,
        "triage_mode": triage_mode,
    }
    if context_inputs:
        context_payload.update(context_inputs)
        context_payload.setdefault("issue_number", issue_number)
        context_payload.setdefault("repository", repository)
        context_payload.setdefault("token", token)

    def _collect_insights(steps, ctx, *, include_recommendation: bool) -> str | None:
        insights = _build_issue_insights(steps, ctx, triage_mode=triage_mode)
        if insights is None:
            return None
        inputs = ctx.inputs
        if isinstance(inputs, MutableMapping):
            inputs["latest_issue_insights"] = insights
        return insights.render(include_recommendation=include_recommendation)

    if triage_mode:
        base_evaluator = TriageMissionEvaluator()

        class _WrappedTriageEvaluator:
            def evaluate(self, mission, steps, context):  # type: ignore[override]
                _collect_insights(steps, context, include_recommendation=True)
                return base_evaluator.evaluate(mission, steps, context)

        evaluator = _WrappedTriageEvaluator()
    else:
        evaluator = SimpleMissionEvaluator(
            success_condition=lambda steps: any(successful_tool_execution(step) for step in steps),
            summary_builder=lambda steps, ctx: _collect_insights(steps, ctx, include_recommendation=False),
            failure_reason="Failed to retrieve issue details.",
        )

    # Setup approval gate for interactive mode
    approval_callback = None
    if interactive:
        from .approval import ApprovalGate, create_approval_callback
        gate = ApprovalGate(auto_approve=False)
        approval_callback = create_approval_callback(gate)

    runtime = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=SafetyValidator(approval_callback=approval_callback),
        evaluator=evaluator,
    )

    context = ExecutionContext(inputs=context_payload)
    outcome = runtime.execute_mission(mission, context)

    insights: IssueInsights | None = context.inputs.get("latest_issue_insights")  # type: ignore[assignment]
    summary = insights.summary if insights else None
    recommendation = insights.recommendation if insights else None

    if outcome.status is MissionStatus.SUCCEEDED and summary is None:
        fallback = _build_issue_insights(outcome.steps, context, triage_mode=triage_mode)
        if fallback is not None:
            summary = fallback.summary
            recommendation = fallback.recommendation

    if outcome.status is MissionStatus.SUCCEEDED and triage_mode and recommendation is None:
        outcome = MissionOutcome(status=MissionStatus.FAILED, steps=outcome.steps, summary="Missing triage recommendation.")

    return outcome, summary, recommendation


def run_parsing_preview_demo(
    *,
    parse_root: str | Path,
    source_path: str | Path,
    plan_path: Path | None = None,
    mission_path: Path | None = None,
    context_inputs: Mapping[str, object] | None = None,
) -> tuple[MissionOutcome, Mapping[str, Any] | None, tuple[str, ...], Mission, DeterministicPlan, Mapping[str, Any]]:
    """Execute the parsing preview mission to capture sanitized Markdown output."""

    registry = ToolRegistry()
    register_parsing_tools(registry)

    mission_file = mission_path or _DEFAULT_PREVIEW_MISSION_PATH
    mission = load_mission(mission_file)

    parse_root_path = Path(parse_root).expanduser().resolve()
    source_path_resolved = Path(source_path).expanduser().resolve()

    base_context: dict[str, object] = {
        "parse_root": str(parse_root_path),
        "source_path": str(source_path_resolved),
    }
    if context_inputs:
        for key, value in context_inputs.items():
            base_context[key] = value

    plan_variables = {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in base_context.items()
        if value is not None
    }

    plan_file = plan_path or _DEFAULT_PREVIEW_PLAN_PATH
    plan = load_deterministic_plan(plan_file, variables=plan_variables)

    planner = DeterministicPlanner(steps=plan.steps, default_finish=plan.default_finish)
    context = ExecutionContext(inputs=dict(base_context))

    evaluator = SimpleMissionEvaluator(
        success_condition=_has_successful_preview,
        summary_builder=_build_preview_summary,
        failure_reason="Failed to capture document preview content.",
    )

    runtime = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=SafetyValidator(),
        evaluator=evaluator,
    )

    outcome = runtime.execute_mission(mission, context)

    preview_payload = _extract_preview_payload(context.inputs)
    candidates_value = context.inputs.get("preview_candidates")
    candidate_list = _coerce_candidate_list(candidates_value)

    return outcome, preview_payload, candidate_list, mission, plan, context.inputs


def _optional_arg(key: str, value: str | None) -> Mapping[str, str]:
    if value in (None, ""):
        return {}
    return {key: value}


def _has_successful_preview(steps: Sequence) -> bool:
    for step in steps:
        tool_call = getattr(step.thought, "tool_call", None)
        result = getattr(step, "result", None)
        if tool_call is None or result is None:
            continue
        if tool_call.name == "preview_parse_document" and result.success:
            return True
    return False


def _build_preview_summary(steps: Sequence, context: ExecutionContext) -> str | None:
    candidates, preview_payload = _collect_preview_artifacts(steps)
    _store_preview_context(context, candidates, preview_payload)

    if preview_payload is None:
        return None

    lines = _render_preview_summary(preview_payload, candidates)
    return "\n".join(lines)


def _collect_preview_artifacts(steps: Sequence) -> tuple[tuple[str, ...] | None, Mapping[str, Any] | None]:
    candidates: tuple[str, ...] | None = None
    preview_payload: Mapping[str, Any] | None = None

    for step in steps:
        tool_call = getattr(step.thought, "tool_call", None)
        result = getattr(step, "result", None)
        if tool_call is None or result is None or not result.success:
            continue

        if tool_call.name == "list_parse_candidates":
            candidates = _coerce_candidate_list(result.output)
        elif tool_call.name == "preview_parse_document" and isinstance(result.output, Mapping):
            preview_payload = result.output

    return candidates, preview_payload


def _store_preview_context(
    context: ExecutionContext,
    candidates: tuple[str, ...] | None,
    preview_payload: Mapping[str, Any] | None,
) -> None:
    inputs = context.inputs
    if not isinstance(inputs, MutableMapping):
        return
    if candidates is not None:
        inputs["preview_candidates"] = candidates
    if preview_payload is not None:
        inputs["latest_preview_payload"] = preview_payload


def _render_preview_summary(
    preview_payload: Mapping[str, Any],
    candidates: tuple[str, ...] | None,
) -> list[str]:
    status = preview_payload.get("status", "unknown")
    parser_name = preview_payload.get("parser") or "unknown"
    lines = [f"Preview status: {status} (parser={parser_name})"]

    preview_block = preview_payload.get("preview")
    if isinstance(preview_block, Mapping):
        relative_path = preview_block.get("relative_path") or "unknown"
        truncated = bool(preview_block.get("truncated"))
        lines.append(f"Preview artifact: {relative_path} (truncated={truncated})")
        content = preview_block.get("content")
        if isinstance(content, str) and content.strip():
            first_line = content.strip().splitlines()[0][:120]
            lines.append(f"Preview excerpt: {first_line}")

    warnings = preview_payload.get("warnings")
    if isinstance(warnings, Sequence) and not isinstance(warnings, (str, bytes, bytearray)) and warnings:
        joined = "; ".join(str(item) for item in warnings)
        lines.append(f"Warnings: {joined}")

    if candidates:
        lines.append(f"Candidates evaluated: {len(candidates)}")
    return lines


def _extract_preview_payload(inputs: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = inputs.get("latest_preview_payload")
    if isinstance(value, Mapping):
        return value
    return None


def _coerce_candidate_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        entries: list[str] = []
        for item in value:
            if item is None:
                continue
            entries.append(str(item))
        return tuple(entries)
    return tuple()


def _build_issue_insights(
    steps,
    context: ExecutionContext,
    *,
    triage_mode: bool,
) -> IssueInsights | None:
    for step in steps:
        if step.result is None or not step.result.success or not isinstance(step.result.output, Mapping):
            continue
        payload = step.result.output
        number = int(payload.get("number", context.inputs.get("issue_number", 0)))
        title = str(payload.get("title", ""))
        state = str(payload.get("state", ""))
        labels = tuple(str(label) for label in payload.get("labels", []) if label)
        url = str(payload.get("url", ""))
        summary = IssueSummary(number=number, title=title, state=state, labels=labels, url=url)
        recommendation = _generate_triage_recommendation(payload) if triage_mode else None
        return IssueInsights(summary=summary, recommendation=recommendation, payload=payload)
    return None


def _generate_triage_recommendation(payload: Mapping[str, Any]) -> TriageRecommendation:
    body = str(payload.get("body", ""))
    title = str(payload.get("title", ""))
    combined = f"{title}\n{body}".lower()
    labels = tuple(str(label).lower() for label in payload.get("labels", []) if label)

    # Check for question/help patterns first (higher priority for user support)
    if any(keyword in combined for keyword in ("how do", "how to", "question", "help me", "can someone")):
        return TriageRecommendation(
            classification="needs-info",
            rationale="Detected question-oriented language; more information required.",
            suggested_labels=("needs-info",),
        )

    # Check for KB extraction - be more specific to avoid false positives
    kb_label_match = any(token in labels for token in ("kb-extraction", "kb", "knowledge-base"))
    kb_content_match = any(
        pattern in combined
        for pattern in ("extract knowledge", "kb extraction", "knowledge extraction", "extract from")
    )
    if kb_label_match or kb_content_match:
        return TriageRecommendation(
            classification="kb-extraction",
            rationale="Detected extraction keywords in title/body or labels.",
            suggested_labels=("kb-extraction",),
        )

    # Check for bug reports
    if any(keyword in combined for keyword in ("bug", "error", "fail", "stacktrace", "crash")) or "bug" in labels:
        return TriageRecommendation(
            classification="bug",
            rationale="Issue references errors or failures indicating a defect.",
            suggested_labels=("bug",),
        )

    # Check for feature requests
    if any(keyword in combined for keyword in ("feature", "enhancement", "request", "would be great")) or "feature-request" in labels:
        return TriageRecommendation(
            classification="feature-request",
            rationale="Language suggests a feature or enhancement request.",
            suggested_labels=("feature-request",),
        )

    # Default to human review
    return TriageRecommendation(
        classification="needs-review",
        rationale="No strong signals detected; escalate for human review.",
        suggested_labels=(),
    )

@dataclass(frozen=True)
class TemplateValidationResult:
    """Result of validating an issue against a template."""

    is_valid: bool
    missing_fields: tuple[str, ...]
    present_fields: tuple[str, ...]
    validation_message: str

    def as_text(self) -> str:
        if self.is_valid:
            return f"✓ Template valid: all {len(self.present_fields)} required fields present"
        missing = ", ".join(self.missing_fields)
        return f"✗ Template incomplete: missing {len(self.missing_fields)} fields: {missing}"


@dataclass(frozen=True)
class ExtractionCheckResult:
    """Combined result of KB extraction issue validation check."""

    summary: IssueSummary
    validation: TemplateValidationResult
    recommended_action: str

    def render(self) -> str:
        lines = [
            self.summary.as_text(),
            "",
            "Template Validation:",
            self.validation.as_text(),
            "",
            f"Recommended Action: {self.recommended_action}",
        ]
        return "\n".join(lines)


def _validate_extraction_template(issue_body: str) -> TemplateValidationResult:
    """Validate that a KB extraction issue contains required template fields.

    Required fields for kb-extract-source template:
    - Source Path (file path to extract from)
    - Source Type (document format: pdf, docx, markdown, etc.)
    - Extraction Requirements (checklist items)
    - Output Requirements (target KB root)
    - Success Criteria (validation checklist)
    """

    required_patterns = {
        "source_path": ("source path:", "**source path:**", "source:", "path:"),
        "source_type": ("source type:", "**source type:**", "type:", "format:"),
        "extraction_requirements": ("extraction requirements", "requirements:", "extract:"),
        "output_requirements": ("output requirements", "target kb", "kb root"),
        "success_criteria": ("success criteria", "criteria:", "[ ]"),
    }

    body_lower = issue_body.lower()
    present_fields: list[str] = []
    missing_fields: list[str] = []

    for field_name, patterns in required_patterns.items():
        if any(pattern in body_lower for pattern in patterns):
            present_fields.append(field_name)
        else:
            missing_fields.append(field_name)

    is_valid = len(missing_fields) == 0
    validation_msg = (
        f"All required template fields present ({len(present_fields)}/{len(required_patterns)})"
        if is_valid
        else f"Missing {len(missing_fields)} required fields: {', '.join(missing_fields)}"
    )

    return TemplateValidationResult(
        is_valid=is_valid,
        missing_fields=tuple(missing_fields),
        present_fields=tuple(present_fields),
        validation_message=validation_msg,
    )


def _generate_extraction_check_recommendation(
    validation: TemplateValidationResult,
) -> str:
    """Generate recommended action based on validation result."""

    if validation.is_valid:
        return "Template is complete. Proceed with automated extraction workflow."

    if len(validation.missing_fields) >= 3:
        return (
            "Template is incomplete. Post comment requesting submitter to use "
            "the kb-extract-source.md template and provide all required fields."
        )

    missing_list = ", ".join(validation.missing_fields)
    return f"Template mostly complete but missing: {missing_list}. Request clarification via comment."


def run_extraction_check_demo(
    *,
    issue_number: int,
    repository: str | None = None,
    token: str | None = None,
) -> tuple[MissionOutcome, ExtractionCheckResult | None]:
    """Execute the KB extraction check mission to validate template completeness.

    This mission fetches a KB extraction issue and validates that it contains
    all required template fields before automated processing can proceed.
    """

    registry = ToolRegistry()
    register_github_read_only_tools(registry)

    mission = Mission(
        id="kb-extraction-check",
        goal="Verify that a KB extraction issue contains all required template fields.",
        max_steps=5,
        constraints=(
            "Only read information from GitHub; do not modify the issue.",
        ),
        success_criteria=(
            "Issue details retrieved successfully.",
            "Template validation completed.",
            "Recommendation generated for next steps.",
        ),
        allowed_tools=("get_issue_details",),
    )

    deterministic_plan = DeterministicPlan(
        steps=(
            PlanStep(
                description="Retrieve KB extraction issue details",
                tool_name="get_issue_details",
                arguments={
                    "issue_number": issue_number,
                    **(_optional_arg("repository", repository)),
                    **(_optional_arg("token", token)),
                },
            ),
        ),
        default_finish="Template validation complete.",
    )

    planner = DeterministicPlanner(
        steps=deterministic_plan.steps,
        default_finish=deterministic_plan.default_finish,
    )

    def _build_extraction_check_summary(steps, ctx) -> str | None:
        check_result = _extract_validation_result(steps, ctx)
        if check_result is None:
            return None

        # Store result in context for retrieval
        inputs = ctx.inputs
        if isinstance(inputs, MutableMapping):
            inputs["extraction_check_result"] = check_result

        return check_result.render()

    evaluator = SimpleMissionEvaluator(
        success_condition=lambda steps: any(successful_tool_execution(step) for step in steps),
        summary_builder=_build_extraction_check_summary,
        failure_reason="Failed to validate KB extraction template.",
    )

    runtime = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=SafetyValidator(),
        evaluator=evaluator,
    )

    context_payload = {
        "issue_number": issue_number,
        "repository": repository,
        "token": token,
    }

    context = ExecutionContext(inputs=context_payload)
    outcome = runtime.execute_mission(mission, context)

    check_result: ExtractionCheckResult | None = context.inputs.get("extraction_check_result")  # type: ignore[assignment]

    if outcome.status is MissionStatus.SUCCEEDED and check_result is None:
        # Fallback: try to reconstruct result from steps
        check_result = _extract_validation_result(outcome.steps, context)

    return outcome, check_result


def _extract_validation_result(
    steps,
    context: ExecutionContext,
) -> ExtractionCheckResult | None:
    """Extract validation result from mission execution steps."""

    for step in steps:
        if step.result is None or not step.result.success or not isinstance(step.result.output, Mapping):
            continue

        payload = step.result.output
        number = int(payload.get("number", context.inputs.get("issue_number", 0)))
        title = str(payload.get("title", ""))
        state = str(payload.get("state", ""))
        labels = tuple(str(label) for label in payload.get("labels", []) if label)
        url = str(payload.get("url", ""))
        body = str(payload.get("body", ""))

        summary = IssueSummary(
            number=number,
            title=title,
            state=state,
            labels=labels,
            url=url,
        )

        validation = _validate_extraction_template(body)
        recommended_action = _generate_extraction_check_recommendation(validation)

        return ExtractionCheckResult(
            summary=summary,
            validation=validation,
            recommended_action=recommended_action,
        )

    return None


@dataclass(frozen=True)
class PRSummary:
    """Concise summary of a GitHub pull request."""

    number: int
    title: str
    state: str
    head_ref: str
    base_ref: str
    url: str

    def as_text(self) -> str:
        return f"PR #{self.number} ({self.state}): {self.title} — {self.head_ref} → {self.base_ref} — {self.url}"


@dataclass(frozen=True)
class PRSafetyCategory:
    """Classification of PR based on changed files."""

    category: str
    rationale: str
    is_safe_for_auto_merge: bool
    changed_paths: tuple[str, ...]
    risky_changes: tuple[str, ...]

    def as_text(self) -> str:
        safe_status = "✓ Safe for auto-merge" if self.is_safe_for_auto_merge else "✗ Requires review"
        paths_summary = f"{len(self.changed_paths)} files changed"
        if self.risky_changes:
            risky_list = ", ".join(self.risky_changes[:3])
            if len(self.risky_changes) > 3:
                risky_list += f", and {len(self.risky_changes) - 3} more"
            return f"{safe_status}: {self.category} — {paths_summary} — Risky: {risky_list} — {self.rationale}"
        return f"{safe_status}: {self.category} — {paths_summary} — {self.rationale}"


@dataclass(frozen=True)
class PRSafetyCheckResult:
    """Combined result of PR safety check."""

    summary: PRSummary
    category: PRSafetyCategory
    recommended_action: str

    def render(self) -> str:
        lines = [
            self.summary.as_text(),
            "",
            "Safety Assessment:",
            self.category.as_text(),
            "",
            f"Recommended Action: {self.recommended_action}",
        ]
        return "\n".join(lines)


def _categorize_pr_safety(files: list[dict[str, Any]]) -> PRSafetyCategory:
    """Categorize a PR based on files changed and assess safety for auto-merge.

    Categories:
    - kb-only: Only touches knowledge-base/ directory (safe for auto-merge if additive)
    - config-only: Only touches config/ or .github/ (requires review)
    - test-only: Only touches tests/ (safe for auto-merge)
    - documentation-only: Only touches README, docs/, or .md files (safe for auto-merge)
    - src-changes: Modifies source code (requires review)
    - mixed: Changes multiple categories (requires review)
    """

    changed_paths = [f.get("filename", "") for f in files]
    kb_files = []
    config_files = []
    test_files = []
    doc_files = []
    src_files = []
    other_files = []

    for path in changed_paths:
        if path.startswith("knowledge-base/"):
            kb_files.append(path)
        elif path.startswith(("config/", ".github/")):
            config_files.append(path)
        elif path.startswith("tests/"):
            test_files.append(path)
        elif path.endswith(".md") or path.startswith("docs/"):
            doc_files.append(path)
        elif path.startswith("src/"):
            src_files.append(path)
        else:
            other_files.append(path)

    # Check for deletions (risky)
    risky_changes = []
    for file_data in files:
        if file_data.get("status") == "removed":
            risky_changes.append(file_data.get("filename", ""))

    # Categorize based on what's changed
    if kb_files and not (config_files or test_files or src_files or other_files):
        # KB-only changes
        if risky_changes:
            return PRSafetyCategory(
                category="kb-only-with-deletions",
                rationale="Changes only KB files but includes deletions which require review.",
                is_safe_for_auto_merge=False,
                changed_paths=tuple(changed_paths),
                risky_changes=tuple(risky_changes),
            )
        return PRSafetyCategory(
            category="kb-only",
            rationale="Changes only KB files with no deletions. Safe for automated processing.",
            is_safe_for_auto_merge=True,
            changed_paths=tuple(changed_paths),
            risky_changes=(),
        )

    if test_files and not (kb_files or config_files or src_files or other_files):
        return PRSafetyCategory(
            category="test-only",
            rationale="Changes only test files. Safe for auto-merge after CI passes.",
            is_safe_for_auto_merge=True,
            changed_paths=tuple(changed_paths),
            risky_changes=tuple(risky_changes),
        )

    if doc_files and not (kb_files or config_files or test_files or src_files or other_files):
        return PRSafetyCategory(
            category="documentation-only",
            rationale="Changes only documentation files. Safe for auto-merge.",
            is_safe_for_auto_merge=True,
            changed_paths=tuple(changed_paths),
            risky_changes=tuple(risky_changes),
        )

    if config_files and not (kb_files or test_files or src_files or doc_files or other_files):
        return PRSafetyCategory(
            category="config-only",
            rationale="Changes configuration files. Requires human review for correctness.",
            is_safe_for_auto_merge=False,
            changed_paths=tuple(changed_paths),
            risky_changes=tuple(risky_changes),
        )

    if src_files and not (kb_files or config_files or test_files or doc_files or other_files):
        return PRSafetyCategory(
            category="src-changes",
            rationale="Modifies source code. Requires code review and testing.",
            is_safe_for_auto_merge=False,
            changed_paths=tuple(changed_paths),
            risky_changes=tuple(risky_changes),
        )

    # Mixed changes
    categories = []
    if kb_files:
        categories.append("KB")
    if config_files:
        categories.append("config")
    if test_files:
        categories.append("tests")
    if doc_files:
        categories.append("docs")
    if src_files:
        categories.append("src")
    if other_files:
        categories.append("other")

    category_str = "+".join(categories) if categories else "unknown"
    return PRSafetyCategory(
        category=f"mixed-{category_str}",
        rationale=f"Changes span multiple categories ({category_str}). Requires comprehensive review.",
        is_safe_for_auto_merge=False,
        changed_paths=tuple(changed_paths),
        risky_changes=tuple(risky_changes),
    )


def _generate_pr_safety_recommendation(category: PRSafetyCategory) -> str:
    """Generate recommended action based on PR safety category."""

    # Check for risky changes FIRST (highest priority)
    if category.risky_changes:
        return f"Risky changes detected ({len(category.risky_changes)} deletions). Require careful human review."

    # Then check category-specific recommendations
    if category.is_safe_for_auto_merge:
        if category.category == "kb-only":
            return "Safe for auto-merge. Run KB validation, then approve and merge automatically."
        if category.category == "test-only":
            return "Safe for auto-merge after CI passes. Approve and merge automatically."
        if category.category == "documentation-only":
            return "Safe for auto-merge. Approve and merge automatically."

    if category.category == "config-only":
        return "Configuration changes detected. Request human review to validate correctness."

    if category.category == "src-changes":
        return "Source code changes detected. Require code review and full test suite execution."

    if category.category.startswith("mixed-"):
        return "Mixed changes detected. Require comprehensive review covering all affected areas."

    return "Unknown change pattern. Escalate for human review."


def run_pr_safety_check_demo(
    *,
    pr_number: int,
    repository: str | None = None,
    token: str | None = None,
) -> tuple[MissionOutcome, PRSafetyCheckResult | None]:
    """Execute the PR safety check mission to categorize and assess merge safety.

    This mission fetches a PR and its changed files, then categorizes it based
    on what files were modified and assesses whether it's safe for auto-merge.
    """

    registry = ToolRegistry()
    from .toolkit import register_github_pr_tools
    register_github_pr_tools(registry)

    mission = Mission(
        id="pr-safety-check",
        goal="Categorize a pull request based on changed files and assess merge safety.",
        max_steps=7,
        constraints=(
            "Only read PR information from GitHub; do not modify the PR.",
        ),
        success_criteria=(
            "PR details retrieved successfully.",
            "File changes analyzed.",
            "Safety category and recommendation generated.",
        ),
        allowed_tools=("get_pr_details", "get_pr_files"),
    )

    deterministic_plan = DeterministicPlan(
        steps=(
            PlanStep(
                description="Retrieve PR details",
                tool_name="get_pr_details",
                arguments={
                    "pr_number": pr_number,
                    **(_optional_arg("repository", repository)),
                    **(_optional_arg("token", token)),
                },
            ),
            PlanStep(
                description="Retrieve PR file changes",
                tool_name="get_pr_files",
                arguments={
                    "pr_number": pr_number,
                    **(_optional_arg("repository", repository)),
                    **(_optional_arg("token", token)),
                },
            ),
        ),
        default_finish="PR safety check complete.",
    )

    planner = DeterministicPlanner(
        steps=deterministic_plan.steps,
        default_finish=deterministic_plan.default_finish,
    )

    def _build_pr_safety_summary(steps, ctx) -> str | None:
        safety_result = _extract_pr_safety_result(steps, ctx)
        if safety_result is None:
            return None

        # Store result in context for retrieval
        inputs = ctx.inputs
        if isinstance(inputs, MutableMapping):
            inputs["pr_safety_result"] = safety_result

        return safety_result.render()

    evaluator = SimpleMissionEvaluator(
        success_condition=lambda steps: sum(1 for step in steps if successful_tool_execution(step)) >= 2,
        summary_builder=_build_pr_safety_summary,
        failure_reason="Failed to complete PR safety check.",
    )

    runtime = AgentRuntime(
        planner=planner,
        tools=registry,
        safety=SafetyValidator(),
        evaluator=evaluator,
    )

    context_payload = {
        "pr_number": pr_number,
        "repository": repository,
        "token": token,
    }

    context = ExecutionContext(inputs=context_payload)
    outcome = runtime.execute_mission(mission, context)

    safety_result: PRSafetyCheckResult | None = context.inputs.get("pr_safety_result")  # type: ignore[assignment]

    if outcome.status is MissionStatus.SUCCEEDED and safety_result is None:
        # Fallback: try to reconstruct result from steps
        safety_result = _extract_pr_safety_result(outcome.steps, context)

    return outcome, safety_result


def _extract_pr_safety_result(
    steps,
    context: ExecutionContext,
) -> PRSafetyCheckResult | None:
    """Extract PR safety result from mission execution steps."""

    pr_data = None
    files_data = None

    for step in steps:
        if step.result is None or not step.result.success:
            continue

        if not isinstance(step.result.output, Mapping):
            continue

        # Check if this is PR details
        if "head_ref" in step.result.output:
            pr_data = step.result.output
        # Check if this is file list
        elif "files" in step.result.output and "count" in step.result.output:
            files_data = step.result.output.get("files", [])

    if pr_data is None or files_data is None:
        return None

    number = int(pr_data.get("number", context.inputs.get("pr_number", 0)))
    title = str(pr_data.get("title", ""))
    state = str(pr_data.get("state", ""))
    head_ref = str(pr_data.get("head_ref", ""))
    base_ref = str(pr_data.get("base_ref", ""))
    url = str(pr_data.get("url", ""))

    summary = PRSummary(
        number=number,
        title=title,
        state=state,
        head_ref=head_ref,
        base_ref=base_ref,
        url=url,
    )

    category = _categorize_pr_safety(files_data)
    recommended_action = _generate_pr_safety_recommendation(category)

    return PRSafetyCheckResult(
        summary=summary,
        category=category,
        recommended_action=recommended_action,
    )
