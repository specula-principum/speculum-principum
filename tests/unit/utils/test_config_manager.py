"""
Unit tests for the configuration manager module
"""

import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, mock_open

from src.utils.config_manager import (
    ConfigLoader, MonitorConfig, SiteConfig, GitHubConfig, SearchConfig,
    load_config_with_env_substitution
)


class TestSiteConfig:
    """Test the SiteConfig dataclass"""
    
    def test_site_config_creation(self):
        """Test creating a basic SiteConfig"""
        site = SiteConfig(url="example.com", name="Example Site")
        assert site.url == "example.com"
        assert site.name == "Example Site"
        assert site.keywords == []
        assert site.max_results == 10
        assert site.search_paths == []
        assert site.exclude_paths == []
        assert site.custom_search_terms == []
    
    def test_site_config_with_parameters(self):
        """Test creating SiteConfig with all parameters"""
        site = SiteConfig(
            url="example.com",
            name="Example Site",
            keywords=["test", "docs"],
            max_results=5,
            search_paths=["/docs"],
            exclude_paths=["/admin"],
            custom_search_terms=["update"]
        )
        assert site.keywords == ["test", "docs"]
        assert site.max_results == 5
        assert site.search_paths == ["/docs"]
        assert site.exclude_paths == ["/admin"]
        assert site.custom_search_terms == ["update"]


class TestGitHubConfig:
    """Test the GitHubConfig dataclass"""
    
    def test_github_config_creation(self):
        """Test creating a basic GitHubConfig"""
        github = GitHubConfig(repository="owner/repo")
        assert github.repository == "owner/repo"
        assert github.issue_labels == ["site-monitor", "automated"]
        assert github.default_assignees == []
    
    def test_github_config_with_parameters(self):
        """Test creating GitHubConfig with all parameters"""
        github = GitHubConfig(
            repository="owner/repo",
            issue_labels=["custom", "label"],
            default_assignees=["user1", "user2"]
        )
        assert github.issue_labels == ["custom", "label"]
        assert github.default_assignees == ["user1", "user2"]


class TestSearchConfig:
    """Test the SearchConfig dataclass"""
    
    def test_search_config_creation(self):
        """Test creating a basic SearchConfig"""
        search = SearchConfig(api_key="key123", search_engine_id="engine123")
        assert search.api_key == "key123"
        assert search.search_engine_id == "engine123"
        assert search.daily_query_limit == 90
        assert search.results_per_query == 10
        assert search.date_range_days == 1
    
    def test_search_config_validation_daily_limit(self):
        """Test validation of daily query limit"""
        with pytest.raises(ValueError, match="Daily query limit cannot exceed 100"):
            SearchConfig(api_key="key", search_engine_id="engine", daily_query_limit=101)
    
    def test_search_config_validation_results_per_query(self):
        """Test validation of results per query"""
        with pytest.raises(ValueError, match="Results per query cannot exceed 10"):
            SearchConfig(api_key="key", search_engine_id="engine", results_per_query=11)


class TestConfigLoader:
    """Test the ConfigLoader class"""
    
    def create_test_config(self):
        """Create a valid test configuration"""
        return {
            'sites': [
                {
                    'url': 'example.com',
                    'name': 'Example Site',
                    'keywords': ['test'],
                    'max_results': 5
                }
            ],
            'github': {
                'repository': 'owner/repo',
                'issue_labels': ['test-label']
            },
            'search': {
                'api_key': 'test-key',
                'search_engine_id': 'test-engine'
            }
        }
    
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file"""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_config("nonexistent.yaml")
    
    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content:")
            f.flush()
            
            try:
                with pytest.raises(ValueError, match="Invalid YAML"):
                    ConfigLoader.load_config(f.name)
            finally:
                os.unlink(f.name)
    
    def test_load_config_validation_error(self):
        """Test loading config that fails validation"""
        invalid_config = {'invalid': 'config'}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            f.flush()
            
            try:
                with pytest.raises(ValueError, match="Configuration validation failed"):
                    ConfigLoader.load_config(f.name)
            finally:
                os.unlink(f.name)
    
    def test_load_config_success(self):
        """Test successfully loading a valid config"""
        config_data = self.create_test_config()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            
            try:
                config = ConfigLoader.load_config(f.name)
                assert isinstance(config, MonitorConfig)
                assert len(config.sites) == 1
                assert config.sites[0].name == "Example Site"
                assert config.github.repository == "owner/repo"
                assert config.search.api_key == "test-key"
            finally:
                os.unlink(f.name)
    
    def test_build_config(self):
        """Test building config from validated data"""
        config_data = self.create_test_config()
        config = ConfigLoader._build_config(config_data)
        
        assert isinstance(config, MonitorConfig)
        assert len(config.sites) == 1
        assert isinstance(config.sites[0], SiteConfig)
        assert isinstance(config.github, GitHubConfig)
        assert isinstance(config.search, SearchConfig)
    
    


class TestEnvironmentSubstitution:
    """Test environment variable substitution functionality"""
    
    def test_env_substitution_simple(self):
        """Test simple environment variable substitution"""
        config_content = """
