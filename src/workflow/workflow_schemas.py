"""
Workflow Schema Validation Module
Defines and validates the schema for workflow YAML files.

This module now supports the Criminal Law Workflow Modernization taxonomy,
including hierarchical categories, base entity requirements, audit trail
metadata, and deliverable template stacks. Legacy workflows remain valid and
are supported alongside the new taxonomy-aware definitions.

The validator is intentionally flexible: teams can register new schema
profiles, extend taxonomy categories, or introduce bespoke workflow fields via
lightweight profile configuration files without editing the core codebase. This
keeps production feedback loops fast while preserving validation guarantees.
"""

from __future__ import annotations

import jsonschema
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import logging
import os
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class WorkflowSchemaValidator:
    """
    Validates workflow YAML files against the expected schema.
    
    This class provides comprehensive validation for workflow definitions,
    ensuring they contain all required fields and conform to expected types
    and constraints.
    """
    
    TAXONOMY_CATEGORIES: Set[str] = {
        "entity-foundation",
        "legal-research",
        "operational-coordination",
    }

    PRIORITY_LEVELS: Set[str] = {"low", "medium", "high", "critical"}

    BASE_ENTITY_TYPES: Set[str] = {"person", "place", "thing"}

    REQUIRED_TAXONOMY_FIELDS: Tuple[str, ...] = (
        "workflow_version",
        "category",
        "priority",
        "confidence_threshold",
        "required_entities",
        "deliverable_templates",
        "audit_trail",
    )

    REQUIRED_TEMPLATE_COMPONENTS: Tuple[str, ...] = (
        "confidentiality_banner",
        "shared_entity_tables",
        "shared_gao_citation_block",
        "entity_backbone",
        "gao_compliance_appendix",
    )

    DEFAULT_SCHEMA_PROFILE: str = "1"
    SCHEMA_PROFILES: Dict[str, Dict[str, Any]] = {}
    PROFILES_INITIALIZED: bool = False
    DEFAULT_PROFILE_PATHS: Tuple[Path, ...] = (
        Path("docs/workflow/schema-profile.yaml"),
        Path("docs/workflow/schema-profile.yml"),
    )

    # JSON Schema for workflow validation
    WORKFLOW_SCHEMA = {
        "type": "object",
        "required": ["name", "trigger_labels", "deliverables"],
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable name for the workflow"
            },
            "description": {
                "type": "string",
                "description": "Brief description of the workflow purpose"
            },
            "version": {
                "type": "string",
                "pattern": r"^\d+\.\d+\.\d+$",
                "description": "Semantic version string (e.g., '1.0.0')"
            },
            "workflow_version": {
                "type": "string",
                "pattern": r"^\d+\.\d+\.\d+$",
                "description": "Semantic version of the workflow definition"
            },
            "category": {
                "type": "string",
                "enum": list(TAXONOMY_CATEGORIES),
                "description": "Taxonomy category for the workflow"
            },
            "priority": {
                "type": "string",
                "enum": list(PRIORITY_LEVELS),
                "description": "Relative urgency for the workflow"
            },
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Minimum confidence required for auto-assignment"
            },
            "trigger_labels": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": r"^[a-zA-Z0-9-_]+$"
                },
                "description": "Labels that trigger this workflow (in addition to 'site-monitor')"
            },
            "deliverables": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "title", "description"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": r"^[a-zA-Z0-9-_]+$",
                            "description": "Unique identifier for the deliverable"
                        },
                        "title": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Human-readable title for the deliverable"
                        },
                        "description": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Description of what this deliverable contains"
                        },
                        "template": {
                            "type": "string",
                            "description": "Template file to use for this deliverable"
                        },
                        "required_sections": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "minLength": 1
                            },
                            "description": "Required section headings that must appear in the generated deliverable"
                        },
                        "required": {
                            "type": "boolean",
                            "description": "Whether this deliverable is required"
                        },
                        "order": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Order in which this deliverable should be generated"
                        }
                    },
                    "additionalProperties": False
                },
                "description": "List of deliverables to generate"
            },
            "required_entities": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/definitions/entity_requirement"},
                "description": "Entity requirements that must be satisfied before running the workflow"
            },
            "deliverable_templates": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": r"^[a-zA-Z0-9-_]+$"
                },
                "description": "Ordered list of template identifiers used to generate deliverables"
            },
            "processing": {
                "type": "object",
                "properties": {
                    "timeout": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Processing timeout in seconds"
                    },
                    "max_retries": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Maximum number of retry attempts"
                    }
                },
                "additionalProperties": False,
                "description": "Processing configuration options"
            },
            "validation": {
                "type": "object",
                "properties": {
                    "required_sections": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Required sections in generated content"
                    },
                    "min_length": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Minimum content length"
                    },
                    "min_word_count": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Minimum word count for generated content"
                    }
                },
                "additionalProperties": False,
                "description": "Validation rules for generated content"
            },
            "audit_trail": {
                "type": "object",
                "required": ["required"],
                "properties": {
                    "required": {
                        "type": "boolean",
                        "description": "Whether audit trail details must be recorded"
                    },
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1
                        },
                        "description": "Fields that must be captured in the audit trail"
                    }
                },
                "additionalProperties": False,
                "description": "Audit logging requirements for this workflow"
            },
            "output": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "html", "text"],
                        "description": "Output format for deliverables"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Output directory for generated files"
                    },
                    "folder_structure": {
                        "type": "string",
                        "description": "Folder structure pattern for output files"
                    }
                },
                "additionalProperties": False,
                "description": "Output configuration options"
            },
            "legacy_mode": {
                "type": "boolean",
                "description": "Flag legacy workflows to bypass taxonomy enforcement"
            },
            "extensions": {
                "type": "object",
                "description": "Forward-compatible namespaced fields for schema experiments",
                "additionalProperties": True,
            },
        },
        "additionalProperties": False,
        "definitions": {
            "entity_requirement": {
                "type": "object",
                "required": ["entity_type", "min_count", "min_confidence"],
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"^[a-zA-Z0-9-_]+$",
                        "description": "Entity type identifier (e.g., person, place, thing)"
                    },
                    "min_count": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Minimum number of entities required"
                    },
                    "min_confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Minimum confidence threshold for the entity"
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1
                        },
                        "description": "Optional relationship keys that must be present"
                    }
                },
                "additionalProperties": False
            }
        }
    }
    
    @classmethod
    def validate_workflow(cls, workflow_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate workflow data against the schema.
        
        Args:
            workflow_data: Dictionary containing workflow configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        cls.initialize_profiles()
        
        try:
            jsonschema.validate(instance=workflow_data, schema=cls.WORKFLOW_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            if e.path:
                errors.append(f"  at path: {' -> '.join(str(p) for p in e.path)}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema definition error: {e.message}")
        
        # Additional custom validations
        if not errors:
            custom_errors = cls._perform_custom_validations(workflow_data)
            errors.extend(custom_errors)
        
        return len(errors) == 0, errors
    
    @classmethod
    def _perform_custom_validations(cls, workflow_data: Dict[str, Any]) -> List[str]:
        """
        Perform custom validations beyond basic schema validation.
        
        Args:
            workflow_data: Dictionary containing workflow configuration
            
        Returns:
            List of error messages
        """
        errors = []
        
        # Check for duplicate deliverable names
        deliverables = workflow_data.get('deliverables', [])
        deliverable_names = [d.get('name') for d in deliverables if d.get('name')]
        duplicate_names = set([name for name in deliverable_names if deliverable_names.count(name) > 1])
        
        if duplicate_names:
            errors.append(f"Duplicate deliverable names found: {', '.join(duplicate_names)}")
        
        # Check for duplicate deliverable orders
        deliverable_orders = [d.get('order') for d in deliverables if d.get('order') is not None]
        duplicate_orders = set([order for order in deliverable_orders if deliverable_orders.count(order) > 1])
        
        if duplicate_orders:
            errors.append(f"Duplicate deliverable orders found: {', '.join(map(str, duplicate_orders))}")
        
        deliverable_sections_union: Set[str] = set()

        for deliverable in deliverables:
            sections_value = deliverable.get("required_sections")
            if sections_value is None:
                continue

            if not isinstance(sections_value, list):
                errors.append(
                    f"Deliverable '{deliverable.get('name', '<unknown>')}' required_sections must be a list"
                )
                continue

            normalized_sections: List[str] = []
            invalid_sections: List[str] = []
            for section in sections_value:
                if not isinstance(section, str) or not section.strip():
                    invalid_sections.append(str(section))
                    continue
                normalized_sections.append(section.strip())

            if invalid_sections:
                errors.append(
                    "Deliverable '"
                    + deliverable.get('name', '<unknown>')
                    + "' required_sections entries must be non-empty strings"
                )

            section_counts = Counter(normalized_sections)
            duplicate_section_names = [
                section for section, count in section_counts.items() if count > 1
            ]
            if duplicate_section_names:
                errors.append(
                    "Deliverable '"
                    + deliverable.get('name', '<unknown>')
                    + "' has duplicate required_sections: "
                    + ", ".join(sorted(duplicate_section_names))
                )

            deliverable_sections_union.update(normalized_sections)

        validation_requirements = (
            workflow_data.get("validation") or {}
        ).get("required_sections") or []
        if validation_requirements:
            missing_sections = [
                section
                for section in validation_requirements
                if section not in deliverable_sections_union
            ]
            if missing_sections:
                errors.append(
                    "validation.required_sections must be provided by deliverable required_sections; missing: "
                    + ", ".join(sorted(missing_sections))
                )

        # Validate trigger labels don't include 'site-monitor' (it's automatic)
        trigger_labels = workflow_data.get('trigger_labels', [])
        if 'site-monitor' in trigger_labels:
            errors.append("trigger_labels should not include 'site-monitor' as it's automatically required")
        
        if workflow_data.get("legacy_mode"):
            return errors

        taxonomy_errors = cls._validate_taxonomy_requirements(workflow_data)
        errors.extend(taxonomy_errors)

        return errors

    @classmethod
    def _is_taxonomy_workflow(cls, workflow_data: Dict[str, Any]) -> bool:
        """Determine if the workflow is expected to follow the new taxonomy."""
        if workflow_data.get("legacy_mode"):
            return False

        return any(field in workflow_data for field in cls.REQUIRED_TAXONOMY_FIELDS)

    @classmethod
    def _validate_taxonomy_requirements(cls, workflow_data: Dict[str, Any]) -> List[str]:
        """Validate taxonomy-specific requirements and constraints."""
        if not cls._is_taxonomy_workflow(workflow_data):
            return []

        errors: List[str] = []

        profile = cls._get_schema_profile(workflow_data.get("workflow_version"))

        required_fields: Iterable[str] = profile.get(
            "required_fields", cls.REQUIRED_TAXONOMY_FIELDS
        )
        missing_fields = [field for field in required_fields if field not in workflow_data]
        if missing_fields:
            errors.append(
                "Taxonomy workflows must include the following fields: "
                + ", ".join(sorted(missing_fields))
            )
            # No point running deeper validations if critical fields are missing.
            return errors

        category = workflow_data.get("category")
        if category not in cls.TAXONOMY_CATEGORIES:
            errors.append(
                f"Invalid category '{category}'. Expected one of: "
                + ", ".join(sorted(cls.TAXONOMY_CATEGORIES))
            )

        priority = workflow_data.get("priority")
        if priority not in cls.PRIORITY_LEVELS:
            errors.append(
                f"Invalid priority '{priority}'. Expected one of: "
                + ", ".join(sorted(cls.PRIORITY_LEVELS))
            )

        confidence_threshold = workflow_data.get("confidence_threshold")
        if not isinstance(confidence_threshold, (int, float)):
            errors.append("confidence_threshold must be a number between 0 and 1")
        elif confidence_threshold < 0 or confidence_threshold > 1:
            errors.append("confidence_threshold must be between 0 and 1 inclusive")

        required_entities = workflow_data.get("required_entities", [])
        entity_types = {
            entity.get("entity_type")
            for entity in required_entities
            if isinstance(entity, dict) and entity.get("entity_type")
        }

        required_entity_types = set(
            profile.get("base_entity_types", cls.BASE_ENTITY_TYPES)
        )
        missing_base_entities = required_entity_types - entity_types
        if missing_base_entities:
            errors.append(
                "Taxonomy workflows must declare base entity requirements for: "
                + ", ".join(sorted(missing_base_entities))
            )

        for entity in required_entities:
            if not isinstance(entity, dict):
                errors.append("Each required entity must be an object with metadata")
                continue

            entity_type = entity.get("entity_type")
            if not entity_type:
                errors.append("Entity requirement missing 'entity_type'")

            min_count = entity.get("min_count")
            if min_count is None or not isinstance(min_count, int) or min_count < 0:
                errors.append(
                    f"Entity requirement '{entity_type}' must define a non-negative integer min_count"
                )

            min_confidence = entity.get("min_confidence")
            if min_confidence is None or not isinstance(min_confidence, (int, float)):
                errors.append(
                    f"Entity requirement '{entity_type}' must define a numeric min_confidence"
                )
            elif min_confidence < 0 or min_confidence > 1:
                errors.append(
                    f"Entity requirement '{entity_type}' min_confidence must be between 0 and 1"
                )

        deliverable_templates = workflow_data.get("deliverable_templates", [])
        required_templates = profile.get(
            "required_templates", cls.REQUIRED_TEMPLATE_COMPONENTS
        )
        missing_templates = [
            template
            for template in required_templates
            if template not in deliverable_templates
        ]
        if missing_templates:
            errors.append(
                "Taxonomy workflows must include required template components: "
                + ", ".join(sorted(missing_templates))
            )

        audit_trail = workflow_data.get("audit_trail")
        if isinstance(audit_trail, dict):
            required_flag = audit_trail.get("required")
            if not isinstance(required_flag, bool):
                errors.append("audit_trail.required must be a boolean")
            if required_flag and not audit_trail.get("fields"):
                errors.append(
                    "audit_trail.fields must be provided when audit logging is required"
                )
        else:
            errors.append("audit_trail must be an object containing audit requirements")

        return errors

    # ------------------------------------------------------------------
    # Dynamic profile support
    # ------------------------------------------------------------------

    @classmethod
    def _refresh_schema_enums(cls) -> None:
        cls.WORKFLOW_SCHEMA["properties"]["category"]["enum"] = sorted(
            cls.TAXONOMY_CATEGORIES
        )
        cls.WORKFLOW_SCHEMA["properties"]["priority"]["enum"] = sorted(
            cls.PRIORITY_LEVELS
        )

    @classmethod
    def register_taxonomy_category(cls, *categories: str) -> None:
        cls.TAXONOMY_CATEGORIES.update({c for c in categories if c})
        cls._refresh_schema_enums()

    @classmethod
    def register_priority_levels(cls, *levels: str) -> None:
        cls.PRIORITY_LEVELS.update({l for l in levels if l})
        cls._refresh_schema_enums()

    @classmethod
    def register_schema_profile(cls, name: str, profile: Dict[str, Any]) -> None:
        if not name:
            raise ValueError("Schema profile name cannot be empty")

        normalized_name = str(name).strip().lower()
        base_profile = dict(profile or {})
        inherited_name = base_profile.get("extends")
        if inherited_name:
            inherited_profile = cls.SCHEMA_PROFILES.get(str(inherited_name).strip().lower(), {})
            merged_profile = dict(inherited_profile)
            merged_profile.update(base_profile)
            base_profile = merged_profile

        for key in ("required_fields", "required_templates", "base_entity_types"):
            if key in base_profile and base_profile[key] is not None:
                base_profile[key] = tuple(dict.fromkeys(base_profile[key]))

        additional_categories = base_profile.get("categories") or []
        additional_priorities = base_profile.get("priority_levels") or []
        if additional_categories:
            cls.register_taxonomy_category(*additional_categories)
        if additional_priorities:
            cls.register_priority_levels(*additional_priorities)

        additional_properties = base_profile.get("properties") or {}
        for prop_name, prop_schema in additional_properties.items():
            if not prop_name or not isinstance(prop_schema, dict):
                continue
            cls.WORKFLOW_SCHEMA["properties"][prop_name] = dict(prop_schema)

        cls.SCHEMA_PROFILES[normalized_name] = base_profile
        logger.info("Registered workflow schema profile '%s'", normalized_name)

    @classmethod
    def load_profiles_from_file(cls, path: Path) -> None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
        except FileNotFoundError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load schema profile file '%s': %s", path, exc)
            return

        profiles = payload.get("profiles") or {}
        for profile_name, profile_body in profiles.items():
            if not isinstance(profile_body, dict):
                continue
            cls.register_schema_profile(profile_name, profile_body)

        default_profile = payload.get("default_profile")
        if default_profile:
            cls.DEFAULT_SCHEMA_PROFILE = str(default_profile).strip().lower()

        logger.info(
            "Loaded %d workflow schema profile(s) from %s",
            len(profiles),
            path,
        )

    @classmethod
    def initialize_profiles(cls) -> None:
        if cls.PROFILES_INITIALIZED:
            return

        env_path = os.getenv("WORKFLOW_SCHEMA_PROFILE_PATH")
        candidate_paths: List[Path] = []
        if env_path:
            candidate_paths.append(Path(env_path))
        candidate_paths.extend(cls.DEFAULT_PROFILE_PATHS)

        for candidate in candidate_paths:
            if candidate.is_file():
                cls.load_profiles_from_file(candidate)

        if cls.DEFAULT_SCHEMA_PROFILE not in cls.SCHEMA_PROFILES:
            cls.register_schema_profile(
                cls.DEFAULT_SCHEMA_PROFILE,
                {
                    "required_fields": cls.REQUIRED_TAXONOMY_FIELDS,
                    "required_templates": cls.REQUIRED_TEMPLATE_COMPONENTS,
                    "base_entity_types": tuple(cls.BASE_ENTITY_TYPES),
                },
            )

        cls.PROFILES_INITIALIZED = True

    @classmethod
    def _parse_version_major(cls, workflow_version: Optional[str]) -> str:
        if not workflow_version:
            return cls.DEFAULT_SCHEMA_PROFILE
        match = re.match(r"^(\d+)\.", workflow_version)
        if match:
            return match.group(1)
        return cls.DEFAULT_SCHEMA_PROFILE

    @classmethod
    def _get_schema_profile(cls, workflow_version: Optional[str]) -> Dict[str, Any]:
        major = cls._parse_version_major(workflow_version).strip().lower()
        profile = cls.SCHEMA_PROFILES.get(major)
        if profile is None:
            logger.info(
                "No schema profile registered for version '%s'; falling back to '%s'",
                workflow_version,
                cls.DEFAULT_SCHEMA_PROFILE,
            )
            profile = cls.SCHEMA_PROFILES.get(cls.DEFAULT_SCHEMA_PROFILE, {})
        return profile or {}
    
    @classmethod
    def validate_deliverable_names(cls, deliverables: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate that deliverable names are unique and properly formatted.
        
        Args:
            deliverables: List of deliverable dictionaries
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        names = []
        
        for i, deliverable in enumerate(deliverables):
            name = deliverable.get('name')
            if not name:
                errors.append(f"Deliverable {i+1} missing required 'name' field")
                continue
            
            if not isinstance(name, str):
                errors.append(f"Deliverable {i+1} name must be a string, got {type(name).__name__}")
                continue
            
            if name in names:
                errors.append(f"Duplicate deliverable name: '{name}'")
            else:
                names.append(name)
            
            # Validate name format
            if not re.match(r'^[a-zA-Z0-9-_]+$', name):
                msg = (f"Deliverable name '{name}' contains invalid characters. "
                      "Use only letters, numbers, hyphens, and underscores.")
                errors.append(msg)
        
        return len(errors) == 0, errors