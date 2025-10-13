"""
Workflow Matcher Module
Handles discovery and matching of workflows based on GitHub issue labels
"""

import os
import yaml
import logging
import time
import functools
import re
from typing import Dict, List, Optional, Tuple, Set, Any, Iterable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from .workflow_schemas import WorkflowSchemaValidator
from ..utils.logging_config import get_logger, log_exception, log_retry_attempt

logger = get_logger(__name__)


class WorkflowMatcherError(Exception):
    """Base exception for workflow matcher errors."""
    
    def __init__(self, message: str, workflow_path: Optional[str] = None, error_code: Optional[str] = None):
        """
        Initialize workflow matcher error.
        
        Args:
            message: Error message
            workflow_path: Path to workflow file if applicable
            error_code: Error code for categorization
        """
        super().__init__(message)
        self.workflow_path = workflow_path
        self.error_code = error_code


class WorkflowValidationError(WorkflowMatcherError):
    """Exception raised for workflow validation errors."""
    pass


class WorkflowLoadError(WorkflowMatcherError):
    """Exception raised for workflow loading errors."""
    pass


def retry_on_io_error(max_attempts: int = 3, delay_seconds: float = 0.5):
    """
    Decorator for retrying I/O operations.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        
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
                except (OSError, IOError, yaml.YAMLError) as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        log_exception(logger, f"Final attempt failed for {func.__name__}", e)
                        raise
                    
                    log_retry_attempt(logger, func.__name__, attempt, max_attempts, e)
                    time.sleep(delay_seconds * attempt)
            
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"Unexpected error in retry decorator for {func.__name__}")
        
        return wrapper
    return decorator


@dataclass
class WorkflowInfo:
    """Information about a discovered workflow."""

    path: str
    name: str
    description: str
    version: str
    trigger_labels: List[str]
    deliverables: List[Dict]
    processing: Dict
    validation: Dict
    output: Dict
    workflow_version: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    confidence_threshold: Optional[float] = None
    required_entities: Optional[List[Dict[str, Any]]] = None
    deliverable_templates: Optional[List[str]] = None
    audit_trail: Optional[Dict[str, Any]] = None
    legacy_mode: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate workflow info after creation."""
        if not self.trigger_labels:
            raise WorkflowValidationError(
                f"Workflow {self.name} must have at least one trigger label",
                workflow_path=self.path,
                error_code="NO_TRIGGER_LABELS",
            )
        if not self.deliverables:
            raise WorkflowValidationError(
                f"Workflow {self.name} must have at least one deliverable",
                workflow_path=self.path,
                error_code="NO_DELIVERABLES",
            )

    def is_taxonomy(self) -> bool:
        """Return True when the workflow adheres to the criminal-law taxonomy."""

        return bool(self.workflow_version and self.category and not self.legacy_mode)


@dataclass(frozen=True)
class WorkflowCandidate:
    """Represents a workflow option selected for execution planning."""

    workflow_info: WorkflowInfo
    priority: int
    conflict_keys: frozenset[str]
    dependencies: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        """Return the candidate workflow's canonical name."""

        return self.workflow_info.name


@dataclass(frozen=True)
class WorkflowPlan:
    """Contains the ordered set of workflow candidates for an issue."""

    issue_labels: tuple[str, ...]
    candidates: tuple[WorkflowCandidate, ...]
    selection_reason: str
    selection_message: str

    def has_candidates(self) -> bool:
        return bool(self.candidates)

    def is_multi_workflow(self) -> bool:
        return len(self.candidates) > 1

    def primary_workflow(self) -> Optional[WorkflowCandidate]:
        return self.candidates[0] if self.candidates else None


