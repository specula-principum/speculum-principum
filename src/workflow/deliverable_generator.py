"""
Deliverable Generator

This module handles the generation of structured deliverable documents based on
workflow specifications and issue data. It provides template-based content
generation with support for various deliverable types and formats.

Key Components:
- DeliverableGenerator: Main class for generating deliverable content
- Template system integration for consistent document structure
- Content generation logic for different deliverable types
- Validation and formatting utilities

The generator is designed to be extensible and can be integrated with AI content
generation services in the future.
"""

import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict, is_dataclass

from .workflow_matcher import WorkflowInfo
from .template_engine import TemplateEngine, TemplateMetadata


@dataclass
class DeliverableSpec:
    """
    Specification for a single deliverable within a workflow.
    
    Attributes:
        name: Unique identifier for the deliverable
        title: Human-readable title
        description: Description of the deliverable's purpose
        template: Template name or reference
        required: Whether this deliverable is mandatory
        order: Order in which deliverable should be generated
        type: Type of deliverable (document, data, etc.)
        format: Output format (markdown, html, etc.)
        sections: Required sections for the deliverable
        metadata: Additional metadata for the deliverable
    """
    name: str
    title: str
    description: str
    template: str = "basic"
    required: bool = True
    order: int = 1
    type: str = "document"
    format: str = "markdown"
    sections: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.sections is None:
            self.sections = []
        if self.metadata is None:
            self.metadata = {}


