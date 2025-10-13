"""
Issue processing agent for automated workflow execution.

This module provides the core issue processing logic that matches issues to appropriate
workflows and coordinates deliverable generation. It works independently of GitHub
operations to maintain clean separation of concerns.

The IssueProcessor class serves as the central coordinator for:
- Workflow matching based on issue labels and content
- Issue state management (assignment, processing status)
- Deliverable generation coordination
- Error handling and recovery

The GitHubIntegratedIssueProcessor class extends this with actual GitHub operations
for production use while maintaining testability through the base class.
"""

import os
import logging
import time
import functools
import re
from typing import Dict, List, Optional, Tuple, Any, Union, Iterable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json

from ..workflow.workflow_matcher import WorkflowMatcher, WorkflowLoadError, WorkflowInfo, WorkflowPlan
from ..workflow.execution_planner import (
    WorkflowExecutionPlan,
    WorkflowExecutionPlanner,
    WorkflowPlanningError,
    build_plan_created_event,
)
from ..workflow.deliverable_namer import MultiWorkflowDeliverableNamer
from ..workflow.workflow_state_manager import (
    WORKFLOW_LABEL_PREFIX,
    SPECIALIST_LABEL_PREFIX,
    WorkflowState,
    plan_state_transition,
)
from ..workflow.issue_handoff_builder import (
    IssueHandoffBuilder,
    IssueHandoffPayload,
    DEFAULT_COPILOT_ASSIGNEE,
)
from ..utils.markdown_sections import upsert_section
from ..utils.config_manager import ConfigManager, MultiWorkflowProcessingConfig
from ..clients.github_issue_creator import GitHubIssueCreator
from ..workflow.deliverable_generator import DeliverableGenerator, DeliverableSpec
from ..storage.git_manager import GitManager, GitOperationError
from ..utils.logging_config import get_logger, log_exception, log_retry_attempt
from ..utils.telemetry import TelemetryPublisher, normalize_publishers, publish_telemetry_event


class IssueProcessingError(Exception):
    """Base exception for issue processing errors."""
    
    def __init__(self, message: str, issue_number: Optional[int] = None, error_code: Optional[str] = None):
        """
        Initialize issue processing error.
        
        Args:
            message: Error message
            issue_number: Issue number if applicable
            error_code: Error code for categorization
        """
        super().__init__(message)
        self.issue_number = issue_number
        self.error_code = error_code


class WorkflowExecutionError(IssueProcessingError):
    """Exception raised during workflow execution."""
    pass


class DeliverableGenerationError(IssueProcessingError):
    """Exception raised during deliverable generation."""
    pass


class ProcessingTimeoutError(IssueProcessingError):
    """Exception raised when processing times out."""
    pass


@dataclass(frozen=True)
class _PlanExecutionContext:
    """Internal container linking planning artefacts for multi-workflow runs."""

    plan: WorkflowPlan
    execution_plan: WorkflowExecutionPlan
    deliverable_manifest: Optional[Dict[str, Any]] = None


def retry_on_exception(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple = (Exception,)
):
    """
    Decorator for retrying operations with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry on
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(__name__)
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        log_exception(logger, f"Final attempt failed for {func.__name__}", e)
                        raise
                    
                    delay = delay_seconds * (backoff_multiplier ** (attempt - 1))
                    log_retry_attempt(logger, func.__name__, attempt, max_attempts, e)
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"Unexpected error in retry decorator for {func.__name__}")
        
        return wrapper
    return decorator


class IssueProcessingStatus(Enum):
    """Status values for issue processing operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    PREVIEW = "preview"
    NEEDS_CLARIFICATION = "needs_clarification"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class IssueData:
    """Standardized issue data structure for processing."""
    number: int
    title: str
    body: str
    labels: List[str]
    assignees: List[str]
    created_at: datetime
    updated_at: datetime
    url: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IssueData':
        """Create IssueData from dictionary representation."""
        return cls(
            number=data['number'],
            title=data['title'],
            body=data.get('body', ''),
            labels=data.get('labels', []),
            assignees=data.get('assignees', []),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now(timezone.utc).isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now(timezone.utc).isoformat())),
            url=data.get('url', '')
        )


