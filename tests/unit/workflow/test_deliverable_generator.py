"""
Tests for the DeliverableGenerator module.

This test suite validates the deliverable generation functionality including
template-based content generation, different deliverable types, and integration
with workflow specifications.
"""

import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock

from src.workflow.deliverable_generator import DeliverableGenerator, DeliverableSpec
from src.workflow.workflow_matcher import WorkflowInfo
from src.core.issue_processor import IssueData
from src.agents.content_extraction_agent import StructuredContent, Entity, Relationship, Event


@pytest.fixture
def sample_issue_data():
    """Create sample issue data for testing."""
    return IssueData(
        number=123,
        title="Test Research Issue",
        body="This is a test issue for research workflow testing.",
        labels=["site-monitor", "research", "analysis"],
        assignees=["test-user"],
        created_at=datetime(2025, 9, 21, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 9, 21, 10, 30, 0, tzinfo=timezone.utc),
        url="https://github.com/test/repo/issues/123"
    )


@pytest.fixture
def sample_workflow_info():
    """Create sample workflow info for testing."""
    return WorkflowInfo(
        path="/test/path/research-workflow.yaml",
        name="Test Research Workflow",
        description="Test workflow for unit testing",
        version="1.0.0",
        trigger_labels=["research", "analysis"],
        deliverables=[
            {"name": "overview", "title": "Research Overview", "template": "research_overview"},
            {"name": "findings", "title": "Key Findings", "template": "findings"}
        ],
        processing={
            "timeout": 120,
            "require_review": True
        },
        validation={
            "min_word_count": 200
        },
        output={
            "folder_structure": "study/{issue_number}-test",
            "file_pattern": "{deliverable_name}.md"
        }
    )


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def deliverable_generator(temp_output_dir):
    """Create a DeliverableGenerator instance for testing."""
    return DeliverableGenerator(
        templates_dir=None,
        output_dir=temp_output_dir
    )


@pytest.fixture
def sample_structured_content():
    """Create structured content fixture with entities, relationships, and events."""
    return StructuredContent(
        summary="Criminal matter involving Alex Doe and financial records in the Eastern District of Virginia.",
        entities=[
            Entity(
                name="Alex Doe",
                type="person",
                confidence=0.91,
                attributes={
                    "role": "Defendant",
                    "risk_score": 0.82,
                    "risk_flags": ["Prior conviction", "Financial fraud"],
                    "conflicts": ["Potential conflict with GAO analyst"],
                    "notes": "Primary subject with extensive financial exposure",
                },
            ),
            Entity(
                name="Eastern District of Virginia",
                type="place",
                confidence=0.88,
                context="Primary venue",
                attributes={"jurisdiction": "EDVA", "notes": "Rocket docket"},
            ),
            Entity(
                name="Financial Records",
                type="thing",
                confidence=0.85,
                attributes={"role": "Evidence", "notes": "Seized during search"},
            ),
            Entity(
                name="GAO Financial Integrity Office",
                type="organization",
                confidence=0.8,
                attributes={"role": "Oversight agency", "notes": "Primary liaison"},
            ),
        ],
        relationships=[
            Relationship(
                entity1="Alex Doe",
                entity2="Financial Records",
                relationship="custodian_of",
                confidence=0.76,
                context="Financial records seized from office",
            )
        ],
        events=[
            Event(
                description="Indictment filed",
                timestamp="2025-09-12",
                entities_involved=["Alex Doe", "Eastern District of Virginia"],
                confidence=0.9,
                event_type="filing",
            )
        ],
        indicators=[],
        key_topics=["sentencing", "financial fraud"],
        urgency_level="high",
        content_type="legal",
        confidence_score=0.84,
        extraction_timestamp="2025-10-06T12:00:00Z",
    )


