"""
Configuration Management Module
Handles loading and validation of YAML configuration files for site monitoring
"""

import yaml
import os
import re
from typing import Dict, List, Optional, Any
from jsonschema import validate, ValidationError
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SiteConfig:
    """Configuration for a single monitored site"""
    url: str
    name: str
    keywords: Optional[List[str]] = None
    max_results: int = 10
    search_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    custom_search_terms: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.keywords is None:
            self.keywords = []
        if self.search_paths is None:
            self.search_paths = []
        if self.exclude_paths is None:
            self.exclude_paths = []
        if self.custom_search_terms is None:
            self.custom_search_terms = []


@dataclass
class GitHubConfig:
    """GitHub repository configuration"""
    repository: str
    issue_labels: Optional[List[str]] = None
    default_assignees: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.issue_labels is None:
            self.issue_labels = ["site-monitor", "automated"]
        if self.default_assignees is None:
            self.default_assignees = []


@dataclass
class AgentProcessingConfig:
    """Agent processing configuration"""
    default_timeout_minutes: int = 60
    max_concurrent_issues: int = 3
    retry_attempts: int = 2
    require_review: bool = True
    auto_create_pr: bool = False


@dataclass
class AgentGitConfig:
    """Agent git configuration"""
    branch_prefix: str = "agent"
    commit_message_template: str = "Agent: {workflow_name} for issue #{issue_number}"
    auto_push: bool = True


@dataclass
class AgentValidationConfig:
    """Agent validation configuration"""
    min_word_count: int = 100
    require_citations: bool = False
    spell_check: bool = False


@dataclass
class AIHistoryConfig:
    """AI history storage configuration"""
    storage_type: str = "gist"
    gist_id: Optional[str] = None
    file_path: str = ".github/ai_assignment_history.json"


@dataclass
class AIConfidenceThresholds:
    """AI confidence thresholds for automated processing"""
    auto_assign: float = 0.8
    request_review: float = 0.6
    entity_extraction: float = 0.7
    relationship_mapping: float = 0.6
    auto_assign_workflow: float = 0.8
    require_human_review: float = 0.5


@dataclass
class AIModelConfig:
    """AI model configuration for different use cases"""
    content_extraction: str = "gpt-4o"
    specialist_analysis: str = "gpt-4o"
    document_generation: str = "gpt-4o"
    workflow_assignment: str = "gpt-4o"


@dataclass
class AISettingsConfig:
    """AI performance and behavior settings"""
    temperature: float = 0.3
    max_tokens: int = 3000
    timeout_seconds: int = 30
    retry_count: int = 3
    enable_logging: bool = True


@dataclass
class AIExtractionFocusConfig:
    """AI content extraction focus configuration"""
    default: Optional[List[str]] = None
    intelligence_analyst: Optional[List[str]] = None
    osint_researcher: Optional[List[str]] = None
    target_profiler: Optional[List[str]] = None
    threat_hunter: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.default is None:
            self.default = ["entities", "relationships", "events", "indicators"]
        if self.intelligence_analyst is None:
            self.intelligence_analyst = ["threat_actors", "attack_vectors", "targets", "capabilities"]
        if self.osint_researcher is None:
            self.osint_researcher = ["digital_footprint", "public_records", "technical_infrastructure"]
        if self.target_profiler is None:
            self.target_profiler = ["organizational_structure", "key_personnel", "business_operations"]
        if self.threat_hunter is None:
            self.threat_hunter = ["iocs", "ttps", "attack_patterns", "threat_indicators"]


@dataclass 
class AIConfig:
    """Enhanced AI configuration for content extraction and workflow assignment"""
    enabled: bool = False
    provider: str = "github-models"  # github-models, openai, anthropic
    models: Optional[AIModelConfig] = None
    settings: Optional[AISettingsConfig] = None
    confidence_thresholds: Optional[AIConfidenceThresholds] = None
    extraction_focus: Optional[AIExtractionFocusConfig] = None
    history: Optional[AIHistoryConfig] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.models is None:
            self.models = AIModelConfig()
        if self.settings is None:
            self.settings = AISettingsConfig()
        if self.confidence_thresholds is None:
            self.confidence_thresholds = AIConfidenceThresholds()
        if self.extraction_focus is None:
            self.extraction_focus = AIExtractionFocusConfig()
        if self.history is None:
            self.history = AIHistoryConfig()