class DeliverableGenerator:
    """
    Generator for creating structured deliverable documents.
    
    This class handles the generation of deliverable content based on workflow
    specifications and issue data. It supports template-based generation with
    the new TemplateEngine system for consistent document structure.
    
    Attributes:
        template_engine: Template engine for processing templates
        output_dir: Base directory for generated outputs
        fallback_strategies: Fallback content strategies for missing templates
    """
    
    def __init__(self, 
                 templates_dir: Optional[Union[str, Path]] = None,
                 output_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the deliverable generator.
        
        Args:
            templates_dir: Directory containing deliverable templates
            output_dir: Base output directory for generated files
        """
        self.template_engine = TemplateEngine(templates_dir or "templates")
        self.output_dir = Path(output_dir or "study")
        
        # Backward compatibility attributes
        self.templates_dir = self.template_engine.templates_dir
        
        # Fallback content generation strategies for when templates are not available
        self.fallback_strategies = {
            "basic": self._generate_basic_content,
            "research_overview": self._generate_research_overview,
            "background_analysis": self._generate_background_analysis,
            "methodology": self._generate_methodology,
            "findings": self._generate_findings,
            "recommendations": self._generate_recommendations,
            "references": self._generate_references,
            "appendices": self._generate_appendices,
            "technical_review": self._generate_technical_review,
            "risk_assessment": self._generate_risk_assessment,
        }
        
        # Backward compatibility alias
        self.content_strategies = self.fallback_strategies
    
    @staticmethod
    def _normalize_template_identifier(template_name: str) -> str:
        """Normalize template identifiers, stripping .md extensions and leading separators."""
        if not template_name:
            return template_name
        normalized = template_name.strip().replace('\\', '/').lstrip('./')
        if normalized.endswith('.md'):
            normalized = normalized[:-3]
        return normalized.strip('/')

    @staticmethod
    def _get_field(data: Any, field: str, default: Any = None) -> Any:
        """Safely retrieve an attribute or dictionary key from a data object."""
        if hasattr(data, field):
            try:
                return getattr(data, field)
            except AttributeError:
                return default
        if isinstance(data, dict):
            return data.get(field, default)
        return default

    @staticmethod
    def _format_confidence(value: Optional[Union[int, float]]) -> str:
        """Format confidence scores into a human-readable string."""
        if isinstance(value, (int, float)):
            if value < 0:
                value = 0
            if value > 1:
                value = min(value / 100, 1.0)
            return f"{value:.2f}"
        return "—"

    @staticmethod
    def _format_percentage(value: Optional[Union[int, float]]) -> str:
        """Format a numeric value as percentage (0-100%)."""
        if isinstance(value, (int, float)):
            fraction = value
            if value > 1:
                fraction = value / 100
            if fraction < 0:
                fraction = 0
            if fraction > 1:
                fraction = 1
            return f"{fraction * 100:.0f}%"
        return "—"

    @staticmethod
    def _format_list(values: Any) -> str:
        """Convert a list-like object to a comma-separated string."""
        if values is None:
            return ""
        if isinstance(values, str):
            return values
        if isinstance(values, (list, tuple, set)):
            filtered = [str(v) for v in values if v not in (None, "")]
            return ", ".join(filtered)
        return str(values)

    @staticmethod
    def _format_entity_label(entity_type: str) -> str:
        """Provide a human-readable label for an entity type."""
        mapping = {
            "person": "Person Entities",
            "organization": "Organization Entities",
            "place": "Place Entities",
            "thing": "Asset / Evidence Entities",
            "asset": "Asset Records",
            "evidence": "Evidence Records",
            "lead": "Investigative Leads",
            "case": "Case References",
            "plan": "Remediation Plans",
            "agency": "Agency Contacts",
            "witness": "Witness Profiles",
        }
        cleaned = entity_type.replace('-', ' ').replace('_', ' ').strip()
        return mapping.get(entity_type.lower(), cleaned.title() if cleaned else "Entities")

    @staticmethod
    def _coerce_to_dict(value: Any) -> Dict[str, Any]:
        """Convert dataclass or object instances to dictionaries when possible."""
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)

        result: Dict[str, Any] = {}
        for attr in [
            "name",
            "type",
            "confidence",
            "context",
            "attributes",
            "jurisdiction",
            "role",
            "event_type",
            "timestamp",
            "entities_involved",
            "description",
            "relationship",
            "entity1",
            "entity2",
        ]:
            if hasattr(value, attr):
                result[attr] = getattr(value, attr)
        return result

    def generate_deliverable(self,
                           issue_data: Any,  # Use Any to avoid type conflicts
                           deliverable_spec: DeliverableSpec,
                           workflow_info: WorkflowInfo,
                           additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate content for a specific deliverable using the template system.
        
        Args:
            issue_data: Issue data for context
            deliverable_spec: Specification for the deliverable to generate
            workflow_info: Workflow information
            additional_context: Additional context for content generation
            
        Returns:
            Generated deliverable content as string
            
        Raises:
            ValueError: If deliverable spec is invalid
            RuntimeError: If content generation fails
        """
        # Validate inputs
        if not issue_data or not deliverable_spec:
            raise ValueError("Issue data and deliverable spec are required")
        
        # Prepare template context
        context = self._prepare_template_context(
            issue_data, deliverable_spec, workflow_info, additional_context
        )
        
        try:
            # Try to use template engine first
            template_name = deliverable_spec.template
            
            # Check if template exists
            if self._template_exists(template_name):
                return self._generate_from_template(template_name, context, deliverable_spec)
            else:
                # Fall back to legacy content strategies
                return self._generate_from_fallback(template_name, context)
                
        except Exception as e:
            raise RuntimeError(f"Failed to generate deliverable '{deliverable_spec.name}': {e}")
    
    def _template_exists(self, template_name: str) -> bool:
        """Check if a template exists."""
        if not template_name:
            return False

        # Generate candidate identifiers to check including aliases and normalized forms
        candidates = {
            template_name,
            self._normalize_template_identifier(template_name),
        }

        if template_name.endswith(".md"):
            without_ext = template_name[:-3]
            candidates.add(without_ext)
            candidates.add(self._normalize_template_identifier(without_ext))
        else:
            with_ext = f"{template_name}.md"
            candidates.add(with_ext)
            candidates.add(self._normalize_template_identifier(with_ext))

        # Include known alias targets so indirect references resolve correctly
        expanded_candidates = set()
        for candidate in list(candidates):
            if not candidate:
                continue
            expanded_candidates.add(candidate)
            alias_target = getattr(self.template_engine, "_resolve_template_alias", lambda _: None)(candidate)
            if alias_target:
                expanded_candidates.add(alias_target)
                expanded_candidates.add(self._normalize_template_identifier(alias_target))
                expanded_candidates.add(f"{self._normalize_template_identifier(alias_target)}.md")

        for candidate in expanded_candidates:
            if not candidate:
                continue
            try:
                self.template_engine.load_template(candidate)
                return True
            except FileNotFoundError:
                continue
            except ValueError:
                # Template exists but failed validation; treat as present so caller can surface error
                return True

        return False
    
    def _generate_from_template(self, 
                              template_name: str, 
                              context: Dict[str, Any],
                              deliverable_spec: DeliverableSpec) -> str:
        """Generate content using the template engine."""
        # Prepare sections if they exist in additional context
        sections = context.get('sections', {})
        
        # Add any custom sections from deliverable spec
        if deliverable_spec.sections:
            for section_name in deliverable_spec.sections:
                if section_name not in sections:
                    # Generate placeholder content for missing sections
                    sections[section_name] = self._generate_section_placeholder(section_name, context)
        
        # Render template
        content = self.template_engine.render_template(template_name, context, sections)
        self._validate_rendered_sections(content, deliverable_spec)
        return content

    def _validate_rendered_sections(self, content: str, deliverable_spec: DeliverableSpec) -> None:
        """Ensure rendered content includes all required section headings."""
        if not deliverable_spec.sections:
            return

        missing_sections: List[str] = []
        for section_name in deliverable_spec.sections:
            heading_pattern = re.compile(rf"^#+\s*{re.escape(section_name)}\b", re.MULTILINE)
            if not heading_pattern.search(content):
                missing_sections.append(section_name)

        if missing_sections:
            raise ValueError(
                "Missing required sections in deliverable '"
                + deliverable_spec.name
                + "': "
                + ", ".join(missing_sections)
            )
    
    def _generate_from_fallback(self, template_name: str, context: Dict[str, Any]) -> str:
        """Generate content using fallback strategies."""
        # For fallback strategies, we need to restore the original issue object
        # because the legacy strategies expect .number, .title, etc. attributes
        fallback_context = context.copy()
        
        # If context has normalized issue dict, we need to convert it back for legacy compatibility
        if "issue" in context and isinstance(context["issue"], dict):
            # We need the original issue object for legacy strategies
            # This is a limitation - we'll create a simple namespace object
            issue_dict = context["issue"]
            
            class IssueNamespace:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
            
            fallback_context["issue"] = IssueNamespace(issue_dict)
        
        normalized = self._normalize_template_identifier(template_name)
        strategy = (
            self.fallback_strategies.get(template_name)
            or self.fallback_strategies.get(normalized)
            or self._generate_basic_content
        )
        content = strategy(fallback_context)
        return self._format_content(content, fallback_context)
    
    def _prepare_template_context(self,
                                issue_data: Any,
                                deliverable_spec: DeliverableSpec,
                                workflow_info: WorkflowInfo,
                                additional_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare the template rendering context."""
        # Convert issue data to dictionary-like structure for template access
        issue_dict = self._normalize_issue_data(issue_data)
        
        # Prepare base context
        context = {
            "issue": issue_dict,
            "deliverable": deliverable_spec,
            "workflow": workflow_info,
            "timestamp": datetime.now(timezone.utc),
            "processing_id": f"{issue_dict.get('number', 'unknown')}-{int(datetime.now().timestamp())}",
        }
        
        # Add additional context
        if additional_context:
            context.update(additional_context)
        
        extracted_content = context.get('extracted_content')
        if extracted_content is not None:
            structured_context = self._build_structured_content_context(extracted_content)
            context.update(structured_context)
        else:
            context.setdefault('entity_groups', [])
            context.setdefault('entity_index', {})

        return context

    def _build_structured_content_context(self, extracted_content: Any) -> Dict[str, Any]:
        """Create a normalized context payload from structured extraction results."""
        structured_dict = self._structured_to_dict(extracted_content)

        entity_context = self._build_entity_context(extracted_content, structured_dict)
        relationship_summary = self._prepare_relationship_summary(extracted_content, structured_dict)
        event_timeline = self._prepare_event_timeline(extracted_content, structured_dict)
        extraction_metadata = self._prepare_extraction_metadata(
            extracted_content,
            structured_dict,
            entity_context,
        )

        return {
            'extracted_content': extracted_content,
            'extracted_content_dict': structured_dict,
            'entity_groups': entity_context['groups'],
            'entity_index': entity_context['index'],
            'entity_counts': entity_context['counts'],
            'entity_summary': entity_context['summary'],
            'entity_foundation': entity_context['foundation'],
            'relationship_summary': relationship_summary,
            'event_timeline': event_timeline,
            'extraction_metadata': extraction_metadata,
        }

    def _structured_to_dict(self, extracted_content: Any) -> Dict[str, Any]:
        """Convert structured content objects into serializable dictionaries."""
        if extracted_content is None:
            return {}

        if isinstance(extracted_content, dict):
            return dict(extracted_content)

        if is_dataclass(extracted_content) and not isinstance(extracted_content, type):
            return asdict(extracted_content)

        result: Dict[str, Any] = {}
        for field in [
            'summary',
            'entities',
            'relationships',
            'events',
            'indicators',
            'key_topics',
            'urgency_level',
            'content_type',
            'confidence_score',
            'extraction_timestamp',
        ]:
            value = self._get_field(extracted_content, field)
            if value is not None:
                result[field] = value
        return result

    def _build_entity_context(
        self,
        extracted_content: Any,
        structured_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        entities_source = self._get_field(extracted_content, 'entities')
        if not entities_source:
            entities_source = structured_dict.get('entities', [])

        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for raw_entity in entities_source or []:
            entity_dict = self._coerce_to_dict(raw_entity)
            if not entity_dict:
                continue

            name = entity_dict.get('name') or 'Unnamed Entity'
            entity_type = (entity_dict.get('type') or 'other').lower()
            safe_type = entity_type.replace(' ', '_').replace('-', '_') or 'other'

            attributes = entity_dict.get('attributes') or {}
            jurisdiction = attributes.get('jurisdiction') or entity_dict.get('jurisdiction')
            role = attributes.get('role') or attributes.get('classification') or entity_dict.get('role')
            risk_score_raw = attributes.get('risk_score') or attributes.get('risk')
            risk_flags = attributes.get('risk_flags') or attributes.get('flags')
            conflicts = attributes.get('conflicts') or attributes.get('conflict_markers')

            display_role = (
                role
                or entity_dict.get('context')
                or attributes.get('title')
                or attributes.get('position')
            )
            display_notes = attributes.get('notes') or attributes.get('summary') or ''

            item = {
                'name': name,
                'type': entity_type,
                'role': role,
                'jurisdiction': jurisdiction,
                'jurisdiction_display': jurisdiction or '—',
                'context': entity_dict.get('context') or '',
                'confidence_raw': entity_dict.get('confidence'),
                'confidence': self._format_confidence(entity_dict.get('confidence')),
                'display_role': display_role or '—',
                'notes': display_notes,
                'display_notes': display_notes or '—',
                'risk_score_raw': risk_score_raw,
                'risk_score': self._format_confidence(risk_score_raw),
                'risk_flags': self._format_list(risk_flags),
                'conflicts': self._format_list(conflicts),
                'attributes': attributes,
            }

            groups[safe_type].append(item)

        # Ensure base entity keys exist for template access
        for base in ('person', 'place', 'thing', 'organization'):
            groups.setdefault(base, [])

        for optional in ('lead', 'case', 'plan', 'witness', 'expert', 'agency', 'asset', 'evidence'):
            groups.setdefault(optional, [])

        # Create ordered group list and supporting metadata
        entity_groups = []
        entity_index: Dict[str, List[Dict[str, Any]]] = {}
        counts: Dict[str, int] = {}

        for safe_type in sorted(groups.keys()):
            items = groups[safe_type]
            entity_groups.append({
                'type': safe_type,
                'label': self._format_entity_label(safe_type),
                'items': items,
                'count': len(items),
            })
            entity_index[safe_type] = items
            counts[safe_type] = len(items)

        total_entities = sum(counts.values())
        types_present = [etype for etype, value in counts.items() if value > 0]
        base_types = {'person', 'place', 'thing'}
        base_present = sorted([etype for etype in types_present if etype in base_types])
        missing_base = sorted(list(base_types - set(base_present)))

        summary = {
            'total_entities': total_entities,
            'types_present': types_present,
            'base_present': base_present,
            'base_missing': missing_base,
            'has_entities': total_entities > 0,
            'types_present_display': self._format_list(types_present),
        }

        foundation = {
            'ready': not missing_base,
            'present': base_present,
            'missing': missing_base,
            'present_display': self._format_list(base_present),
            'missing_display': self._format_list(missing_base),
        }

        return {
            'groups': entity_groups,
            'index': entity_index,
            'counts': counts,
            'summary': summary,
            'foundation': foundation,
        }

    def _prepare_relationship_summary(
        self,
        extracted_content: Any,
        structured_dict: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        relationships_source = self._get_field(extracted_content, 'relationships')
        if not relationships_source:
            relationships_source = structured_dict.get('relationships', [])

        summary: List[Dict[str, Any]] = []

        for raw_relationship in relationships_source or []:
            relationship_dict = self._coerce_to_dict(raw_relationship)
            if not relationship_dict:
                continue

            summary.append({
                'source': relationship_dict.get('entity1') or relationship_dict.get('source') or 'Unknown',
                'target': relationship_dict.get('entity2') or relationship_dict.get('target') or 'Unknown',
                'relationship': relationship_dict.get('relationship') or relationship_dict.get('type') or 'related-to',
                'confidence_raw': relationship_dict.get('confidence'),
                'confidence': self._format_confidence(relationship_dict.get('confidence')),
                'context': relationship_dict.get('context') or '',
                'context_display': relationship_dict.get('context') or '—',
            })

        return summary

    def _prepare_event_timeline(
        self,
        extracted_content: Any,
        structured_dict: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        events_source = self._get_field(extracted_content, 'events')
        if not events_source:
            events_source = structured_dict.get('events', [])

        timeline: List[Dict[str, Any]] = []

        for raw_event in events_source or []:
            event_dict = self._coerce_to_dict(raw_event)
            if not event_dict:
                continue

            entities_involved = event_dict.get('entities_involved') or event_dict.get('entities') or []

            timeline.append({
                'timestamp': event_dict.get('timestamp') or '',
                'display_timestamp': event_dict.get('timestamp') or 'Pending',
                'description': event_dict.get('description') or '',
                'description_display': event_dict.get('description') or '—',
                'confidence_raw': event_dict.get('confidence'),
                'confidence': self._format_confidence(event_dict.get('confidence')),
                'event_type': event_dict.get('event_type') or '',
                'entities_involved': entities_involved,
                'entities_display': self._format_list(entities_involved),
            })

        return timeline

    def _prepare_extraction_metadata(
        self,
        extracted_content: Any,
        structured_dict: Dict[str, Any],
        entity_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata = {
            'summary': self._get_field(extracted_content, 'summary') or structured_dict.get('summary') or '',
            'key_topics': self._get_field(extracted_content, 'key_topics') or structured_dict.get('key_topics') or [],
            'urgency_level': self._get_field(extracted_content, 'urgency_level') or structured_dict.get('urgency_level') or '',
            'content_type': self._get_field(extracted_content, 'content_type') or structured_dict.get('content_type') or '',
            'confidence_raw': self._get_field(extracted_content, 'confidence_score') or structured_dict.get('confidence_score'),
            'extraction_timestamp': self._get_field(extracted_content, 'extraction_timestamp') or structured_dict.get('extraction_timestamp'),
            'entity_counts': entity_context['counts'],
            'entity_foundation_ready': entity_context['foundation']['ready'],
            'missing_base_entities': entity_context['foundation']['missing'],
            'indicators': [],
        }

        confidence_value = metadata['confidence_raw']
        metadata['confidence'] = self._format_confidence(confidence_value)
        metadata['confidence_percent'] = self._format_percentage(confidence_value)

        key_topics = metadata['key_topics']
        if isinstance(key_topics, str):
            key_topics = [key_topics]
        metadata['key_topics'] = list(key_topics)
        metadata['key_topics_display'] = self._format_list(metadata['key_topics'])

        timestamp = metadata['extraction_timestamp']
        if isinstance(timestamp, datetime):
            metadata['extraction_timestamp_display'] = timestamp.strftime('%Y-%m-%d %H:%M UTC')
        elif isinstance(timestamp, str):
            metadata['extraction_timestamp_display'] = timestamp
        else:
            metadata['extraction_timestamp_display'] = ''

        metadata['urgency_level_display'] = metadata['urgency_level'] or 'unspecified'
        metadata['content_type_display'] = metadata['content_type'] or 'unspecified'

        indicators_source = self._get_field(extracted_content, 'indicators')
        if not indicators_source:
            indicators_source = structured_dict.get('indicators', [])

        indicators: List[Dict[str, Any]] = []
        for raw_indicator in indicators_source or []:
            indicator_dict = self._coerce_to_dict(raw_indicator)
            if not indicator_dict:
                continue

            indicators.append({
                'type': indicator_dict.get('type') or '',
                'value': indicator_dict.get('value') or '',
                'confidence_raw': indicator_dict.get('confidence'),
                'confidence': self._format_confidence(indicator_dict.get('confidence')),
                'description': indicator_dict.get('description') or '',
                'source': indicator_dict.get('source') or '',
            })

        metadata['indicators'] = indicators
        metadata['has_indicators'] = bool(indicators)
        metadata['entity_total'] = entity_context['summary']['total_entities']
        metadata['missing_base_entities_display'] = self._format_list(metadata['missing_base_entities'])

        return metadata
    
    def _normalize_issue_data(self, issue_data: Any) -> Dict[str, Any]:
        """Normalize issue data to a dictionary format for template access."""
        if isinstance(issue_data, dict):
            return issue_data
        
        # Handle GitHub issue objects
        issue_dict = {}
        
        # Common attributes
        for attr in ['number', 'title', 'body', 'url', 'created_at', 'updated_at']:
            if hasattr(issue_data, attr):
                value = getattr(issue_data, attr)
                issue_dict[attr] = value
        
        # Handle labels
        if hasattr(issue_data, 'labels'):
            labels = getattr(issue_data, 'labels')
            if hasattr(labels, '__iter__'):
                issue_dict['labels'] = [getattr(label, 'name', str(label)) for label in labels]
            else:
                issue_dict['labels'] = []
        else:
            issue_dict['labels'] = []
        
        # Handle author/user
        if hasattr(issue_data, 'user'):
            user = getattr(issue_data, 'user')
            if hasattr(user, 'login'):
                issue_dict['author'] = user.login
            else:
                issue_dict['author'] = str(user)
        elif hasattr(issue_data, 'author'):
            issue_dict['author'] = getattr(issue_data, 'author')
        else:
            issue_dict['author'] = 'Unknown'
        
        return issue_dict
    
    def _generate_section_placeholder(self, section_name: str, context: Dict[str, Any]) -> str:
        """Generate placeholder content for a missing section."""
        return f"""### {section_name.replace('_', ' ').title()}

*This section requires additional content based on the specific requirements of the {section_name} analysis.*

**Context**: Issue #{context.get('issue', {}).get('number', 'unknown')}  
**Section**: {section_name}  
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*[Content would be generated here based on workflow specifications and issue analysis]*
"""
    
    def generate_multiple_deliverables(self,
                                     issue_data: Any,  # Use Any to avoid type conflicts
                                     deliverable_specs: List[DeliverableSpec],
                                     workflow_info: WorkflowInfo,
                                     additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Generate multiple deliverables for a workflow.
        
        Args:
            issue_data: Issue data for context
            deliverable_specs: List of deliverable specifications
            workflow_info: Workflow information
            additional_context: Additional context for content generation
            
        Returns:
            Dictionary mapping deliverable names to generated content
        """
        results = {}
        
        # Sort deliverables by order
        sorted_specs = sorted(deliverable_specs, key=lambda x: x.order)
        
        for spec in sorted_specs:
            try:
                content = self.generate_deliverable(
                    issue_data, spec, workflow_info, additional_context
                )
                results[spec.name] = content
            except Exception as e:
                if spec.required:
                    raise RuntimeError(f"Failed to generate required deliverable '{spec.name}': {e}")
                else:
                    # Log warning for optional deliverables but continue
                    print(f"Warning: Failed to generate optional deliverable '{spec.name}': {e}")
        
        return results
    
    def _generate_basic_content(self, context: Dict[str, Any]) -> str:
        """Generate basic deliverable content."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        processing_id = context.get('processing_id', 'unknown')

        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Overview

{deliverable.description}

## Issue Context

**Labels**: {', '.join(issue.labels) if issue.labels else 'None'}
**Author**: {getattr(issue, 'author', 'Unknown')}
**Created**: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
**URL**: {issue.url}

### Issue Description

{issue.body}

## Analysis

*[This section would contain detailed analysis based on the issue content and deliverable requirements]*

### Key Points

- Deliverable type: {deliverable.type}
- Format: {deliverable.format}
- Processing completed successfully

## Summary

This deliverable was generated automatically based on the workflow specifications.
Further content development would be handled by AI integration in future versions.

---

*Generated automatically by Deliverable Generator*
*Workflow: {workflow.name}*
*Processing ID: {processing_id}*
"""
        return content
    
    def _generate_research_overview(self, context: Dict[str, Any]) -> str:
        """Generate research overview deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Executive Summary

This research overview provides a high-level scope and direction for investigating
the topic outlined in issue #{issue.number}.

## Research Scope

### Primary Research Questions

Based on the issue description, the following key questions will guide this research:

1. **Context Analysis**: What is the current state of the topic?
2. **Problem Definition**: What specific challenges or opportunities exist?
3. **Solution Exploration**: What potential approaches or solutions should be investigated?

### Research Boundaries

**In Scope:**
- [To be defined based on issue analysis]

**Out of Scope:**
- [To be defined based on issue constraints]

## Methodology Preview

The research will follow a structured approach:

1. **Background Review**: Comprehensive analysis of existing knowledge
2. **Current State Assessment**: Evaluation of present conditions
3. **Gap Analysis**: Identification of knowledge or solution gaps
4. **Recommendation Development**: Formulation of actionable next steps

## Expected Deliverables

This research will produce the following outputs:
- Background analysis document
- Methodology documentation
- Key findings report
- Actionable recommendations
- Reference compilation

## Timeline and Milestones

**Phase 1**: Background Analysis (Days 1-2)
**Phase 2**: Primary Research (Days 3-5)
**Phase 3**: Analysis and Synthesis (Days 6-7)
**Phase 4**: Recommendations and Documentation (Days 8-10)

## Success Criteria

The research will be considered successful when:
- All primary research questions are addressed
- Actionable recommendations are provided
- Findings are properly documented and referenced
- Results can inform decision-making processes

---

*Generated automatically by Deliverable Generator*
*Research Overview Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_background_analysis(self, context: Dict[str, Any]) -> str:
        """Generate background analysis deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Introduction

This document provides comprehensive background analysis for the topic outlined
in issue #{issue.number}, establishing the historical and contextual foundation
for further research.

## Historical Context

### Timeline of Development

*[This section would contain a chronological overview of relevant developments]*

### Key Milestones

- **[Date]**: [Significant event or development]
- **[Date]**: [Major change or breakthrough]
- **[Date]**: [Current state establishment]

## Current State Analysis

### Industry/Domain Overview

*[Analysis of the current state of the relevant industry or domain]*

### Existing Solutions

#### Available Approaches

1. **[Solution/Approach 1]**
   - Description: [Brief overview]
   - Strengths: [Key advantages]
   - Limitations: [Known constraints]

2. **[Solution/Approach 2]**
   - Description: [Brief overview]
   - Strengths: [Key advantages]
   - Limitations: [Known constraints]

### Market/Technology Landscape

*[Overview of relevant market conditions or technological landscape]*

## Stakeholder Analysis

### Primary Stakeholders

- **[Stakeholder Group 1]**: [Role and interests]
- **[Stakeholder Group 2]**: [Role and interests]
- **[Stakeholder Group 3]**: [Role and interests]

### Stakeholder Interests and Concerns

*[Analysis of different stakeholder perspectives and potential conflicts]*

## Previous Research and Studies

### Academic Research

*[Overview of relevant academic work and findings]*

### Industry Studies

*[Summary of industry reports and analyses]*

### Case Studies

*[Relevant case studies and their implications]*

## Knowledge Gaps

### Identified Gaps

1. **[Gap Area 1]**: [Description of missing knowledge or understanding]
2. **[Gap Area 2]**: [Description of missing knowledge or understanding]
3. **[Gap Area 3]**: [Description of missing knowledge or understanding]

### Research Opportunities

*[Areas where new research could provide valuable insights]*

## Conclusions

### Key Insights

- [Primary insight from background analysis]
- [Secondary insight from background analysis]
- [Additional relevant conclusions]

### Implications for Current Research

*[How this background analysis informs the current research direction]*

---

*Generated automatically by Deliverable Generator*
*Background Analysis Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_methodology(self, context: Dict[str, Any]) -> str:
        """Generate methodology deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Overview

This document outlines the research methodology employed to investigate the topic
defined in issue #{issue.number}.

## Research Approach

### Research Philosophy

**Approach Type**: [Qualitative/Quantitative/Mixed Methods]
**Research Paradigm**: [Positivist/Interpretivist/Pragmatic]
**Reasoning Method**: [Deductive/Inductive/Abductive]

### Research Design

**Study Type**: [Exploratory/Descriptive/Explanatory]
**Time Horizon**: [Cross-sectional/Longitudinal]
**Data Strategy**: [Mono-method/Multi-method/Mixed-method]

## Data Collection Methods

### Primary Data Sources

1. **[Method 1]**
   - **Description**: [What this method involves]
   - **Rationale**: [Why this method was chosen]
   - **Process**: [How data will be collected]
   - **Expected Output**: [What kind of data this will provide]

2. **[Method 2]**
   - **Description**: [What this method involves]
   - **Rationale**: [Why this method was chosen]
   - **Process**: [How data will be collected]
   - **Expected Output**: [What kind of data this will provide]

### Secondary Data Sources

- **Literature Review**: Academic papers, industry reports, case studies
- **Documentation Analysis**: Technical specifications, user guides, standards
- **Historical Data**: Previous studies, archived information, trend data

## Sampling Strategy

### Target Population

**Definition**: [Description of the target population]
**Size**: [Estimated size of population]
**Characteristics**: [Key characteristics relevant to research]

### Sample Selection

**Sampling Method**: [Random/Purposive/Convenience/Stratified]
**Sample Size**: [Planned sample size and justification]
**Selection Criteria**: [Inclusion and exclusion criteria]

## Data Analysis Framework

### Analytical Approach

**Analysis Type**: [Content analysis/Statistical analysis/Thematic analysis]
**Tools and Techniques**: [Software, frameworks, or methods to be used]
**Validation Methods**: [How findings will be validated]

### Quality Assurance

**Reliability Measures**: [Steps to ensure consistent results]
**Validity Measures**: [Steps to ensure accurate conclusions]
**Bias Mitigation**: [Strategies to minimize research bias]

## Ethical Considerations

### Ethical Approval

**Requirements**: [Any ethical review or approval needed]
**Considerations**: [Key ethical issues to address]

### Data Protection

**Privacy**: [How participant/subject privacy will be protected]
**Confidentiality**: [Data confidentiality measures]
**Storage**: [Secure data storage and retention policies]

## Timeline and Milestones

### Phase 1: Preparation (Days 1-2)
- Finalize research instruments
- Prepare data collection materials
- Establish access to data sources

### Phase 2: Data Collection (Days 3-6)
- Execute primary data collection
- Gather secondary data sources
- Document collection process

### Phase 3: Analysis (Days 7-9)
- Process and organize collected data
- Apply analytical frameworks
- Identify patterns and themes

### Phase 4: Validation (Days 10)
- Validate findings through triangulation
- Review conclusions for consistency
- Prepare final analysis report

## Limitations and Constraints

### Methodological Limitations

- **[Limitation 1]**: [Description and potential impact]
- **[Limitation 2]**: [Description and potential impact]
- **[Limitation 3]**: [Description and potential impact]

### Resource Constraints

- **Time**: [Time-related constraints and implications]
- **Access**: [Data or resource access limitations]
- **Scope**: [Scope limitations and their effects]

## Expected Outcomes

### Primary Deliverables

1. **Data Collection Report**: Summary of collected information
2. **Analysis Results**: Processed findings and insights
3. **Methodology Evaluation**: Assessment of approach effectiveness

### Success Metrics

- **Completeness**: [Criteria for complete data collection]
- **Quality**: [Standards for data and analysis quality]
- **Relevance**: [Measures of finding relevance to research questions]

---

*Generated automatically by Deliverable Generator*
*Research Methodology Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_findings(self, context: Dict[str, Any]) -> str:
        """Generate findings deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Executive Summary

This document presents the key findings from the research conducted on the topic
outlined in issue #{issue.number}.

## Research Questions Addressed

### Primary Research Question
*[Restate the main research question being addressed]*

### Secondary Questions
1. *[Secondary question 1]*
2. *[Secondary question 2]*
3. *[Secondary question 3]*

## Key Findings

### Finding 1: [Major Finding Title]

**Summary**: [Brief summary of the finding]

**Evidence**: 
- [Supporting evidence point 1]
- [Supporting evidence point 2]
- [Supporting evidence point 3]

**Implications**: [What this finding means for the research objectives]

**Confidence Level**: [High/Medium/Low] - [Brief justification]

### Finding 2: [Major Finding Title]

**Summary**: [Brief summary of the finding]

**Evidence**: 
- [Supporting evidence point 1]
- [Supporting evidence point 2]
- [Supporting evidence point 3]

**Implications**: [What this finding means for the research objectives]

**Confidence Level**: [High/Medium/Low] - [Brief justification]

### Finding 3: [Major Finding Title]

**Summary**: [Brief summary of the finding]

**Evidence**: 
- [Supporting evidence point 1]
- [Supporting evidence point 2]
- [Supporting evidence point 3]

**Implications**: [What this finding means for the research objectives]

**Confidence Level**: [High/Medium/Low] - [Brief justification]

## Detailed Analysis

### Data Overview

**Sources Analyzed**: [Summary of data sources used]
**Volume**: [Quantity of data analyzed]
**Quality Assessment**: [Overall assessment of data quality]

### Analytical Results

#### Quantitative Results
*[If applicable, present numerical findings, statistics, measurements]*

#### Qualitative Insights
*[Present thematic findings, patterns, observations]*

### Cross-Analysis Patterns

**Convergent Themes**: [Patterns that appeared across multiple data sources]
**Divergent Results**: [Areas where findings conflicted or varied]
**Unexpected Discoveries**: [Findings that were not anticipated]

## Validation and Reliability

### Triangulation Results
*[How findings were validated across multiple sources or methods]*

### Peer Review Feedback
*[If applicable, summary of expert review or feedback]*

### Limitations Assessment
*[How identified limitations may have affected findings]*

## Comparative Analysis

### Comparison with Previous Research
*[How findings align with or differ from existing knowledge]*

### Industry/Domain Benchmarks
*[How findings compare to industry standards or benchmarks]*

### Best Practice Alignment
*[How findings relate to established best practices]*

## Significance Assessment

### Statistical Significance
*[If applicable, statistical significance of quantitative findings]*

### Practical Significance
*[Real-world importance and applicability of findings]*

### Strategic Implications
*[How findings impact strategic decision-making]*

## Emerging Themes

### Theme 1: [Theme Title]
- **Description**: [What this theme represents]
- **Frequency**: [How often this theme appeared]
- **Relevance**: [Why this theme is important]

### Theme 2: [Theme Title]
- **Description**: [What this theme represents]
- **Frequency**: [How often this theme appeared]
- **Relevance**: [Why this theme is important]

### Theme 3: [Theme Title]
- **Description**: [What this theme represents]
- **Frequency**: [How often this theme appeared]
- **Relevance**: [Why this theme is important]

## Gaps and Unknowns

### Data Gaps
*[Areas where insufficient data was available]*

### Research Gaps
*[Questions that remain unanswered]*

### Future Research Needs
*[Areas requiring additional investigation]*

## Conclusions

### Primary Conclusions
1. [Main conclusion based on findings]
2. [Secondary conclusion based on findings]
3. [Additional conclusion based on findings]

### Answer to Research Questions
*[Direct answers to the original research questions based on findings]*

### Overall Assessment
*[Overall evaluation of what the research has revealed]*

---

*Generated automatically by Deliverable Generator*
*Key Findings Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_recommendations(self, context: Dict[str, Any]) -> str:
        """Generate recommendations deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Executive Summary

Based on the research findings from issue #{issue.number}, this document provides
actionable recommendations for addressing the identified opportunities and challenges.

## Recommendation Framework

### Decision Criteria
- **Feasibility**: Technical and resource feasibility
- **Impact**: Expected positive outcomes
- **Risk**: Associated risks and mitigation strategies
- **Timeline**: Implementation timeframe
- **Cost**: Resource requirements and budget implications

## Primary Recommendations

### Recommendation 1: [Recommendation Title]

**Priority**: High/Medium/Low
**Category**: [Strategic/Operational/Technical/Process]

**Problem Addressed**: [Specific issue or opportunity this addresses]

**Recommended Action**: 
[Clear, specific description of what should be done]

**Rationale**: 
[Why this recommendation is important based on research findings]

**Implementation Steps**:
1. [Step 1 with timeline]
2. [Step 2 with timeline]
3. [Step 3 with timeline]

**Success Metrics**:
- [Measurable outcome 1]
- [Measurable outcome 2]
- [Measurable outcome 3]

**Resources Required**:
- **Personnel**: [Skill sets and time commitments needed]
- **Technology**: [Technical requirements or tools]
- **Budget**: [Estimated costs]

**Risks and Mitigation**:
- **Risk 1**: [Description] → **Mitigation**: [Strategy]
- **Risk 2**: [Description] → **Mitigation**: [Strategy]

**Timeline**: [Expected implementation duration]

### Recommendation 2: [Recommendation Title]

**Priority**: High/Medium/Low
**Category**: [Strategic/Operational/Technical/Process]

**Problem Addressed**: [Specific issue or opportunity this addresses]

**Recommended Action**: 
[Clear, specific description of what should be done]

**Rationale**: 
[Why this recommendation is important based on research findings]

**Implementation Steps**:
1. [Step 1 with timeline]
2. [Step 2 with timeline]
3. [Step 3 with timeline]

**Success Metrics**:
- [Measurable outcome 1]
- [Measurable outcome 2]
- [Measurable outcome 3]

**Resources Required**:
- **Personnel**: [Skill sets and time commitments needed]
- **Technology**: [Technical requirements or tools]
- **Budget**: [Estimated costs]

**Risks and Mitigation**:
- **Risk 1**: [Description] → **Mitigation**: [Strategy]
- **Risk 2**: [Description] → **Mitigation**: [Strategy]

**Timeline**: [Expected implementation duration]

### Recommendation 3: [Recommendation Title]

**Priority**: High/Medium/Low
**Category**: [Strategic/Operational/Technical/Process]

**Problem Addressed**: [Specific issue or opportunity this addresses]

**Recommended Action**: 
[Clear, specific description of what should be done]

**Rationale**: 
[Why this recommendation is important based on research findings]

**Implementation Steps**:
1. [Step 1 with timeline]
2. [Step 2 with timeline]
3. [Step 3 with timeline]

**Success Metrics**:
- [Measurable outcome 1]
- [Measurable outcome 2]
- [Measurable outcome 3]

**Resources Required**:
- **Personnel**: [Skill sets and time commitments needed]
- **Technology**: [Technical requirements or tools]
- **Budget**: [Estimated costs]

**Risks and Mitigation**:
- **Risk 1**: [Description] → **Mitigation**: [Strategy]
- **Risk 2**: [Description] → **Mitigation**: [Strategy]

**Timeline**: [Expected implementation duration]

## Implementation Roadmap

### Phase 1: Foundation (Months 1-2)
- [Key activities and milestones]
- **Dependencies**: [What needs to be completed first]
- **Deliverables**: [Expected outputs]

### Phase 2: Development (Months 3-5)
- [Key activities and milestones]
- **Dependencies**: [What needs to be completed first]
- **Deliverables**: [Expected outputs]

### Phase 3: Implementation (Months 6-8)
- [Key activities and milestones]
- **Dependencies**: [What needs to be completed first]
- **Deliverables**: [Expected outputs]

### Phase 4: Optimization (Months 9-12)
- [Key activities and milestones]
- **Dependencies**: [What needs to be completed first]
- **Deliverables**: [Expected outputs]

## Resource Allocation

### Personnel Requirements
- **Project Manager**: [Time commitment and responsibilities]
- **Technical Lead**: [Time commitment and responsibilities]
- **Domain Expert**: [Time commitment and responsibilities]
- **Additional Staff**: [Other roles and requirements]

### Budget Estimation
- **Personnel Costs**: [Estimated costs]
- **Technology/Tools**: [Estimated costs]
- **External Services**: [Estimated costs]
- **Contingency**: [Buffer for unexpected costs]
- **Total Estimated Cost**: [Sum of all components]

## Risk Assessment

### High-Risk Items
1. **[Risk Description]**
   - **Probability**: High/Medium/Low
   - **Impact**: High/Medium/Low
   - **Mitigation Strategy**: [Detailed approach]

2. **[Risk Description]**
   - **Probability**: High/Medium/Low
   - **Impact**: High/Medium/Low
   - **Mitigation Strategy**: [Detailed approach]

### Medium-Risk Items
*[List and describe medium-risk considerations]*

### Risk Monitoring
*[How risks will be tracked and managed throughout implementation]*

## Success Monitoring

### Key Performance Indicators (KPIs)
- **[KPI 1]**: [Definition and measurement method]
- **[KPI 2]**: [Definition and measurement method]
- **[KPI 3]**: [Definition and measurement method]

### Monitoring Schedule
- **Weekly**: [What will be monitored weekly]
- **Monthly**: [What will be monitored monthly]
- **Quarterly**: [What will be monitored quarterly]

### Review and Adjustment Process
*[How recommendations will be reviewed and adjusted based on results]*

## Alternative Approaches

### Option A: [Alternative Title]
**Description**: [Brief description of alternative approach]
**Pros**: [Advantages compared to primary recommendations]
**Cons**: [Disadvantages or limitations]
**Recommendation**: [When this might be preferred]

### Option B: [Alternative Title]
**Description**: [Brief description of alternative approach]
**Pros**: [Advantages compared to primary recommendations]
**Cons**: [Disadvantages or limitations]
**Recommendation**: [When this might be preferred]

## Next Steps

### Immediate Actions (Next 30 Days)
1. [Action item with owner and deadline]
2. [Action item with owner and deadline]
3. [Action item with owner and deadline]

### Short-term Actions (Next 3 Months)
1. [Action item with owner and deadline]
2. [Action item with owner and deadline]
3. [Action item with owner and deadline]

### Long-term Actions (Next 6-12 Months)
1. [Action item with owner and deadline]
2. [Action item with owner and deadline]
3. [Action item with owner and deadline]

## Conclusion

*[Summary of key recommendations and expected benefits]*

---

*Generated automatically by Deliverable Generator*
*Recommendations Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_references(self, context: Dict[str, Any]) -> str:
        """Generate references deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Bibliography

### Academic Sources

#### Journal Articles

1. Author, A. A. (Year). Title of article. *Title of Journal*, Volume(Issue), pages. DOI or URL

2. Author, B. B., & Author, C. C. (Year). Title of article. *Title of Journal*, Volume(Issue), pages. DOI or URL

3. Author, D. D., Author, E. E., & Author, F. F. (Year). Title of article. *Title of Journal*, Volume(Issue), pages. DOI or URL

#### Books and Monographs

1. Author, A. A. (Year). *Title of book*. Publisher.

2. Author, B. B., & Author, C. C. (Year). *Title of book* (Edition). Publisher.

3. Editor, A. A. (Ed.). (Year). *Title of edited book*. Publisher.

#### Conference Proceedings

1. Author, A. A. (Year, Month). Title of paper. In *Proceedings of Conference Name* (pp. xx-xx). Publisher.

2. Author, B. B., & Author, C. C. (Year, Month). Title of paper. In A. Editor & B. Editor (Eds.), *Proceedings of Conference Name* (pp. xx-xx). Publisher.

### Industry and Technical Reports

#### White Papers

1. Organization Name. (Year). *Title of white paper*. Retrieved from URL

2. Author, A. A. (Year). *Title of white paper*. Organization Name. Retrieved from URL

#### Industry Reports

1. Research Firm. (Year). *Title of industry report*. Retrieved from URL

2. Government Agency. (Year). *Title of government report* (Report No. xxx). Retrieved from URL

#### Technical Documentation

1. Organization Name. (Year). *Title of technical documentation* (Version x.x). Retrieved from URL

2. Software Vendor. (Year). *Product documentation: Feature guide*. Retrieved from URL

### Web Resources

#### Websites and Online Articles

1. Author, A. A. (Year, Month Day). Title of web page. *Website Name*. Retrieved Month Day, Year, from URL

2. Organization Name. (Year, Month Day). Title of web page. Retrieved Month Day, Year, from URL

#### Blog Posts and Online Content

1. Author, A. A. (Year, Month Day). Title of blog post. *Blog Name*. Retrieved from URL

2. Author, B. B. (Year, Month Day). Title of article. *Online Publication*. Retrieved from URL

### Data Sources

#### Databases

1. Database Name. (Year). Title of dataset or query. Retrieved Month Day, Year, from URL

2. Organization Name. (Year). *Statistical database name*. Retrieved from URL

#### APIs and Services

1. Service Provider. (Year). *API name and version*. Retrieved from URL

2. Data Provider. (Year). *Dataset name*. Retrieved via API from URL

### Standards and Specifications

#### Technical Standards

1. Standards Organization. (Year). *Standard title* (Standard No. XXX-YYYY). Retrieved from URL

2. Industry Consortium. (Year). *Specification title* (Version x.x). Retrieved from URL

#### Legal and Regulatory Documents

1. Government Body. (Year). *Regulation or law title* (Regulation No. XXX). Retrieved from URL

2. Regulatory Agency. (Year). *Guidance document title*. Retrieved from URL

### Interviews and Personal Communications

#### Expert Interviews

1. Expert, A. A. (Year, Month Day). Personal interview.

2. Professional, B. B. (Year, Month Day). Email interview.

#### Industry Contacts

1. Practitioner, C. C. (Year, Month Day). Phone interview.

2. Specialist, D. D. (Year, Month Day). Video conference interview.

## Source Quality Assessment

### Primary Sources
*[List and assess the quality and reliability of primary sources used]*

### Secondary Sources
*[List and assess the quality and reliability of secondary sources used]*

### Currency and Relevance
*[Assessment of how current and relevant the sources are to the research topic]*

## Search Strategy

### Databases Searched
- Academic Database 1
- Academic Database 2
- Industry Database 1
- Industry Database 2

### Search Terms Used
- Primary keywords: [list]
- Secondary keywords: [list]
- Boolean operators: [describe search strategy]

### Inclusion/Exclusion Criteria
**Included:**
- [Criteria for including sources]

**Excluded:**
- [Criteria for excluding sources]

### Date Range
- **Start Date**: [Earliest acceptable publication date]
- **End Date**: [Latest acceptable publication date]
- **Rationale**: [Why this date range was chosen]

## Source Annotation

### Key Sources

#### [Source Title 1]
**Citation**: [Full citation]
**Summary**: [Brief summary of content and relevance]
**Key Findings**: [Main points or findings relevant to research]
**Limitations**: [Any limitations or biases noted]
**Quality Rating**: [High/Medium/Low with justification]

#### [Source Title 2]
**Citation**: [Full citation]
**Summary**: [Brief summary of content and relevance]
**Key Findings**: [Main points or findings relevant to research]
**Limitations**: [Any limitations or biases noted]
**Quality Rating**: [High/Medium/Low with justification]

#### [Source Title 3]
**Citation**: [Full citation]
**Summary**: [Brief summary of content and relevance]
**Key Findings**: [Main points or findings relevant to research]
**Limitations**: [Any limitations or biases noted]
**Quality Rating**: [High/Medium/Low with justification]

## Additional Resources

### Recommended Further Reading
1. [Source with brief explanation of relevance]
2. [Source with brief explanation of relevance]
3. [Source with brief explanation of relevance]

### Related Topics for Future Research
- [Topic 1]: [Brief description]
- [Topic 2]: [Brief description]
- [Topic 3]: [Brief description]

---

*Generated automatically by Deliverable Generator*
*References Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*

## Citation Style Note

This bibliography follows a modified APA style format. For specific publication requirements,
please adjust citations according to the required style guide (APA, MLA, Chicago, etc.).
"""
        return content
    
    def _generate_appendices(self, context: Dict[str, Any]) -> str:
        """Generate appendices deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Overview

This document contains supporting materials, detailed data, and supplementary information
that supports the main research deliverables for issue #{issue.number}.

## Appendix A: Raw Data Summary

### Data Collection Summary
- **Collection Period**: [Start date] to [End date]
- **Data Sources**: [Number and types of sources]
- **Data Volume**: [Quantity of data collected]
- **Quality Assessment**: [Overall quality rating and notes]

### Data Structure
*[Description of how data is organized and structured]*

### Data Dictionary
| Field Name | Type | Description | Source |
|------------|------|-------------|---------|
| [field1] | [type] | [description] | [source] |
| [field2] | [type] | [description] | [source] |
| [field3] | [type] | [description] | [source] |

## Appendix B: Detailed Analysis Results

### Statistical Analysis Output
*[If applicable, detailed statistical results, tables, charts]*

### Qualitative Analysis Details
*[Detailed coding schemes, theme development, quote collections]*

### Cross-Reference Analysis
*[Detailed correlation or relationship analysis between different data points]*

## Appendix C: Research Instruments

### Survey Questionnaires
*[Full text of any surveys or questionnaires used]*

### Interview Guides
*[Interview protocols and question frameworks used]*

### Data Collection Templates
*[Templates and forms used for data collection]*

## Appendix D: Technical Specifications

### System Requirements
*[Technical requirements and specifications relevant to the research]*

### Configuration Details
*[System or tool configurations used in the research]*

### Code and Scripts
*[Any code, scripts, or automation tools used in analysis]*

```
# Example analysis script
# [Include relevant code snippets or scripts]
```

## Appendix E: Regulatory and Compliance Information

### Applicable Standards
*[Relevant industry standards or regulations]*

### Compliance Checklist
- [ ] Standard/Regulation 1: [Compliance status]
- [ ] Standard/Regulation 2: [Compliance status]
- [ ] Standard/Regulation 3: [Compliance status]

### Legal Considerations
*[Any legal or regulatory considerations relevant to the research]*

## Appendix F: Extended Literature Review

### Additional Sources Reviewed
*[Sources reviewed but not included in main references]*

### Comparative Analysis Tables
*[Detailed comparison tables of different approaches or solutions]*

### Historical Timeline
*[Extended chronological information]*

## Appendix G: Stakeholder Information

### Stakeholder Contact Directory
*[Contact information for key stakeholders (anonymized as appropriate)]*

### Stakeholder Interview Summaries
*[Detailed summaries of stakeholder interviews]*

### Stakeholder Feedback Compilation
*[Compilation of feedback received during research process]*

## Appendix H: Risk Assessment Details

### Risk Register
| Risk ID | Risk Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-----------------|-------------|---------|-------------------|-------|
| R001 | [Risk description] | [High/Med/Low] | [High/Med/Low] | [Strategy] | [Owner] |
| R002 | [Risk description] | [High/Med/Low] | [High/Med/Low] | [Strategy] | [Owner] |

### Risk Analysis Matrices
*[Detailed risk analysis frameworks and assessment matrices]*

### Contingency Plans
*[Detailed contingency plans for identified risks]*

## Appendix I: Financial Analysis

### Cost-Benefit Analysis Details
*[Detailed financial calculations and projections]*

### Budget Breakdown
*[Detailed budget information and cost categories]*

### ROI Calculations
*[Return on investment calculations and assumptions]*

## Appendix J: Implementation Planning

### Detailed Project Plans
*[Comprehensive project plans with tasks, timelines, and dependencies]*

### Resource Allocation Models
*[Detailed resource planning and allocation frameworks]*

### Success Metrics Framework
*[Comprehensive measurement and evaluation frameworks]*

## Appendix K: Quality Assurance

### Review Checklists
*[Quality assurance checklists used throughout the research]*

### Validation Results
*[Results of validation activities and verification processes]*

### Audit Trail
*[Documentation of research process and decision-making]*

## Appendix L: Glossary

### Technical Terms
- **[Term 1]**: [Definition]
- **[Term 2]**: [Definition]
- **[Term 3]**: [Definition]

### Acronyms and Abbreviations
- **[Acronym 1]**: [Full form and explanation]
- **[Acronym 2]**: [Full form and explanation]
- **[Acronym 3]**: [Full form and explanation]

### Domain-Specific Terminology
*[Definitions of specialized terms used in the research domain]*

## Appendix M: Version Control and Change Log

### Document Version History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [Date] | [Author] | Initial version |
| 1.1 | [Date] | [Author] | [Changes made] |

### Change Management Process
*[Process used for managing changes to deliverables and analysis]*

### Approval Records
*[Records of approvals and sign-offs received]*

---

*Generated automatically by Deliverable Generator*
*Appendices Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*

## Usage Notes

- This appendix structure can be customized based on specific research needs
- Not all sections may be applicable to every research project
- Additional appendices can be added as needed for specific deliverables
- Sensitive information should be redacted or anonymized as appropriate
"""
        return content
    
    def _generate_technical_review(self, context: Dict[str, Any]) -> str:
        """Generate technical review deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Review Summary

This technical review evaluates the technical aspects, architecture, and implementation
considerations related to issue #{issue.number}.

## Technical Architecture Review

### System Overview
*[High-level description of the system or technology being reviewed]*

### Architecture Evaluation

#### Current State
- **Architecture Pattern**: [Description of current architectural approach]
- **Technology Stack**: [Technologies currently in use]
- **Integration Points**: [Key integration and interface points]
- **Data Flow**: [How data moves through the system]

#### Strengths
1. **[Strength 1]**: [Description and impact]
2. **[Strength 2]**: [Description and impact]
3. **[Strength 3]**: [Description and impact]

#### Weaknesses
1. **[Weakness 1]**: [Description and impact]
2. **[Weakness 2]**: [Description and impact]
3. **[Weakness 3]**: [Description and impact]

## Code Quality Assessment

### Code Review Methodology
- **Review Scope**: [What code/components were reviewed]
- **Review Criteria**: [Standards and criteria used for evaluation]
- **Tools Used**: [Static analysis tools, linters, etc.]

### Quality Metrics
- **Code Coverage**: [Test coverage percentage]
- **Complexity Score**: [Cyclomatic complexity or similar metrics]
- **Technical Debt**: [Assessment of technical debt level]
- **Documentation**: [Quality and completeness of code documentation]

### Key Findings
1. **[Finding 1]**: [Description and severity]
2. **[Finding 2]**: [Description and severity]
3. **[Finding 3]**: [Description and severity]

## Security Assessment

### Security Review Scope
*[Description of what security aspects were evaluated]*

### Security Findings

#### Vulnerabilities Identified
1. **[Vulnerability 1]**
   - **Severity**: Critical/High/Medium/Low
   - **Description**: [Detailed description]
   - **Impact**: [Potential impact if exploited]
   - **Recommendation**: [How to address]

2. **[Vulnerability 2]**
   - **Severity**: Critical/High/Medium/Low
   - **Description**: [Detailed description]
   - **Impact**: [Potential impact if exploited]
   - **Recommendation**: [How to address]

#### Security Best Practices
- **Authentication**: [Assessment of authentication mechanisms]
- **Authorization**: [Assessment of authorization controls]
- **Data Protection**: [Assessment of data protection measures]
- **Input Validation**: [Assessment of input validation]

## Performance Analysis

### Performance Testing Results
- **Load Testing**: [Results of load testing]
- **Stress Testing**: [Results of stress testing]
- **Performance Benchmarks**: [Comparison with benchmarks]

### Performance Bottlenecks
1. **[Bottleneck 1]**: [Description and impact on performance]
2. **[Bottleneck 2]**: [Description and impact on performance]
3. **[Bottleneck 3]**: [Description and impact on performance]

### Optimization Opportunities
*[Areas where performance could be improved]*

## Scalability Assessment

### Current Capacity
- **User Capacity**: [Current user capacity]
- **Data Capacity**: [Current data handling capacity]
- **Processing Capacity**: [Current processing capacity]

### Scalability Constraints
*[Factors that limit scalability]*

### Scaling Recommendations
*[Recommendations for improving scalability]*

## Technology Stack Evaluation

### Current Technologies

#### Frontend Technologies
- **Framework**: [Frontend framework assessment]
- **Libraries**: [Key libraries and their assessment]
- **Build Tools**: [Build and deployment tools assessment]

#### Backend Technologies
- **Platform**: [Backend platform assessment]
- **Database**: [Database technology assessment]
- **APIs**: [API design and implementation assessment]

#### Infrastructure
- **Hosting**: [Hosting and infrastructure assessment]
- **Monitoring**: [Monitoring and logging assessment]
- **Deployment**: [Deployment process assessment]

### Technology Recommendations

#### Upgrade Recommendations
1. **[Technology/Component]**: [Current version] → [Recommended version]
   - **Rationale**: [Why upgrade is recommended]
   - **Benefits**: [Expected benefits]
   - **Risks**: [Associated risks]

2. **[Technology/Component]**: [Current version] → [Recommended version]
   - **Rationale**: [Why upgrade is recommended]
   - **Benefits**: [Expected benefits]
   - **Risks**: [Associated risks]

#### Alternative Technologies
*[Alternative technology options that could be considered]*

## Compliance and Standards

### Standards Compliance
- **[Standard 1]**: [Compliance status and gaps]
- **[Standard 2]**: [Compliance status and gaps]
- **[Standard 3]**: [Compliance status and gaps]

### Regulatory Requirements
*[Assessment of regulatory compliance requirements]*

### Certification Considerations
*[Any certifications that may be relevant or required]*

## Risk Assessment

### Technical Risks

#### High-Priority Risks
1. **[Risk Description]**
   - **Probability**: [High/Medium/Low]
   - **Impact**: [High/Medium/Low]
   - **Mitigation**: [Mitigation strategy]

2. **[Risk Description]**
   - **Probability**: [High/Medium/Low]
   - **Impact**: [High/Medium/Low]
   - **Mitigation**: [Mitigation strategy]

#### Medium-Priority Risks
*[List and describe medium-priority technical risks]*

### Operational Risks
*[Risks related to operations, maintenance, and support]*

## Recommendations

### Immediate Actions (0-30 days)
1. **[Action Item]**: [Description and rationale]
2. **[Action Item]**: [Description and rationale]
3. **[Action Item]**: [Description and rationale]

### Short-term Improvements (1-6 months)
1. **[Improvement]**: [Description and expected benefit]
2. **[Improvement]**: [Description and expected benefit]
3. **[Improvement]**: [Description and expected benefit]

### Long-term Strategic Changes (6-12 months)
1. **[Strategic Change]**: [Description and expected impact]
2. **[Strategic Change]**: [Description and expected impact]
3. **[Strategic Change]**: [Description and expected impact]

## Implementation Roadmap

### Phase 1: Critical Fixes
- **Timeline**: [Duration]
- **Focus**: [Primary focus areas]
- **Deliverables**: [Expected outputs]

### Phase 2: Performance Optimization
- **Timeline**: [Duration]
- **Focus**: [Primary focus areas]
- **Deliverables**: [Expected outputs]

### Phase 3: Architecture Enhancement
- **Timeline**: [Duration]
- **Focus**: [Primary focus areas]
- **Deliverables**: [Expected outputs]

## Resource Requirements

### Technical Resources
- **Development Team**: [Required skills and capacity]
- **Infrastructure**: [Hardware/software requirements]
- **Tools**: [Additional tools needed]

### Budget Estimation
- **Development Costs**: [Estimated costs]
- **Infrastructure Costs**: [Estimated costs]
- **Tooling Costs**: [Estimated costs]
- **Total Estimated Cost**: [Total estimation]

## Success Metrics

### Key Performance Indicators
- **Performance**: [Performance-related KPIs]
- **Quality**: [Quality-related KPIs]
- **Security**: [Security-related KPIs]
- **Reliability**: [Reliability-related KPIs]

### Measurement Plan
*[How success will be measured and monitored]*

---

*Generated automatically by Deliverable Generator*
*Technical Review Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*
"""
        return content
    
    def _generate_risk_assessment(self, context: Dict[str, Any]) -> str:
        """Generate risk assessment deliverable."""
        issue = context["issue"]
        deliverable = context["deliverable"]
        workflow = context["workflow"]
        timestamp = context["timestamp"]
        
        content = f"""# {deliverable.title}

**Issue**: #{issue.number} - {issue.title}
**Generated**: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Workflow**: {workflow.name}

## Executive Summary

This risk assessment evaluates potential risks associated with the topic outlined
in issue #{issue.number}, providing a comprehensive analysis of threats,
vulnerabilities, and mitigation strategies.

## Risk Assessment Methodology

### Assessment Framework
- **Risk Model**: [Framework used for risk assessment]
- **Evaluation Criteria**: [Criteria used to evaluate risks]
- **Scoring System**: [How risks are scored and prioritized]
- **Assessment Scope**: [What areas are covered in this assessment]

### Risk Categories
1. **Technical Risks**: Technology-related risks and failures
2. **Operational Risks**: Process and operational challenges
3. **Financial Risks**: Budget, cost, and financial impacts
4. **Strategic Risks**: Strategic alignment and business risks
5. **Compliance Risks**: Regulatory and compliance issues
6. **Security Risks**: Security vulnerabilities and threats

## Risk Register

### Critical Risks (High Impact, High Probability)

#### Risk CR-001: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: High (>70%)
- **Impact**: High (Severe consequences)
- **Risk Score**: [Calculated risk score]
- **Triggers**: [What could cause this risk to occur]
- **Indicators**: [Early warning signs]
- **Owner**: [Risk owner/responsible party]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Contingency Plan**: [Backup plan if risk occurs]
- **Timeline**: [When risk might occur]

#### Risk CR-002: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: High (>70%)
- **Impact**: High (Severe consequences)
- **Risk Score**: [Calculated risk score]
- **Triggers**: [What could cause this risk to occur]
- **Indicators**: [Early warning signs]
- **Owner**: [Risk owner/responsible party]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Contingency Plan**: [Backup plan if risk occurs]
- **Timeline**: [When risk might occur]

### High Risks (High Impact, Medium Probability OR Medium Impact, High Probability)

#### Risk HR-001: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: [High/Medium] ([Percentage range])
- **Impact**: [High/Medium] ([Impact description])
- **Risk Score**: [Calculated risk score]
- **Triggers**: [What could cause this risk to occur]
- **Indicators**: [Early warning signs]
- **Owner**: [Risk owner/responsible party]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Contingency Plan**: [Backup plan if risk occurs]
- **Timeline**: [When risk might occur]

#### Risk HR-002: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: [High/Medium] ([Percentage range])
- **Impact**: [High/Medium] ([Impact description])
- **Risk Score**: [Calculated risk score]
- **Triggers**: [What could cause this risk to occur]
- **Indicators**: [Early warning signs]
- **Owner**: [Risk owner/responsible party]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Contingency Plan**: [Backup plan if risk occurs]
- **Timeline**: [When risk might occur]

### Medium Risks

#### Risk MR-001: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: Medium (30-70%)
- **Impact**: Medium (Moderate consequences)
- **Risk Score**: [Calculated risk score]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Owner**: [Risk owner/responsible party]

#### Risk MR-002: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: Medium (30-70%)
- **Impact**: Medium (Moderate consequences)
- **Risk Score**: [Calculated risk score]
- **Mitigation Strategy**: [Primary mitigation approach]
- **Owner**: [Risk owner/responsible party]

### Low Risks

#### Risk LR-001: [Risk Title]
- **Description**: [Detailed description of the risk]
- **Category**: [Risk category]
- **Probability**: Low (<30%)
- **Impact**: Low (Minor consequences)
- **Risk Score**: [Calculated risk score]
- **Monitoring**: [How this risk will be monitored]

## Risk Analysis by Category

### Technical Risks

#### Technology Failure Risks
- **System Outages**: [Risk of system downtime]
- **Performance Degradation**: [Risk of poor performance]
- **Integration Failures**: [Risk of integration issues]
- **Data Loss**: [Risk of data corruption or loss]

#### Technology Obsolescence
- **Platform Risks**: [Risk of platform becoming obsolete]
- **Vendor Risks**: [Risk of vendor discontinuation]
- **Upgrade Risks**: [Risk of failed upgrades]

### Operational Risks

#### Process Risks
- **Process Failures**: [Risk of process breakdowns]
- **Quality Issues**: [Risk of quality degradation]
- **Resource Constraints**: [Risk of insufficient resources]
- **Skills Gaps**: [Risk of inadequate skills]

#### Supply Chain Risks
- **Vendor Dependencies**: [Risk of vendor failures]
- **Service Disruptions**: [Risk of service interruptions]
- **Cost Escalations**: [Risk of unexpected cost increases]

### Financial Risks

#### Budget Risks
- **Cost Overruns**: [Risk of exceeding budget]
- **Revenue Shortfalls**: [Risk of not meeting revenue targets]
- **Economic Factors**: [Risk from economic conditions]

#### Investment Risks
- **ROI Risks**: [Risk of poor return on investment]
- **Opportunity Costs**: [Risk of missing better opportunities]
- **Funding Risks**: [Risk of funding shortfalls]

### Strategic Risks

#### Market Risks
- **Competition**: [Risk from competitive pressures]
- **Market Changes**: [Risk from market shifts]
- **Customer Demands**: [Risk from changing customer needs]

#### Strategic Alignment
- **Goal Misalignment**: [Risk of strategic misalignment]
- **Priority Conflicts**: [Risk of conflicting priorities]
- **Stakeholder Risks**: [Risk of stakeholder disagreement]

### Compliance Risks

#### Regulatory Risks
- **Regulatory Changes**: [Risk from new regulations]
- **Compliance Failures**: [Risk of non-compliance]
- **Legal Issues**: [Risk of legal complications]

#### Standards Compliance
- **Industry Standards**: [Risk of standards non-compliance]
- **Certification Risks**: [Risk of losing certifications]
- **Audit Findings**: [Risk of adverse audit results]

### Security Risks

#### Cybersecurity Threats
- **Data Breaches**: [Risk of unauthorized data access]
- **System Intrusions**: [Risk of system compromises]
- **Malware**: [Risk of malicious software]

#### Physical Security
- **Facility Security**: [Risk to physical facilities]
- **Asset Protection**: [Risk to physical assets]
- **Personnel Security**: [Risk to personnel safety]

## Risk Mitigation Strategies

### Preventive Measures
*[Strategies to prevent risks from occurring]*

### Detective Measures
*[Strategies to detect risks early]*

### Corrective Measures
*[Strategies to correct issues when risks occur]*

### Risk Transfer
*[Strategies to transfer risk to other parties]*

## Risk Monitoring Plan

### Key Risk Indicators (KRIs)
- **[KRI 1]**: [Description and threshold]
- **[KRI 2]**: [Description and threshold]
- **[KRI 3]**: [Description and threshold]

### Monitoring Schedule
- **Daily**: [What risks are monitored daily]
- **Weekly**: [What risks are monitored weekly]
- **Monthly**: [What risks are monitored monthly]
- **Quarterly**: [What risks are reviewed quarterly]

### Escalation Procedures
*[When and how risks are escalated]*

## Business Continuity Planning

### Critical Business Functions
*[Identification of critical functions that must be maintained]*

### Recovery Strategies
*[Strategies for recovering from major risk events]*

### Communication Plans
*[How communication will be maintained during risk events]*

## Risk Appetite and Tolerance

### Risk Appetite Statement
*[Organization's overall appetite for risk]*

### Risk Tolerance Levels
*[Specific tolerance levels for different types of risks]*

### Decision Criteria
*[Criteria for making risk-related decisions]*

## Recommendations

### Immediate Actions (Next 30 Days)
1. **[Action]**: [Description and rationale]
2. **[Action]**: [Description and rationale]
3. **[Action]**: [Description and rationale]

### Short-term Actions (1-6 Months)
1. **[Action]**: [Description and rationale]
2. **[Action]**: [Description and rationale]
3. **[Action]**: [Description and rationale]

### Long-term Actions (6+ Months)
1. **[Action]**: [Description and rationale]
2. **[Action]**: [Description and rationale]
3. **[Action]**: [Description and rationale]

## Conclusion

### Overall Risk Profile
*[Summary of the overall risk profile]*

### Key Risk Priorities
*[Top priority risks that require immediate attention]*

### Risk Management Maturity
*[Assessment of current risk management capabilities]*

---

*Generated automatically by Deliverable Generator*
*Risk Assessment Template v1.0*
*Processing ID: {context.get('processing_id', 'unknown')}*

## Risk Assessment Matrix

| Risk Level | Probability | Impact | Action Required |
|------------|-------------|---------|-----------------|
| Critical | High | High | Immediate action required |
| High | High | Medium OR Medium | High | Action required within 30 days |
| Medium | Medium | Medium | Action required within 90 days |
| Low | Low | Low | Monitor and review |

## Probability Scale
- **High (>70%)**: Very likely to occur
- **Medium (30-70%)**: Moderately likely to occur  
- **Low (<30%)**: Unlikely to occur

## Impact Scale
- **High**: Severe consequences, major disruption
- **Medium**: Moderate consequences, manageable disruption
- **Low**: Minor consequences, minimal disruption
"""
        return content
    
    def _format_content(self, content: str, context: Dict[str, Any]) -> str:
        """
        Apply final formatting to generated content.
        
        Args:
            content: Generated content string
            context: Generation context
            
        Returns:
            Formatted content string
        """
        # Basic formatting cleanup
        content = content.strip()
        
        # Ensure consistent line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Ensure document ends with single newline
        if not content.endswith('\n'):
            content += '\n'
        
        return content
    
    def get_supported_templates(self) -> List[str]:
        """
        Get list of supported template types.
        
        Returns:
            List of supported template names (from both template engine and fallback strategies)
        """
        # Get templates from template engine
        engine_templates: List[str] = []
        try:
            engine_templates = self.template_engine.list_templates()
        except Exception:
            engine_templates = []

        alias_templates = set(engine_templates)
        alias_templates.update(f"{name}.md" for name in engine_templates)
        alias_templates.update(self.template_engine.template_aliases.keys())

        # Get fallback strategy templates and provide .md aliases for compatibility
        fallback_templates = set(self.fallback_strategies.keys())
        fallback_aliases = {f"{name}.md" for name in fallback_templates}

        # Combine and deduplicate
        all_templates = alias_templates.union(fallback_templates).union(fallback_aliases)
        return sorted(all_templates)
    
    def validate_deliverable_spec(self, spec: DeliverableSpec) -> List[str]:
        """
        Validate a deliverable specification.
        
        Args:
            spec: Deliverable specification to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not spec.name:
            errors.append("Deliverable name is required")
        
        if not spec.title:
            errors.append("Deliverable title is required")
        
        if not spec.description:
            errors.append("Deliverable description is required")
        
        # Check if template is supported (either by template engine or fallback)
        supported_templates = self.get_supported_templates()
        normalized_template = self._normalize_template_identifier(spec.template)
        if spec.template not in supported_templates and normalized_template not in supported_templates:
            errors.append(f"Unsupported template: {spec.template}. Available: {', '.join(supported_templates)}")
        
        if spec.order < 1:
            errors.append("Deliverable order must be positive")
        
        return errors
    
    def get_template_info(self, template_name: str) -> Optional[TemplateMetadata]:
        """
        Get information about a specific template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template metadata if available, None otherwise
        """
        try:
            return self.template_engine.get_template_metadata(template_name)
        except Exception:
            return None
    
    def validate_template(self, template_name: str) -> Dict[str, Any]:
        """
        Validate a template for syntax and completeness.
        
        Args:
            template_name: Name of the template to validate
            
        Returns:
            Validation results
        """
        try:
            return self.template_engine.validate_template(template_name)
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Failed to validate template: {e}"],
                "warnings": [],
                "metadata": None
            }
    
    def create_deliverable_from_template(self,
                                       template_name: str,
                                       issue_data: Any,
                                       workflow_info: WorkflowInfo,
                                       custom_sections: Optional[Dict[str, str]] = None,
                                       additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a deliverable directly from a template name.
        
        Args:
            template_name: Name of the template to use
            issue_data: Issue data for context
            workflow_info: Workflow information  
            custom_sections: Custom section content to include
            additional_context: Additional context for template rendering
            
        Returns:
            Generated deliverable content
        """
        # Create a basic deliverable spec
        spec = DeliverableSpec(
            name=template_name,
            title=f"Generated from {template_name}",
            description=f"Deliverable generated using {template_name} template",
            template=template_name
        )
        
        # Add custom sections to context
        context = additional_context or {}
        if custom_sections:
            context['sections'] = custom_sections
        
        return self.generate_deliverable(issue_data, spec, workflow_info, context)