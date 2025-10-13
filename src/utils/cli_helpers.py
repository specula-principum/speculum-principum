"""
CLI helper utilities for Speculum Principum command-line interface.

This module provides reusable utilities for CLI operations including:
- Progress reporting and status display
- Command validation and error handling
- Issue processing result formatting
- Batch operation utilities

The helpers maintain consistent output formatting and error handling
across all CLI commands while providing clean interfaces for testing.
"""

import sys
import os
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass, replace
from datetime import datetime

from .config_manager import ConfigManager


@dataclass
class CliResult:
    """Standardized CLI operation result."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: int = 0


class ProgressReporter:
    """Progress reporting utilities for CLI operations."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize progress reporter.
        
        Args:
            verbose: Whether to show detailed progress information
        """
        self.verbose = verbose
        self._current_operation = None
        self._start_time = None
    
    def start_operation(self, operation_name: str) -> None:
        """
        Start tracking an operation.
        
        Args:
            operation_name: Human-readable name of the operation
        """
        self._current_operation = operation_name
        self._start_time = datetime.now()
        
        if self.verbose:
            print(f"🚀 Starting: {operation_name}")
        else:
            print(f"⏳ {operation_name}...")
    
    def update_progress(self, message: str, step: Optional[int] = None, total: Optional[int] = None) -> None:
        """
        Update operation progress.
        
        Args:
            message: Progress message
            step: Current step number (optional)
            total: Total steps (optional)
        """
        if not self.verbose:
            return
        
        progress_info = ""
        if step is not None and total is not None:
            percentage = (step / total) * 100
            progress_info = f" [{step}/{total} - {percentage:.1f}%]"
        
        print(f"  📋 {message}{progress_info}")
    
    def complete_operation(self, success: bool, message: Optional[str] = None) -> None:
        """
        Complete the current operation.
        
        Args:
            success: Whether the operation succeeded
            message: Optional completion message
        """
        if not self._current_operation:
            return
        
        elapsed = datetime.now() - self._start_time if self._start_time else None
        elapsed_str = f" (took {elapsed.total_seconds():.1f}s)" if elapsed else ""
        
        if success:
            status_icon = "✅"
            final_message = message or f"Completed: {self._current_operation}"
        else:
            status_icon = "❌"
            final_message = message or f"Failed: {self._current_operation}"
        
        print(f"{status_icon} {final_message}{elapsed_str}")
        
        self._current_operation = None
        self._start_time = None
    
    def show_warning(self, message: str) -> None:
        """Show a warning message."""
        print(f"⚠️  {message}")
    
    def show_info(self, message: str) -> None:
        """Show an informational message."""
        print(f"ℹ️  {message}")
    
    def show_error(self, message: str) -> None:
        """Show an error message."""
        print(f"❌ {message}", file=sys.stderr)


class ConfigValidator:
    """Validates CLI command configuration and environment."""
    
    @staticmethod
    def validate_config_file(config_path: str) -> CliResult:
        """
        Validate that configuration file exists and is accessible.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            CliResult indicating validation success/failure
        """
        if not os.path.exists(config_path):
            return CliResult(
                success=False,
                message=f"Configuration file not found: {config_path}",
                error_code=1
            )
        
        try:
            # Try to load the configuration
            ConfigManager.load_config_with_env_substitution(config_path)
            return CliResult(
                success=True,
                message="Configuration file is valid"
            )
        except Exception as e:
            return CliResult(
                success=False,
                message=f"Invalid configuration file: {str(e)}",
                error_code=1
            )
    
    @staticmethod
    def validate_environment() -> CliResult:
        """
        Validate required environment variables.
        
        Returns:
            CliResult indicating validation success/failure
        """
        required_vars = ['GITHUB_TOKEN', 'GITHUB_REPOSITORY']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            return CliResult(
                success=False,
                message=f"Missing required environment variables: {', '.join(missing_vars)}",
                error_code=1
            )
        
        return CliResult(
            success=True,
            message="Environment validation passed"
        )
    
    @staticmethod
    def validate_workflow_directory(workflow_dir: str) -> CliResult:
        """
        Validate that workflow directory exists and contains workflows.
        
        Args:
            workflow_dir: Path to workflow directory
            
        Returns:
            CliResult indicating validation success/failure
        """
        workflow_path = Path(workflow_dir)
        
        if not workflow_path.exists():
            return CliResult(
                success=False,
                message=f"Workflow directory not found: {workflow_dir}",
                error_code=1
            )
        
        # Check for workflow files
        workflow_files = list(workflow_path.rglob("*.yaml")) + list(workflow_path.rglob("*.yml"))
        
        if not workflow_files:
            return CliResult(
                success=False,
                message=f"No workflow files found in: {workflow_dir}",
                error_code=1
            )
        
        return CliResult(
            success=True,
            message=f"Found {len(workflow_files)} workflow file(s)",
            data={"workflow_count": len(workflow_files), "workflow_files": [str(f) for f in workflow_files]}
        )


class IssueResultFormatter:
    """Formats issue processing results for CLI display."""
    
    @staticmethod
    def format_single_result(result: Dict[str, Any]) -> str:
        """
        Format a single issue processing result.
        
        Args:
            result: Issue processing result dictionary
            
        Returns:
            Formatted result string
        """
        status = result.get('status', 'unknown')
        issue_number = result.get('issue', 'unknown')
        
        status_icons = {
            'completed': '✅',
            'needs_clarification': '❓',
            'already_processing': '⏳',
            'error': '❌',
            'preview': '🧪',
            'skipped': '⏭️',
            'paused': '⏸️'
        }
        
        icon = status_icons.get(status, '❔')
        
        # Base message
        message = f"{icon} Issue #{issue_number}: {status}"
        
        metadata = result.get('metadata') if isinstance(result, dict) else None

        # Add additional details based on status
        if status == 'completed':
            workflow = result.get('workflow', 'Unknown workflow')
            files_created = result.get('files_created', [])
            message += f"\n  📋 Workflow: {workflow}"
            if files_created:
                message += f"\n  📄 Created {len(files_created)} file(s)"
            copilot_assignee = result.get('copilot_assignee')
            copilot_due = result.get('copilot_due_at')
            if copilot_assignee or copilot_due:
                assignee_display = f"@{copilot_assignee}" if copilot_assignee else "Copilot"
                due_display = f" (due {copilot_due})" if copilot_due else ""
                message += f"\n  🤖 Copilot: {assignee_display}{due_display}"
            handoff_summary = result.get('handoff_summary')
            if handoff_summary:
                headline = handoff_summary.strip().splitlines()[0]
                message += f"\n  📝 Handoff: {headline}"

        elif status == 'preview':
            workflow = result.get('workflow', 'Unknown workflow')
            files_created = result.get('files_created', [])
            message += f"\n  🧪 Dry-run preview for workflow: {workflow}"
            if files_created:
                message += f"\n  📄 Expected file outputs: {len(files_created)}"
            copilot_assignee = result.get('copilot_assignee')
            copilot_due = result.get('copilot_due_at')
            if copilot_assignee or copilot_due:
                assignee_display = f"@{copilot_assignee}" if copilot_assignee else "Copilot"
                due_display = f" (due {copilot_due})" if copilot_due else ""
                message += f"\n  🤖 Copilot (preview): {assignee_display}{due_display}"
            handoff_summary = result.get('handoff_summary')
            if handoff_summary:
                headline = handoff_summary.strip().splitlines()[0]
                message += f"\n  📝 Handoff preview: {headline}"
        
        elif status == 'error':
            error = result.get('error', 'Unknown error')
            message += f"\n  💥 Error: {error}"
        
        elif status == 'needs_clarification':
            message += "\n  💬 Waiting for workflow clarification"
        
        elif status == 'already_processing':
            assignee = result.get('assignee', 'unknown')
            message += f"\n  👤 Assigned to: {assignee}"
        
        multi_lines = IssueResultFormatter._render_multi_workflow_metadata(metadata)
        for line in multi_lines:
            message += f"\n  {line}"

        return message
    
    @staticmethod
    def format_batch_results(results: List[Dict[str, Any]]) -> str:
        """
        Format batch processing results.
        
        Args:
            results: List of issue processing results
            
        Returns:
            Formatted batch results string
        """
        if not results:
            return "📭 No issues processed"
        
        # Count results by status
        status_counts = {}
        for result in results:
            status = result.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Create summary
        total = len(results)
        summary_lines = [f"📊 Processed {total} issue(s):"]
        
        for status, count in sorted(status_counts.items()):
            percentage = (count / total) * 100
            summary_lines.append(f"  {status}: {count} ({percentage:.1f}%)")
        
        # Add individual results if not too many
        if total <= 10:
            summary_lines.append("\n📋 Individual Results:")
            for result in results:
                formatted = IssueResultFormatter.format_single_result(result)
                # Indent individual results
                indented = "\n".join(f"  {line}" for line in formatted.split("\n"))
                summary_lines.append(indented)
        
        return "\n".join(summary_lines)

    @staticmethod
    def _render_multi_workflow_metadata(metadata: Optional[Dict[str, Any]]) -> List[str]:
        """Render multi-workflow metadata, if available, into human-friendly lines."""

        if not metadata or not isinstance(metadata, dict):
            return []

        plan = metadata.get('multi_workflow_plan')
        execution = metadata.get('multi_workflow_execution')
        selection_message = metadata.get('workflow_selection_message')

        lines: List[str] = []

        plan_dict = plan if isinstance(plan, dict) else {}

        plan_count_value = plan_dict.get('workflow_count')
        plan_count = plan_count_value if isinstance(plan_count_value, int) else None

        plan_stages_obj = plan_dict.get('stages')
        plan_stages: List[Dict[str, Any]] = plan_stages_obj if isinstance(plan_stages_obj, list) else []

        planned_workflows: List[str] = []
        for stage in plan_stages:
            stage_workflows = stage.get('workflows') if isinstance(stage, dict) else None
            if not isinstance(stage_workflows, list):
                continue
            for name in stage_workflows:
                if isinstance(name, str) and name not in planned_workflows:
                    planned_workflows.append(name)

        manifest_obj = plan_dict.get('deliverable_manifest')
        manifest: Dict[str, Any] = manifest_obj if isinstance(manifest_obj, dict) else {}

        deliverable_count_value = manifest.get('deliverable_count')
        deliverable_count = deliverable_count_value if isinstance(deliverable_count_value, int) else None

        conflict_groups_obj = manifest.get('conflict_groups')
        conflict_groups: List[Any] = conflict_groups_obj if isinstance(conflict_groups_obj, list) else []
        conflict_count = len(conflict_groups)

        if plan_count and plan_count > 1:
            workflow_summary = ", ".join(planned_workflows) if planned_workflows else str(plan_count)
            lines.append(f"🔀 Multi-workflow plan ({plan_count}): {workflow_summary}")
        elif plan_count == 1 and planned_workflows:
            lines.append(f"🔀 Multi-workflow plan: {planned_workflows[0]}")

        if selection_message and isinstance(selection_message, str):
            trimmed_message = selection_message.strip()
            if trimmed_message:
                lines.append(f"💡 Selection: {trimmed_message}")

        stage_lines_source: List[Dict[str, Any]] = []
        execution_dict = execution if isinstance(execution, dict) else {}
        stage_runs_obj = execution_dict.get('stage_runs')
        stage_runs: List[Dict[str, Any]] = stage_runs_obj if isinstance(stage_runs_obj, list) else []

        if stage_runs:
            stage_lines_source = stage_runs
        elif plan_stages:
            stage_lines_source = plan_stages

        max_stage_lines = 2
        rendered_stage_count = 0
        for stage in stage_lines_source:
            if rendered_stage_count >= max_stage_lines:
                break
            if not isinstance(stage, dict):
                continue
            stage_index = stage.get('index')
            stage_mode = stage.get('run_mode', 'sequential')

            workflow_entries: List[str] = []
            stage_workflows = stage.get('workflows')
            if isinstance(stage_workflows, list):
                for entry in stage_workflows:
                    if isinstance(entry, dict):
                        wf_name = entry.get('workflow_name')
                        wf_status = entry.get('status')
                        if wf_name:
                            if wf_status:
                                workflow_entries.append(f"{wf_name} ({wf_status})")
                            else:
                                workflow_entries.append(wf_name)
                    elif isinstance(entry, str):
                        workflow_entries.append(entry)

            if not workflow_entries:
                continue

            index_display = stage_index if stage_index is not None else rendered_stage_count
            workflows_display = ", ".join(workflow_entries)
            lines.append(f"    - Stage {index_display} [{stage_mode}]: {workflows_display}")
            rendered_stage_count += 1

        extra_stage_count = len(stage_lines_source) - rendered_stage_count
        if extra_stage_count > 0:
            lines.append(f"    - … {extra_stage_count} more stage(s)")

        if deliverable_count:
            descriptor = f"{deliverable_count} deliverable{'s' if deliverable_count != 1 else ''}"
            if conflict_count:
                descriptor += f" ({conflict_count} conflict{'s' if conflict_count != 1 else ''} resolved)"
            lines.append(f"    - Deliverables: {descriptor}")

        execution_status = execution_dict.get('status') if isinstance(execution_dict.get('status'), str) else None
        if execution_status:
            status_display = execution_status.replace('_', ' ')
            lines.append(f"🧪 Multi-workflow execution: {status_display}")

        return lines


class BatchProcessor:
    """Utilities for batch processing operations."""
    
    @staticmethod
    def process_with_progress(
        items: List[Any],
        processor_func: Callable[[Any], Dict[str, Any]],
        operation_name: str = "Processing items",
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Process a list of items with progress reporting.
        
        Args:
            items: List of items to process
            processor_func: Function to process each item
            operation_name: Name of the operation for progress reporting
            verbose: Whether to show detailed progress
            
        Returns:
            List of processing results
        """
        reporter = ProgressReporter(verbose)
        reporter.start_operation(operation_name)
        
        results = []
        total = len(items)
        
        for i, item in enumerate(items, 1):
            if verbose:
                reporter.update_progress(f"Processing item {i}", i, total)
            
            try:
                result = processor_func(item)
                results.append(result)
            except Exception as e:
                # Create error result for failed item
                error_result = {
                    'status': 'error',
                    'error': str(e),
                    'item': str(item)
                }
                results.append(error_result)
        
        # Determine overall success
        error_count = sum(1 for r in results if r.get('status') == 'error')
        success = error_count == 0
        
        completion_message = f"Processed {total} items"
        if error_count > 0:
            completion_message += f" ({error_count} errors)"
        
        reporter.complete_operation(success, completion_message)
        
        return results