@dataclass
class AgentConfig:
    """Agent configuration for automated issue processing"""
    username: str
    workflow_directory: str = "docs/workflow/deliverables"
    template_directory: str = "templates"
    output_directory: str = "study"
    processing: Optional[AgentProcessingConfig] = None
    git: Optional[AgentGitConfig] = None
    validation: Optional[AgentValidationConfig] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.processing is None:
            self.processing = AgentProcessingConfig()
        if self.git is None:
            self.git = AgentGitConfig()
        if self.validation is None:
            self.validation = AgentValidationConfig()


@dataclass
class SearchConfig:
    """Google Custom Search configuration"""
    api_key: str
    search_engine_id: str
    daily_query_limit: int = 90  # Leave buffer from 100 daily limit
    results_per_query: int = 10
    date_range_days: int = 1  # Search for results in last N days
    
    def __post_init__(self):
        """Validate search configuration"""
        if self.daily_query_limit > 100:
            raise ValueError("Daily query limit cannot exceed 100 (Google free tier limit)")
        if self.results_per_query > 10:
            raise ValueError("Results per query cannot exceed 10 (Google API limit)")


@dataclass
class WorkflowConfig:
    """Workflow configuration"""
    dir: str = "docs/workflow/deliverables"
    output_dir: str = "study"


@dataclass
class GitConfig:
    """Git configuration"""
    enabled: bool = False
    repository_path: Optional[str] = None
    auto_commit: bool = False
    auto_push: bool = False


@dataclass
class MonitorConfig:
    """Complete monitoring configuration"""
    sites: List[SiteConfig]
    github: GitHubConfig
    search: SearchConfig
    agent: Optional[AgentConfig] = None
    ai: Optional[AIConfig] = None
    storage_path: str = "processed_urls.json"
    log_level: str = "INFO"
    git: Optional[GitConfig] = None
    workflow: Optional[WorkflowConfig] = None