class TestDeliverableSpec:
    """Test the DeliverableSpec dataclass."""
    
    def test_deliverable_spec_creation(self):
        """Test creating a DeliverableSpec with all parameters."""
        spec = DeliverableSpec(
            name="test-deliverable",
            title="Test Deliverable",
            description="A test deliverable for unit testing",
            template="basic",
            required=True,
            order=1,
            type="document",
            format="markdown",
            sections=["summary", "details"],
            metadata={"category": "test"}
        )
        
        assert spec.name == "test-deliverable"
        assert spec.title == "Test Deliverable"
        assert spec.description == "A test deliverable for unit testing"
        assert spec.template == "basic"
        assert spec.required is True
        assert spec.order == 1
        assert spec.type == "document"
        assert spec.format == "markdown"
        assert spec.sections == ["summary", "details"]
        assert spec.metadata == {"category": "test"}
    
    def test_deliverable_spec_defaults(self):
        """Test DeliverableSpec with default values."""
        spec = DeliverableSpec(
            name="minimal-spec",
            title="Minimal Spec",
            description="Minimal test spec"
        )
        
        assert spec.template == "basic"
        assert spec.required is True
        assert spec.order == 1
        assert spec.type == "document"
        assert spec.format == "markdown"
        assert spec.sections == []
        assert spec.metadata == {}
    
    def test_deliverable_spec_post_init(self):
        """Test __post_init__ method initializes None values."""
        spec = DeliverableSpec(
            name="test-spec",
            title="Test Spec",
            description="Test description",
            sections=None,
            metadata=None
        )
        
        assert spec.sections == []
        assert spec.metadata == {}


class TestDeliverableGenerator:
    """Test the DeliverableGenerator class."""
    
    def test_initialization(self, temp_output_dir):
        """Test DeliverableGenerator initialization."""
        generator = DeliverableGenerator(
            templates_dir=temp_output_dir / "templates",
            output_dir=temp_output_dir / "output"
        )
        
        assert generator.templates_dir == temp_output_dir / "templates"
        assert generator.output_dir == temp_output_dir / "output"
        assert len(generator.content_strategies) > 0
        assert "basic" in generator.content_strategies
    
    def test_initialization_with_defaults(self):
        """Test DeliverableGenerator with default parameters."""
        generator = DeliverableGenerator()
        
        assert generator.templates_dir == Path("templates")
        assert generator.output_dir == Path("study")
    
    def test_get_supported_templates(self, deliverable_generator):
        """Test getting list of supported templates."""
        templates = deliverable_generator.get_supported_templates()
        
        assert isinstance(templates, list)
        assert len(templates) > 0
        assert "basic" in templates
        assert "research_overview" in templates
        assert "background_analysis" in templates
        assert "methodology" in templates
        assert "findings" in templates
        assert "recommendations" in templates
        assert "references" in templates
        assert "appendices" in templates
        assert "technical_review" in templates
        assert "risk_assessment" in templates
    
    def test_validate_deliverable_spec_valid(self, deliverable_generator):
        """Test validation of a valid deliverable spec."""
        spec = DeliverableSpec(
            name="valid-spec",
            title="Valid Spec",
            description="A valid test spec",
            template="basic",
            order=1
        )
        
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert errors == []
    
    def test_validate_deliverable_spec_invalid(self, deliverable_generator):
        """Test validation of invalid deliverable specs."""
        # Test missing name
        spec = DeliverableSpec(
            name="",
            title="Test",
            description="Test description"
        )
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert "Deliverable name is required" in errors
        
        # Test missing title
        spec = DeliverableSpec(
            name="test",
            title="",
            description="Test description"
        )
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert "Deliverable title is required" in errors
        
        # Test missing description
        spec = DeliverableSpec(
            name="test",
            title="Test",
            description=""
        )
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert "Deliverable description is required" in errors
        
        # Test unsupported template
        spec = DeliverableSpec(
            name="test",
            title="Test",
            description="Test description",
            template="unsupported_template"
        )
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert any("Unsupported template: unsupported_template" in error for error in errors)
        
        # Test negative order
        spec = DeliverableSpec(
            name="test",
            title="Test",
            description="Test description",
            order=0
        )
        errors = deliverable_generator.validate_deliverable_spec(spec)
        assert "Deliverable order must be positive" in errors


