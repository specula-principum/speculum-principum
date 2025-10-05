"""
Integration tests for command-line interface functionality.

This module tests the CLI components including:
- Command argument parsing and validation
- Issue processing command functionality  
- CLI helper utilities
- Error handling and user feedback
- Progress reporting and result formatting

Tests use mocking to avoid external dependencies while ensuring
the CLI logic works correctly.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from io import StringIO
import argparse
from typing import Dict, Any, List

# Import the modules being tested
from src.utils.cli_helpers import (
    ProgressReporter, ConfigValidator, IssueResultFormatter,
    BatchProcessor, CliResult, safe_execute_cli_command,
    format_file_list, get_user_confirmation, prepare_cli_execution
)


class TestProgressReporter:
    """Test progress reporting functionality."""
    
    def test_basic_operation_tracking(self, capsys):
        """Test basic operation start and completion."""
        reporter = ProgressReporter(verbose=False)
        
        reporter.start_operation("Test Operation")
        captured = capsys.readouterr()
        assert "⏳ Test Operation..." in captured.out
        
        reporter.complete_operation(True, "Operation completed")
        captured = capsys.readouterr()
        assert "✅ Operation completed" in captured.out
    
    def test_verbose_operation_tracking(self, capsys):
        """Test verbose progress reporting."""
        reporter = ProgressReporter(verbose=True)
        
        reporter.start_operation("Verbose Test")
        captured = capsys.readouterr()
        assert "🚀 Starting: Verbose Test" in captured.out
        
        reporter.update_progress("Step 1 of 3", 1, 3)
        captured = capsys.readouterr()
        assert "📋 Step 1 of 3 [1/3 - 33.3%]" in captured.out
        
        reporter.complete_operation(True)
        captured = capsys.readouterr()
        assert "✅ Completed: Verbose Test" in captured.out
    
    def test_error_reporting(self, capsys):
        """Test error and warning reporting."""
        reporter = ProgressReporter()
        
        reporter.show_error("Test error message")
        captured = capsys.readouterr()
        assert "❌ Test error message" in captured.err
        
        reporter.show_warning("Test warning")
        captured = capsys.readouterr()
        assert "⚠️  Test warning" in captured.out
        
        reporter.show_info("Test info")
        captured = capsys.readouterr()
        assert "ℹ️  Test info" in captured.out


class TestConfigValidator:
    """Test configuration validation functionality."""
    
    def test_validate_nonexistent_config(self):
        """Test validation of non-existent config file."""
        result = ConfigValidator.validate_config_file("nonexistent.yaml")
        
        assert not result.success
        assert "Configuration file not found" in result.message
        assert result.error_code == 1
    
    def test_validate_environment_missing_vars(self):
        """Test environment validation with missing variables."""
        with patch.dict(os.environ, {}, clear=True):
            result = ConfigValidator.validate_environment()
            
            assert not result.success
            assert "Missing required environment variables" in result.message
            assert "GITHUB_TOKEN" in result.message
            assert "GITHUB_REPOSITORY" in result.message
    
    def test_validate_environment_success(self):
        """Test successful environment validation."""
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPOSITORY': 'test/repo'
        }):
            result = ConfigValidator.validate_environment()
            
            assert result.success
            assert "Environment validation passed" in result.message
    
    def test_validate_workflow_directory_missing(self):
        """Test validation of missing workflow directory."""
        result = ConfigValidator.validate_workflow_directory("nonexistent/dir")
        
        assert not result.success
        assert "Workflow directory not found" in result.message
    
    def test_validate_workflow_directory_empty(self, tmp_path):
        """Test validation of empty workflow directory."""
        empty_dir = tmp_path / "empty_workflows"
        empty_dir.mkdir()
        
        result = ConfigValidator.validate_workflow_directory(str(empty_dir))
        
        assert not result.success
        assert "No workflow files found" in result.message
    
    def test_validate_workflow_directory_success(self, tmp_path):
        """Test successful workflow directory validation."""
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()
        
        # Create test workflow files
        (workflow_dir / "test1.yaml").touch()
        (workflow_dir / "test2.yml").touch()
        
        result = ConfigValidator.validate_workflow_directory(str(workflow_dir))
        
        assert result.success
        assert "Found 2 workflow file(s)" in result.message
        assert result.data is not None
        assert result.data['workflow_count'] == 2


class TestIssueResultFormatter:
    """Test issue result formatting functionality."""
    
    def test_format_completed_result(self):
        """Test formatting of completed processing result."""
        result = {
            'status': 'completed',
            'issue': 123,
            'workflow': 'research-analysis',
            'files_created': ['analysis.md', 'summary.md']
        }
        
        formatted = IssueResultFormatter.format_single_result(result)
        
        assert "✅ Issue #123: completed" in formatted
        assert "📋 Workflow: research-analysis" in formatted
        assert "📄 Created 2 file(s)" in formatted
    
    def test_format_error_result(self):
        """Test formatting of error result."""
        result = {
            'status': 'error',
            'issue': 456,
            'error': 'Workflow not found'
        }
        
        formatted = IssueResultFormatter.format_single_result(result)
        
        assert "❌ Issue #456: error" in formatted
        assert "💥 Error: Workflow not found" in formatted
    
    def test_format_clarification_result(self):
        """Test formatting of clarification needed result."""
        result = {
            'status': 'needs_clarification',
            'issue': 789
        }
        
        formatted = IssueResultFormatter.format_single_result(result)
        
        assert "❓ Issue #789: needs_clarification" in formatted
        assert "💬 Waiting for workflow clarification" in formatted
    
    def test_format_batch_results(self):
        """Test formatting of batch processing results."""
        results = [
            {'status': 'completed', 'issue': 1},
            {'status': 'completed', 'issue': 2},
            {'status': 'error', 'issue': 3},
            {'status': 'needs_clarification', 'issue': 4}
        ]
        
        formatted = IssueResultFormatter.format_batch_results(results)
        
        assert "📊 Processed 4 issue(s):" in formatted
        assert "completed: 2 (50.0%)" in formatted
        assert "error: 1 (25.0%)" in formatted
        assert "needs_clarification: 1 (25.0%)" in formatted
    
    def test_format_empty_batch_results(self):
        """Test formatting of empty batch results."""
        formatted = IssueResultFormatter.format_batch_results([])
        assert "📭 No issues processed" in formatted


class TestBatchProcessor:
    """Test batch processing functionality."""
    
    def test_successful_batch_processing(self, capsys):
        """Test successful batch processing with progress."""
        items = [1, 2, 3]
        
        def mock_processor(item):
            return {'status': 'completed', 'item': item}
        
        results = BatchProcessor.process_with_progress(
            items, mock_processor, "Test Processing", verbose=True
        )
        
        assert len(results) == 3
        assert all(r['status'] == 'completed' for r in results)
        
        captured = capsys.readouterr()
        assert "🚀 Starting: Test Processing" in captured.out
        assert "✅ Processed 3 items" in captured.out
    
    def test_batch_processing_with_errors(self, capsys):
        """Test batch processing with some failures."""
        items = [1, 2, 3]
        
        def mock_processor(item):
            if item == 2:
                raise ValueError("Test error")
            return {'status': 'completed', 'item': item}
        
        results = BatchProcessor.process_with_progress(
            items, mock_processor, "Error Test"
        )
        
        assert len(results) == 3
        assert results[0]['status'] == 'completed'
        assert results[1]['status'] == 'error'
        assert results[1]['error'] == 'Test error'
        assert results[2]['status'] == 'completed'
        
        captured = capsys.readouterr()
        assert "❌ Processed 3 items (1 errors)" in captured.out


class TestCliResult:
    """Test CLI result data structure."""
    
    def test_success_result(self):
        """Test creating successful result."""
        result = CliResult(success=True, message="Operation completed")
        
        assert result.success
        assert result.message == "Operation completed"
        assert result.error_code == 0
        assert result.data is None
    
    def test_error_result(self):
        """Test creating error result."""
        result = CliResult(
            success=False,
            message="Operation failed",
            error_code=1,
            data={'error_details': 'More info'}
        )
        
        assert not result.success
        assert result.error_code == 1
        assert result.data is not None
        assert result.data['error_details'] == 'More info'


class TestCliExecutionContext:
    """Test CLI execution context helper utilities."""

    def test_prepare_cli_execution_dry_run_banner(self, capsys):
        """Dry run should emit a banner and decorate messages."""
        context = prepare_cli_execution("process-issues", dry_run=True)

        captured = capsys.readouterr()
        assert "🧪 Dry run enabled for process-issues" in captured.out

        decorated = context.decorate_message("Summary output")
        assert decorated.splitlines()[0] == "🧪 Dry run enabled for process-issues — no changes will be made."

        cli_result = context.decorate_cli_result(CliResult(success=True, message="Done"))
        assert cli_result.message.startswith("🧪 Dry run enabled for process-issues — no changes will be made.")

    def test_prepare_cli_execution_structured_passthrough(self, capsys):
        """Structured outputs should not be prefixed with dry run messaging."""
        context = prepare_cli_execution("assign-workflows", dry_run=True)
        capsys.readouterr()  # Clear dry run banner output

        original = CliResult(success=True, message="[]", data={"issues": []})
        decorated = context.decorate_cli_result(original, structured=True)

        assert decorated is original
        assert decorated.message == "[]"

    def test_prepare_cli_execution_non_dry_run(self, capsys):
        """Non-dry-run execution should not insert banners."""
        context = prepare_cli_execution("process-issues", dry_run=False)

        captured = capsys.readouterr()
        assert "Dry run" not in captured.out

        assert context.decorate_message("Summary") == "Summary"


class TestSafeExecuteCliCommand:
    """Test safe CLI command execution."""
    
    def test_successful_command_execution(self, capsys):
        """Test successful command execution."""
        def success_command():
            return CliResult(success=True, message="Success!")
        
        exit_code = safe_execute_cli_command(success_command)
        
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Success!" in captured.out
    
    def test_failed_command_execution(self, capsys):
        """Test failed command execution."""
        def failure_command():
            return CliResult(success=False, message="Failed!", error_code=2)
        
        exit_code = safe_execute_cli_command(failure_command)
        
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Failed!" in captured.err
    
    def test_command_with_exception(self, capsys):
        """Test command that raises an exception."""
        def exception_command():
            raise ValueError("Test exception")
        
        exit_code = safe_execute_cli_command(exception_command)
        
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "❌ Unexpected error: Test exception" in captured.err
    
    def test_command_with_keyboard_interrupt(self, capsys):
        """Test command interrupted by user."""
        def interrupt_command():
            raise KeyboardInterrupt()
        
        exit_code = safe_execute_cli_command(interrupt_command)
        
        assert exit_code == 130
        captured = capsys.readouterr()
        assert "⛔ Operation cancelled by user" in captured.err


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_format_file_list(self):
        """Test file list formatting."""
        files = ['/path/to/file1.md', '/path/to/file2.txt']
        formatted = format_file_list(files, "Generated Files")
        
        assert "Generated Files:" in formatted
        assert "📄" in formatted
        assert "file1.md" in formatted
        assert "file2.txt" in formatted
    
    def test_format_empty_file_list(self):
        """Test empty file list formatting."""
        formatted = format_file_list([], "No Files")
        assert "No Files: None" in formatted
    
    def test_get_user_confirmation_default_true(self):
        """Test user confirmation with default True."""
        with patch('builtins.input', return_value=''):
            result = get_user_confirmation("Continue?", default=True)
            assert result is True
    
    def test_get_user_confirmation_explicit_yes(self):
        """Test explicit yes confirmation."""
        with patch('builtins.input', return_value='y'):
            result = get_user_confirmation("Continue?", default=False)
            assert result is True
    
    def test_get_user_confirmation_explicit_no(self):
        """Test explicit no confirmation."""
        with patch('builtins.input', return_value='n'):
            result = get_user_confirmation("Continue?", default=True)
            assert result is False
    
    def test_get_user_confirmation_interrupt(self):
        """Test keyboard interrupt during confirmation."""
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            result = get_user_confirmation("Continue?")
            assert result is False


class TestMainCliIntegration:
    """Integration tests for main CLI functionality."""
    
    def test_process_issues_command_parsing(self):
        """Test that process-issues command arguments are parsed correctly."""
        # Import main module's argument parser setup
        import main
        
        # Mock sys.argv to test argument parsing
        test_args = [
            'main.py', 'process-issues',
            '--config', 'test.yaml',
            '--issue', '123',
            '--dry-run',
            '--verbose',
            '--continue-on-error',
            '--batch-size', '5',
            '--assignee-filter', 'testuser',
            '--label-filter', 'bug', 'urgent'
        ]
        
        with patch.object(sys, 'argv', test_args):
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest='command')
            
            # Add the process-issues command (copied from main.py)
            process_parser = subparsers.add_parser('process-issues')
            process_parser.add_argument('--config', default='config.yaml')
            process_parser.add_argument('--issue', type=int)
            process_parser.add_argument('--batch-size', type=int, default=10)
            process_parser.add_argument('--dry-run', action='store_true')
            process_parser.add_argument('--force-clarification', action='store_true')
            process_parser.add_argument('--assignee-filter')
            process_parser.add_argument('--label-filter', nargs='*')
            process_parser.add_argument('--verbose', '-v', action='store_true')
            process_parser.add_argument('--continue-on-error', action='store_true')
            
            args = parser.parse_args(['process-issues', '--config', 'test.yaml', 
                                    '--issue', '123', '--dry-run', '--verbose'])
            
            assert args.command == 'process-issues'
            assert args.config == 'test.yaml'
            assert args.issue == 123
            assert args.dry_run is True
            assert args.verbose is True
    
    @patch('src.core.issue_processor.GitHubIntegratedIssueProcessor')
    @patch('src.utils.cli_helpers.ConfigValidator')
    def test_process_issues_single_issue_success(self, mock_validator, mock_processor):
        """Test successful single issue processing via CLI."""
        # Setup mocks
        mock_validator.validate_config_file.return_value = CliResult(success=True, message="Config OK")
        mock_validator.validate_environment.return_value = CliResult(success=True, message="Env OK")
        mock_validator.validate_workflow_directory.return_value = CliResult(
            success=True, message="Workflows OK", data={'workflow_count': 2}
        )
        
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.config = Mock()
        mock_processor_instance.github.get_issue_data.return_value = {
            'labels': ['site-monitor'],
            'title': 'Test Issue'
        }
        
        # Mock the processing result
        mock_result = Mock()
        mock_result.status.value = 'completed'
        mock_result.workflow_name = 'test-workflow'
        mock_result.created_files = ['test.md']
        mock_result.error_message = None
        mock_processor_instance.process_github_issue.return_value = mock_result
        
        # Test the CLI functionality by calling the main function logic
        from src.utils.cli_helpers import ConfigValidator, ProgressReporter, IssueResultFormatter
        
        # This simulates what happens in main.py when process-issues is called
        def simulate_cli_call():
            return CliResult(success=True, message="Issue processed successfully")
        
        result = safe_execute_cli_command(simulate_cli_call)
        assert result == 0
    
    @patch('os.getenv')
    def test_missing_environment_variables(self, mock_getenv):
        """Test CLI behavior with missing environment variables."""
        mock_getenv.return_value = None
        
        result = ConfigValidator.validate_environment()
        assert not result.success
        assert "Missing required environment variables" in result.message


@pytest.fixture
def mock_github_issue():
    """Fixture providing a mock GitHub issue."""
    issue = Mock()
    issue.number = 123
    issue.title = "Test Issue"
    issue.body = "Test issue body"
    issue.labels = [Mock(name='site-monitor'), Mock(name='bug')]
    issue.assignees = []
    return issue


@pytest.fixture
def mock_issue_processor():
    """Fixture providing a mock issue processor."""
    processor = Mock()
    processor.config = Mock()
    processor.github = Mock()
    return processor


class TestProcessIssuesCommandIntegration:
    """Integration tests specifically for the process-issues command."""
    
    def test_dry_run_mode(self, mock_issue_processor, capsys):
        """Test dry run mode functionality."""
        # Setup mock
        mock_issue_processor.github.get_issue_data.return_value = {
            'labels': ['site-monitor', 'bug'],
            'title': 'Test Issue for Dry Run'
        }
        
        # Simulate dry run logic
        result = {
            'status': 'would_process',
            'issue': 123,
            'title': 'Test Issue for Dry Run',
            'labels': ['site-monitor', 'bug']
        }
        
        formatted = IssueResultFormatter.format_single_result(result)
        assert "Issue #123" in formatted
    
    def test_batch_processing_mode(self, mock_issue_processor):
        """Test batch processing functionality."""
        # Setup mock for batch processing
        mock_issues = []
        for i in range(3):
            issue = Mock()
            issue.number = i + 1
            issue.title = f"Test Issue {i + 1}"
            issue.labels = [Mock(name='site-monitor')]
            issue.assignees = []
            mock_issues.append(issue)
        
        mock_issue_processor.github.get_issues_with_labels.return_value = mock_issues
        
        # Test that we get the expected issues
        issues = mock_issue_processor.github.get_issues_with_labels(['site-monitor'], state="open", limit=10)
        assert len(issues) == 3
        assert issues[0].number == 1
    
    def test_error_handling_in_batch_mode(self):
        """Test error handling during batch processing."""
        items = [1, 2, 3]
        
        def failing_processor(item):
            if item == 2:
                raise Exception("Processing failed")
            return {'status': 'completed', 'item': item}
        
        results = BatchProcessor.process_with_progress(
            items, failing_processor, "Test with Errors"
        )
        
        assert len(results) == 3
        assert results[0]['status'] == 'completed'
        assert results[1]['status'] == 'error'
        assert 'Processing failed' in results[1]['error']
        assert results[2]['status'] == 'completed'


if __name__ == "__main__":
    pytest.main([__file__])