class ConfigLoader:
    """Loads and validates monitoring configuration from YAML files"""
    
    # JSON Schema for configuration validation
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["sites", "github", "search"],
        "properties": {
            "sites": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["url", "name"],
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                        "name": {"type": "string", "minLength": 1},
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10
                        },
                        "search_paths": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "exclude_paths": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "custom_search_terms": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "additionalProperties": False
                }
            },
            "github": {
                "type": "object",
                "required": ["repository"],
                "properties": {
                    "repository": {"type": "string", "pattern": r"^[^/]+/[^/]+$"},
                    "token": {"type": "string", "minLength": 1},
                    "issue_labels": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "default_assignees": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "additionalProperties": False
            },
            "search": {
                "type": "object",
                "required": ["api_key", "search_engine_id"],
                "properties": {
                    "api_key": {"type": "string", "minLength": 1},
                    "search_engine_id": {"type": "string", "minLength": 1},
                    "daily_query_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100
                    },
                    "results_per_query": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "date_range_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30
                    }
                },
                "additionalProperties": False
            },
            "agent": {
                "type": "object",
                "required": ["username"],
                "properties": {
                    "username": {"type": "string", "minLength": 1},
                    "workflow_directory": {"type": "string"},
                    "template_directory": {"type": "string"},
                    "output_directory": {"type": "string"},
                    "processing": {
                        "type": "object",
                        "properties": {
                            "default_timeout_minutes": {"type": "integer", "minimum": 1},
                            "max_concurrent_issues": {"type": "integer", "minimum": 1},
                            "retry_attempts": {"type": "integer", "minimum": 0},
                            "require_review": {"type": "boolean"},
                            "auto_create_pr": {"type": "boolean"}
                        },
                        "additionalProperties": False
                    },
                    "git": {
                        "type": "object",
                        "properties": {
                            "branch_prefix": {"type": "string"},
                            "commit_message_template": {"type": "string"},
                            "auto_push": {"type": "boolean"}
                        },
                        "additionalProperties": False
                    },
                    "validation": {
                        "type": "object",
                        "properties": {
                            "min_word_count": {"type": "integer", "minimum": 0},
                            "require_citations": {"type": "boolean"},
                            "spell_check": {"type": "boolean"}
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            },
            "storage_path": {"type": "string"},
            "log_level": {
                "type": "string",
                "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "git": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "repository_path": {"type": "string"},
                    "auto_commit": {"type": "boolean"},
                    "auto_push": {"type": "boolean"}
                },
                "additionalProperties": False
            },
            "workflow": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string"},
                    "output_dir": {"type": "string"}
                },
                "additionalProperties": False
            },
            "ai": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "model": {"type": "string"},
                    "confidence_thresholds": {
                        "type": "object",
                        "properties": {
                            "auto_assign": {"type": "number", "minimum": 0, "maximum": 1},
                            "request_review": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "additionalProperties": False
                    },
                    "max_tokens": {"type": "integer", "minimum": 1},
                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                    "history": {
                        "type": "object",
                        "properties": {
                            "storage_type": {"type": "string", "enum": ["gist", "repo_file"]},
                            "gist_id": {"type": "string"},
                            "file_path": {"type": "string"}
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            }
        },
        "additionalProperties": False
    }
    
    @classmethod
    def load_config(cls, config_path: str) -> MonitorConfig:
        """
        Load and validate configuration from YAML file
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            MonitorConfig object with loaded configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValidationError: If configuration doesn't match schema
            ValueError: If configuration values are invalid
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}") from e
        
        # Validate against schema
        try:
            validate(instance=config_data, schema=cls.CONFIG_SCHEMA)
        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e.message}") from e
        
        # Convert to dataclass objects
        return cls._build_config(config_data)
    
    @classmethod
    def _build_config(cls, config_data: Dict[str, Any]) -> MonitorConfig:
        """Build MonitorConfig object from validated configuration data"""
        
        # Build site configurations
        sites = []
        for site_data in config_data['sites']:
            site = SiteConfig(
                url=site_data['url'],
                name=site_data['name'],
                keywords=site_data.get('keywords', []),
                max_results=site_data.get('max_results', 10),
                search_paths=site_data.get('search_paths', []),
                exclude_paths=site_data.get('exclude_paths', []),
                custom_search_terms=site_data.get('custom_search_terms', [])
            )
            sites.append(site)
        
        # Build GitHub configuration
        github_data = config_data['github']
        github = GitHubConfig(
            repository=github_data['repository'],
            issue_labels=github_data.get('issue_labels', ["site-monitor", "automated"]),
            default_assignees=github_data.get('default_assignees', [])
        )
        
        # Build search configuration
        search_data = config_data['search']
        search = SearchConfig(
            api_key=search_data['api_key'],
            search_engine_id=search_data['search_engine_id'],
            daily_query_limit=search_data.get('daily_query_limit', 90),
            results_per_query=search_data.get('results_per_query', 10),
            date_range_days=search_data.get('date_range_days', 1)
        )
        
        # Build agent configuration (optional)
        agent = None
        if 'agent' in config_data:
            agent_data = config_data['agent']
            
            # Build processing config
            processing = AgentProcessingConfig()
            if 'processing' in agent_data:
                proc_data = agent_data['processing']
                processing = AgentProcessingConfig(
                    default_timeout_minutes=proc_data.get('default_timeout_minutes', 60),
                    max_concurrent_issues=proc_data.get('max_concurrent_issues', 3),
                    retry_attempts=proc_data.get('retry_attempts', 2),
                    require_review=proc_data.get('require_review', True),
                    auto_create_pr=proc_data.get('auto_create_pr', False)
                )
            
            # Build git config
            git = AgentGitConfig()
            if 'git' in agent_data:
                git_data = agent_data['git']
                git = AgentGitConfig(
                    branch_prefix=git_data.get('branch_prefix', 'agent'),
                    commit_message_template=git_data.get('commit_message_template', 
                                                       'Agent: {workflow_name} for issue #{issue_number}'),
                    auto_push=git_data.get('auto_push', True)
                )
            
            # Build validation config
            validation = AgentValidationConfig()
            if 'validation' in agent_data:
                val_data = agent_data['validation']
                validation = AgentValidationConfig(
                    min_word_count=val_data.get('min_word_count', 100),
                    require_citations=val_data.get('require_citations', False),
                    spell_check=val_data.get('spell_check', False)
                )
            
            agent = AgentConfig(
                username=agent_data['username'],
                workflow_directory=agent_data.get('workflow_directory', 'docs/workflow/deliverables'),
                template_directory=agent_data.get('template_directory', 'templates'),
                output_directory=agent_data.get('output_directory', 'study'),
                processing=processing,
                git=git,
                validation=validation
            )
        
        # Parse AI configuration
        ai = None
        if 'ai' in config_data:
            ai_data = config_data['ai']
            
            confidence_thresholds = None
            if 'confidence_thresholds' in ai_data:
                threshold_data = ai_data['confidence_thresholds']
                confidence_thresholds = AIConfidenceThresholds(
                    auto_assign=threshold_data.get('auto_assign', 0.8),
                    request_review=threshold_data.get('request_review', 0.6)
                )
            
            history = None
            if 'history' in ai_data:
                history_data = ai_data['history']
                history = AIHistoryConfig(
                    storage_type=history_data.get('storage_type', 'gist'),
                    gist_id=history_data.get('gist_id'),
                    file_path=history_data.get('file_path', '.github/ai_assignment_history.json')
                )
            
            # Handle models configuration
            models = None
            if 'models' in ai_data:
                models_data = ai_data['models']
                models = AIModelConfig(
                    content_extraction=models_data.get('content_extraction', 'gpt-4o'),
                    specialist_analysis=models_data.get('specialist_analysis', 'gpt-4o'),
                    document_generation=models_data.get('document_generation', 'gpt-4o'),
                    workflow_assignment=models_data.get('workflow_assignment', 'gpt-4o')
                )
            
            # Handle settings configuration
            settings = None
            if 'settings' in ai_data:
                settings_data = ai_data['settings']
                settings = AISettingsConfig(
                    temperature=settings_data.get('temperature', 0.3),
                    max_tokens=settings_data.get('max_tokens', 3000),
                    timeout_seconds=settings_data.get('timeout_seconds', 30),
                    retry_count=settings_data.get('retry_count', 3),
                    enable_logging=settings_data.get('enable_logging', True)
                )
            
            # Handle extraction focus configuration
            extraction_focus = None
            if 'extraction_focus' in ai_data:
                focus_data = ai_data['extraction_focus']
                extraction_focus = AIExtractionFocusConfig(
                    default=focus_data.get('default'),
                    intelligence_analyst=focus_data.get('intelligence_analyst'),
                    osint_researcher=focus_data.get('osint_researcher'),
                    target_profiler=focus_data.get('target_profiler'),
                    threat_hunter=focus_data.get('threat_hunter')
                )
            
            ai = AIConfig(
                enabled=ai_data.get('enabled', False),
                provider=ai_data.get('provider', 'github-models'),
                models=models,
                settings=settings,
                confidence_thresholds=confidence_thresholds,
                extraction_focus=extraction_focus,
                history=history
            )
        
        return MonitorConfig(
            sites=sites,
            github=github,
            search=search,
            agent=agent,
            ai=ai,
            storage_path=config_data.get('storage_path', 'processed_urls.json'),
            log_level=config_data.get('log_level', 'INFO')
        )
    



class ConfigManager:
    """Public interface for configuration management"""
    
    @classmethod
    def load_config(cls, config_path: str) -> MonitorConfig:
        """Load configuration from file"""
        return ConfigLoader.load_config(config_path)
    
    @classmethod
    def load_config_with_env_substitution(cls, config_path: str) -> MonitorConfig:
        """Load configuration with environment variable substitution"""
        return load_config_with_env_substitution(config_path)


def load_config_with_env_substitution(config_path: str) -> MonitorConfig:
    """
    Load configuration with environment variable substitution
    
    This function allows configuration values to reference environment variables
    using the format: ${ENV_VAR_NAME} or ${ENV_VAR_NAME:default_value}
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        MonitorConfig object with environment variables substituted
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Read raw YAML content
    with open(config_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Pattern to match ${VAR_NAME} or ${VAR_NAME:default_value}
    env_pattern = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')
    
    def replace_env_var(match):
        var_name = match.group(1)
        default_provided = match.group(2) is not None
        default_value = match.group(2) if default_provided else None

        env_value = os.getenv(var_name)

        # Treat empty strings the same as missing values so YAML does not coerce to null
        if env_value not in (None, ''):
            return env_value

        if default_provided:
            return default_value or ''

        raise ValueError(
            f"Environment variable '{var_name}' is required but not set for configuration file '{config_path}'."
        )
    
    # Substitute environment variables
    try:
        content = env_pattern.sub(replace_env_var, content)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    
    # Parse the substituted YAML
    try:
        config_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML after environment substitution: {e}") from e
    
    # Validate and build config
    try:
        validate(instance=config_data, schema=ConfigLoader.CONFIG_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Configuration validation failed: {e.message}") from e
    
    return ConfigLoader._build_config(config_data)