class WorkflowMatcher:
    """
    Matches GitHub issues to appropriate workflow definitions based on labels.
    
    This class scans the workflow directory for YAML workflow definitions,
    caches them in memory, and provides matching logic to determine which
    workflow should be used for a given set of issue labels.
    """
    
    def __init__(self, workflow_directory: str = "docs/workflow/deliverables"):
        """
        Initialize the workflow matcher.
        
        Args:
            workflow_directory: Path to directory containing workflow YAML files
            
        Raises:
            WorkflowLoadError: If initialization fails
        """
        self.workflow_directory = Path(workflow_directory)
        self._workflow_cache: Dict[str, WorkflowInfo] = {}
        self._last_scan_time: Optional[datetime] = None
        self._scan_interval_seconds = 300  # Re-scan every 5 minutes
        self._schema_validator = WorkflowSchemaValidator()
        
        logger.info(f"Initializing WorkflowMatcher with directory: {self.workflow_directory}")
        
        # Load workflows - don't catch WorkflowLoadError since it has specific error codes
        try:
            self._load_workflows()
        except WorkflowLoadError:
            # Re-raise WorkflowLoadError as-is to preserve specific error codes
            raise
        except Exception as e:
            error_msg = f"Failed to initialize WorkflowMatcher: {e}"
            log_exception(logger, error_msg, e)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(self.workflow_directory),
                error_code="INITIALIZATION_FAILED"
            ) from e

    @staticmethod
    def _slugify_name(value: str) -> str:
        """Convert workflow names into stable slug identifiers."""

        slug = re.sub(r"[^\w\s-]", "", value.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    def _load_workflows(self) -> None:
        """
        Load and cache all workflow definitions from the workflow directory.
        
        Raises:
            WorkflowLoadError: If workflow directory doesn't exist or no valid workflows found
        """
        if not self.workflow_directory.exists():
            error_msg = f"Workflow directory not found: {self.workflow_directory}"
            logger.error(error_msg)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(self.workflow_directory),
                error_code="DIRECTORY_NOT_FOUND"
            )
        
        if not self.workflow_directory.is_dir():
            error_msg = f"Workflow path is not a directory: {self.workflow_directory}"
            logger.error(error_msg)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(self.workflow_directory),
                error_code="NOT_A_DIRECTORY"
            )
        
        logger.info(f"Loading workflows from {self.workflow_directory}")
        self._workflow_cache.clear()
        
        # Find workflow files
        workflow_files = []
        try:
            workflow_files.extend(self.workflow_directory.glob("*.yaml"))
            workflow_files.extend(self.workflow_directory.glob("*.yml"))
            # Also search subdirectories
            workflow_files.extend(self.workflow_directory.glob("**/*.yaml"))
            workflow_files.extend(self.workflow_directory.glob("**/*.yml"))
            
            # Remove duplicates that can occur when files are in both top-level and recursive search
            workflow_files = list(set(workflow_files))
        except OSError as e:
            error_msg = f"Failed to scan workflow directory: {e}"
            log_exception(logger, error_msg, e)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(self.workflow_directory),
                error_code="DIRECTORY_SCAN_FAILED"
            ) from e
        
        if not workflow_files:
            logger.warning(f"No workflow files found in {self.workflow_directory}")
            # This is not necessarily an error - we might have an empty directory
            self._last_scan_time = datetime.now()
            return
        
        loaded_count = 0
        error_count = 0
        
        for workflow_file in workflow_files:
            try:
                workflow_info = self._parse_workflow_file(workflow_file)
                if workflow_info:
                    self._workflow_cache[str(workflow_file)] = workflow_info
                    logger.debug(f"Loaded workflow: {workflow_info.name} from {workflow_file}")
                    loaded_count += 1
            except WorkflowValidationError as e:
                logger.error(f"Workflow validation failed for {workflow_file}: {e}")
                error_count += 1
                continue
            except Exception as e:
                log_exception(logger, f"Failed to load workflow from {workflow_file}", e)
                error_count += 1
                continue
        
        self._last_scan_time = datetime.now()
        
        # Only raise NO_VALID_WORKFLOWS if there were multiple files and ALL failed
        # If there's only one file that failed, or if there are no files at all, just log and continue
        if loaded_count == 0 and error_count > 1:
            error_msg = f"No valid workflows could be loaded from {self.workflow_directory} ({error_count} errors)"
            logger.error(error_msg)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(self.workflow_directory),
                error_code="NO_VALID_WORKFLOWS"
            )
        elif loaded_count == 0 and error_count == 1:
            logger.warning(f"Single workflow file failed to load from {self.workflow_directory} - continuing with empty cache")
        
        logger.info(f"Loaded {loaded_count} workflow(s) with {error_count} error(s)")

    @retry_on_io_error(max_attempts=3, delay_seconds=0.5)
    def _parse_workflow_file(self, workflow_file: Path) -> Optional[WorkflowInfo]:
        """
        Parse a single workflow YAML file.
        
        Args:
            workflow_file: Path to the workflow YAML file
            
        Returns:
            WorkflowInfo object if parsing succeeds, None otherwise
            
        Raises:
            WorkflowValidationError: If workflow file format is invalid
            WorkflowLoadError: If file cannot be read
        """
        logger.debug(f"Parsing workflow file: {workflow_file}")
        
        # Validate file exists and is readable
        if not workflow_file.exists():
            raise WorkflowLoadError(
                f"Workflow file not found: {workflow_file}",
                workflow_path=str(workflow_file),
                error_code="FILE_NOT_FOUND"
            )
        
        if not workflow_file.is_file():
            raise WorkflowLoadError(
                f"Workflow path is not a file: {workflow_file}",
                workflow_path=str(workflow_file),
                error_code="NOT_A_FILE"
            )
        
        try:
            # Read and parse YAML file
            with open(workflow_file, 'r', encoding='utf-8') as f:
                workflow_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in workflow file: {e}"
            logger.error(f"{error_msg} (file: {workflow_file})")
            raise WorkflowValidationError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="INVALID_YAML"
            ) from e
        except OSError as e:
            error_msg = f"Failed to read workflow file: {e}"
            log_exception(logger, error_msg, e)
            raise WorkflowLoadError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="FILE_READ_ERROR"
            ) from e
        except UnicodeDecodeError as e:
            error_msg = f"Workflow file contains invalid UTF-8: {e}"
            logger.error(f"{error_msg} (file: {workflow_file})")
            raise WorkflowValidationError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="INVALID_ENCODING"
            ) from e
        
        # Validate YAML content
        if workflow_data is None:
            logger.warning(f"Empty workflow file: {workflow_file}")
            return None
        
        if not isinstance(workflow_data, dict):
            raise WorkflowValidationError(
                f"Workflow file must contain a dictionary/mapping: {workflow_file}",
                workflow_path=str(workflow_file),
                error_code="INVALID_ROOT_TYPE"
            )
        
        # Validate required fields
        required_fields = ['name', 'trigger_labels', 'deliverables']
        missing_fields = [field for field in required_fields if field not in workflow_data]
        if missing_fields:
            raise WorkflowValidationError(
                f"Workflow missing required fields: {missing_fields}",
                workflow_path=str(workflow_file),
                error_code="MISSING_REQUIRED_FIELDS"
            )
        
        # Use schema validator if available
        try:
            self._schema_validator.validate_workflow(workflow_data)
        except Exception as e:
            error_msg = f"Workflow schema validation failed: {e}"
            logger.error(f"{error_msg} (file: {workflow_file})")
            raise WorkflowValidationError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="SCHEMA_VALIDATION_FAILED"
            ) from e
        
        # Extract and validate workflow information
        try:
            workflow_info = WorkflowInfo(
                path=str(workflow_file),
                name=workflow_data['name'],
                description=workflow_data.get('description', ''),
                version=workflow_data.get('version', '1.0'),
                trigger_labels=workflow_data['trigger_labels'],
                deliverables=workflow_data['deliverables'],
                processing=workflow_data.get('processing', {}),
                validation=workflow_data.get('validation', {}),
                output=workflow_data.get('output', {}),
                workflow_version=workflow_data.get('workflow_version'),
                category=workflow_data.get('category'),
                priority=workflow_data.get('priority'),
                confidence_threshold=workflow_data.get('confidence_threshold'),
                required_entities=workflow_data.get('required_entities'),
                deliverable_templates=workflow_data.get('deliverable_templates'),
                audit_trail=workflow_data.get('audit_trail'),
                legacy_mode=bool(workflow_data.get('legacy_mode', False)),
                metadata=dict(workflow_data),
            )
            
            logger.debug(f"Successfully parsed workflow: {workflow_info.name}")
            return workflow_info
            
        except (KeyError, TypeError, ValueError) as e:
            error_msg = f"Invalid workflow data structure: {e}"
            logger.error(f"{error_msg} (file: {workflow_file})")
            raise WorkflowValidationError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="INVALID_DATA_STRUCTURE"
            ) from e
        except WorkflowValidationError:
            # Re-raise workflow validation errors as-is
            raise
        except Exception as e:
            error_msg = f"Unexpected error creating WorkflowInfo: {e}"
            log_exception(logger, error_msg, e)
            raise WorkflowValidationError(
                error_msg,
                workflow_path=str(workflow_file),
                error_code="WORKFLOW_CREATION_FAILED"
            ) from e

    def _should_rescan(self) -> bool:
        """
        Check if workflows should be rescanned due to time elapsed or file changes.
        
        Returns:
            True if rescan is needed
        """
        if self._last_scan_time is None:
            return True
        
        elapsed = (datetime.now() - self._last_scan_time).total_seconds()
        return elapsed > self._scan_interval_seconds
    
    def refresh_workflows(self) -> None:
        """Force refresh of workflow cache from disk."""
        logger.info("Forcing workflow refresh")
        self._load_workflows()
    
    def get_available_workflows(
        self,
        *,
        categories: Optional[Iterable[str]] = None,
        taxonomy_only: bool = False,
    ) -> List[WorkflowInfo]:
        """
        Get list of all available workflows.
        
        Returns:
            List of WorkflowInfo objects for all loaded workflows
        """
        if self._should_rescan():
            self._load_workflows()

        workflows = list(self._workflow_cache.values())

        if taxonomy_only:
            workflows = [workflow for workflow in workflows if workflow.is_taxonomy()]

        if categories:
            category_set = {category.lower() for category in categories}
            workflows = [
                workflow
                for workflow in workflows
                if workflow.category and workflow.category.lower() in category_set
            ]

        return workflows
    
    def find_matching_workflows(
        self,
        issue_labels: List[str],
        *,
        categories: Optional[Iterable[str]] = None,
    ) -> List[WorkflowInfo]:
        """
        Find all workflows that match the given issue labels.
        
        Args:
            issue_labels: List of labels from a GitHub issue
            
        Returns:
            List of matching WorkflowInfo objects
        """
        if self._should_rescan():
            self._load_workflows()
        
        # Must have site-monitor label to be processed
        if 'site-monitor' not in issue_labels:
            logger.debug("Issue missing 'site-monitor' label, no workflows matched")
            return []
        
        issue_label_set = set(issue_labels)

        taxonomy_matches: List[WorkflowInfo] = []
        legacy_matches: List[WorkflowInfo] = []
        
        for workflow_info in self._workflow_cache.values():
            trigger_set = set(workflow_info.trigger_labels)
            
            # Check if any trigger labels match issue labels
            if trigger_set.intersection(issue_label_set):
                intersection = list(trigger_set.intersection(issue_label_set))
                logger.debug(
                    "Workflow '%s' matches labels: %s",
                    workflow_info.name,
                    intersection,
                )
                if workflow_info.is_taxonomy():
                    taxonomy_matches.append(workflow_info)
                else:
                    legacy_matches.append(workflow_info)

        if categories:
            category_set = {category.lower() for category in categories}
            taxonomy_matches = [
                workflow
                for workflow in taxonomy_matches
                if workflow.category and workflow.category.lower() in category_set
            ]
            legacy_matches = [
                workflow
                for workflow in legacy_matches
                if workflow.category and workflow.category.lower() in category_set
            ]

        if taxonomy_matches:
            if legacy_matches:
                logger.debug(
                    "Ignoring %d legacy workflow match(es) in favor of taxonomy-aligned definitions",
                    len(legacy_matches),
                )
            logger.info(
                "Found %d taxonomy workflow(s) for labels: %s",
                len(taxonomy_matches),
                issue_labels,
            )
            return taxonomy_matches

        logger.info(
            "Found %d legacy workflow(s) for labels: %s",
            len(legacy_matches),
            issue_labels,
        )
        return legacy_matches
    
    def get_best_workflow_match(
        self,
        issue_labels: List[str],
        *,
        categories: Optional[Iterable[str]] = None,
    ) -> Tuple[Optional[WorkflowInfo], str]:
        """
        Get the best single workflow match for the given labels.
        
        Args:
            issue_labels: List of labels from a GitHub issue
            
        Returns:
            Tuple of (WorkflowInfo, status_message)
            - WorkflowInfo is None if no clear match
            - status_message explains the result
        """
        matching_workflows = self.find_matching_workflows(issue_labels, categories=categories)
        
        if not matching_workflows:
            if 'site-monitor' not in issue_labels:
                return None, "Issue must have 'site-monitor' label to be processed"
            else:
                return None, "No workflows match the current labels. Add specific workflow labels."
        
        if len(matching_workflows) == 1:
            workflow = matching_workflows[0]
            return workflow, f"Selected workflow: {workflow.name}"
        
        # Multiple matches - need clarification
        workflow_names = [w.name for w in matching_workflows]
        message = (
            "Multiple workflows match ("
            f"{', '.join(workflow_names)}). "
            "Enable multi-workflow processing with the --allow-multi-workflow flag "
            "or set agent.processing.enable_multi_workflow: true to run all applicable workflows."
        )
        return None, message
    
    def get_workflow_plan(
        self,
        issue_labels: List[str],
        *,
        categories: Optional[Iterable[str]] = None,
    ) -> WorkflowPlan:
        """Return the set of workflow candidates for the provided labels."""

        matching_workflows = self.find_matching_workflows(issue_labels, categories=categories)

        if not matching_workflows:
            message = (
                "Issue must have 'site-monitor' label to be processed"
                if 'site-monitor' not in issue_labels
                else "No workflows match the current labels. Add specific workflow labels."
            )
            return WorkflowPlan(
                issue_labels=tuple(issue_labels),
                candidates=(),
                selection_reason="no_match",
                selection_message=message,
            )

        # Build deterministic candidates list
        sorted_workflows = sorted(
            matching_workflows,
            key=lambda wf: (
                self._resolve_candidate_priority(wf),
                wf.name.lower(),
            ),
        )

        candidates: List[WorkflowCandidate] = []
        for workflow in sorted_workflows:
            candidate = WorkflowCandidate(
                workflow_info=workflow,
                priority=self._resolve_candidate_priority(workflow),
                conflict_keys=self._extract_conflict_keys(workflow),
                dependencies=tuple(self._extract_dependencies(workflow)),
            )
            candidates.append(candidate)

        if len(candidates) == 1:
            reason = "single_match"
            message = f"Selected workflow: {candidates[0].name}"
        else:
            reason = "multiple_matches"
            workflow_names = ", ".join(candidate.name for candidate in candidates)
            message = (
                "Multiple workflows match the current labels. "
                f"Execution plan includes: {workflow_names}."
            )

        return WorkflowPlan(
            issue_labels=tuple(issue_labels),
            candidates=tuple(candidates),
            selection_reason=reason,
            selection_message=message,
        )

    @staticmethod
    def _resolve_candidate_priority(workflow_info: WorkflowInfo) -> int:
        """Resolve a deterministic priority value for a workflow."""

        raw_priority = workflow_info.priority or workflow_info.metadata.get("priority")
        if raw_priority is None:
            return 100

        try:
            return int(raw_priority)
        except (TypeError, ValueError):
            return 100

    @staticmethod
    def _extract_conflict_keys(workflow_info: WorkflowInfo) -> frozenset[str]:
        """Generate conflict keys used for execution planning heuristics."""

        keys: Set[str] = set()

        output_config = workflow_info.output or {}
        folder_structure = output_config.get("folder_structure")
        if folder_structure:
            keys.add(f"folder:{folder_structure}")

        file_pattern = output_config.get("file_pattern")
        if file_pattern:
            keys.add(f"file_pattern:{file_pattern}")

        for deliverable in workflow_info.deliverables:
            name = deliverable.get("name")
            if name:
                keys.add(f"deliverable:{name}")

            template = deliverable.get("template")
            if template:
                keys.add(f"template:{template}")

        if workflow_info.category:
            keys.add(f"category:{workflow_info.category.lower()}")

        if workflow_info.legacy_mode:
            keys.add("mode:legacy")

        return frozenset(keys)

    @staticmethod
    def _extract_dependencies(workflow_info: WorkflowInfo) -> List[str]:
        """Extract declared workflow dependencies from metadata, if any."""

        metadata = workflow_info.metadata or {}
        dependencies = metadata.get("dependencies", [])
        if not isinstance(dependencies, list):
            return []

        cleaned = [dep for dep in dependencies if isinstance(dep, str) and dep.strip()]
        return [dep.strip() for dep in cleaned]

    def get_workflow_by_name(self, workflow_name: str) -> Optional[WorkflowInfo]:
        """
        Get a specific workflow by name.
        
        Args:
            workflow_name: Name of the workflow to find
            
        Returns:
            WorkflowInfo if found, None otherwise
        """
        if self._should_rescan():
            self._load_workflows()
        
        for workflow_info in self._workflow_cache.values():
            if workflow_info.name == workflow_name:
                return workflow_info
        
        return None

    def get_workflow_by_slug(self, workflow_slug: str) -> Optional[WorkflowInfo]:
        """Return workflow info matching the provided slug identifier."""

        if self._should_rescan():
            self._load_workflows()

        slug = (workflow_slug or "").lower().strip()
        if not slug:
            return None

        for workflow_info in self._workflow_cache.values():
            if self._slugify_name(workflow_info.name) == slug:
                return workflow_info

        return None
    
    def get_workflow_suggestions(
        self,
        issue_labels: List[str],
        *,
        categories: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """
        Get suggestions for workflow labels based on current issue labels.
        
        Args:
            issue_labels: Current labels on the issue
            
        Returns:
            List of suggested labels that could help with workflow selection
        """
        if self._should_rescan():
            self._load_workflows()
        
        issue_label_set = set(issue_labels)
        suggestions = set()
        
        # Collect all trigger labels from workflows
        category_set = {category.lower() for category in categories} if categories else None

        for workflow_info in self._workflow_cache.values():
            if category_set:
                category_value = (workflow_info.category or '').lower()
                if category_value not in category_set:
                    continue
            for trigger_label in workflow_info.trigger_labels:
                if trigger_label not in issue_label_set:
                    suggestions.add(trigger_label)
        
        return sorted(list(suggestions))
    
    def validate_workflow_directory(self) -> Tuple[bool, List[str]]:
        """
        Validate the workflow directory and all workflow files.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if not self.workflow_directory.exists():
            errors.append(f"Workflow directory does not exist: {self.workflow_directory}")
            return False, errors
        
        workflow_files = list(self.workflow_directory.glob("*.yaml")) + list(self.workflow_directory.glob("*.yml"))
        
        if not workflow_files:
            errors.append(f"No workflow files found in {self.workflow_directory}")
            return False, errors
        
        for workflow_file in workflow_files:
            try:
                self._parse_workflow_file(workflow_file)
            except Exception as e:
                errors.append(f"Invalid workflow file {workflow_file}: {e}")
        
        # Check for duplicate workflow names
        workflow_names = [info.name for info in self._workflow_cache.values()]
        duplicate_names = set([name for name in workflow_names if workflow_names.count(name) > 1])
        
        if duplicate_names:
            errors.append(f"Duplicate workflow names found: {', '.join(duplicate_names)}")
        
        # Check for conflicting trigger labels
        label_to_workflows = {}
        for workflow_info in self._workflow_cache.values():
            for label in workflow_info.trigger_labels:
                if label not in label_to_workflows:
                    label_to_workflows[label] = []
                label_to_workflows[label].append(workflow_info.name)
        
        conflicting_labels = {label: workflows for label, workflows in label_to_workflows.items() 
                            if len(workflows) > 1}
        
        if conflicting_labels:
            for label, workflows in conflicting_labels.items():
                errors.append(f"Label '{label}' triggers multiple workflows: {', '.join(workflows)}")
        
        return len(errors) == 0, errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the workflow matcher state.
        
        Returns:
            Dictionary with statistics
        """
        if self._should_rescan():
            self._load_workflows()
        
        total_workflows = len(self._workflow_cache)
        total_trigger_labels = len(set(label for workflow in self._workflow_cache.values() 
                                     for label in workflow.trigger_labels))
        total_deliverables = sum(len(workflow.deliverables) for workflow in self._workflow_cache.values())
        
        workflow_by_deliverable_count = {}
        for workflow in self._workflow_cache.values():
            count = len(workflow.deliverables)
            if count not in workflow_by_deliverable_count:
                workflow_by_deliverable_count[count] = 0
            workflow_by_deliverable_count[count] += 1
        
        return {
            'total_workflows': total_workflows,
            'total_trigger_labels': total_trigger_labels,
            'total_deliverables': total_deliverables,
            'workflow_directory': str(self.workflow_directory),
            'last_scan_time': self._last_scan_time.isoformat() if self._last_scan_time else None,
            'workflows_by_deliverable_count': workflow_by_deliverable_count,
            'workflow_names': [w.name for w in self._workflow_cache.values()]
        }