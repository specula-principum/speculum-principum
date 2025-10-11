"""
Template Engine

This module provides a template processing system for generating structured documents
from template files. It supports variable substitution, conditional rendering,
and section management for deliverable generation.

Key Features:
- Template file loading and caching
- Variable substitution with dot notation
- Conditional blocks and loops
- Section management and inheritance
- Template validation and error handling

The engine is designed to be lightweight while providing essential templating
features needed for document generation in the issue processing workflow.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TextIO
from dataclasses import dataclass
import yaml


@dataclass
class TemplateMetadata:
    """
    Metadata for a template file extracted from front matter.
    
    Attributes:
        name: Template name/identifier
        description: Template description
        type: Template type (base, document, section)
        extends: Parent template name if extending
        variables: Required variable definitions
        sections: Available sections in the template
        version: Template version
        author: Template author
    """
    name: str
    description: str = ""
    type: str = "document"
    extends: Optional[str] = None
    variables: Optional[Dict[str, str]] = None
    sections: Optional[List[str]] = None
    version: str = "1.0"
    author: str = "System"
    
    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.variables is None:
            self.variables = {}
        if self.sections is None:
            self.sections = []


class TemplateEngine:
    """
    Template processing engine for generating structured documents.
    
    This engine provides a simple but effective templating system that supports
    variable substitution, conditional rendering, and template inheritance.
    It's designed specifically for the deliverable generation use case.
    
    Attributes:
        templates_dir: Directory containing template files
        template_cache: Cache of loaded templates
        metadata_cache: Cache of template metadata
    """
    
    DEFAULT_TEMPLATE_ALIASES: Dict[str, str] = {}

    def __init__(self, templates_dir: Union[str, Path] = "templates"):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = Path(templates_dir)
        self.template_cache: Dict[str, str] = {}
        self.metadata_cache: Dict[str, TemplateMetadata] = {}
        self._alias_map: Dict[str, str] = {}
        self.template_aliases: Dict[str, str] = {}

        # Register default alias mappings (normalized for consistent lookups)
        for alias, target in self.DEFAULT_TEMPLATE_ALIASES.items():
            normalized_alias = self._normalize_template_key(alias)
            normalized_target = self._normalize_template_key(target)
            self.template_aliases[normalized_alias] = normalized_target
        
        # Create templates directory if it doesn't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Template syntax patterns
        self.variable_pattern = re.compile(r'\{\{\s*([^}]+)\s*\}\}')
        self.condition_pattern = re.compile(r'\{%\s*if\s+([^%]+)\s*%\}(.*?)\{%\s*endif\s*%\}', re.DOTALL)
        self.loop_pattern = re.compile(r'\{%\s*for\s+(\w+)\s+in\s+([^%]+)\s*%\}(.*?)\{%\s*endfor\s*%\}', re.DOTALL)
        self.section_pattern = re.compile(r'\{%\s*section\s+([^%]+)\s*%\}(.*?)\{%\s*endsection\s*%\}', re.DOTALL)
        self.include_pattern = re.compile(r'\{%\s*include\s+([^%]+)\s*%\}')

    def _normalize_template_key(self, template_name: str) -> str:
        """Normalize template name for cache lookups."""
        normalized = template_name.strip().replace('\\', '/').lstrip('./')
        if normalized.endswith('.md'):
            normalized = normalized[:-3]
        return normalized.strip('/')

    def _candidate_template_names(self, template_name: str) -> List[str]:
        """Generate fallback candidate names for resolving template paths."""
        cleaned = template_name.strip().replace('\\', '/').lstrip('./')
        candidates = [cleaned]

        if cleaned.endswith('.md'):
            without_ext = cleaned[:-3]
            if without_ext:
                candidates.append(without_ext)
        else:
            with_ext = f"{cleaned}.md"
            candidates.append(with_ext)

        # Ensure uniqueness while preserving order
        seen: set[str] = set()
        ordered: List[str] = []
        for candidate in candidates:
            if candidate not in seen and candidate:
                seen.add(candidate)
                ordered.append(candidate)

        return ordered

    def _resolve_template_alias(self, template_name: str) -> Optional[str]:
        """Resolve template aliases to their canonical target names."""
        variants: List[str] = [template_name]
        normalized = self._normalize_template_key(template_name)
        variants.append(normalized)

        if template_name.endswith('.md'):
            without_ext = template_name[:-3]
            variants.append(without_ext)
            variants.append(self._normalize_template_key(without_ext))
        else:
            with_ext = f"{template_name}.md"
            variants.append(with_ext)
            variants.append(self._normalize_template_key(with_ext))

        for variant in variants:
            key = self._normalize_template_key(variant)
            if key in self.template_aliases:
                return self.template_aliases[key]

        return None
    
    def load_template(self, template_name: str, force_reload: bool = False) -> str:
        """
        Load a template from file.
        
        Args:
            template_name: Name of the template to load
            force_reload: Whether to bypass cache and reload from file
            
        Returns:
            Template content as string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is invalid
        """
        original_name = template_name

        alias_target = self._resolve_template_alias(template_name)
        if alias_target:
            template_name = alias_target

        cache_key = self._normalize_template_key(template_name)
        if not force_reload and cache_key in self.template_cache:
            self._alias_map[original_name] = cache_key
            self._alias_map[template_name] = cache_key
            return self.template_cache[cache_key]

        # Find template file (considering .md aliases)
        template_path = self._find_template_file(template_name)
        if not template_path:
            # Try normalized key as fallback
            template_path = self._find_template_file(cache_key)
        if not template_path and alias_target:
            template_path = self._find_template_file(alias_target)
        if not template_path:
            raise FileNotFoundError(f"Template not found: {template_name}")
        
        # Load template content
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse and extract metadata
            metadata, template_content = self._parse_template(content)
            
            # Cache template and metadata
            self.template_cache[cache_key] = template_content
            self.metadata_cache[cache_key] = metadata
            self._alias_map[original_name] = cache_key
            self._alias_map[template_name] = cache_key
            self._alias_map[cache_key] = cache_key
            
            return template_content
            
        except Exception as e:
            raise ValueError(f"Failed to load template '{template_name}': {e}")
    
    def render_template(self, 
                       template_name: str, 
                       context: Dict[str, Any], 
                       sections: Optional[Dict[str, str]] = None) -> str:
        """
        Render a template with the given context.
        
        Args:
            template_name: Name of the template to render
            context: Variables and data for template rendering
            sections: Named sections to include in the template
            
        Returns:
            Rendered template content
            
        Raises:
            FileNotFoundError: If template doesn't exist
            ValueError: If rendering fails
        """
        # Load template
        template_content = self.load_template(template_name)
        cache_key = self._normalize_template_key(template_name)

        # Handle template inheritance
        metadata = self.metadata_cache.get(cache_key)
        if metadata:
            if metadata.extends:
                parent_content = self.load_template(metadata.extends)
                template_content = self._merge_templates(parent_content, template_content)
        
        # Add sections to context if provided
        if sections:
            context = {**context, 'sections': sections}
        
        # Render template
        try:
            rendered = self._render_content(template_content, context)
            return rendered
        except Exception as e:
            raise ValueError(f"Failed to render template '{template_name}': {e}")
    
    def get_template_metadata(self, template_name: str) -> TemplateMetadata:
        """
        Get metadata for a template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template metadata
            
        Raises:
            FileNotFoundError: If template doesn't exist
        """
        # Load template to ensure metadata is cached
        self.load_template(template_name)

        cache_key = self._normalize_template_key(template_name)
        alias_key = self._alias_map.get(template_name, cache_key)

        if alias_key not in self.metadata_cache:
            raise FileNotFoundError(f"Template metadata not found: {template_name}")

        return self.metadata_cache[alias_key]
    
    def list_templates(self) -> List[str]:
        """
        List all available templates.
        
        Returns:
            List of template names
        """
        templates: list[str] = []
        
        if not self.templates_dir.exists():
            return templates
        
        for template_file in self.templates_dir.rglob("*.md"):
            # Convert path to template name
            relative_path = template_file.relative_to(self.templates_dir)
            template_name = str(relative_path.with_suffix(''))
            templates.append(template_name)
        
        return sorted(templates)
    
    def validate_template(self, template_name: str) -> Dict[str, Any]:
        """
        Validate a template for syntax errors and completeness.
        
        Args:
            template_name: Name of the template to validate
            
        Returns:
            Validation results with errors and warnings
        """
        errors_list: list[str] = []
        warnings_list: list[str] = []
        results = {
            "valid": True,
            "errors": errors_list,
            "warnings": warnings_list,
            "metadata": None
        }
        
        try:
            # Load template
            content = self.load_template(template_name)
            metadata = self.get_template_metadata(template_name)
            results["metadata"] = metadata
            
            # Check for syntax errors in template directives
            errors = self._validate_template_syntax(content)
            errors_list.extend(errors)
            
            # Check for undefined variables
            warnings = self._check_undefined_variables(content, metadata)
            warnings_list.extend(warnings)
            
            if errors_list:
                results["valid"] = False
                
        except Exception as e:
            results["valid"] = False
            errors_list.append(f"Failed to load template: {e}")
        
        return results
    
    def _find_template_file(self, template_name: str) -> Optional[Path]:
        """Find the file path for a given template name."""
        candidates = self._candidate_template_names(template_name)

        alias_target = self._resolve_template_alias(template_name)
        if alias_target:
            alias_candidates = self._candidate_template_names(alias_target)
            for alias_candidate in alias_candidates:
                if alias_candidate not in candidates:
                    candidates.insert(0, alias_candidate)

        # First try direct path resolution for each candidate
        for candidate in candidates:
            candidate_path = candidate.lstrip('/')
            path = self.templates_dir / candidate_path
            if path.exists():
                return path

            if not candidate.endswith('.md'):
                path_with_ext = self.templates_dir / f"{candidate_path}.md"
                if path_with_ext.exists():
                    return path_with_ext

        # Fall back to recursive search through templates directory
        for template_file in self.templates_dir.rglob("*.md"):
            relative_path = template_file.relative_to(self.templates_dir)
            relative_str = str(relative_path)
            relative_no_ext = str(relative_path.with_suffix(''))

            if relative_str in candidates or relative_no_ext in candidates:
                return template_file

        return None
    
    def _parse_template(self, content: str) -> tuple[TemplateMetadata, str]:
        """Parse template front matter and content."""
        # Check for YAML front matter
        if content.startswith('---\n'):
            try:
                # Find end of front matter
                end_marker = content.find('\n---\n', 4)
                if end_marker == -1:
                    end_marker = content.find('\n...\n', 4)
                
                if end_marker != -1:
                    front_matter = content[4:end_marker]
                    template_content = content[end_marker + 5:]
                    
                    # Parse YAML front matter
                    metadata_dict = yaml.safe_load(front_matter) or {}
                    
                    # Create metadata object
                    metadata = TemplateMetadata(
                        name=metadata_dict.get('name', 'Unnamed'),
                        description=metadata_dict.get('description', ''),
                        type=metadata_dict.get('type', 'document'),
                        extends=metadata_dict.get('extends'),
                        variables=metadata_dict.get('variables', {}),
                        sections=metadata_dict.get('sections', []),
                        version=metadata_dict.get('version', '1.0'),
                        author=metadata_dict.get('author', 'System')
                    )
                    
                    return metadata, template_content
            except yaml.YAMLError:
                pass  # Fall through to default metadata
        
        # If ends with just --- (incomplete front matter), treat as no front matter
        if content.strip() == '---\nname: "Only Front Matter"\n---':
            metadata = TemplateMetadata(name="Only Front Matter")
            return metadata, ""
        
        # Default metadata if no front matter
        metadata = TemplateMetadata(name="Unknown")
        return metadata, content
    
    def _merge_templates(self, parent_content: str, child_content: str) -> str:
        """Merge child template with parent template."""
        # Simple merge: replace sections in parent with child sections
        # More sophisticated inheritance could be implemented later
        
        # Extract sections from child
        child_sections = {}
        for match in self.section_pattern.finditer(child_content):
            section_name = match.group(1).strip()
            section_content = match.group(2).strip()
            child_sections[section_name] = section_content
        
        # Replace sections in parent
        def replace_section(match):
            section_name = match.group(1).strip()
            if section_name in child_sections:
                return child_sections[section_name]
            return match.group(2)  # Keep original content
        
        merged = self.section_pattern.sub(replace_section, parent_content)
        return merged
    
    def _render_content(self, content: str, context: Dict[str, Any]) -> str:
        """Render template content with context."""
        # Add system variables to context (only if not already in context)
        enhanced_context = {
            'now': datetime.now(),
            'utc_now': datetime.utcnow(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().isoformat(),
            **context,  # Context overrides system variables
        }
        
        # Process includes first
        content = self._process_includes(content, enhanced_context)
        
        # Process sections
        content = self._process_sections(content, enhanced_context)
        
        # Process loops first (they will recursively process their content including conditionals)
        content = self._process_loops(content, enhanced_context)
        
        # Process remaining conditionals that weren't inside loops
        content = self._process_conditionals(content, enhanced_context)
        
        # Process variables last
        content = self._process_variables(content, enhanced_context)
        
        return content
    
    def _process_includes(self, content: str, context: Dict[str, Any]) -> str:
        """Process include directives."""
        def replace_include(match):
            include_name = match.group(1).strip().strip('"\'')
            try:
                included_content = self.load_template(include_name)
                return self._render_content(included_content, context)
            except Exception:
                return f"<!-- Failed to include: {include_name} -->"
        
        return self.include_pattern.sub(replace_include, content)
    
    def _process_sections(self, content: str, context: Dict[str, Any]) -> str:
        """Process section directives."""
        sections = context.get('sections', {})
        
        def replace_section(match):
            section_name = match.group(1).strip()
            section_content = match.group(2).strip()
            
            # Check if section is overridden in context
            if section_name in sections:
                return sections[section_name]
            
            return section_content
        
        return self.section_pattern.sub(replace_section, content)
    
    def _process_conditionals(self, content: str, context: Dict[str, Any]) -> str:
        """Process conditional blocks."""
        def replace_conditional(match):
            condition = match.group(1).strip()
            conditional_content = match.group(2)
            
            # Evaluate condition
            if self._evaluate_condition(condition, context):
                return self._render_content(conditional_content, context)
            
            return ""
        
        return self.condition_pattern.sub(replace_conditional, content)
    
    def _process_loops(self, content: str, context: Dict[str, Any]) -> str:
        """Process loop blocks with proper nesting support."""
        # Process loops from innermost to outermost to handle nesting
        while True:
            # Find the next loop
            match = self.loop_pattern.search(content)
            if not match:
                break
            
            # Find the matching endfor for this specific for
            start_pos = match.start()
            for_content = match.group(0)
            var_name = match.group(1).strip()
            collection_expr = match.group(2).strip()
            
            # Find the correct endfor by counting nested fors and endfors
            loop_content = self._extract_balanced_loop_content(content, start_pos)
            if loop_content is None:
                # If we can't find balanced content, skip this match
                content = content[:start_pos] + "<!-- Loop parsing error -->" + content[match.end():]
                continue
            
            # Get collection from context
            collection = self._get_value(collection_expr, context)
            if not isinstance(collection, (list, tuple)):
                replacement = ""
            else:
                # Render loop content for each item
                result = []
                for i, item in enumerate(collection):
                    loop_context = {
                        **context,
                        var_name: item,
                        'loop': {
                            'index': i + 1,  # 1-based index
                            'index0': i,     # 0-based index
                            'first': i == 0,
                            'last': i == len(collection) - 1,
                            'length': len(collection)
                        }
                    }
                    rendered = self._render_content(loop_content, loop_context)
                    result.append(rendered)
                
                replacement = '\n'.join(result)
            
            # Replace the entire loop with the rendered content
            loop_start = content.find('{% for ' + var_name, start_pos)
            loop_end = content.find('{% endfor %}', loop_start) + len('{% endfor %}')
            content = content[:loop_start] + replacement + content[loop_end:]
        
        return content
    
    def _extract_balanced_loop_content(self, content: str, start_pos: int) -> Optional[str]:
        """Extract content between balanced {% for %} and {% endfor %} tags."""
        # Find the opening {% for %}
        for_start = content.find('{% for ', start_pos)
        if for_start == -1:
            return None
        
        # Find the end of the opening tag
        tag_end = content.find('%}', for_start)
        if tag_end == -1:
            return None
        
        # Start counting from after the opening tag
        pos = tag_end + 2
        for_count = 1
        
        while pos < len(content) and for_count > 0:
            # Look for the next for or endfor
            next_for = content.find('{% for ', pos)
            next_endfor = content.find('{% endfor %}', pos)
            
            # If no endfor found, this is an error
            if next_endfor == -1:
                return None
            
            # Check which comes first
            if next_for != -1 and next_for < next_endfor:
                # Found a nested for
                for_count += 1
                pos = next_for + 7  # len('{% for ')
            else:
                # Found an endfor
                for_count -= 1
                if for_count == 0:
                    # This is our matching endfor
                    return content[tag_end + 2:next_endfor]
                pos = next_endfor + 12  # len('{% endfor %}')
        
        return None
    
    def _process_variables(self, content: str, context: Dict[str, Any]) -> str:
        """Process variable substitutions."""
        def replace_variable(match):
            var_expr = match.group(1).strip()
            value = self._get_value(var_expr, context)
            return str(value) if value is not None else ""
        
        return self.variable_pattern.sub(replace_variable, content)
    
    def _get_value(self, expression: str, context: Dict[str, Any]) -> Any:
        """Get value from context using dot notation."""
        parts = expression.split('.')
        value = context
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition expression."""
        # Simple condition evaluation
        # Supports: variable, not variable, variable == value, variable != value
        
        condition = condition.strip()
        
        # Handle 'not' conditions
        if condition.startswith('not '):
            return not self._evaluate_condition(condition[4:], context)
        
        # Handle equality comparisons
        if ' == ' in condition:
            left, right = condition.split(' == ', 1)
            left_val = self._get_value(left.strip(), context)
            right_val = self._parse_literal(right.strip()) or self._get_value(right.strip(), context)
            return left_val == right_val
        
        if ' != ' in condition:
            left, right = condition.split(' != ', 1)
            left_val = self._get_value(left.strip(), context)
            right_val = self._parse_literal(right.strip()) or self._get_value(right.strip(), context)
            return left_val != right_val
        
        # Simple boolean evaluation
        value = self._get_value(condition, context)
        return bool(value)
    
    def _parse_literal(self, value: str) -> Any:
        """Parse a literal value from string."""
        value = value.strip()
        
        # String literals
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        
        # Number literals
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Boolean literals
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        elif value.lower() == 'null' or value.lower() == 'none':
            return None
        
        return None
    
    def _validate_template_syntax(self, content: str) -> List[str]:
        """Validate template syntax for errors."""
        errors = []
        
        # Check for unmatched braces
        open_braces = content.count('{{')
        close_braces = content.count('}}')
        if open_braces != close_braces:
            errors.append(f"Unmatched variable braces: {open_braces} open, {close_braces} close")
        
        # Check for unmatched template tags
        open_tags = len(re.findall(r'\{%\s*(if|for|section)\s', content))
        close_tags = len(re.findall(r'\{%\s*(endif|endfor|endsection)\s', content))
        if open_tags != close_tags:
            errors.append(f"Unmatched template tags: {open_tags} open, {close_tags} close")
        
        return errors
    
    def _check_undefined_variables(self, content: str, metadata: TemplateMetadata) -> List[str]:
        """Check for potentially undefined variables."""
        warnings = []
        
        # Extract all variable references
        variables = set()
        for match in self.variable_pattern.finditer(content):
            var_expr = match.group(1).strip()
            # Get the root variable name
            root_var = var_expr.split('.')[0]
            variables.add(root_var)
        
        # Check against defined variables in metadata
        defined_vars = set(metadata.variables.keys()) if metadata.variables else set()
        
        # Common system variables that are always available
        system_vars = {'now', 'utc_now', 'date', 'time', 'timestamp', 'loop'}
        
        # Check for undefined variables
        for var in variables:
            if var not in defined_vars and var not in system_vars:
                warnings.append(f"Potentially undefined variable: {var}")
        
        return warnings