@dataclass
class ProcessingResult:
    """Result of issue processing operation."""
    issue_number: int
    status: IssueProcessingStatus
    workflow_name: Optional[str] = None
    created_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    clarification_needed: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    output_directory: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    copilot_assignee: Optional[str] = None
    copilot_due_at: Optional[str] = None
    handoff_summary: Optional[str] = None
    specialist_guidance: Optional[str] = None
    copilot_assignment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.created_files is None:
            self.created_files = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert processing result to a JSON-serializable dictionary."""
        return {
            'issue_number': self.issue_number,
            'status': self.status.value,
            'workflow_name': self.workflow_name,
            'created_files': list(self.created_files or []),
            'error_message': self.error_message,
            'clarification_needed': self.clarification_needed,
            'processing_time_seconds': self.processing_time_seconds,
            'output_directory': self.output_directory,
            'git_branch': self.git_branch,
            'git_commit': self.git_commit,
            'copilot_assignee': self.copilot_assignee,
            'copilot_due_at': self.copilot_due_at,
            'handoff_summary': self.handoff_summary,
            'specialist_guidance': self.specialist_guidance,
            'copilot_assignment': self.copilot_assignment,
            'metadata': dict(self.metadata or {}),
        }


class IssueProcessor:
    """
    Core issue processing engine that coordinates workflow matching and execution.
    
    This class handles the business logic of processing issues without direct GitHub
    integration, making it testable and reusable across different contexts.
    
    Key responsibilities:
    - Match issues to appropriate workflows using WorkflowMatcher
    - Manage processing state and status tracking
    - Coordinate deliverable generation
    - Handle error conditions and recovery
    - Provide detailed processing results
    """
    
    def __init__(self, 
                 config_path: str = "config.yaml",
                 workflow_dir: Optional[str] = None,
                 output_base_dir: Optional[str] = None,
                 enable_git: bool = True,
                 enable_state_saving: bool = True,
                 telemetry_publishers: Optional[Iterable[TelemetryPublisher]] = None):
        """
        Initialize the issue processor.
        
        Args:
            config_path: Path to configuration file
            workflow_dir: Override for workflow directory path
            output_base_dir: Override for output base directory
            enable_git: Whether to enable git operations for deliverables
            enable_state_saving: Whether to enable processing state persistence
            
        Raises:
            IssueProcessingError: If initialization fails
        """
        self.logger = get_logger(__name__)
        self.logger.info("Initializing IssueProcessor")
        self.telemetry_publishers = normalize_publishers(telemetry_publishers)
        
        # Load configuration with error handling
        try:
            self.config = ConfigManager.load_config_with_env_substitution(config_path)
            self.logger.info(f"Configuration loaded from {config_path}")
        except FileNotFoundError as e:
            error_msg = f"Configuration file not found: {config_path}"
            self.logger.error(error_msg)
            raise IssueProcessingError(error_msg, error_code="CONFIG_NOT_FOUND") from e
        except ValueError as e:
            error_msg = f"Invalid configuration: {e}"
            self.logger.error(error_msg)
            raise IssueProcessingError(error_msg, error_code="CONFIG_INVALID") from e
        except Exception as e:
            error_msg = f"Unexpected error loading configuration: {e}"
            log_exception(self.logger, "Failed to load configuration", e)
            raise IssueProcessingError(error_msg, error_code="CONFIG_ERROR") from e

        # Initialize workflow matcher with error handling
        workflow_path = workflow_dir or (self.config.agent.workflow_directory if self.config.agent else 'docs/workflow/deliverables')
        try:
            self.workflow_directory = workflow_path
            self.workflow_matcher = WorkflowMatcher(workflow_path)
            self.logger.info(f"Workflow matcher initialized with directory: {workflow_path}")
        except WorkflowLoadError as e:
            # Pass through the specific error code from WorkflowLoadError
            error_msg = f"Workflow matcher initialization failed: {e}"
            self.logger.error(error_msg)
            raise IssueProcessingError(error_msg, error_code=e.error_code) from e
        except Exception as e:
            error_msg = f"Failed to initialize workflow matcher: {e}"
            log_exception(self.logger, "Workflow matcher initialization failed", e)
            raise IssueProcessingError(error_msg, error_code="WORKFLOW_MATCHER_ERROR") from e

        # Set output directory with error handling
        try:
            self.output_base_dir = Path(output_base_dir or (self.config.agent.output_directory if self.config.agent else 'study'))
            self.output_base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory set to: {self.output_base_dir}")
        except OSError as e:
            error_msg = f"Failed to create output directory: {self.output_base_dir}"
            log_exception(self.logger, error_msg, e)
            raise IssueProcessingError(error_msg, error_code="OUTPUT_DIR_ERROR") from e

        # Initialize deliverable generator with error handling
        try:
            template_dir = self.config.agent.template_directory if self.config.agent else None
            self.deliverable_generator = DeliverableGenerator(
                templates_dir=template_dir,
                output_dir=self.output_base_dir
            )
            self.logger.info(f"Deliverable generator initialized with templates: {template_dir}")
        except Exception as e:
            error_msg = f"Failed to initialize deliverable generator: {e}"
            log_exception(self.logger, error_msg, e)
            raise IssueProcessingError(error_msg, error_code="DELIVERABLE_GENERATOR_ERROR") from e

        # Multi-workflow planner configuration
        self.multi_workflow_planning_enabled = False
        self.multi_workflow_preview_only = False
        self.workflow_execution_planner: Optional[WorkflowExecutionPlanner] = None
        self._multi_workflow_plan_config = None

        processing_config = self.config.agent.processing if self.config.agent else None
        if processing_config:
            try:
                self._multi_workflow_plan_config = getattr(processing_config, 'multi_workflow', None)
                if self._multi_workflow_plan_config:
                    self.multi_workflow_preview_only = getattr(self._multi_workflow_plan_config, 'preview_only', False)

                self.multi_workflow_planning_enabled = bool(getattr(processing_config, 'enable_multi_workflow', False))
                if self.multi_workflow_planning_enabled:
                    self._initialize_multi_workflow_planner()
                    plan_cfg = self._multi_workflow_plan_config or MultiWorkflowProcessingConfig()
                    self.logger.info(
                        "Multi-workflow planner enabled (preview_only=%s, allow_parallel=%s, max_parallel=%s)",
                        self.multi_workflow_preview_only,
                        plan_cfg.allow_parallel_stages,
                        plan_cfg.max_parallel_workflows,
                    )
                else:
                    self.logger.info("Multi-workflow planner disabled in agent processing configuration")
            except Exception as exc:
                self.logger.warning("Failed to initialize multi-workflow planner: %s", exc)
                self.multi_workflow_planning_enabled = False
                self.workflow_execution_planner = None
        else:
            self.logger.info("No agent processing configuration; multi-workflow planner disabled")

        # Initialize content extraction agent if AI is configured
        self.content_extraction_agent: Optional['ContentExtractionAgent'] = None
        self.enable_ai_extraction = False
        try:
            if (
                self.config.ai
                and getattr(self.config.ai, 'enabled', False)
                and getattr(self.config.ai, 'content_extraction_enabled', False)
            ):
                from ..agents.content_extraction_agent import ContentExtractionAgent
                # We'll need github_token for AI client, this will be passed by subclass
                self.enable_ai_extraction = True
                self.logger.info("AI content extraction enabled (agent will be initialized with GitHub token)")
            else:
                self.logger.info(
                    "AI content extraction disabled in configuration (enabled=%s, content_extraction_enabled=%s)",
                    getattr(self.config.ai, 'enabled', False),
                    getattr(self.config.ai, 'content_extraction_enabled', False),
                )
        except Exception as e:
            self.logger.warning(f"Failed to initialize AI content extraction: {e}")
            self.enable_ai_extraction = False

        # Initialize git manager if enabled
        self.enable_git = enable_git
        self.enable_state_saving = enable_state_saving
        self.git_manager: Optional[GitManager] = None
        if self.enable_git:
            try:
                git_config = self.config.agent.git if self.config.agent else None
                branch_prefix = git_config.branch_prefix if git_config else "issue"
                
                self.git_manager = GitManager(
                    base_branch="main",  # Use default base branch
                    branch_prefix=branch_prefix,
                    auto_cleanup=True  # Use default auto_cleanup
                )
                self.logger.info("Git operations enabled")
            except GitOperationError as e:
                self.logger.warning(f"Git operations disabled due to error: {e}")
                self.enable_git = False
                self.git_manager = None
            except Exception as e:
                self.logger.warning(f"Unexpected error initializing git manager: {e}")
                self.enable_git = False
                self.git_manager = None

        # Agent configuration with defaults
        try:
            self.agent_username = self.config.agent.username if self.config.agent else 'github-actions[bot]'
            self.processing_timeout = (self.config.agent.processing.default_timeout_minutes * 60 
                                     if self.config.agent and self.config.agent.processing 
                                     else 300)
            self.max_retries = 3  # Default retry count
            self.logger.info(f"Agent configuration: username={self.agent_username}, timeout={self.processing_timeout}s")
        except Exception as e:
            self.logger.warning(f"Error reading agent configuration, using defaults: {e}")
            self.agent_username = 'github-actions[bot]'
            self.processing_timeout = 300
            self.max_retries = 3

        # State tracking
        self._processing_state: Dict[str, Dict[str, Any]] = {}
        self._load_processing_state()
        
        self.logger.info("IssueProcessor initialization completed successfully")
    
    def _load_processing_state(self) -> None:
        """Load processing state from persistent storage with error handling."""
        if not self.enable_state_saving:
            self._processing_state = {}
            return
            
        state_file = self.output_base_dir / '.processing_state.json'
        try:
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    self._processing_state = json.load(f)
                self.logger.info(f"Loaded processing state for {len(self._processing_state)} issues")
                
                # Validate loaded state structure
                self._validate_processing_state()
            else:
                self.logger.info("No existing processing state file found, starting fresh")
                self._processing_state = {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Corrupted processing state file, starting fresh: {e}")
            self._processing_state = {}
            # Backup the corrupted file
            try:
                backup_file = state_file.with_suffix(f'.backup.{int(datetime.now().timestamp())}')
                state_file.rename(backup_file)
                self.logger.info(f"Corrupted state file backed up to: {backup_file}")
            except Exception as backup_error:
                self.logger.warning(f"Failed to backup corrupted state file: {backup_error}")
        except Exception as e:
            log_exception(self.logger, "Failed to load processing state", e)
            self._processing_state = {}

    def _validate_processing_state(self) -> None:
        """Validate the structure of loaded processing state."""
        if not isinstance(self._processing_state, dict):
            self.logger.warning("Invalid processing state format, resetting")
            self._processing_state = {}
            return
        
        # Clean up invalid entries
        valid_statuses = {status.value for status in IssueProcessingStatus}
        cleaned_count = 0
        
        for issue_id, state in list(self._processing_state.items()):
            if not isinstance(state, dict):
                del self._processing_state[issue_id]
                cleaned_count += 1
                continue
            
            # Validate status
            if 'status' in state and state['status'] not in valid_statuses:
                self.logger.warning(f"Invalid status '{state['status']}' for issue {issue_id}, resetting to PENDING")
                state['status'] = IssueProcessingStatus.PENDING.value
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} invalid state entries")

    @retry_on_exception(max_attempts=3, delay_seconds=0.5, exceptions=(OSError, IOError))
    def _save_processing_state(self) -> None:
        """Save processing state to persistent storage with retry logic."""
        if not self.enable_state_saving:
            return
            
        state_file = self.output_base_dir / '.processing_state.json'
        temp_file = state_file.with_suffix('.tmp')
        
        try:
            # Ensure output directory exists
            self.output_base_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a temporary file first for atomic writes
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._processing_state, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(state_file)
            self.logger.debug(f"Processing state saved for {len(self._processing_state)} issues")
            
        except Exception as e:
            log_exception(self.logger, "Failed to save processing state", e)
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass  # Ignore cleanup errors
            raise
    
    def process_issue(self, issue_data: IssueData) -> ProcessingResult:
        """
        Process a single issue through the complete workflow.
        
        This is the main entry point for issue processing. It coordinates all
        aspects of processing from workflow matching to deliverable generation.
        
        Args:
            issue_data: Standardized issue data structure
            
        Returns:
            ProcessingResult with status and details of processing
            
        Raises:
            ProcessingTimeoutError: If processing exceeds timeout
            IssueProcessingError: For other processing failures
        """
        start_time = datetime.now()
        issue_number = issue_data.number
        
        self.logger.info(f"Starting processing for issue #{issue_number}: {issue_data.title}")
        result_metadata: Dict[str, Any] = {}
        
        try:
            # Validate issue data
            self._validate_issue_data(issue_data)
            
            # Check processing timeout
            self._check_processing_timeout(issue_number, start_time)
            
            # Check if already processing
            current_status = self._get_issue_status(issue_number)
            if current_status == IssueProcessingStatus.PROCESSING:
                self.logger.info(f"Issue #{issue_number} already being processed")
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.PROCESSING,
                    metadata=result_metadata,
                )
            
            # Update status to processing
            self._update_issue_status(issue_number, IssueProcessingStatus.PROCESSING, {
                'started_at': start_time.isoformat(),
                'title': issue_data.title,
                'labels': issue_data.labels
            })
            
            # Validate site-monitor label
            if 'site-monitor' not in issue_data.labels:
                self.logger.info(f"Issue #{issue_number} does not have site-monitor label, skipping")
                self._update_issue_status(issue_number, IssueProcessingStatus.PENDING)
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.PENDING,
                    error_message="Issue does not have required 'site-monitor' label",
                    metadata=result_metadata,
                )

            # Perform AI content extraction if enabled
            extracted_content = None
            if self.enable_ai_extraction and self.content_extraction_agent:
                try:
                    extracted_content = self._extract_issue_content(issue_data)
                    self.logger.info(f"Content extraction completed for issue #{issue_number}")
                except Exception as e:
                    self.logger.warning(f"Content extraction failed for issue #{issue_number}: {e}")
                    # Continue without extracted content - maintain backward compatibility
                    extracted_content = None

            # Find matching workflow with retry logic
            try:
                workflow_result = self._find_workflow_with_retry(issue_data)
            except Exception as e:
                error_msg = f"Failed to find matching workflow: {e}"
                log_exception(self.logger, error_msg, e)
                self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                    'error_message': error_msg,
                    'error_time': datetime.now().isoformat(),
                    'error_type': 'workflow_matching'
                })
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.ERROR,
                    error_message=error_msg,
                    metadata=result_metadata,
                )
            
            workflow_info, status_message = workflow_result

            if status_message:
                result_metadata['workflow_selection_message'] = status_message

            plan_summary, plan_context = self._prepare_multi_workflow_plan(issue_data)
            if plan_summary:
                result_metadata['multi_workflow_plan'] = plan_summary

            selection_state_update: Dict[str, Any] = {}
            if status_message:
                selection_state_update['workflow_selection_message'] = status_message
            if plan_summary:
                selection_state_update.update(
                    {
                        'multi_workflow_plan': plan_summary,
                        'plan_generated_at': datetime.now().isoformat(),
                    }
                )
            if selection_state_update:
                self._update_issue_status(
                    issue_number,
                    IssueProcessingStatus.PROCESSING,
                    selection_state_update,
                )
            
            execution_plan_obj = plan_context.execution_plan if plan_context else None
            multi_plan_available = bool(execution_plan_obj and execution_plan_obj.workflow_count())
            preview_only_mode = getattr(self, 'multi_workflow_preview_only', False)
            multi_runtime_enabled = bool(
                execution_plan_obj
                and execution_plan_obj.workflow_count() > 1
                and not preview_only_mode
            )

            if multi_runtime_enabled:
                try:
                    execution_result = self._execute_multi_workflow_plan(
                        issue_data,
                        plan_context,
                        extracted_content=extracted_content,
                    )
                except WorkflowExecutionError as e:
                    error_msg = f"Multi-workflow execution failed: {e}"
                    self.logger.error(error_msg)
                    self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                        'error_message': error_msg,
                        'error_time': datetime.now().isoformat(),
                        'error_type': 'multi_workflow_execution',
                    })
                    return ProcessingResult(
                        issue_number=issue_number,
                        status=IssueProcessingStatus.ERROR,
                        error_message=error_msg,
                        metadata=result_metadata,
                    )
                except Exception as e:  # pragma: no cover - defensive guard
                    error_msg = f"Unexpected error during multi-workflow execution: {e}"
                    log_exception(self.logger, error_msg, e)
                    self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                        'error_message': error_msg,
                        'error_time': datetime.now().isoformat(),
                        'error_type': 'multi_workflow_execution',
                    })
                    return ProcessingResult(
                        issue_number=issue_number,
                        status=IssueProcessingStatus.ERROR,
                        error_message=error_msg,
                        metadata=result_metadata,
                    )

                if execution_result.get('multi_workflow_execution'):
                    result_metadata['multi_workflow_execution'] = execution_result['multi_workflow_execution']
                if execution_result.get('workflow_results'):
                    result_metadata['multi_workflow_results'] = execution_result['workflow_results']
                if execution_result.get('errors'):
                    result_metadata['multi_workflow_errors'] = execution_result['errors']
                if execution_result.get('partial_success'):
                    result_metadata['multi_workflow_partial_success'] = True

                processing_time = (datetime.now() - start_time).total_seconds()
                workflow_display_name = execution_result.get('workflow_name') or 'multi_workflow'
                created_files = list(execution_result.get('created_files') or [])
                git_branch = execution_result.get('git_branch')
                git_commit = execution_result.get('git_commit')
                output_directory = execution_result.get('output_directory')

                completed_state = {
                    'completed_at': datetime.now().isoformat(),
                    'workflow_name': workflow_display_name,
                    'created_files': created_files,
                    'processing_time_seconds': processing_time,
                    'multi_workflow_execution': execution_result.get('multi_workflow_execution'),
                    'multi_workflow_results': execution_result.get('workflow_results'),
                }
                if execution_result.get('errors'):
                    completed_state['multi_workflow_errors'] = execution_result['errors']
                    completed_state['partial_success'] = True
                if output_directory:
                    completed_state['output_directory'] = output_directory

                if execution_result.get('errors') and not created_files:
                    error_msg = "Multi-workflow execution failed for all workflows; no deliverables were produced."
                    self.logger.error(error_msg)
                    failure_state = dict(completed_state)
                    failure_state['error_message'] = error_msg
                    self._update_issue_status(
                        issue_number,
                        IssueProcessingStatus.ERROR,
                        failure_state,
                    )
                    return ProcessingResult(
                        issue_number=issue_number,
                        status=IssueProcessingStatus.ERROR,
                        error_message=error_msg,
                        metadata=result_metadata,
                    )

                self._update_issue_status(
                    issue_number,
                    IssueProcessingStatus.COMPLETED,
                    completed_state,
                )

                self.logger.info(
                    "Successfully processed multi-workflow issue #%s in %.2fs",
                    issue_number,
                    processing_time,
                )

                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.COMPLETED,
                    workflow_name=workflow_display_name,
                    created_files=created_files,
                    processing_time_seconds=processing_time,
                    output_directory=output_directory,
                    git_branch=git_branch,
                    git_commit=git_commit,
                    metadata=result_metadata,
                )

            if plan_context and preview_only_mode:
                preview_result = self._execute_multi_workflow_plan(
                    issue_data,
                    plan_context,
                    extracted_content=extracted_content,
                )
                if preview_result.get('multi_workflow_execution'):
                    result_metadata['multi_workflow_execution'] = preview_result['multi_workflow_execution']

            if workflow_info is None:
                # Need clarification
                clarification_msg = self._generate_clarification_message(issue_data)
                self._update_issue_status(issue_number, IssueProcessingStatus.NEEDS_CLARIFICATION, {
                    'clarification_message': clarification_msg
                })
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.NEEDS_CLARIFICATION,
                    clarification_needed=clarification_msg,
                    metadata=result_metadata,
                )
            
            # Execute workflow with comprehensive error handling
            try:
                execution_result = self._execute_workflow_with_recovery(
                    issue_data,
                    workflow_info,
                    extracted_content,
                    plan_context=plan_context,
                )
            except WorkflowExecutionError as e:
                error_msg = f"Workflow execution failed: {e}"
                self.logger.error(error_msg)
                self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                    'error_message': error_msg,
                    'error_time': datetime.now().isoformat(),
                    'error_type': 'workflow_execution',
                    'workflow_name': workflow_info.name
                })
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.ERROR,
                    error_message=error_msg,
                    workflow_name=workflow_info.name,
                    metadata=result_metadata,
                )
            except Exception as e:
                error_msg = f"Unexpected error during workflow execution: {e}"
                log_exception(self.logger, error_msg, e)
                self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                    'error_message': error_msg,
                    'error_time': datetime.now().isoformat(),
                    'error_type': 'unexpected_error',
                    'workflow_name': workflow_info.name
                })
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.ERROR,
                    error_message=error_msg,
                    workflow_name=workflow_info.name,
                    metadata=result_metadata,
                )
            
            if execution_result.get('multi_workflow_execution'):
                result_metadata['multi_workflow_execution'] = execution_result['multi_workflow_execution']

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Update status to completed
            completed_state = {
                'completed_at': datetime.now().isoformat(),
                'workflow_name': workflow_info.name,
                'created_files': execution_result['created_files'],
                'processing_time_seconds': processing_time
            }
            if execution_result.get('multi_workflow_execution'):
                completed_state['multi_workflow_execution'] = execution_result['multi_workflow_execution']

            self._update_issue_status(
                issue_number,
                IssueProcessingStatus.COMPLETED,
                completed_state,
            )
            
            self.logger.info(f"Successfully processed issue #{issue_number} in {processing_time:.2f}s")
            
            return ProcessingResult(
                issue_number=issue_number,
                status=IssueProcessingStatus.COMPLETED,
                workflow_name=workflow_info.name,
                created_files=execution_result['created_files'],
                processing_time_seconds=processing_time,
                output_directory=execution_result.get('output_directory'),
                git_branch=execution_result.get('git_branch'),
                git_commit=execution_result.get('git_commit'),
                metadata=result_metadata,
            )
            
        except ProcessingTimeoutError as e:
            error_msg = f"Processing timeout: {e}"
            self.logger.error(error_msg)
            self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                'error_message': error_msg,
                'error_time': datetime.now().isoformat(),
                'error_type': 'timeout'
            })
            return ProcessingResult(
                issue_number=issue_number,
                status=IssueProcessingStatus.ERROR,
                error_message=error_msg,
                metadata=result_metadata,
            )
        except IssueProcessingError as e:
            error_msg = f"Issue processing error: {e}"
            self.logger.error(error_msg)
            self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                'error_message': error_msg,
                'error_time': datetime.now().isoformat(),
                'error_type': getattr(e, 'error_code', 'processing_error')
            })
            return ProcessingResult(
                issue_number=issue_number,
                status=IssueProcessingStatus.ERROR,
                error_message=error_msg,
                metadata=result_metadata,
            )
        except Exception as e:
            error_msg = f"Unexpected error processing issue #{issue_number}: {e}"
            log_exception(self.logger, error_msg, e)
            self._update_issue_status(issue_number, IssueProcessingStatus.ERROR, {
                'error_message': str(e),
                'error_time': datetime.now().isoformat(),
                'error_type': 'unexpected_error'
            })
            
            return ProcessingResult(
                issue_number=issue_number,
                status=IssueProcessingStatus.ERROR,
                error_message=str(e),
                metadata=result_metadata,
            )
        finally:
            # Always save state changes
            try:
                self._save_processing_state()
            except Exception as e:
                self.logger.warning(f"Failed to save processing state after issue #{issue_number}: {e}")

    def generate_preview_result(self, issue_data: IssueData) -> ProcessingResult:
        """Return a simulated processing result for preview/dry-run scenarios."""

        return ProcessingResult(
            issue_number=issue_data.number,
            status=IssueProcessingStatus.PENDING,
            error_message="Preview generation is not available for this processor.",
        )

    def _validate_issue_data(self, issue_data: IssueData) -> None:
        """
        Validate issue data before processing.
        
        Args:
            issue_data: Issue data to validate
            
        Raises:
            IssueProcessingError: If validation fails
        """
        if not isinstance(issue_data.number, int) or issue_data.number <= 0:
            raise IssueProcessingError(
                f"Invalid issue number: {issue_data.number}",
                issue_number=issue_data.number,
                error_code="INVALID_ISSUE_NUMBER"
            )
        
        if not issue_data.title or not issue_data.title.strip():
            raise IssueProcessingError(
                f"Issue #{issue_data.number} has empty title",
                issue_number=issue_data.number,
                error_code="EMPTY_TITLE"
            )
        
        if not isinstance(issue_data.labels, list):
            raise IssueProcessingError(
                f"Issue #{issue_data.number} has invalid labels format",
                issue_number=issue_data.number,
                error_code="INVALID_LABELS"
            )

    def _check_processing_timeout(self, issue_number: int, start_time: datetime) -> None:
        """
        Check if processing should timeout.
        
        Args:
            issue_number: Issue number being processed
            start_time: When processing started
            
        Raises:
            ProcessingTimeoutError: If timeout exceeded
        """
        # Check for existing processing that has exceeded timeout
        state = self._processing_state.get(str(issue_number), {})
        if state.get('status') == IssueProcessingStatus.PROCESSING.value:
            try:
                started_at_str = state.get('started_at')
                if started_at_str:
                    started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                    elapsed = (datetime.now() - started_at).total_seconds()
                    if elapsed > self.processing_timeout:
                        raise ProcessingTimeoutError(
                            f"Issue #{issue_number} processing exceeded timeout ({self.processing_timeout}s)",
                            issue_number=issue_number,
                            error_code="PROCESSING_TIMEOUT"
                        )
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Invalid started_at timestamp for issue #{issue_number}: {e}")

    @retry_on_exception(max_attempts=3, delay_seconds=1.0, exceptions=(Exception,))
    def _find_workflow_with_retry(self, issue_data: IssueData) -> Tuple:
        """
        Find matching workflow with retry logic.
        
        Args:
            issue_data: Issue data for workflow matching
            
        Returns:
            Tuple of workflow info and status message
        """
        if getattr(self, 'multi_workflow_planning_enabled', False):
            try:
                plan = self.workflow_matcher.get_workflow_plan(issue_data.labels)
            except Exception as exc:
                self.logger.warning(
                    "Failed to build workflow plan for issue #%s: %s",
                    issue_data.number,
                    exc,
                )
            else:
                if self._is_valid_workflow_plan(plan):
                    primary = plan.primary_workflow()
                    if primary and primary.workflow_info:
                        return primary.workflow_info, plan.selection_message

        return self.workflow_matcher.get_best_workflow_match(issue_data.labels)

    @staticmethod
    def _is_valid_workflow_plan(plan: Any) -> bool:
        """Return True when a workflow plan contains concrete candidates."""

        if not isinstance(plan, WorkflowPlan):
            return False

        candidates = getattr(plan, 'candidates', ())
        if isinstance(candidates, tuple):
            return len(candidates) > 0
        if isinstance(candidates, list):
            return len(candidates) > 0
        return False

    def _prepare_multi_workflow_plan(
        self,
        issue_data: IssueData,
        workflow_plan: Optional[WorkflowPlan] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[_PlanExecutionContext]]:
        """Return plan summary and execution context when planning is enabled."""

        if not getattr(self, 'multi_workflow_planning_enabled', False):
            return None, None

        planner = getattr(self, 'workflow_execution_planner', None)
        if not planner:
            return None, None

        plan = workflow_plan
        if plan is None:
            try:
                plan = self.workflow_matcher.get_workflow_plan(issue_data.labels)
            except Exception as exc:
                self.logger.warning(
                    "Failed to generate workflow plan for issue #%s: %s",
                    issue_data.number,
                    exc,
                )
                return None, None

        if not self._is_valid_workflow_plan(plan):
            return None, None

        try:
            execution_plan = planner.build_execution_plan(plan)
        except WorkflowPlanningError as exc:
            candidate_names = [candidate.name for candidate in plan.candidates]
            self.logger.warning(
                "Execution planning failed for issue #%s (candidates=%s): %s",
                issue_data.number,
                candidate_names,
                exc,
            )
            summary = {
                'error': str(exc),
                'selection_reason': plan.selection_reason,
                'selection_message': plan.selection_message,
                'candidate_names': candidate_names,
                'preview_only': getattr(self, 'multi_workflow_preview_only', False),
            }
            return summary, None

        deliverable_manifest: Optional[Dict[str, Any]] = None
        try:
            plan_config = getattr(self, '_multi_workflow_plan_config', None)
            manifest_strategy = getattr(plan_config, 'conflict_resolution', 'suffix') if plan_config else 'suffix'
            manifest_separator = getattr(plan_config, 'suffix_separator', '--') if plan_config else '--'
            namer = MultiWorkflowDeliverableNamer(
                strategy=manifest_strategy,
                separator=manifest_separator,
            )
            deliverable_manifest = namer.build_manifest(
                issue_number=issue_data.number,
                issue_title=issue_data.title,
                plan=plan,
            )
        except Exception as naming_error:  # pragma: no cover - defensive guard
            self.logger.warning(
                "Failed to compute deliverable manifest for issue #%s: %s",
                issue_data.number,
                naming_error,
            )

        plan_context = _PlanExecutionContext(
            plan=plan,
            execution_plan=execution_plan,
            deliverable_manifest=deliverable_manifest,
        )

        preview_only = getattr(self, 'multi_workflow_preview_only', False)

        summary = execution_plan.to_summary()
        summary.update(
            {
                'preview_only': preview_only,
                'selection_reason': plan.selection_reason,
                'selection_message': plan.selection_message,
                'allow_partial_success': execution_plan.allow_partial_success,
                'overall_timeout_seconds': execution_plan.overall_timeout_seconds,
            }
        )
        if deliverable_manifest:
            summary['deliverable_manifest'] = deliverable_manifest

        self.logger.info(
            "Generated multi-workflow execution plan for issue #%s: %s",
            issue_data.number,
            summary,
        )

        self._emit_plan_created_event(issue_data, plan_context)

        return summary, plan_context

    def _maybe_build_execution_plan_summary(
        self,
        issue_data: IssueData,
        workflow_plan: Optional[WorkflowPlan] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return execution plan summary when multi-workflow planning is enabled."""
        summary, _ = self._prepare_multi_workflow_plan(issue_data, workflow_plan)
        return summary

    def _publish_telemetry_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Safely emit telemetry events when publishers are configured."""

        if not self.telemetry_publishers:
            return

        publish_telemetry_event(
            self.telemetry_publishers,
            event_type,
            payload,
            logger=self.logger,
        )

    def _emit_plan_created_event(
        self,
        issue_data: IssueData,
        plan_context: _PlanExecutionContext,
    ) -> None:
        """Emit telemetry for newly created multi-workflow plans."""

        if not self.telemetry_publishers:
            return

        try:
            event_payload = build_plan_created_event(
                plan_context.execution_plan,
                issue_number=issue_data.number,
            )
            event_type = str(event_payload.pop("event_type", "multi_workflow.plan_created"))
            event_payload.update(
                {
                    "preview_only": getattr(self, 'multi_workflow_preview_only', False),
                    "selection_reason": plan_context.plan.selection_reason,
                    "selection_message": plan_context.plan.selection_message,
                }
            )
            self._publish_telemetry_event(event_type, event_payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning(
                "Failed to emit multi-workflow plan telemetry for issue #%s: %s",
                issue_data.number,
                exc,
            )

    def _emit_execution_summary_event(
        self,
        issue_data: IssueData,
        overview: Dict[str, Any],
    ) -> None:
        """Emit telemetry summarizing multi-workflow execution."""

        if not self.telemetry_publishers:
            return

        try:
            payload = dict(overview)
            payload.setdefault("issue_number", issue_data.number)
            self._publish_telemetry_event("multi_workflow.execution_summary", payload)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning(
                "Failed to emit multi-workflow execution telemetry for issue #%s: %s",
                issue_data.number,
                exc,
            )

    def _build_deliverable_overrides(
        self,
        plan_context: _PlanExecutionContext,
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Return per-workflow deliverable overrides derived from the manifest."""

        manifest = getattr(plan_context, "deliverable_manifest", None) or {}
        workflows = manifest.get("workflows", []) if isinstance(manifest, dict) else []

        overrides: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for workflow_entry in workflows:
            workflow_name = workflow_entry.get("workflow_name")
            if not workflow_name:
                continue

            deliverable_map: Dict[str, Dict[str, Any]] = {}
            for deliverable in workflow_entry.get("deliverables", []):
                slug = deliverable.get("deliverable_slug") or self._slugify(deliverable.get("deliverable_name", ""))
                deliverable_map[slug] = deliverable

            overrides[workflow_name] = deliverable_map

        return overrides

    def _execute_multi_workflow_plan(
        self,
        issue_data: IssueData,
        plan_context: Optional[_PlanExecutionContext],
        *,
        extracted_content=None,
    ) -> Dict[str, Any]:
        """Execute all workflows in the provided plan and return aggregated results."""

        if not plan_context:
            return {
                'workflow_name': None,
                'workflow_names': [],
                'created_files': [],
                'multi_workflow_execution': None,
                'workflow_results': [],
                'errors': [],
                'partial_success': False,
                'git_branch': None,
                'git_commit': None,
            }

        execution_plan = plan_context.execution_plan
        overview = execution_plan.to_summary()
        preview_only = getattr(self, 'multi_workflow_preview_only', False)
        overview.update(
            {
                'preview_only': preview_only,
                'selection_reason': plan_context.plan.selection_reason,
                'selection_message': plan_context.plan.selection_message,
                'allow_partial_success': execution_plan.allow_partial_success,
                'overall_timeout_seconds': execution_plan.overall_timeout_seconds,
            }
        )

        if plan_context.deliverable_manifest:
            overview['deliverable_manifest'] = plan_context.deliverable_manifest

        ordered_workflow_names: List[str] = []
        for candidate in plan_context.plan.candidates:
            name = candidate.workflow_info.name
            if name not in ordered_workflow_names:
                ordered_workflow_names.append(name)

        stage_runs: List[Dict[str, Any]] = []

        if preview_only:
            for stage in execution_plan.stages:
                stage_runs.append(
                    {
                        'index': stage.index,
                        'run_mode': stage.run_mode,
                        'blocking_conflicts': sorted(stage.blocking_conflicts),
                        'workflows': [
                            {
                                'workflow_name': run_spec.name,
                                'status': 'skipped',
                                'message': 'Multi-workflow execution skipped due to preview-only mode.',
                            }
                            for run_spec in stage.workflows
                        ],
                    }
                )

            overview['stage_runs'] = stage_runs
            overview['status'] = 'skipped'
            overview['skip_reason'] = 'preview_only_guard'
            self._emit_execution_summary_event(issue_data, overview)
            return {
                'workflow_name': ", ".join(ordered_workflow_names) if ordered_workflow_names else None,
                'workflow_names': ordered_workflow_names,
                'created_files': [],
                'multi_workflow_execution': overview,
                'workflow_results': [],
                'errors': [],
                'partial_success': False,
                'git_branch': None,
                'git_commit': None,
            }

        overrides_map = self._build_deliverable_overrides(plan_context)
        aggregated_files: List[str] = []
        workflow_results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        primary_branch: Optional[str] = None
        primary_commit: Optional[str] = None

        for stage in execution_plan.stages:
            stage_entry: Dict[str, Any] = {
                'index': stage.index,
                'run_mode': stage.run_mode,
                'blocking_conflicts': sorted(stage.blocking_conflicts),
                'workflows': [],
            }

            for run_spec in stage.workflows:
                workflow_info = run_spec.candidate.workflow_info
                overrides = overrides_map.get(workflow_info.name, {})

                try:
                    result = self._execute_workflow_with_recovery(
                        issue_data,
                        workflow_info,
                        extracted_content,
                        plan_context=None,
                        deliverable_overrides=overrides,
                    )

                    created = list(result.get('created_files') or [])
                    for path in created:
                        if path not in aggregated_files:
                            aggregated_files.append(path)

                    if result.get('git_branch') and not primary_branch:
                        primary_branch = result.get('git_branch')
                    if result.get('git_commit') and not primary_commit:
                        primary_commit = result.get('git_commit')

                    workflow_results.append(result)
                    stage_entry['workflows'].append(
                        {
                            'workflow_name': workflow_info.name,
                            'status': 'executed',
                            'message': 'Workflow executed successfully.',
                            'created_files': created,
                        }
                    )

                except WorkflowExecutionError as exc:
                    error_message = str(exc)
                    stage_entry['workflows'].append(
                        {
                            'workflow_name': workflow_info.name,
                            'status': 'failed',
                            'message': error_message,
                        }
                    )
                    errors.append(
                        {
                            'workflow_name': workflow_info.name,
                            'error': error_message,
                        }
                    )

                    if not execution_plan.allow_partial_success:
                        stage_runs.append(stage_entry)
                        overview['stage_runs'] = stage_runs
                        overview['status'] = 'failed'
                        overview['errors'] = errors
                        self._emit_execution_summary_event(issue_data, overview)
                        raise

                    continue

                except Exception as exc:  # pragma: no cover - defensive guard
                    error_message = str(exc)
                    stage_entry['workflows'].append(
                        {
                            'workflow_name': workflow_info.name,
                            'status': 'failed',
                            'message': error_message,
                        }
                    )
                    errors.append(
                        {
                            'workflow_name': workflow_info.name,
                            'error': error_message,
                        }
                    )

                    if not execution_plan.allow_partial_success:
                        stage_runs.append(stage_entry)
                        overview['stage_runs'] = stage_runs
                        overview['status'] = 'failed'
                        overview['errors'] = errors
                        self._emit_execution_summary_event(issue_data, overview)
                        raise WorkflowExecutionError(
                            f"Unexpected error executing workflow '{workflow_info.name}': {exc}",
                            issue_number=issue_data.number,
                            error_code="MULTI_WORKFLOW_EXECUTION_ERROR",
                        ) from exc

                    continue

            stage_runs.append(stage_entry)

        overview['stage_runs'] = stage_runs
        if errors:
            overview['status'] = 'partial' if aggregated_files else 'failed'
            overview['errors'] = errors
        else:
            overview['status'] = 'executed'

        self._emit_execution_summary_event(issue_data, overview)

        output_directory = None
        for res in workflow_results:
            candidate_dir = res.get('output_directory') if isinstance(res, dict) else None
            if candidate_dir:
                output_directory = candidate_dir
                break

        return {
            'workflow_name': ", ".join(ordered_workflow_names) if ordered_workflow_names else None,
            'workflow_names': ordered_workflow_names,
            'created_files': aggregated_files,
            'multi_workflow_execution': overview,
            'workflow_results': workflow_results,
            'errors': errors,
            'partial_success': bool(errors),
            'git_branch': primary_branch,
            'git_commit': primary_commit,
            'output_directory': output_directory,
        }

    def _execute_workflow_with_recovery(
        self,
        issue_data: IssueData,
        workflow_info,
        extracted_content=None,
        *,
        plan_context: Optional[_PlanExecutionContext] = None,
        deliverable_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute workflow with error recovery and partial success handling.
        
        Args:
            issue_data: Issue data for processing
            workflow_info: Matched workflow information object
            extracted_content: Optional AI-extracted structured content
            
        Returns:
            Dictionary with execution results including created files
            
        Raises:
            WorkflowExecutionError: If workflow execution fails critically
        """
        self.logger.info(f"Executing workflow '{workflow_info.name}' for issue #{issue_data.number}")
        
        try:
            return self._execute_workflow(
                issue_data,
                workflow_info,
                extracted_content,
                plan_context=plan_context,
                deliverable_overrides=deliverable_overrides,
            )
        except Exception as e:
            # Try to recover by falling back to basic workflow execution
            self.logger.warning(f"Primary workflow execution failed, attempting recovery: {e}")
            
            try:
                return self._execute_basic_workflow(
                    issue_data,
                    workflow_info,
                    extracted_content,
                    plan_context=plan_context,
                    deliverable_overrides=deliverable_overrides,
                )
            except Exception as recovery_error:
                error_msg = f"Workflow execution and recovery both failed: {recovery_error}"
                log_exception(self.logger, error_msg, recovery_error)
                raise WorkflowExecutionError(
                    error_msg,
                    issue_number=issue_data.number,
                    error_code="WORKFLOW_EXECUTION_FAILED"
                ) from recovery_error

    def _execute_basic_workflow(
        self,
        issue_data: IssueData,
        workflow_info,
        extracted_content=None,
        *,
        plan_context: Optional[_PlanExecutionContext] = None,
        deliverable_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a basic version of the workflow with minimal dependencies.
        
        This is a fallback method that creates basic deliverables without
        advanced features like git integration or complex templating.
        
        Args:
            issue_data: Issue data for processing
            workflow_info: Workflow information object
            
        Returns:
            Dictionary with execution results
        """
        self.logger.info(f"Executing basic workflow for issue #{issue_data.number}")
        
        # Create basic output directory
        output_dir = self.output_base_dir / f"issue_{issue_data.number}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        created_files = []
        
        # Create basic deliverables without complex templating
        for deliverable in workflow_info.deliverables:
            try:
                deliverable_slug = self._slugify(deliverable['name'])
                override_entry = None
                if deliverable_overrides:
                    override_entry = deliverable_overrides.get(deliverable_slug)

                if override_entry:
                    relative_path_value = override_entry.get('final_relative_path') or override_entry.get('base_relative_path')
                    if not relative_path_value:
                        relative_path_value = f"issue_{issue_data.number}/{deliverable_slug}.md"
                    file_path = self.output_base_dir / str(relative_path_value)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    file_name = f"{deliverable_slug}.md"
                    file_path = output_dir / file_name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Generate basic content
                content = self._generate_basic_deliverable_content(issue_data, deliverable)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                created_files.append(str(file_path))
                self.logger.info(f"Created basic deliverable: {file_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to create basic deliverable '{deliverable.get('name', 'Unknown')}': {e}")
                continue
        
        if not created_files:
            raise WorkflowExecutionError(
                f"No deliverables could be created for issue #{issue_data.number}",
                issue_number=issue_data.number,
                error_code="NO_DELIVERABLES_CREATED"
            )
        
        result = {
            'workflow_name': workflow_info.name,
            'created_files': created_files,
            'output_directory': str(output_dir),
            'execution_mode': 'basic_recovery'
        }

        return result

    def _generate_basic_deliverable_content(self, issue_data: IssueData, deliverable_spec: Dict[str, Any]) -> str:
        """
        Generate basic content for a deliverable when advanced generation fails.
        
        Args:
            issue_data: Issue data for context
            deliverable_spec: Deliverable specification
            
        Returns:
            Basic content string
        """
        return f"""# {deliverable_spec.get('name', 'Unknown Deliverable')}

Generated from issue #{issue_data.number}: {issue_data.title}

## Overview
{deliverable_spec.get('description', 'No description provided')}

## Issue Information
- **Number**: #{issue_data.number}
- **Title**: {issue_data.title}
- **Labels**: {', '.join(issue_data.labels)}

## Content
This deliverable was generated using basic recovery mode due to processing constraints.

{issue_data.body if issue_data.body else 'No issue body provided.'}

---
*Generated automatically by issue processor (basic recovery mode)*
*Generated at: {datetime.now().isoformat()}*
"""
    
    def _generate_clarification_message(self, issue_data: IssueData) -> str:
        """
        Generate a clarification message for ambiguous workflow selection.
        
        Args:
            issue_data: Issue data for context
            
        Returns:
            Formatted clarification message
        """
        available_workflows = self.workflow_matcher.get_available_workflows()
        workflow_list = "\n".join([f"- `{workflow.name}`: {workflow.description}" for workflow in available_workflows])
        
        return (
            f"🤖 **Workflow Selection Required for Issue #{issue_data.number}**\n\n"
            f"Multiple workflows could apply to this issue, or no specific workflow was found.\n"
            f"Current labels: {', '.join(issue_data.labels)}\n\n"
            f"Available workflows:\n{workflow_list}\n\n"
            f"Please add additional labels to clarify which workflow should be used.\n"
            f"You can find workflow definitions in `docs/workflow/deliverables/`"
        )
    
    def _execute_workflow(
        self,
        issue_data: IssueData,
        workflow_info,
        extracted_content=None,
        *,
        plan_context: Optional[_PlanExecutionContext] = None,
        deliverable_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the matched workflow for the given issue.
        
        Args:
            issue_data: Issue data for processing
            workflow_info: Matched workflow information object
            
        Returns:
            Dictionary with execution results including created files
        """
        self.logger.info(f"Executing workflow '{workflow_info.name}' for issue #{issue_data.number}")
        
        # Create git branch if git operations are enabled
        branch_info = None
        if self.enable_git and self.git_manager:
            try:
                branch_info = self.git_manager.create_issue_branch(
                    issue_number=issue_data.number,
                    title=issue_data.title
                )
                self.logger.info(f"Created git branch: {branch_info.name}")
            except GitOperationError as e:
                self.logger.warning(f"Failed to create git branch: {e}")
                # Continue without git operations
        
        # Extract naming conventions from workflow output settings
        output_config = workflow_info.output
        folder_structure = output_config.get('folder_structure', 'issue_{issue_number}')
        file_pattern = output_config.get('file_pattern', '{deliverable_name}.md')
        
        # Create output directory
        output_dir = self.output_base_dir / folder_structure.format(
            issue_number=issue_data.number,
            title_slug=self._slugify(issue_data.title)
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Process deliverables
        created_files = []
        
        for deliverable in workflow_info.deliverables:
            try:
                deliverable_slug = self._slugify(deliverable['name'])
                override_entry = None
                if deliverable_overrides:
                    override_entry = deliverable_overrides.get(deliverable_slug)

                file_name = file_pattern.format(
                    deliverable_name=self._slugify(deliverable['name']),
                    issue_number=issue_data.number,
                    title_slug=self._slugify(issue_data.title)
                )
                if override_entry:
                    relative_path_value = override_entry.get('final_relative_path') or override_entry.get('base_relative_path')
                    if not relative_path_value:
                        relative_path_value = (output_dir / file_name).relative_to(self.output_base_dir)
                    file_path = self.output_base_dir / str(relative_path_value)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    file_path = output_dir / file_name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Generate content based on issue and deliverable spec
                content = self._generate_deliverable_content(issue_data, deliverable, workflow_info, extracted_content)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                created_files.append(str(file_path))
                self.logger.info(f"Created deliverable: {file_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to create deliverable '{deliverable.get('name', 'Unknown')}': {e}")
                # Continue with other deliverables
                continue
        
        # Commit deliverables to git if git operations are enabled
        commit_info = None
        if self.enable_git and self.git_manager and created_files:
            try:
                commit_info = self.git_manager.commit_deliverables(
                    file_paths=created_files,
                    issue_number=issue_data.number,
                    workflow_name=workflow_info.name
                )
                self.logger.info(f"Committed deliverables: {commit_info.hash[:8]}")
                
                # Push branch if auto_push is enabled
                git_config = self.config.agent.git if self.config.agent else None
                if git_config and git_config.auto_push and branch_info:
                    success = self.git_manager.push_branch(branch_info.name)
                    if success:
                        self.logger.info(f"Pushed branch: {branch_info.name}")
                
            except GitOperationError as e:
                self.logger.warning(f"Failed to commit deliverables: {e}")
                # Continue without git operations
        
        result = {
            'workflow_name': workflow_info.name,
            'created_files': created_files,
            'output_directory': str(output_dir)
        }
        
        # Add git information if available
        if branch_info:
            result['git_branch'] = branch_info.name
        if commit_info:
            result['git_commit'] = commit_info.hash
        
        return result
    
    def _generate_deliverable_content(self, 
                                    issue_data: IssueData, 
                                    deliverable_spec: Dict[str, Any],
                                    workflow_info,
                                    extracted_content=None) -> str:
        """
        Generate content for a specific deliverable using the DeliverableGenerator.
        
        Args:
            issue_data: Issue data for context
            deliverable_spec: Deliverable specification from workflow
            workflow_info: Full workflow information object
            extracted_content: Optional AI-extracted structured content
            
        Returns:
            Generated content string
        """
        # Convert deliverable_spec to DeliverableSpec object
        spec = DeliverableSpec(
            name=deliverable_spec.get('name', 'Unknown Deliverable'),
            title=deliverable_spec.get('title', deliverable_spec.get('name', 'Unknown Deliverable')),
            description=deliverable_spec.get('description', 'No description provided'),
            template=deliverable_spec.get('template', 'basic'),
            required=deliverable_spec.get('required', True),
            order=deliverable_spec.get('order', 1),
            type=deliverable_spec.get('type', 'document'),
            format=deliverable_spec.get('format', 'markdown'),
            sections=deliverable_spec.get('required_sections', []),
            metadata=deliverable_spec.get('metadata', {})
        )
        
        # Use the deliverable generator to create content
        additional_context = {}
        if extracted_content:
            additional_context['extracted_content'] = extracted_content
            self.logger.info("Passing AI-extracted content to deliverable generator")
        
        return self.deliverable_generator.generate_deliverable(
            issue_data=issue_data,
            deliverable_spec=spec,
            workflow_info=workflow_info,
            additional_context=additional_context
        )

    def _initialize_multi_workflow_planner(self) -> None:
        """Ensure the workflow execution planner is ready for multi-workflow runs."""

        if getattr(self, 'workflow_execution_planner', None):
            return

        plan_config = self._multi_workflow_plan_config
        if not isinstance(plan_config, MultiWorkflowProcessingConfig):
            plan_config = MultiWorkflowProcessingConfig()
            self._multi_workflow_plan_config = plan_config

        self.workflow_execution_planner = WorkflowExecutionPlanner(
            allow_parallel_stages=plan_config.allow_parallel_stages,
            max_parallel_workflows=plan_config.max_parallel_workflows,
            allow_partial_success=plan_config.allow_partial_success,
            overall_timeout_seconds=plan_config.overall_timeout_seconds,
        )

    def enable_multi_workflow_runtime(
        self,
        *,
        allow_parallel_stages: Optional[bool] = None,
        max_parallel_workflows: Optional[int] = None,
        allow_partial_success: Optional[bool] = None,
        overall_timeout_seconds: Optional[int] = None,
        preview_only: Optional[bool] = None,
    ) -> None:
        """Enable multi-workflow planning at runtime, overriding config defaults if provided."""

        plan_config = self._multi_workflow_plan_config
        if not isinstance(plan_config, MultiWorkflowProcessingConfig):
            plan_config = MultiWorkflowProcessingConfig()
            self._multi_workflow_plan_config = plan_config

        if allow_parallel_stages is not None:
            plan_config.allow_parallel_stages = allow_parallel_stages
        if max_parallel_workflows is not None:
            plan_config.max_parallel_workflows = max_parallel_workflows
        if allow_partial_success is not None:
            plan_config.allow_partial_success = allow_partial_success
        if overall_timeout_seconds is not None:
            plan_config.overall_timeout_seconds = overall_timeout_seconds
        if preview_only is not None:
            plan_config.preview_only = bool(preview_only)
            self.multi_workflow_preview_only = bool(preview_only)

        if preview_only is None:
            self.multi_workflow_preview_only = plan_config.preview_only

        self.multi_workflow_planning_enabled = True
        self._initialize_multi_workflow_planner()

        self.logger.info(
            "Multi-workflow planner enabled via runtime override (preview_only=%s, allow_parallel=%s, max_parallel=%s)",
            self.multi_workflow_preview_only,
            plan_config.allow_parallel_stages,
            plan_config.max_parallel_workflows,
        )
    
    def _extract_issue_content(self, issue_data: IssueData) -> Optional[Any]:
        """
        Extract structured content from issue using AI content extraction.
        
        Args:
            issue_data: Issue data to extract content from
            
        Returns:
            Extracted structured content or None if extraction fails
        """
        if not self.content_extraction_agent:
            self.logger.warning("Content extraction requested but agent not initialized")
            return None
        
        try:
            # Convert IssueData to dictionary format expected by extraction agent
            issue_dict = {
                'number': issue_data.number,
                'title': issue_data.title,
                'body': issue_data.body,
                'labels': [{'name': label} for label in issue_data.labels],
                'assignees': [{'login': assignee} for assignee in issue_data.assignees],
                'created_at': issue_data.created_at.isoformat(),
                'updated_at': issue_data.updated_at.isoformat(),
                'url': issue_data.url
            }
            
            # Perform content extraction
            extraction_result = self.content_extraction_agent.extract_content(issue_dict)
            
            if extraction_result.success and extraction_result.structured_content:
                self.logger.info(f"Successfully extracted content with {len(extraction_result.structured_content.entities)} entities, "
                               f"{len(extraction_result.structured_content.relationships)} relationships")
                return extraction_result.structured_content
            else:
                self.logger.warning(f"Content extraction failed: {extraction_result.error_message}")
                return None
                
        except Exception as e:
            log_exception(self.logger, f"Content extraction error for issue #{issue_data.number}", e)
            return None

    def _slugify(self, text: str) -> str:
        """
        Convert text to a URL-friendly slug.
        
        Args:
            text: Text to slugify
            
        Returns:
            Slugified text
        """
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def _get_issue_status(self, issue_number: int) -> IssueProcessingStatus:
        """
        Get current processing status for an issue.
        
        Args:
            issue_number: Issue number to check
            
        Returns:
            Current processing status
        """
        state = self._processing_state.get(str(issue_number), {})
        status_str = state.get('status', IssueProcessingStatus.PENDING.value)
        try:
            return IssueProcessingStatus(status_str)
        except ValueError:
            return IssueProcessingStatus.PENDING
    
    def _update_issue_status(self, 
                           issue_number: int, 
                           status: IssueProcessingStatus,
                           additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Update processing status for an issue.
        
        Args:
            issue_number: Issue number to update
            status: New processing status
            additional_data: Additional state data to store
        """
        state_key = str(issue_number)
        if state_key not in self._processing_state:
            self._processing_state[state_key] = {}
        
        self._processing_state[state_key]['status'] = status.value
        self._processing_state[state_key]['updated_at'] = datetime.now().isoformat()
        
        if additional_data:
            self._processing_state[state_key].update(additional_data)
        
        self._save_processing_state()
    
    def get_issue_processing_state(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """
        Get complete processing state for an issue.
        
        Args:
            issue_number: Issue number to query
            
        Returns:
            Processing state dictionary or None if not found
        """
        return self._processing_state.get(str(issue_number))
    
    def list_processing_issues(self, 
                             status_filter: Optional[IssueProcessingStatus] = None) -> List[Dict[str, Any]]:
        """
        List all issues being tracked with optional status filtering.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of issue processing states
        """
        results = []
        for issue_number, state in self._processing_state.items():
            if status_filter is None or state.get('status') == status_filter.value:
                results.append({
                    'issue_number': int(issue_number),
                    **state
                })
        
        return sorted(results, key=lambda x: x['issue_number'])
    
    def clear_issue_state(self, issue_number: int) -> bool:
        """
        Clear processing state for a specific issue.
        
        Args:
            issue_number: Issue number to clear
            
        Returns:
            True if state was cleared, False if no state existed
        """
        state_key = str(issue_number)
        if state_key in self._processing_state:
            del self._processing_state[state_key]
            self._save_processing_state()
            return True
        return False
    
    def reset_all_processing_state(self) -> int:
        """
        Reset all processing state (useful for testing/recovery).
        
        Returns:
            Number of issues that had their state cleared
        """
        count = len(self._processing_state)
        self._processing_state = {}
        self._save_processing_state()
        return count


class GitHubIntegratedIssueProcessor(IssueProcessor):
    """
    GitHub-integrated issue processor that can automatically process issues
    from GitHub repositories.
    
    This class extends the base IssueProcessor with GitHub integration capabilities:
    - Automatic issue retrieval and conversion to IssueData
    - Issue assignment and unassignment
    - Clarification comments on issues
    - Label management and status updates
    
    It maintains the same core processing logic while adding the GitHub
    operations needed for automated workflow execution.
    """
    
    def __init__(self, 
                 github_token: str,
                 repository: str,
                 config_path: str = "config.yaml",
                 workflow_dir: Optional[str] = None,
                 output_base_dir: Optional[str] = None,
                 telemetry_publishers: Optional[Iterable[TelemetryPublisher]] = None):
        """
        Initialize GitHub-integrated issue processor.
        
        Args:
            github_token: GitHub personal access token
            repository: Repository name in format 'owner/repo'
            config_path: Path to configuration file
            workflow_dir: Override for workflow directory path
            output_base_dir: Override for output base directory
        """
        # Initialize base processor
        super().__init__(
            config_path,
            workflow_dir,
            output_base_dir,
            telemetry_publishers=telemetry_publishers,
        )
        
        # Initialize GitHub client
        try:
            self.github = GitHubIssueCreator(github_token, repository)
            self.repository = repository
        except Exception as e:
            error_msg = f"Failed to initialize GitHub client: {e}"
            self.logger.error(error_msg)
            raise IssueProcessingError(error_msg, error_code="GITHUB_INIT_FAILED") from e
        
        # Initialize AI content extraction agent if enabled
        if self.enable_ai_extraction and self.config.ai:
            try:
                from ..agents.content_extraction_agent import ContentExtractionAgent
                self.content_extraction_agent = ContentExtractionAgent(
                    github_token=github_token,
                    ai_config=self.config.ai,
                    enable_validation=True
                )
                self.logger.info("AI content extraction agent initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize AI content extraction agent: {e}")
                self.enable_ai_extraction = False
                self.content_extraction_agent = None

        try:
            self.handoff_builder = IssueHandoffBuilder(
                config_path=config_path,
                workflow_directory=self.workflow_directory,
            )
            self.logger.info("Issue handoff builder initialized")
        except Exception as e:
            self.logger.warning(f"Issue handoff builder unavailable: {e}")
            self.handoff_builder = None
    
    def generate_preview_result(self, issue_data: IssueData) -> ProcessingResult:  # type: ignore[override]
        """Return a simulated processing result with rendered handoff sections."""

        try:
            self._validate_issue_data(issue_data)
        except IssueProcessingError as exc:  # pragma: no cover - defensive guard
            return ProcessingResult(
                issue_number=issue_data.number,
                status=IssueProcessingStatus.ERROR,
                error_message=str(exc),
            )

        if 'site-monitor' not in issue_data.labels:
            return ProcessingResult(
                issue_number=issue_data.number,
                status=IssueProcessingStatus.ERROR,
                error_message="Preview requires the 'site-monitor' label to determine workflow context.",
            )

        try:
            workflow_result = self._find_workflow_with_retry(issue_data)
        except Exception as exc:  # pragma: no cover - defensive guard
            return ProcessingResult(
                issue_number=issue_data.number,
                status=IssueProcessingStatus.ERROR,
                error_message=f"Failed to analyse workflow for preview: {exc}",
            )

        workflow_info, status_message = workflow_result
        if workflow_info is None:
            clarification_msg = self._generate_clarification_message(issue_data)
            return ProcessingResult(
                issue_number=issue_data.number,
                status=IssueProcessingStatus.NEEDS_CLARIFICATION,
                clarification_needed=clarification_msg,
            )

        preview_files = self._build_preview_file_list(workflow_info, issue_data)
        metadata: Dict[str, Any] = {
            'git_branch': self._build_preview_branch_name(issue_data, workflow_info),
            'preview': True,
        }
        if status_message:
            metadata['workflow_selection_message'] = status_message

        plan_summary = self._maybe_build_execution_plan_summary(issue_data)
        if plan_summary:
            metadata['multi_workflow_plan'] = plan_summary

        payload: Optional[IssueHandoffPayload] = None
        if self.handoff_builder:
            try:
                payload = self.handoff_builder.build_handoff(
                    issue_title=issue_data.title,
                    issue_url=issue_data.url,
                    issue_body=issue_data.body,
                    workflow_info=workflow_info,
                    labels=issue_data.labels,
                    created_files=preview_files,
                    metadata=metadata,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                self.logger.warning("Failed to render preview handoff sections: %s", exc)
                payload = None

        result = ProcessingResult(
            issue_number=issue_data.number,
            status=IssueProcessingStatus.PREVIEW,
            workflow_name=workflow_info.name,
            created_files=preview_files,
            metadata=metadata,
        )

        if payload:
            result.copilot_assignee = payload.copilot_assignee
            result.copilot_due_at = payload.copilot_due_iso
            result.handoff_summary = payload.summary_comment
            result.specialist_guidance = payload.specialist_guidance
            result.copilot_assignment = payload.copilot_assignment
        else:
            result.copilot_assignee = DEFAULT_COPILOT_ASSIGNEE
            result.copilot_due_at = None
            result.handoff_summary = "Preview available, but specialist guidance template could not be rendered."
            result.specialist_guidance = (
                "Preview unavailable: specialist configuration is missing."
            )
            result.copilot_assignment = (
                "Preview unavailable: Copilot assignment template could not be generated."
            )

        return result

    def _build_preview_file_list(self, workflow_info: WorkflowInfo, issue_data: IssueData) -> List[str]:
        """Create placeholder file paths mirroring workflow deliverables."""

        base_slug = self._slugify(workflow_info.name) or "workflow"
        base_dir = f"study/preview/{base_slug}-{issue_data.number}"
        preview_files: List[str] = []

        for deliverable in workflow_info.deliverables or []:
            filename = deliverable.get('filename') if isinstance(deliverable, dict) else None
            if isinstance(filename, str) and filename.strip():
                formatted = filename.replace('{issue_number}', str(issue_data.number))
                formatted = formatted.replace('{workflow}', base_slug)
                if not formatted.startswith('study/') and '/' not in formatted.split('/', 1)[0]:
                    formatted = f"study/{formatted}"
                preview_files.append(formatted)
                continue

            name_hint = None
            if isinstance(deliverable, dict):
                name_hint = deliverable.get('name') or deliverable.get('title')
            slug = self._slugify(str(name_hint)) if name_hint else f"deliverable-{len(preview_files) + 1}"
            preview_files.append(f"{base_dir}/{slug}.md")

        if not preview_files:
            preview_files.append(f"{base_dir}/summary.md")

        # De-duplicate while preserving order
        seen: set[str] = set()
        deduped: List[str] = []
        for path in preview_files:
            if path not in seen:
                seen.add(path)
                deduped.append(path)
        return deduped

    def _build_preview_branch_name(self, issue_data: IssueData, workflow_info: WorkflowInfo) -> str:
        """Derive a human-readable branch name for preview output."""

        prefix = "preview"
        if getattr(self, 'git_manager', None) is not None:
            branch_prefix = getattr(self.git_manager, 'branch_prefix', None)
            if branch_prefix:
                prefix = f"{branch_prefix}-preview"

        workflow_slug = self._slugify(workflow_info.name)
        title_slug = self._slugify(issue_data.title)
        descriptor = workflow_slug or title_slug or "issue"
        branch_name = f"{prefix}-{issue_data.number}-{descriptor}"[:60]
        return branch_name.rstrip('-')

    def process_github_issue(self, issue_number: int) -> ProcessingResult:
        """
        Process a GitHub issue by number.
        
        This method automatically retrieves issue data from GitHub,
        converts it to the standard format, and processes it through
        the complete workflow.
        
        Args:
            issue_number: GitHub issue number to process
            
        Returns:
            ProcessingResult with status and details
            
        Raises:
            ValueError: If issue_number is not a valid positive integer
            TypeError: If issue_number is not an integer
        """
        # Validate input parameters
        if not isinstance(issue_number, int):
            raise TypeError(f"Issue number must be an integer, got {type(issue_number).__name__}")
        
        if issue_number <= 0:
            raise ValueError(f"Issue number must be positive, got {issue_number}")
        
        try:
            # Retrieve issue data from GitHub
            issue_data_dict = self.github.get_issue_data(issue_number)
            issue_data = IssueData.from_dict(issue_data_dict)
            
            self.logger.info(f"Retrieved GitHub issue #{issue_number}: {issue_data.title}")
            
            # Check if agent should process this issue
            if not self._should_process_issue(issue_data):
                return ProcessingResult(
                    issue_number=issue_number,
                    status=IssueProcessingStatus.PENDING,
                    error_message="Issue does not meet processing criteria"
                )
            
            # Assign issue to agent before processing
            try:
                self._assign_to_agent(issue_number)
            except Exception as e:
                self.logger.warning(f"Failed to assign issue #{issue_number} to agent: {e}")
                # Continue processing even if assignment fails
            
            # Process through base processor
            result = self.process_issue(issue_data)
            
            # Handle result-specific GitHub operations
            try:
                self._handle_processing_result(issue_number, result)
            except Exception as e:
                self.logger.error(f"Failed to handle GitHub operations for issue #{issue_number}: {e}")
                # Don't fail the whole operation for GitHub operation failures
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing GitHub issue #{issue_number}: {e}"
            self.logger.error(error_msg)
            # For certain GitHub errors, raise IssueProcessingError
            from github.GithubException import GithubException
            if isinstance(e, GithubException):
                raise IssueProcessingError(error_msg, error_code="GITHUB_API_ERROR") from e
            # For other errors, return error result
            return ProcessingResult(
                issue_number=issue_number,
                status=IssueProcessingStatus.ERROR,
                error_message=str(e)
            )
    
    def process_labeled_issues(self, 
                              labels: List[str], 
                              limit: Optional[int] = None) -> List[ProcessingResult]:
        """
        Process all open issues that have specific labels.
        
        Args:
            labels: List of label names to filter by
            limit: Maximum number of issues to process
            
        Returns:
            List of ProcessingResults for each processed issue
        """
        try:
            # Get issues with specified labels
            issues = self.github.get_issues_with_labels(labels, state="open", limit=limit)
            results = []
            
            self.logger.info(f"Found {len(issues)} issues with labels {labels}")
            
            for issue in issues:
                try:
                    result = self.process_github_issue(issue.number)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Failed to process issue #{issue.number}: {e}")
                    results.append(ProcessingResult(
                        issue_number=issue.number,
                        status=IssueProcessingStatus.ERROR,
                        error_message=str(e)
                    ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing labeled issues: {e}")
            return []
    
    def _should_process_issue(self, issue_data: IssueData) -> bool:
        """
        Determine if an issue should be processed by the agent.
        
        Args:
            issue_data: Issue data to evaluate
            
        Returns:
            True if issue should be processed
        """
        # Must have site-monitor label
        if 'site-monitor' not in issue_data.labels:
            return False
        
        # Don't process if already assigned to agent
        if self.agent_username in issue_data.assignees:
            current_status = self._get_issue_status(issue_data.number)
            if current_status == IssueProcessingStatus.PROCESSING:
                return False
        
        return True
    
    def _assign_to_agent(self, issue_number: int) -> None:
        """
        Assign issue to the processing agent.
        
        Args:
            issue_number: Issue number to assign
        """
        try:
            self.github.assign_issue(issue_number, [self.agent_username])
            self.logger.info(f"Assigned issue #{issue_number} to {self.agent_username}")
        except Exception as e:
            self.logger.error(f"Failed to assign issue #{issue_number}: {e}")
            raise
    
    def _unassign_from_agent(self, issue_number: int) -> None:
        """
        Remove agent assignment from issue.
        
        Args:
            issue_number: Issue number to unassign
        """
        try:
            self.github.unassign_issue(issue_number, [self.agent_username])
            self.logger.info(f"Unassigned issue #{issue_number} from {self.agent_username}")
        except Exception as e:
            self.logger.warning(f"Failed to unassign issue #{issue_number}: {e}")
    
    def _handle_processing_result(self, issue_number: int, result: ProcessingResult) -> None:
        """
        Handle GitHub operations based on processing result.
        
        Args:
            issue_number: Issue number that was processed
            result: Processing result to handle
        """
        if result.status == IssueProcessingStatus.NEEDS_CLARIFICATION:
            # Add clarification comment and unassign
            if result.clarification_needed:
                self.github.add_comment(issue_number, result.clarification_needed)
                self.logger.info(f"Added clarification comment to issue #{issue_number}")
            
            self._unassign_from_agent(issue_number)
            
        elif result.status == IssueProcessingStatus.COMPLETED:
            handoff_payload = None
            try:
                handoff_payload = self._finalize_copilot_handoff(issue_number, result)
            except Exception as e:
                self.logger.error(f"Failed to finalize Copilot handoff for issue #{issue_number}: {e}")

            completion_comment = self._generate_completion_comment(result)
            if handoff_payload:
                result.copilot_assignee = handoff_payload.copilot_assignee
                result.copilot_due_at = handoff_payload.copilot_due_iso
                result.handoff_summary = handoff_payload.summary_comment
                result.specialist_guidance = handoff_payload.specialist_guidance
                result.copilot_assignment = handoff_payload.copilot_assignment

            comment_body = handoff_payload.summary_comment if handoff_payload else None
            if comment_body:
                comment_body = f"{comment_body}\n\n---\n{completion_comment}"
            else:
                comment_body = completion_comment

            self.github.add_comment(issue_number, comment_body)
            self.logger.info(f"Posted completion summary to issue #{issue_number}")
            try:
                self._unassign_from_agent(issue_number)
            except Exception as e:
                self.logger.warning(f"Failed to unassign agent from issue #{issue_number}: {e}")
            
        elif result.status == IssueProcessingStatus.ERROR:
            # Add error comment and unassign
            error_comment = self._generate_error_comment(result)
            self.github.add_comment(issue_number, error_comment)
            self._unassign_from_agent(issue_number)
            self.logger.info(f"Added error comment to issue #{issue_number}")
    
    def _generate_completion_comment(self, result: ProcessingResult) -> str:
        """
        Generate completion comment for successfully processed issue.
        
        Args:
            result: Processing result to comment on
            
        Returns:
            Formatted completion comment
        """
        files_list = "\n".join([f"- {file}" for file in (result.created_files or [])])
        processing_time = f"{result.processing_time_seconds:.1f}s" if result.processing_time_seconds else "unknown"
        
        return (
            f"✅ **Issue Processing Complete**\n\n"
            f"**Workflow**: {result.workflow_name}\n"
            f"**Processing Time**: {processing_time}\n"
            f"**Generated Files**:\n{files_list}\n\n"
            f"The requested deliverables have been generated and are ready for review.\n\n"
            f"---\n"
            f"*Automated processing by Issue Processor v1.0*"
        )

    def _finalize_copilot_handoff(self, issue_number: int, result: ProcessingResult) -> Optional[IssueHandoffPayload]:
        """Update issue metadata and assignment for Copilot handoff."""

        if not self.handoff_builder:
            self.logger.debug("Handoff builder not available; skipping Copilot handoff update")
            return None

        if not result.workflow_name:
            self.logger.debug("No workflow name recorded; skipping Copilot handoff update")
            return None

        issue = self.github.get_issue(issue_number)
        workflow_info = self.workflow_matcher.get_workflow_by_name(result.workflow_name)

        if workflow_info is None:
            self.logger.warning(
                f"Workflow '{result.workflow_name}' not found in matcher; skipping handoff update"
            )
            return None

        current_labels = [label.name for label in issue.labels] if issue.labels else []
        metadata: Dict[str, str] = {}
        if result.git_branch:
            metadata["git_branch"] = result.git_branch
        if result.git_commit:
            metadata["git_commit"] = result.git_commit
        if result.output_directory:
            metadata["output_directory"] = result.output_directory

        payload = self.handoff_builder.build_handoff(
            issue_title=issue.title,
            issue_url=issue.html_url,
            issue_body=issue.body or "",
            workflow_info=workflow_info,
            labels=current_labels,
            created_files=result.created_files or [],
            metadata=metadata if metadata else None,
        )

        updated_body = upsert_section(issue.body or "", "Specialist Guidance", payload.specialist_guidance.strip())
        updated_body = upsert_section(updated_body, "Copilot Assignment", payload.copilot_assignment.strip())

        workflow_label = f"{WORKFLOW_LABEL_PREFIX}{self._slugify(workflow_info.name)}"
        specialist_labels = [label for label in current_labels if label.startswith(SPECIALIST_LABEL_PREFIX)]
        transition_plan = plan_state_transition(
            current_labels,
            WorkflowState.COPILOT_ASSIGNED,
            ensure_labels=[workflow_label],
            specialist_labels=specialist_labels or None,
            clear_temporary=True,
        )

        final_labels = sorted(transition_plan.final_labels)
        edit_kwargs: Dict[str, Any] = {}

        if updated_body != (issue.body or ""):
            edit_kwargs["body"] = updated_body
        if set(final_labels) != set(current_labels):
            edit_kwargs["labels"] = final_labels

        if edit_kwargs:
            issue.edit(**edit_kwargs)

        copilot_assignee = payload.copilot_assignee
        try:
            current_assignees = [assignee.login for assignee in issue.assignees] if issue.assignees else []
            if copilot_assignee not in current_assignees:
                self.github.assign_issue(issue_number, [copilot_assignee])
        except Exception as e:
            self.logger.warning(f"Failed to assign issue #{issue_number} to {copilot_assignee}: {e}")

        result.copilot_assignee = payload.copilot_assignee
        result.copilot_due_at = payload.copilot_due_iso
        result.handoff_summary = payload.summary_comment
        result.specialist_guidance = payload.specialist_guidance
        result.copilot_assignment = payload.copilot_assignment

        return payload
    
    def _generate_error_comment(self, result: ProcessingResult) -> str:
        """
        Generate error comment for failed processing.
        
        Args:
            result: Processing result to comment on
            
        Returns:
            Formatted error comment
        """
        return (
            f"❌ **Issue Processing Failed**\n\n"
            f"An error occurred while processing this issue:\n\n"
            f"```\n{result.error_message}\n```\n\n"
            f"The issue has been unassigned and will require manual review.\n"
            f"Please check the logs for more details or retry processing.\n\n"
            f"---\n"
            f"*Automated processing by Issue Processor v1.0*"
        )
    

    
    def get_copilot_assigned_issues(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get issues assigned to GitHub Copilot for AI processing.
        
        Args:
            limit: Maximum number of issues to return
            
        Returns:
            List of Copilot-assigned issue data
        """
        try:
            # Query issues assigned to Copilot using direct repo access
            copilot_usernames = ['github-copilot[bot]', 'copilot', 'github-actions[bot]']
            
            issues = []
            # Get all open issues and filter by assignee
            all_issues = self.github.repo.get_issues(state='open')
            
            for issue in all_issues:
                if issue.assignee and issue.assignee.login in copilot_usernames:
                    if self._should_process_copilot_issue(issue):
                        issues.append(self._convert_issue_to_dict(issue))
                        if limit and len(issues) >= limit:
                            return issues[:limit]
            
            self.logger.info(f"Found {len(issues)} Copilot-assigned processable issues")
            return issues
        except Exception as e:
            self.logger.error(f"Failed to get Copilot-assigned issues: {e}")
            return []
    
    def is_copilot_assigned(self, issue_data: Union[Dict[str, Any], Any]) -> bool:
        """
        Check if issue is assigned to GitHub Copilot.
        
        Args:
            issue_data: Issue data or GitHub issue object
            
        Returns:
            True if assigned to Copilot
        """
        if isinstance(issue_data, dict):
            assignee = issue_data.get('assignee')
        else:
            assignee = getattr(issue_data, 'assignee', None)
            if assignee:
                assignee = assignee.login if hasattr(assignee, 'login') else str(assignee)
        
        copilot_identifiers = ['github-copilot[bot]', 'copilot', 'github-actions[bot]']
        return assignee in copilot_identifiers
    
    def _should_process_copilot_issue(self, issue) -> bool:
        """
        Determine if Copilot-assigned issue should be processed.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            True if issue should be processed
        """
        # Check for required labels or content indicators
        labels = {label.name for label in issue.labels}
        content_indicators = ['intelligence', 'research', 'analysis', 'target', 'osint', 'site-monitor']
        
        # Must have at least one processing indicator
        return bool(labels.intersection(content_indicators) or 
                   any(indicator in (issue.title + issue.body).lower() 
                       for indicator in content_indicators))
    
    def _convert_issue_to_dict(self, issue) -> Dict[str, Any]:
        """
        Convert GitHub issue object to dictionary format.
        
        Args:
            issue: GitHub issue object
            
        Returns:
            Issue data dictionary
        """
        return {
            'number': issue.number,
            'title': issue.title,
            'body': issue.body or '',
            'labels': [label.name for label in issue.labels],
            'assignees': [assignee.login for assignee in issue.assignees] if issue.assignees else [],
            'assignee': issue.assignee.login if issue.assignee else None,
            'created_at': issue.created_at.isoformat(),
            'updated_at': issue.updated_at.isoformat(),
            'url': issue.html_url
        }

    def get_processable_issues(self,
                              assignee_filter: Optional[str] = None,
                              additional_labels: Optional[List[str]] = None,
                              limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get list of issues that can be processed.
        
        Args:
            assignee_filter: Filter by assignee ('none' for unassigned, username for specific user)
            additional_labels: Additional labels that must be present
            limit: Maximum number of issues to return
            
        Returns:
            List of issue data dictionaries
        """
        try:
            # Get site-monitor issues
            issues = self.github.get_issues_with_labels(['site-monitor'], state='open')
            
            processable_issues = []
            for issue in issues:
                # Apply assignee filter
                if assignee_filter:
                    if assignee_filter == 'none':
                        if issue.assignee is not None:
                            continue
                    else:
                        if not issue.assignee or issue.assignee.login != assignee_filter:
                            continue
                
                # Apply additional label filter
                if additional_labels:
                    issue_labels = [label.name for label in issue.labels]
                    if not any(label in issue_labels for label in additional_labels):
                        continue
                
                # Convert to dictionary format
                issue_data = {
                    'number': issue.number,
                    'title': issue.title,
                    'labels': [label.name for label in issue.labels],
                    'assignee': issue.assignee.login if issue.assignee else None,
                    'created_at': issue.created_at.isoformat(),
                    'updated_at': issue.updated_at.isoformat(),
                    'url': issue.html_url
                }
                
                processable_issues.append(issue_data)
                
                # Apply limit
                if limit and len(processable_issues) >= limit:
                    break
            
            self.logger.info(f"Found {len(processable_issues)} processable issues")
            return processable_issues
        
        except Exception as e:
            self.logger.error(f"Failed to get processable issues: {e}")
            return []