@dataclass
class CliExecutionContext:
    """Runtime helpers for standardized CLI command execution."""

    command_name: str
    reporter: ProgressReporter
    dry_run: bool
    dry_run_message: Optional[str] = None

    def decorate_message(self, message: str, *, structured: bool = False) -> str:
        """Prefix CLI output with a dry run banner when appropriate."""

        if structured or not self.dry_run or not self.dry_run_message:
            return message

        if not message:
            return self.dry_run_message

        if self.dry_run_message in message:
            return message

        return f"{self.dry_run_message}\n{message}"

    def decorate_cli_result(self, result: CliResult, *, structured: bool = False) -> CliResult:
        """Return a CliResult with standardized dry run messaging."""

        if structured or not self.dry_run or not self.dry_run_message:
            return result

        message = result.message or ""
        decorated_message = self.decorate_message(message, structured=structured)

        if decorated_message == message:
            return result

        return replace(result, message=decorated_message)


def prepare_cli_execution(
    command_name: str,
    *,
    verbose: bool = False,
    dry_run: bool = False,
) -> CliExecutionContext:
    """Create a CLI execution context with consistent messaging."""

    reporter = ProgressReporter(verbose=verbose)
    dry_run_message: Optional[str] = None

    if dry_run:
        dry_run_message = (
            f"🧪 Dry run enabled for {command_name} — no changes will be made."
        )
        reporter.show_info(dry_run_message)

    return CliExecutionContext(
        command_name=command_name,
        reporter=reporter,
        dry_run=dry_run,
        dry_run_message=dry_run_message,
    )


