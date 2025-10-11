"""
GitHub Models API Client

Enhanced, reusable client for GitHub Models API with comprehensive error handling,
rate limiting, and support for multiple AI use cases including content extraction,
workflow assignment, and document generation.
"""

import json
import time
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from ..utils.logging_config import get_logger, log_exception


@dataclass
class AIResponse:
    """Structured AI response with metadata"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    response_time_ms: Optional[int] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class RateLimitInfo:
    """Rate limiting information"""
    requests_remaining: int = 100
    reset_time: Optional[datetime] = None
    request_count: int = 0
    last_request: Optional[datetime] = None


class GitHubModelsClient:
    """
    Enhanced client for GitHub Models API
    
    Provides access to AI models through GitHub's inference API with:
    - Comprehensive error handling and retries
    - Rate limiting and request tracking
    - Support for multiple model types and use cases
    - Structured response parsing
    - Request/response logging
    """
    
    BASE_URL = "https://models.github.ai/inference"
    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 3
    RETRY_DELAY = 1.0  # Base delay between retries (exponential backoff)
    
    def __init__(self, 
                 github_token: str, 
                 model: str = "gpt-4o",
                 timeout: int = None,
                 max_retries: int = None,
                 enable_logging: bool = True):
        """
        Initialize GitHub Models client.
        
        Args:
            github_token: GitHub token with models API access
            model: Model to use (gpt-4o, gpt-4o-mini, etc.)
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts (default: 3)
            enable_logging: Whether to log requests/responses
        """
        self.logger = get_logger(__name__)
        self.token = github_token
        self.model = model
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_RETRIES
        self.enable_logging = enable_logging
        
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Speculum-Principum/1.0"
        }
        
        # Rate limiting
        self.rate_limit = RateLimitInfo()
        
        # Validate configuration
        self._validate_config()
        
    def _validate_config(self):
        """Validate client configuration"""
        if not self.token:
            raise ValueError("GitHub token is required")
        if not self.model:
            raise ValueError("Model name is required")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
    
    def chat_completion(self,
                       messages: List[Dict[str, str]],
                       temperature: float = 0.3,
                       max_tokens: int = 1000,
                       **kwargs) -> AIResponse:
        """
        Make a chat completion request to GitHub Models.
        
        Args:
            messages: List of message objects (role, content)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API
            
        Returns:
            AIResponse with structured response data
            
        Raises:
            ValueError: Invalid parameters
            requests.RequestException: API request failed
            json.JSONDecodeError: Invalid response format
        """
        # Validate parameters
        if not messages:
            raise ValueError("Messages list cannot be empty")
        if not all('role' in msg and 'content' in msg for msg in messages):
            raise ValueError("All messages must have 'role' and 'content' fields")
        if not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        if max_tokens <= 0:
            raise ValueError("Max tokens must be positive")
        
        # Check rate limits
        self._check_rate_limit()
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        start_time = time.time()
        
        if self.enable_logging:
            self.logger.debug(f"GitHub Models request: {json.dumps(payload, indent=2)}")
        
        # Make request with retries
        response_data = self._make_request_with_retries(payload)
        
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Parse response
        ai_response = self._parse_chat_response(response_data, response_time_ms)
        
        if self.enable_logging:
            self.logger.debug(f"GitHub Models response: {asdict(ai_response)}")
        
        # Update rate limiting info
        self._update_rate_limit()
        
        return ai_response
    
    def simple_completion(self, 
                         prompt: str,
                         system_message: str = None,
                         **kwargs) -> AIResponse:
        """
        Simple completion with a single prompt.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            **kwargs: Additional parameters for chat_completion
            
        Returns:
            AIResponse with the completion
        """
        messages = []
        
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        
        messages.append({
            "role": "user", 
            "content": prompt
        })
        
        return self.chat_completion(messages, **kwargs)
    
    def _make_request_with_retries(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with exponential backoff retries"""
        endpoint = f"{self.BASE_URL}/chat/completions"
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if attempt < self.max_retries:
                        self.logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt + 1}")
                        time.sleep(retry_after)
                        continue
                    else:
                        raise requests.exceptions.RequestException(f"Rate limited after {self.max_retries} retries")
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Request failed after {self.max_retries + 1} attempts")
                    raise
        
        # This shouldn't be reached, but just in case
        raise last_exception or requests.exceptions.RequestException("Unknown error in request retries")
    
    def _parse_chat_response(self, response_data: Dict[str, Any], response_time_ms: int) -> AIResponse:
        """Parse chat completion response into structured format"""
        try:
            if "choices" not in response_data or not response_data["choices"]:
                raise ValueError("Invalid response structure: no choices found")
            
            choice = response_data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            if not content:
                raise ValueError("Empty content in response")
            
            # Extract usage information
            usage = response_data.get("usage", {})
            finish_reason = choice.get("finish_reason")
            
            return AIResponse(
                content=content.strip(),
                model=self.model,
                usage=usage,
                finish_reason=finish_reason,
                response_time_ms=response_time_ms
            )
            
        except (KeyError, IndexError, TypeError) as e:
            self.logger.error(f"Failed to parse GitHub Models response: {e}")
            self.logger.error(f"Response data: {json.dumps(response_data, indent=2)}")
            raise ValueError(f"Invalid response format: {e}")
    
    def _check_rate_limit(self):
        """Check if we're within rate limits"""
        now = datetime.utcnow()
        
        # Reset counter if needed (assuming hourly reset)
        if (self.rate_limit.reset_time and 
            now > self.rate_limit.reset_time):
            self.rate_limit.request_count = 0
            self.rate_limit.reset_time = None
        
        # Set initial reset time
        if self.rate_limit.reset_time is None:
            self.rate_limit.reset_time = now + timedelta(hours=1)
        
        # Check if we're hitting limits (conservative estimate)
        if self.rate_limit.request_count >= 50:  # Conservative limit
            remaining_time = (self.rate_limit.reset_time - now).total_seconds()
            if remaining_time > 0:
                self.logger.warning(f"Approaching rate limit, {remaining_time:.0f}s until reset")
    
    def _update_rate_limit(self):
        """Update rate limiting counters"""
        self.rate_limit.request_count += 1
        self.rate_limit.last_request = datetime.utcnow()
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status"""
        return {
            "request_count": self.rate_limit.request_count,
            "requests_remaining": max(0, 50 - self.rate_limit.request_count),
            "reset_time": self.rate_limit.reset_time.isoformat() if self.rate_limit.reset_time else None,
            "last_request": self.rate_limit.last_request.isoformat() if self.rate_limit.last_request else None
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a simple health check on the GitHub Models API.
        
        Returns:
            Dict with health status and basic metrics
        """
        try:
            test_response = self.simple_completion(
                prompt="Hello, are you working?",
                system_message="Respond with 'Yes, I'm working' if you receive this message.",
                max_tokens=10
            )
            
            return {
                "status": "healthy",
                "model": self.model,
                "response_time_ms": test_response.response_time_ms,
                "timestamp": test_response.timestamp,
                "rate_limit": self.get_rate_limit_status()
            }
            
        except Exception as e:
            log_exception(self.logger, "Health check failed", e)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "rate_limit": self.get_rate_limit_status()
            }