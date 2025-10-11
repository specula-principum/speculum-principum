"""
Unit tests for WorkflowSchemaValidator module
"""

from copy import deepcopy

import pytest

from src.workflow.workflow_schemas import WorkflowSchemaValidator


@pytest.fixture(autouse=True)
def reset_schema_validator_state():
    """Ensure schema validator mutations don't leak between tests."""

    original_profiles = deepcopy(WorkflowSchemaValidator.SCHEMA_PROFILES)
    original_default = WorkflowSchemaValidator.DEFAULT_SCHEMA_PROFILE
    original_initialized = WorkflowSchemaValidator.PROFILES_INITIALIZED
    original_categories = set(WorkflowSchemaValidator.TAXONOMY_CATEGORIES)
    original_priorities = set(WorkflowSchemaValidator.PRIORITY_LEVELS)
    original_properties = deepcopy(WorkflowSchemaValidator.WORKFLOW_SCHEMA["properties"])

    WorkflowSchemaValidator.SCHEMA_PROFILES = deepcopy(original_profiles)
    WorkflowSchemaValidator.DEFAULT_SCHEMA_PROFILE = original_default
    WorkflowSchemaValidator.PROFILES_INITIALIZED = False
    WorkflowSchemaValidator.TAXONOMY_CATEGORIES = set(original_categories)
    WorkflowSchemaValidator.PRIORITY_LEVELS = set(original_priorities)
    WorkflowSchemaValidator.WORKFLOW_SCHEMA["properties"] = deepcopy(original_properties)
    WorkflowSchemaValidator._refresh_schema_enums()

    yield

    WorkflowSchemaValidator.SCHEMA_PROFILES = original_profiles
    WorkflowSchemaValidator.DEFAULT_SCHEMA_PROFILE = original_default
    WorkflowSchemaValidator.PROFILES_INITIALIZED = original_initialized
    WorkflowSchemaValidator.TAXONOMY_CATEGORIES = original_categories
    WorkflowSchemaValidator.PRIORITY_LEVELS = original_priorities
    WorkflowSchemaValidator.WORKFLOW_SCHEMA["properties"] = original_properties
    WorkflowSchemaValidator._refresh_schema_enums()


