"""
Processing orchestrator for coordinating batch operations.

This module provides high-level orchestration functions that coordinate
between IssueProcessor and BatchProcessor without creating circular dependencies.
"""

from typing import Dict, List, Optional, Tuple, Any, Iterable
from .batch_processor import BatchProcessor, BatchConfig, BatchProgressReporter
from ..utils.telemetry import TelemetryPublisher, normalize_publishers


class ProcessingOrchestrator:
    """
    Orchestrator for coordinating batch processing operations.
    
    This class separates the concerns of issue processing and batch coordination,
    eliminating circular dependencies while providing convenient high-level APIs.
    """
    
    def __init__(
        self,
        issue_processor,
        telemetry_publishers: Optional[Iterable[TelemetryPublisher]] = None,
    ):
        """
        Initialize processing orchestrator.
        
        Args:
            issue_processor: GitHub-integrated issue processor instance
        """
        self.issue_processor = issue_processor
        self.telemetry_publishers = normalize_publishers(telemetry_publishers)
    
    def process_batch(self, 
                     issue_numbers: List[int],
                     batch_size: int = 10,
                     dry_run: bool = False,
                     filters: Optional[Dict[str, Any]] = None) -> Tuple[Any, List[Any]]:
        """
        Process multiple issues in batches.
        
        Args:
            issue_numbers: List of issue numbers to process
            batch_size: Maximum issues per batch
            dry_run: If True, only analyze what would be processed
            filters: Additional filtering criteria
            
        Returns:
            Tuple of (batch metrics, list of processing results)
        """
        # Configure batch processing
        batch_config = BatchConfig(
            max_batch_size=batch_size,
            max_concurrent_workers=min(3, batch_size),
            include_assigned=filters.get('include_assigned', False) if filters else False
        )
        
        # Create progress reporter
        progress_reporter = BatchProgressReporter(verbose=True)
        
        # Create batch processor
        batch_processor = BatchProcessor(
            issue_processor=self.issue_processor,
            github_client=self.issue_processor.github,
            config=batch_config,
            progress_reporter=progress_reporter,
            telemetry_publishers=self.telemetry_publishers,
        )
        
        # Process the batch
        return batch_processor.process_issues(issue_numbers, dry_run=dry_run)
    
    def process_all_site_monitor_issues(self,
                                       batch_size: int = 10,
                                       dry_run: bool = False,
                                       assignee_filter: Optional[str] = None,
                                       additional_labels: Optional[List[str]] = None) -> Tuple[Any, List[Any]]:
        """
        Process all open issues with site-monitor label.
        
        Args:
            batch_size: Maximum issues per batch
            dry_run: If True, only analyze what would be processed
            assignee_filter: Filter by assignee ('none' for unassigned, username for specific user)
            additional_labels: Additional labels that must be present
            
        Returns:
            Tuple of (batch metrics, list of processing results)
        """
        # Build filters
        filters = {}
        if assignee_filter:
            filters['assignee'] = assignee_filter
        if additional_labels:
            filters['additional_labels'] = additional_labels
        
        # Configure batch processing
        batch_config = BatchConfig(
            max_batch_size=batch_size,
            max_concurrent_workers=min(3, batch_size),
            include_assigned=assignee_filter is not None and assignee_filter != 'none'
        )
        
        # Create progress reporter
        progress_reporter = BatchProgressReporter(verbose=True)
        
        # Create batch processor
        batch_processor = BatchProcessor(
            issue_processor=self.issue_processor,
            github_client=self.issue_processor.github,
            config=batch_config,
            progress_reporter=progress_reporter,
            telemetry_publishers=self.telemetry_publishers,
        )
        
        # Process all site-monitor issues
        return batch_processor.process_site_monitor_issues(filters=filters, dry_run=dry_run)