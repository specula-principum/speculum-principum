"""
Unit tests for WorkflowMatcher module
"""

import pytest
import yaml
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from src.workflow.workflow_matcher import (
    WorkflowMatcher,
    WorkflowInfo,
    WorkflowValidationError,
    WorkflowLoadError,
    WorkflowPlan,
    WorkflowCandidate,
)


class TestWorkflowMatcher:
    """Test cases for WorkflowMatcher class"""

    @pytest.fixture
    def temp_workflow_dir(self):
        """Create a temporary directory with sample workflow files"""
        temp_dir = tempfile.mkdtemp()
        workflow_dir = Path(temp_dir) / "workflows"
        workflow_dir.mkdir()

        profiling_workflow = {
            "name": "Person Entity Profiling",
            "description": "Comprehensive profiling workflow",
            "version": "1.0.0",
            "trigger_labels": ["person-entity-profiling", "investigative"],
            "deliverables": [
                {
                    "name": "entity_profile",
                    "title": "Entity Profile Overview",
                    "description": "Background and affiliations of the person of interest",
                    "required": True,
                    "order": 1,
                },
                {
                    "name": "credibility_matrix",
                    "title": "Credibility Matrix",
                    "description": "Credibility assessment of testimonial and documentary evidence",
                    "required": True,
                    "order": 2,
                },
            ],
            "processing": {"timeout": 60},
            "validation": {"min_word_count": 100},
            "output": {"folder_structure": "study/{issue_number}/person-entity-profiling"},
        }

        witness_workflow = {
            "name": "Witness Expert Reliability Assessment",
            "description": "Reliability assessment for witnesses and expert testimony",
            "version": "1.1.0",
            "trigger_labels": ["witness-expert-reliability-assessment", "trial-prep"],
            "deliverables": [
                {
                    "name": "testimony_analysis",
                    "title": "Testimony Analysis",
                    "description": "Evaluation of prior testimony and public statements",
                    "required": True,
                    "order": 1,
                },
                {
                    "name": "impeachment_risks",
                    "title": "Impeachment Risk Summary",
                    "description": "Potential impeachment paths and mitigation recommendations",
                    "required": True,
                    "order": 2,
                },
            ],
            "processing": {"timeout": 90},
            "validation": {"min_word_count": 150},
            "output": {"folder_structure": "study/{issue_number}/witness-reliability"},
        }

        with (workflow_dir / "person-entity-profiling.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(profiling_workflow, handle)

        with (workflow_dir / "witness.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(witness_workflow, handle)

        with (workflow_dir / "invalid.yaml").open("w", encoding="utf-8") as handle:
            handle.write("invalid: yaml: content: [")

        incomplete_workflow = {
            "name": "Incomplete Workflow",
            "description": "Missing required fields",
        }
        with (workflow_dir / "incomplete.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(incomplete_workflow, handle)

        yield str(workflow_dir)

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def empty_workflow_dir(self):
        """Create an empty temporary directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_init_with_valid_directory(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        assert len(matcher._workflow_cache) == 2
        assert matcher._last_scan_time is not None

        workflow_names = [w.name for w in matcher._workflow_cache.values()]
        assert "Person Entity Profiling" in workflow_names
        assert "Witness Expert Reliability Assessment" in workflow_names

    def test_init_with_nonexistent_directory(self):
        with pytest.raises(WorkflowLoadError):
            WorkflowMatcher("/path/that/does/not/exist")

    def test_init_with_empty_directory(self, empty_workflow_dir):
        matcher = WorkflowMatcher(empty_workflow_dir)
        assert len(matcher._workflow_cache) == 0

    def test_parse_workflow_file_valid(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)
        workflow_file = Path(temp_workflow_dir) / "person-entity-profiling.yaml"

        workflow_info = matcher._parse_workflow_file(workflow_file)

        assert workflow_info is not None
        assert workflow_info.name == "Person Entity Profiling"
        assert workflow_info.description == "Comprehensive profiling workflow"
        assert workflow_info.version == "1.0.0"
        assert "person-entity-profiling" in workflow_info.trigger_labels
        assert "investigative" in workflow_info.trigger_labels
        assert len(workflow_info.deliverables) == 2

    def test_parse_workflow_file_invalid_yaml(self, temp_workflow_dir):
        matcher = WorkflowMatcher.__new__(WorkflowMatcher)
        matcher.workflow_directory = Path(temp_workflow_dir)

        workflow_file = Path(temp_workflow_dir) / "invalid.yaml"

        with pytest.raises(WorkflowValidationError, match="Invalid YAML"):
            matcher._parse_workflow_file(workflow_file)

    def test_parse_workflow_file_missing_required_fields(self, temp_workflow_dir):
        matcher = WorkflowMatcher.__new__(WorkflowMatcher)
        matcher.workflow_directory = Path(temp_workflow_dir)

        workflow_file = Path(temp_workflow_dir) / "incomplete.yaml"

        with pytest.raises(WorkflowValidationError, match="missing required fields"):
            matcher._parse_workflow_file(workflow_file)

    def test_find_matching_workflows_with_site_monitor(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor", "person-entity-profiling"]
        matches = matcher.find_matching_workflows(labels)
        assert len(matches) == 1
        assert matches[0].name == "Person Entity Profiling"

        labels = ["site-monitor", "witness-expert-reliability-assessment"]
        matches = matcher.find_matching_workflows(labels)
        assert len(matches) == 1
        assert matches[0].name == "Witness Expert Reliability Assessment"

    def test_find_matching_workflows_without_site_monitor(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["person-entity-profiling", "investigative"]
        matches = matcher.find_matching_workflows(labels)

        assert len(matches) == 0

    def test_find_matching_workflows_multiple_matches(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        profiling_workflow = None
        for workflow in matcher._workflow_cache.values():
            if workflow.name == "Person Entity Profiling":
                profiling_workflow = workflow
                break

        assert profiling_workflow is not None
        profiling_workflow.trigger_labels.append("witness-expert-reliability-assessment")

        labels = ["site-monitor", "witness-expert-reliability-assessment"]
        matches = matcher.find_matching_workflows(labels)

        assert len(matches) == 2

    def test_get_best_workflow_match_single_match(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor", "person-entity-profiling"]
        workflow, message = matcher.get_best_workflow_match(labels)

        assert workflow is not None
        assert workflow.name == "Person Entity Profiling"

    def test_get_workflow_plan_single_match(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor", "person-entity-profiling"]
        plan = matcher.get_workflow_plan(labels)

        assert isinstance(plan, WorkflowPlan)
        assert plan.has_candidates()
        assert not plan.is_multi_workflow()
        assert plan.selection_reason == "single_match"
        primary = plan.primary_workflow()
        assert primary is not None
        assert primary.name == "Person Entity Profiling"

    def test_get_workflow_plan_no_matches(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor", "unknown-label"]
        plan = matcher.get_workflow_plan(labels)

        assert not plan.has_candidates()
        assert plan.selection_reason == "no_match"
        assert "No workflows match" in plan.selection_message

    def test_get_workflow_plan_multiple_matches(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        profiling_workflow = None
        for workflow in matcher._workflow_cache.values():
            if workflow.name == "Person Entity Profiling":
                profiling_workflow = workflow
                break

        assert profiling_workflow is not None
        profiling_workflow.trigger_labels.append("witness-expert-reliability-assessment")

        labels = ["site-monitor", "witness-expert-reliability-assessment"]
        plan = matcher.get_workflow_plan(labels)

        assert plan.has_candidates()
        assert plan.is_multi_workflow()
        candidate_names = [candidate.name for candidate in plan.candidates]
        assert sorted(candidate_names) == sorted([
            "Person Entity Profiling",
            "Witness Expert Reliability Assessment",
        ])
        for candidate in plan.candidates:
            assert isinstance(candidate, WorkflowCandidate)
            assert candidate.conflict_keys  # conflict metadata should not be empty

    def test_get_best_workflow_match_no_site_monitor(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["person-entity-profiling"]
        workflow, message = matcher.get_best_workflow_match(labels)

        assert workflow is None
        assert "site-monitor" in message

    def test_get_best_workflow_match_no_matches(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor", "unknown-label"]
        workflow, message = matcher.get_best_workflow_match(labels)

        assert workflow is None
        assert "No workflows match" in message

    def test_get_workflow_by_name(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        workflow = matcher.get_workflow_by_name("Person Entity Profiling")
        assert workflow is not None
        assert workflow.name == "Person Entity Profiling"

        workflow = matcher.get_workflow_by_name("Nonexistent Workflow")
        assert workflow is None

    def test_get_workflow_suggestions(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        labels = ["site-monitor"]
        suggestions = matcher.get_workflow_suggestions(labels)

        assert "person-entity-profiling" in suggestions
        assert "investigative" in suggestions
        assert "witness-expert-reliability-assessment" in suggestions
        assert "trial-prep" in suggestions
        assert "site-monitor" not in suggestions

    def test_validate_workflow_directory_valid(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        is_valid, errors = matcher.validate_workflow_directory()

        assert len(matcher._workflow_cache) == 2
        if not is_valid:
            assert any("Invalid workflow file" in error for error in errors)

    def test_validate_workflow_directory_nonexistent(self):
        matcher = WorkflowMatcher.__new__(WorkflowMatcher)
        matcher.workflow_directory = Path("/nonexistent/path")
        matcher._workflow_cache = {}

        is_valid, errors = matcher.validate_workflow_directory()

        assert not is_valid
        assert len(errors) > 0
        assert "does not exist" in errors[0]

    def test_validate_workflow_directory_empty(self, empty_workflow_dir):
        matcher = WorkflowMatcher.__new__(WorkflowMatcher)
        matcher.workflow_directory = Path(empty_workflow_dir)
        matcher._workflow_cache = {}

        is_valid, errors = matcher.validate_workflow_directory()

        assert not is_valid
        assert len(errors) > 0
        assert "No workflow files found" in errors[0]

    def test_get_statistics(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        stats = matcher.get_statistics()

        assert stats["total_workflows"] == 2
        assert stats["total_trigger_labels"] == 4  # profiling, investigative, witness, trial-prep
        assert stats["total_deliverables"] == 4
        assert stats["workflow_directory"] == temp_workflow_dir
        assert stats["last_scan_time"] is not None
        assert "Person Entity Profiling" in stats["workflow_names"]
        assert "Witness Expert Reliability Assessment" in stats["workflow_names"]

    def test_refresh_workflows(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        original_scan_time = matcher._last_scan_time
        assert original_scan_time is not None

        import time

        time.sleep(0.01)
        matcher.refresh_workflows()

        assert matcher._last_scan_time is not None
        assert matcher._last_scan_time > original_scan_time

    def test_should_rescan_based_on_time(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)
        matcher._scan_interval_seconds = 1

        assert not matcher._should_rescan()

        with patch("src.workflow.workflow_matcher.datetime") as mock_datetime:
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            assert matcher._should_rescan()

    def test_get_available_workflows(self, temp_workflow_dir):
        matcher = WorkflowMatcher(temp_workflow_dir)

        workflows = matcher.get_available_workflows()

        assert len(workflows) == 2
        workflow_names = [w.name for w in workflows]
        assert "Person Entity Profiling" in workflow_names
        assert "Witness Expert Reliability Assessment" in workflow_names

    def test_find_matching_workflows_prefers_taxonomy_over_legacy(self, tmp_path):
        workflow_dir = tmp_path / "workflows"
        workflow_dir.mkdir()

        legacy_workflow = {
            "name": "Legacy Research",
            "description": "Legacy research workflow",
            "version": "1.0.0",
            "trigger_labels": ["research"],
            "deliverables": [
                {
                    "name": "legacy-report",
                    "title": "Legacy Report",
                    "description": "Legacy deliverable",
                    "order": 1,
                }
            ],
        }

        taxonomy_workflow = {
            "name": "Statutory Tracker",
            "description": "Taxonomy-aligned statutory research workflow",
            "version": "1.0.0",
            "workflow_version": "1.0.0",
            "category": "legal-research",
            "priority": "high",
            "confidence_threshold": 0.7,
            "trigger_labels": ["statute-review", "criminal-law"],
            "required_entities": [
                {"entity_type": "person", "min_count": 0, "min_confidence": 0.6},
                {"entity_type": "place", "min_count": 0, "min_confidence": 0.6},
                {"entity_type": "thing", "min_count": 0, "min_confidence": 0.6},
            ],
            "deliverable_templates": [
                "confidentiality_banner",
                "shared_entity_tables",
                "shared_gao_citation_block",
                "entity_backbone",
                "statute_research_core",
                "gao_compliance_appendix",
            ],
            "audit_trail": {"required": True, "fields": ["model_version"]},
            "deliverables": [
                {
                    "name": "statute-digest",
                    "title": "Statute Digest",
                    "description": "Digest of applicable statutes",
                    "order": 1,
                    "template": "statute_research_core.md",
                    "required_sections": [
                        "Summary",
                        "Statute Digest",
                        "GAO Directive Alignment",
                    ],
                }
            ],
        }

        with (workflow_dir / "legacy.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(legacy_workflow, handle)

        with (workflow_dir / "taxonomy.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(taxonomy_workflow, handle)

        matcher = WorkflowMatcher(str(workflow_dir))

        labels = ["site-monitor", "research", "statute-review"]
        matches = matcher.find_matching_workflows(labels)

        assert len(matches) == 1
        assert matches[0].name == "Statutory Tracker"
        assert matches[0].is_taxonomy()


class TestWorkflowInfo:
    """Test cases for WorkflowInfo dataclass"""
    
    def test_workflow_info_creation_valid(self):
        """Test creating valid WorkflowInfo"""
        workflow = WorkflowInfo(
            path="/test/path.yaml",
            name="Test Workflow",
            description="Test description",
            version="1.0.0",
            trigger_labels=["test"],
            deliverables=[{"name": "test", "required": True}],
            processing={},
            validation={},
            output={}
        )
        
        assert workflow.name == "Test Workflow"
        assert workflow.trigger_labels == ["test"]
    
    def test_workflow_info_creation_no_trigger_labels(self):
        """Test creating WorkflowInfo without trigger labels"""
        with pytest.raises(WorkflowValidationError, match="must have at least one trigger label"):
            WorkflowInfo(
                path="/test/path.yaml",
                name="Test Workflow",
                description="Test description",
                version="1.0.0",
                trigger_labels=[],  # Empty list
                deliverables=[{"name": "test", "required": True}],
                processing={},
                validation={},
                output={}
            )
    
    def test_workflow_info_creation_no_deliverables(self):
        """Test creating WorkflowInfo without deliverables"""
        with pytest.raises(WorkflowValidationError, match="must have at least one deliverable"):
            WorkflowInfo(
                path="/test/path.yaml",
                name="Test Workflow",
                description="Test description",
                version="1.0.0",
                trigger_labels=["test"],
                deliverables=[],  # Empty list
                processing={},
                validation={},
                output={}
            )