class TestWorkflowSchemaValidator:
    """Test cases for WorkflowSchemaValidator class"""
    
    def test_validate_workflow_valid_minimal(self):
        """Test validation of minimal valid workflow"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_workflow_valid_complete(self):
        """Test validation of complete valid workflow"""
        workflow_data = {
            'name': 'Complete Test Workflow',
            'description': 'A complete test workflow',
            'version': '1.0.0',
            'trigger_labels': ['test', 'complete'],
            'deliverables': [
                {
                    'name': 'overview',
                    'title': 'Overview',
                    'description': 'Overview deliverable',
                    'template': 'overview.md',
                    'required': True,
                    'order': 1
                },
                {
                    'name': 'details',
                    'title': 'Details',
                    'description': 'Details deliverable',
                    'template': 'details.md',
                    'required': False,
                    'order': 2
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_workflow_missing_required_fields(self):
        """Test validation with missing required fields"""
        # Missing name
        workflow_data = {
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert len(errors) > 0
        assert any("'name'" in error for error in errors)
        
        # Missing trigger_labels
        workflow_data = {
            'name': 'Test Workflow',
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("'trigger_labels'" in error for error in errors)
        
        # Missing deliverables
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test']
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("'deliverables'" in error for error in errors)
    
    def test_validate_workflow_empty_arrays(self):
        """Test validation with empty required arrays"""
        # Empty trigger_labels
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': [],  # Empty array
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("minItems" in error or "trigger_labels" in error for error in errors)
        
        # Empty deliverables
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': []  # Empty array
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("minItems" in error or "deliverables" in error for error in errors)
    
    def test_validate_workflow_invalid_version_format(self):
        """Test validation with invalid version format"""
        workflow_data = {
            'name': 'Test Workflow',
            'version': 'invalid-version',  # Invalid semantic version
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("pattern" in error.lower() or "version" in error for error in errors)
    
    def test_validate_workflow_invalid_trigger_labels(self):
        """Test validation with invalid trigger label format"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['invalid label with spaces'],  # Invalid format
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("does not match" in error for error in errors)
    
    def test_validate_workflow_invalid_deliverable_name(self):
        """Test validation with invalid deliverable name format"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'invalid name with spaces',  # Invalid format
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("does not match" in error for error in errors)
    
    def test_validate_workflow_missing_deliverable_fields(self):
        """Test validation with missing deliverable required fields"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    # Missing 'title' and 'description'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("'title'" in error for error in errors)
        # Note: jsonschema only reports the first missing field, so we might not see description error
    
    def test_validate_workflow_duplicate_deliverable_names(self):
        """Test validation with duplicate deliverable names"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'duplicate-name',
                    'title': 'First Deliverable',
                    'description': 'First deliverable'
                },
                {
                    'name': 'duplicate-name',  # Duplicate name
                    'title': 'Second Deliverable',
                    'description': 'Second deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("Duplicate deliverable names" in error for error in errors)
    
    def test_validate_workflow_duplicate_deliverable_orders(self):
        """Test validation with duplicate deliverable orders"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test'],
            'deliverables': [
                {
                    'name': 'first-deliverable',
                    'title': 'First Deliverable',
                    'description': 'First deliverable',
                    'order': 1
                },
                {
                    'name': 'second-deliverable',
                    'title': 'Second Deliverable',
                    'description': 'Second deliverable',
                    'order': 1  # Duplicate order
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("Duplicate deliverable orders" in error for error in errors)
    
    def test_validate_workflow_site_monitor_in_trigger_labels(self):
        """Test validation with 'site-monitor' in trigger labels"""
        workflow_data = {
            'name': 'Test Workflow',
            'trigger_labels': ['test', 'site-monitor'],  # Should not include site-monitor
            'deliverables': [
                {
                    'name': 'test-deliverable',
                    'title': 'Test Deliverable',
                    'description': 'A test deliverable'
                }
            ]
        }
        
        is_valid, errors = WorkflowSchemaValidator.validate_workflow(workflow_data)
        
        assert not is_valid
        assert any("site-monitor" in error and "automatically required" in error for error in errors)
    
    def test_validate_deliverable_names_valid(self):
        """Test deliverable names validation with valid names"""
        deliverables = [
            {'name': 'overview', 'title': 'Overview', 'description': 'Overview'},
            {'name': 'details-report', 'title': 'Details', 'description': 'Details'},
            {'name': 'summary_doc', 'title': 'Summary', 'description': 'Summary'}
        ]
        
        is_valid, errors = WorkflowSchemaValidator.validate_deliverable_names(deliverables)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_deliverable_names_missing_name(self):
        """Test deliverable names validation with missing name"""
        deliverables = [
            {'title': 'Overview', 'description': 'Overview'},  # Missing name
            {'name': 'details', 'title': 'Details', 'description': 'Details'}
        ]
        
        is_valid, errors = WorkflowSchemaValidator.validate_deliverable_names(deliverables)
        
        assert not is_valid
        assert any("missing required 'name' field" in error for error in errors)
    
    def test_validate_deliverable_names_invalid_format(self):
        """Test deliverable names validation with invalid format"""
        deliverables = [
            {'name': 'invalid name with spaces', 'title': 'Invalid', 'description': 'Invalid'},
            {'name': 'valid-name', 'title': 'Valid', 'description': 'Valid'}
        ]
        
        is_valid, errors = WorkflowSchemaValidator.validate_deliverable_names(deliverables)
        
        assert not is_valid
        assert any("invalid characters" in error for error in errors)
    
    def test_validate_deliverable_names_duplicate(self):
        """Test deliverable names validation with duplicates"""
        deliverables = [
            {'name': 'duplicate', 'title': 'First', 'description': 'First'},
            {'name': 'duplicate', 'title': 'Second', 'description': 'Second'}
        ]
        
        is_valid, errors = WorkflowSchemaValidator.validate_deliverable_names(deliverables)
        
        assert not is_valid
        assert any("Duplicate deliverable name" in error for error in errors)
    
    def test_validate_deliverable_names_wrong_type(self):
        """Test deliverable names validation with wrong type"""
        deliverables = [
            {'name': 123, 'title': 'Number', 'description': 'Number'},  # Name is not string
            {'name': 'valid', 'title': 'Valid', 'description': 'Valid'}
        ]
        
        is_valid, errors = WorkflowSchemaValidator.validate_deliverable_names(deliverables)
        
        assert not is_valid
        assert any("must be a string" in error for error in errors)