sites:
  - url: example.com
    name: Example Site
github:
  repository: ${GITHUB_REPOSITORY}
search:
  api_key: ${GOOGLE_API_KEY}
  search_engine_id: ${GOOGLE_SEARCH_ENGINE_ID}
"""
        
        with patch.dict(os.environ, {
            'GITHUB_REPOSITORY': 'owner/repo',
            'GOOGLE_API_KEY': 'test-key',
            'GOOGLE_SEARCH_ENGINE_ID': 'test-engine'
        }):
            with patch('builtins.open', mock_open(read_data=config_content)):
                with patch('os.path.exists', return_value=True):
                    config = load_config_with_env_substitution('test.yaml')
                    
                    assert config.github.repository == 'owner/repo'
                    assert config.search.api_key == 'test-key'
                    assert config.search.search_engine_id == 'test-engine'
    
    def test_env_substitution_with_defaults(self):
        """Test environment variable substitution with default values"""
        config_content = """
sites:
  - url: example.com
    name: Example Site
github:
  repository: ${GITHUB_REPOSITORY:default/repo}
search:
  api_key: ${MISSING_VAR:default-key}
  search_engine_id: test-engine
"""
        
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'actual/repo'}, clear=True):
            with patch('builtins.open', mock_open(read_data=config_content)):
                with patch('os.path.exists', return_value=True):
                    config = load_config_with_env_substitution('test.yaml')
                    
                    assert config.github.repository == 'actual/repo'
                    assert config.search.api_key == 'default-key'
    
    def test_env_substitution_missing_no_default(self):
        """Test environment variable substitution with missing var and no default"""
        config_content = """
sites:
  - url: example.com
    name: Example Site
github:
  repository: ${MISSING_VAR}
search:
  api_key: test-key
  search_engine_id: test-engine
"""
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('builtins.open', mock_open(read_data=config_content)):
                with patch('os.path.exists', return_value=True):
                    # Missing environment variable without default should raise a descriptive error
                    with pytest.raises(ValueError, match="Environment variable 'MISSING_VAR' is required"):
                        load_config_with_env_substitution('test.yaml')


@pytest.fixture
def sample_config():
    """Fixture providing a sample configuration"""
    return {
        'sites': [
            {
                'url': 'example.com',
                'name': 'Example Site',
                'keywords': ['documentation', 'updates'],
                'max_results': 10,
                'search_paths': ['/docs'],
                'exclude_paths': ['/admin']
            }
        ],
        'github': {
            'repository': 'owner/repo',
            'issue_labels': ['site-monitor', 'automated'],
            'default_assignees': ['maintainer']
        },
        'search': {
            'api_key': 'test-api-key',
            'search_engine_id': 'test-search-engine-id',
            'daily_query_limit': 90,
            'results_per_query': 10,
            'date_range_days': 1
        },
        'storage_path': 'test_processed_urls.json',
        'log_level': 'DEBUG'
    }


class TestCompleteConfigFlow:
    """Test the complete configuration loading flow"""
    
    def test_complete_config_loading(self, sample_config):
        """Test loading a complete configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config, f)
            f.flush()
            
            try:
                config = ConfigLoader.load_config(f.name)
                
                # Verify sites
                assert len(config.sites) == 1
                site = config.sites[0]
                assert site.url == 'example.com'
                assert site.name == 'Example Site'
                assert site.keywords == ['documentation', 'updates']
                assert site.max_results == 10
                assert site.search_paths == ['/docs']
                assert site.exclude_paths == ['/admin']
                
                # Verify GitHub config
                assert config.github.repository == 'owner/repo'
                assert config.github.issue_labels == ['site-monitor', 'automated']
                assert config.github.default_assignees == ['maintainer']
                
                # Verify search config
                assert config.search.api_key == 'test-api-key'
                assert config.search.search_engine_id == 'test-search-engine-id'
                assert config.search.daily_query_limit == 90
                assert config.search.results_per_query == 10
                assert config.search.date_range_days == 1
                
                # Verify other settings
                assert config.storage_path == 'test_processed_urls.json'
                assert config.log_level == 'DEBUG'
                
            finally:
                os.unlink(f.name)