def safe_execute_cli_command(func: Callable[[], CliResult]) -> int:
    """
    Safely execute a CLI command function with error handling.
    
    Args:
        func: Function that returns a CliResult
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        result = func()
        
        if not result.success:
            print(result.message, file=sys.stderr)
            return result.error_code
        
        print(result.message)
        return 0
    
    except KeyboardInterrupt:
        print("\n⛔ Operation cancelled by user", file=sys.stderr)
        return 130
    
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}", file=sys.stderr)
        return 1


def format_file_list(files: List[str], title: str = "Files") -> str:
    """
    Format a list of files for display.
    
    Args:
        files: List of file paths
        title: Title for the file list
        
    Returns:
        Formatted file list string
    """
    if not files:
        return f"{title}: None"
    
    lines = [f"{title}:"]
    for file_path in files:
        # Convert to relative path if under current directory
        try:
            rel_path = os.path.relpath(file_path)
            if not rel_path.startswith('../'):
                file_path = rel_path
        except ValueError:
            # Keep absolute path if relative conversion fails
            pass
        
        lines.append(f"  📄 {file_path}")
    
    return "\n".join(lines)


def get_user_confirmation(message: str, default: bool = False) -> bool:
    """
    Get user confirmation for an operation.
    
    Args:
        message: Confirmation message to display
        default: Default response if user just presses Enter
        
    Returns:
        True if user confirmed, False otherwise
    """
    default_text = "Y/n" if default else "y/N"
    
    try:
        response = input(f"❓ {message} [{default_text}]: ").strip().lower()
        
        if not response:
            return default
        
        return response in ['y', 'yes', 'true', '1']
    
    except (EOFError, KeyboardInterrupt):
        print("\n⛔ Operation cancelled")
        return False