class TestContentGeneration:
    """Test content generation for different templates."""

    def test_generate_entity_backbone_with_structured_content(
        self,
        deliverable_generator,
        sample_issue_data,
        sample_workflow_info,
        sample_structured_content,
    ):
        """Entity backbone template should render entity tables and telemetry."""
        spec = DeliverableSpec(
            name="entity-backbone",
            title="Entity Backbone",
            description="Shared entity backbone",
            template="entity_backbone.md",
        )

        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info,
            additional_context={"extracted_content": sample_structured_content},
        )

        assert "Entity Backbone Summary" in content
        assert "CONFIDENTIAL" in content
        assert "Alex Doe" in content
        assert "Eastern District of Virginia" in content

    def test_generate_person_risk_core(
        self,
        deliverable_generator,
        sample_issue_data,
        sample_workflow_info,
        sample_structured_content,
    ):
        """Person risk core should surface risk flags and conflicts."""
        spec = DeliverableSpec(
            name="person-risk",
            title="Person Risk Core",
            description="Risk assessment for persons",
            template="person_risk_core.md",
        )

        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info,
            additional_context={"extracted_content": sample_structured_content},
        )

        assert "Person Risk Posture" in content
        assert "Prior conviction" in content
        assert "Potential conflict" in content

    def test_generate_gao_compliance_appendix(
        self,
        deliverable_generator,
        sample_issue_data,
        sample_workflow_info,
        sample_structured_content,
    ):
        """GAO compliance appendix should include audit tables and metadata."""
        spec = DeliverableSpec(
            name="gao-appendix",
            title="GAO Compliance Appendix",
            description="Audit appendix",
            template="gao_compliance_appendix.md",
        )

        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info,
            additional_context={"extracted_content": sample_structured_content},
        )

        assert "GAO Compliance Appendix" in content
        assert "Audit Snapshot" in content
        assert "#" + str(sample_issue_data.number) in content
    
    def test_generate_basic_deliverable(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a basic deliverable."""
        spec = DeliverableSpec(
            name="basic-test",
            title="Basic Test Deliverable",
            description="A basic test deliverable",
            template="basic"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert isinstance(content, str)
        assert len(content) > 0
        assert "# Basic Test Deliverable" in content
        assert f"**Issue**: #{sample_issue_data.number}" in content
        assert sample_issue_data.title in content
        assert sample_workflow_info.name in content
        assert "Generated automatically by Deliverable Generator" in content
    
    def test_generate_research_overview(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a research overview deliverable."""
        spec = DeliverableSpec(
            name="research-overview",
            title="Research Overview",
            description="Comprehensive research overview",
            template="research_overview"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Research Overview" in content
        assert "## Executive Summary" in content
        assert "## Research Scope" in content
        assert "## Methodology Preview" in content
        assert "## Expected Deliverables" in content
        assert f"**Issue**: #{sample_issue_data.number}" in content
    
    def test_generate_background_analysis(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a background analysis deliverable."""
        spec = DeliverableSpec(
            name="background-analysis",
            title="Background Analysis",
            description="Historical context and existing knowledge review",
            template="background_analysis"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Background Analysis" in content
        assert "## Introduction" in content
        assert "## Historical Context" in content
        assert "## Current State Analysis" in content
        assert "## Stakeholder Analysis" in content
        assert "## Knowledge Gaps" in content
    
    def test_generate_methodology(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a methodology deliverable."""
        spec = DeliverableSpec(
            name="methodology",
            title="Research Methodology",
            description="Approach and methods used for investigation",
            template="methodology"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Research Methodology" in content
        assert "## Research Approach" in content
        assert "## Data Collection Methods" in content
        assert "## Sampling Strategy" in content
        assert "## Data Analysis Framework" in content
    
    def test_generate_findings(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a findings deliverable."""
        spec = DeliverableSpec(
            name="findings",
            title="Key Findings",
            description="Primary research results and discoveries",
            template="findings"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Key Findings" in content
        assert "## Executive Summary" in content
        assert "## Key Findings" in content
        assert "## Detailed Analysis" in content
        assert "## Significance Assessment" in content
        assert "## Conclusions" in content
    
    def test_generate_recommendations(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a recommendations deliverable."""
        spec = DeliverableSpec(
            name="recommendations",
            title="Recommendations",
            description="Actionable recommendations based on findings",
            template="recommendations"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Recommendations" in content
        assert "## Primary Recommendations" in content
        assert "## Implementation Roadmap" in content
        assert "## Resource Allocation" in content
        assert "## Risk Assessment" in content
        assert "## Success Monitoring" in content
    
    def test_generate_references(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a references deliverable."""
        spec = DeliverableSpec(
            name="references",
            title="References and Sources",
            description="Bibliography and source documentation",
            template="references"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# References and Sources" in content
        assert "## Bibliography" in content
        assert "### Academic Sources" in content
        assert "### Industry and Technical Reports" in content
        assert "### Web Resources" in content
        assert "## Source Quality Assessment" in content
    
    def test_generate_appendices(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating an appendices deliverable."""
        spec = DeliverableSpec(
            name="appendices",
            title="Appendices",
            description="Supporting materials and detailed data",
            template="appendices"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Appendices" in content
        assert "## Appendix A: Raw Data Summary" in content
        assert "## Appendix B: Detailed Analysis Results" in content
        assert "## Appendix C: Research Instruments" in content
        assert "## Appendix L: Glossary" in content
    
    def test_generate_technical_review(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a technical review deliverable."""
        spec = DeliverableSpec(
            name="technical-review",
            title="Technical Review",
            description="Technical architecture and implementation review",
            template="technical_review"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Technical Review" in content
        assert "## Technical Architecture Review" in content
        assert "## Code Quality Assessment" in content
        assert "## Security Assessment" in content
        assert "## Performance Analysis" in content
    
    def test_generate_risk_assessment(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating a risk assessment deliverable."""
        spec = DeliverableSpec(
            name="risk-assessment",
            title="Risk Assessment",
            description="Comprehensive risk analysis and mitigation strategies",
            template="risk_assessment"
        )
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info
        )
        
        assert "# Risk Assessment" in content
        assert "## Risk Register" in content
        assert "### Critical Risks" in content
        assert "## Risk Analysis by Category" in content
        assert "## Risk Mitigation Strategies" in content
        assert "## Risk Monitoring Plan" in content


class TestMultipleDeliverables:
    """Test generating multiple deliverables."""
    
    def test_generate_multiple_deliverables(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating multiple deliverables for a workflow."""
        specs = [
            DeliverableSpec(
                name="overview",
                title="Research Overview",
                description="High-level overview",
                template="research_overview",
                order=1
            ),
            DeliverableSpec(
                name="findings",
                title="Key Findings",
                description="Primary research results",
                template="findings",
                order=2
            ),
            DeliverableSpec(
                name="recommendations",
                title="Recommendations",
                description="Actionable recommendations",
                template="recommendations",
                order=3
            )
        ]
        
        results = deliverable_generator.generate_multiple_deliverables(
            issue_data=sample_issue_data,
            deliverable_specs=specs,
            workflow_info=sample_workflow_info
        )
        
        assert isinstance(results, dict)
        assert len(results) == 3
        assert "overview" in results
        assert "findings" in results
        assert "recommendations" in results
        
        # Verify content
        assert "# Research Overview" in results["overview"]
        assert "# Key Findings" in results["findings"]
        assert "# Recommendations" in results["recommendations"]
    
    def test_generate_multiple_deliverables_with_optional(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating multiple deliverables with optional ones that fail."""
        specs = [
            DeliverableSpec(
                name="required",
                title="Required Deliverable",
                description="A required deliverable",
                template="basic",
                required=True,
                order=1
            ),
            DeliverableSpec(
                name="optional",
                title="Optional Deliverable",
                description="An optional deliverable",
                template="nonexistent_template",  # This will fail
                required=False,
                order=2
            )
        ]
        
        # Mock the basic content strategy to work but fail for nonexistent_template
        original_strategies = deliverable_generator.content_strategies.copy()
        deliverable_generator.content_strategies["nonexistent_template"] = lambda ctx: (_ for _ in ()).throw(Exception("Template error"))
        
        try:
            results = deliverable_generator.generate_multiple_deliverables(
                issue_data=sample_issue_data,
                deliverable_specs=specs,
                workflow_info=sample_workflow_info
            )
            
            # Should complete successfully with only the required deliverable
            assert len(results) == 1
            assert "required" in results
            assert "optional" not in results
        finally:
            # Restore original strategies
            deliverable_generator.content_strategies = original_strategies
    
    def test_generate_multiple_deliverables_required_failure(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test that failure of required deliverable raises exception."""
        specs = [
            DeliverableSpec(
                name="required",
                title="Required Deliverable",
                description="A required deliverable",
                template="nonexistent_template",  # This will fail
                required=True,
                order=1
            )
        ]
        
        # Mock a failing strategy
        deliverable_generator.content_strategies["nonexistent_template"] = lambda ctx: (_ for _ in ()).throw(Exception("Template error"))
        
        with pytest.raises(RuntimeError, match="Failed to generate required deliverable"):
            deliverable_generator.generate_multiple_deliverables(
                issue_data=sample_issue_data,
                deliverable_specs=specs,
                workflow_info=sample_workflow_info
            )


class TestErrorHandling:
    """Test error handling in deliverable generation."""
    
    def test_generate_deliverable_invalid_spec(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test error handling with invalid deliverable spec."""
        with pytest.raises(ValueError, match="Issue data and deliverable spec are required"):
            deliverable_generator.generate_deliverable(
                issue_data=None,
                deliverable_spec=None,
                workflow_info=sample_workflow_info
            )
    
    def test_generate_deliverable_template_error(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test error handling when template generation fails."""
        spec = DeliverableSpec(
            name="error-test",
            title="Error Test",
            description="Test error handling",
            template="basic"
        )
        
        # Mock the basic strategy to fail
        original_strategy = deliverable_generator.content_strategies["basic"]
        deliverable_generator.content_strategies["basic"] = lambda ctx: (_ for _ in ()).throw(Exception("Generation error"))
        
        try:
            with pytest.raises(RuntimeError, match="Failed to generate deliverable 'error-test'"):
                deliverable_generator.generate_deliverable(
                    issue_data=sample_issue_data,
                    deliverable_spec=spec,
                    workflow_info=sample_workflow_info
                )
        finally:
            # Restore original strategy
            deliverable_generator.content_strategies["basic"] = original_strategy


class TestContentFormatting:
    """Test content formatting functionality."""
    
    def test_format_content(self, deliverable_generator):
        """Test content formatting functionality."""
        # Test basic formatting
        content = "Test content\r\n\r\nSecond line\r"
        formatted = deliverable_generator._format_content(content, {})
        
        assert formatted == "Test content\n\nSecond line\n"
        assert formatted.endswith('\n')
        assert '\r' not in formatted
    
    def test_format_content_with_context(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test formatting with context."""
        context = {
            "issue": sample_issue_data,
            "workflow": sample_workflow_info,
            "timestamp": datetime.now(timezone.utc)
        }
        
        content = "# Test Document\n\nContent here"
        formatted = deliverable_generator._format_content(content, context)
        
        assert formatted == "# Test Document\n\nContent here\n"


class TestAdditionalContext:
    """Test additional context functionality in deliverable generation."""
    
    def test_generate_with_additional_context(self, deliverable_generator, sample_issue_data, sample_workflow_info):
        """Test generating deliverable with additional context."""
        spec = DeliverableSpec(
            name="context-test",
            title="Context Test",
            description="Test with additional context",
            template="basic"
        )
        
        additional_context = {
            "custom_field": "custom_value",
            "processing_notes": "Special processing instructions"
        }
        
        content = deliverable_generator.generate_deliverable(
            issue_data=sample_issue_data,
            deliverable_spec=spec,
            workflow_info=sample_workflow_info,
            additional_context=additional_context
        )
        
        assert isinstance(content, str)
        assert "# Context Test" in content
        # The additional context is passed but may not appear in basic template
        # This tests that the parameter is accepted and processed