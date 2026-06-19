"""
Enhanced HTTP Request Node

An advanced HTTP request node with retry logic, authentication,
response validation, and comprehensive error handling.
"""

import json
import time
import hashlib
import hmac
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# These imports would be validated against the plugin's allowed_imports
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from automation.backend.workflows.nodes.base_node import BaseNode, NodeExecutionError
from automation.backend.workflows.nodes.registry import register_node


@register_node
class EnhancedHttpNode(BaseNode):
    """
    Enhanced HTTP Request Node with advanced features:
    - Automatic retry logic with exponential backoff
    - Multiple authentication methods (Bearer, Basic, API Key, HMAC)
    - Response validation and transformation
    - Request/response caching
    - Comprehensive error handling and logging
    - Rate limiting and timeout management
    """
    
    NODE_TYPE = "enhanced_http"
    DISPLAY_NAME = "Enhanced HTTP Request"
    DESCRIPTION = "Advanced HTTP request node with retry, auth, and validation"
    CATEGORY = "network"
    SUPPORTS_RETRY = True
    DEFAULT_TIMEOUT = 30
    
    # Authentication methods
    AUTH_METHODS = {
        "none": "No authentication",
        "bearer": "Bearer token authentication",
        "basic": "Basic authentication (username/password)",
        "api_key": "API key authentication",
        "hmac": "HMAC signature authentication",
        "custom": "Custom header authentication"
    }
    
    # HTTP methods
    HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    
    # Response formats
    RESPONSE_FORMATS = ["json", "text", "xml", "binary", "auto"]
    
    def __init__(self):
        super().__init__()
        self.response_cache = {}  # Simple in-memory cache
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute enhanced HTTP request with advanced features.
        
        Args:
            input_data: Data from previous nodes
            params: HTTP request configuration
            context: Execution context
            
        Returns:
            Dict with HTTP response data and metadata
        """
        self.logger.info("Executing enhanced HTTP request")
        
        try:
            # Extract and validate parameters
            url = self._resolve_template(params.get('url', ''), input_data, context)
            method = params.get('method', 'GET').upper()
            headers = params.get('headers', {})
            body = params.get('body')
            auth_config = params.get('authentication', {})
            retry_config = params.get('retry', {})
            validation_config = params.get('validation', {})
            cache_config = params.get('caching', {})
            
            # Validate method
            if method not in self.HTTP_METHODS:
                raise NodeExecutionError(f"Invalid HTTP method: {method}")
            
            if not url:
                raise NodeExecutionError("URL is required")
            
            # Check cache first (for GET requests)
            if method == 'GET' and cache_config.get('enabled', False):
                cached_response = self._get_cached_response(url, headers)
                if cached_response:
                    self.logger.info("Returning cached response")
                    return {
                        **input_data,
                        'http_response': cached_response,
                        'from_cache': True
                    }
            
            # Prepare request
            session = self._create_session(retry_config)
            
            # Apply authentication
            if auth_config.get('method') != 'none':
                headers = self._apply_authentication(headers, auth_config, method, url, body)
            
            # Resolve templates in headers and body
            headers = self._resolve_templates_in_dict(headers, input_data, context)
            if body:
                body = self._resolve_template_in_body(body, input_data, context)
            
            # Execute request with retry logic
            start_time = datetime.utcnow()
            
            response = self._execute_request(
                session, method, url, headers, body, params
            )
            
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Process response
            response_data = self._process_response(response, params.get('response_format', 'auto'))
            
            # Validate response if configured
            if validation_config:
                self._validate_response(response, response_data, validation_config)
            
            # Cache response if configured
            if method == 'GET' and cache_config.get('enabled', False):
                self._cache_response(url, headers, response_data, cache_config)
            
            # Create response object
            http_response = {
                'status_code': response.status_code,
                'status_text': response.reason,
                'headers': dict(response.headers),
                'data': response_data,
                'url': response.url,
                'method': method,
                'response_time_ms': response_time_ms,
                'success': 200 <= response.status_code < 300,
                'cached': False,
                'timestamp': start_time.isoformat()
            }
            
            self.logger.info(f"HTTP request completed: {method} {url} -> {response.status_code} ({response_time_ms}ms)")
            
            return {
                **input_data,
                'http_response': http_response,
                'from_cache': False
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP request failed: {str(e)}"
            self.logger.error(error_msg)
            raise NodeExecutionError(error_msg)
        
        except Exception as e:
            error_msg = f"Enhanced HTTP node execution failed: {str(e)}"
            self.logger.error(error_msg)
            raise NodeExecutionError(error_msg)
    
    def _create_session(self, retry_config: Dict[str, Any]) -> requests.Session:
        """Create HTTP session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_attempts = retry_config.get('attempts', 3)
        backoff_factor = retry_config.get('backoff_factor', 0.3)
        status_forcelist = retry_config.get('status_codes', [500, 502, 503, 504])
        
        retry_strategy = Retry(
            total=retry_attempts,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            method_whitelist=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _apply_authentication(self, headers: Dict[str, str], auth_config: Dict[str, Any],
                            method: str, url: str, body: Any) -> Dict[str, str]:
        """Apply authentication to request headers."""
        auth_method = auth_config.get('method', 'none')
        headers = headers.copy()
        
        if auth_method == 'bearer':
            token = auth_config.get('token', '')
            headers['Authorization'] = f'Bearer {token}'
        
        elif auth_method == 'basic':
            username = auth_config.get('username', '')
            password = auth_config.get('password', '')
            credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        elif auth_method == 'api_key':
            key_name = auth_config.get('key_name', 'X-API-Key')
            key_value = auth_config.get('key_value', '')
            headers[key_name] = key_value
        
        elif auth_method == 'hmac':
            secret = auth_config.get('secret', '')
            key_id = auth_config.get('key_id', '')
            
            # Create HMAC signature
            timestamp = str(int(time.time()))
            string_to_sign = f"{method}\\n{url}\\n{timestamp}"
            if body:
                string_to_sign += f"\\n{json.dumps(body) if isinstance(body, dict) else str(body)}"
            
            signature = hmac.new(
                secret.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers['Authorization'] = f'HMAC-SHA256 KeyId={key_id}, Signature={signature}, Timestamp={timestamp}'
        
        elif auth_method == 'custom':
            custom_headers = auth_config.get('headers', {})
            headers.update(custom_headers)
        
        return headers
    
    def _execute_request(self, session: requests.Session, method: str, url: str,
                        headers: Dict[str, str], body: Any, params: Dict[str, Any]) -> requests.Response:
        """Execute the HTTP request with proper error handling."""
        timeout = params.get('timeout', self.DEFAULT_TIMEOUT)
        
        request_kwargs = {
            'method': method,
            'url': url,
            'headers': headers,
            'timeout': timeout
        }
        
        # Add body for methods that support it
        if method in ['POST', 'PUT', 'PATCH'] and body is not None:
            if isinstance(body, dict):
                request_kwargs['json'] = body
            else:
                request_kwargs['data'] = body
        
        # Add query parameters
        query_params = params.get('query_params')
        if query_params:
            request_kwargs['params'] = query_params
        
        return session.request(**request_kwargs)
    
    def _process_response(self, response: requests.Response, response_format: str) -> Any:
        """Process response based on format specification."""
        if response_format == 'auto':
            # Auto-detect format based on content type
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                response_format = 'json'
            elif 'text/' in content_type:
                response_format = 'text'
            elif 'application/xml' in content_type or 'text/xml' in content_type:
                response_format = 'xml'
            else:
                response_format = 'binary'
        
        if response_format == 'json':
            try:
                return response.json()
            except ValueError:
                return response.text
        
        elif response_format == 'text':
            return response.text
        
        elif response_format == 'xml':
            # Simple XML handling (would use proper XML parser in production)
            return response.text
        
        elif response_format == 'binary':
            return {
                'content_length': len(response.content),
                'content_type': response.headers.get('content-type'),
                'data': base64.b64encode(response.content).decode()
            }
        
        else:
            return response.text
    
    def _validate_response(self, response: requests.Response, response_data: Any,
                          validation_config: Dict[str, Any]):
        """Validate response against configured rules."""
        # Status code validation
        expected_status = validation_config.get('expected_status_code')
        if expected_status and response.status_code != expected_status:
            raise NodeExecutionError(f"Unexpected status code: {response.status_code}, expected: {expected_status}")
        
        # Response schema validation (simplified)
        required_fields = validation_config.get('required_fields', [])
        if isinstance(response_data, dict):
            for field in required_fields:
                if field not in response_data:
                    raise NodeExecutionError(f"Required field missing in response: {field}")
        
        # Custom validation rules
        validation_rules = validation_config.get('rules', [])
        for rule in validation_rules:
            # Simple rule evaluation (would be more sophisticated in production)
            if rule.get('type') == 'not_empty' and not response_data:
                raise NodeExecutionError("Response data is empty")
    
    def _get_cached_response(self, url: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        cache_key = self._generate_cache_key(url, headers)
        
        if cache_key in self.response_cache:
            cached_entry = self.response_cache[cache_key]
            
            # Check if cache entry is still valid
            if datetime.fromisoformat(cached_entry['expires_at']) > datetime.utcnow():
                return cached_entry['response']
            else:
                # Remove expired entry
                del self.response_cache[cache_key]
        
        return None
    
    def _cache_response(self, url: str, headers: Dict[str, str], response_data: Dict[str, Any],
                       cache_config: Dict[str, Any]):
        """Cache response data."""
        cache_key = self._generate_cache_key(url, headers)
        ttl_seconds = cache_config.get('ttl_seconds', 300)
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        self.response_cache[cache_key] = {
            'response': response_data,
            'expires_at': expires_at.isoformat(),
            'cached_at': datetime.utcnow().isoformat()
        }
    
    def _generate_cache_key(self, url: str, headers: Dict[str, str]) -> str:
        """Generate cache key for request."""
        # Create deterministic cache key
        key_data = f"{url}:{json.dumps(sorted(headers.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _resolve_template(self, template: str, input_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Resolve template variables in string."""
        # Simple template resolution ({{variable}} format)
        import re
        
        def replace_var(match):
            var_path = match.group(1)
            return self._get_nested_value(input_data, var_path, str(match.group(0)))
        
        return re.sub(r'\\{\\{([^}]+)\\}\\}', replace_var, template)
    
    def _resolve_templates_in_dict(self, data: Dict[str, Any], input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve templates in dictionary values."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._resolve_template(value, input_data, context)
            else:
                result[key] = value
        return result
    
    def _resolve_template_in_body(self, body: Any, input_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Resolve templates in request body."""
        if isinstance(body, str):
            return self._resolve_template(body, input_data, context)
        elif isinstance(body, dict):
            return self._resolve_templates_in_dict(body, input_data, context)
        else:
            return body
    
    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for enhanced HTTP node parameters."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "title": "URL",
                    "description": "Target URL for the HTTP request (supports templates)",
                    "format": "uri"
                },
                "method": {
                    "type": "string",
                    "enum": cls.HTTP_METHODS,
                    "title": "HTTP Method",
                    "description": "HTTP method to use",
                    "default": "GET"
                },
                "headers": {
                    "type": "object",
                    "title": "Headers",
                    "description": "HTTP headers to send (supports templates)",
                    "additionalProperties": {"type": "string"}
                },
                "body": {
                    "title": "Request Body",
                    "description": "Request body data (supports templates)",
                    "oneOf": [
                        {"type": "object"},
                        {"type": "string"},
                        {"type": "null"}
                    ]
                },
                "authentication": {
                    "type": "object",
                    "title": "Authentication",
                    "description": "Authentication configuration",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": list(cls.AUTH_METHODS.keys()),
                            "default": "none"
                        },
                        "token": {"type": "string"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                        "key_name": {"type": "string"},
                        "key_value": {"type": "string"},
                        "secret": {"type": "string"},
                        "key_id": {"type": "string"}
                    }
                },
                "retry": {
                    "type": "object",
                    "title": "Retry Configuration",
                    "description": "Retry logic configuration",
                    "properties": {
                        "attempts": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 10,
                            "default": 3
                        },
                        "backoff_factor": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 5,
                            "default": 0.3
                        },
                        "status_codes": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "default": [500, 502, 503, 504]
                        }
                    }
                },
                "timeout": {
                    "type": "integer",
                    "title": "Timeout (seconds)",
                    "description": "Request timeout in seconds",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30
                },
                "response_format": {
                    "type": "string",
                    "enum": cls.RESPONSE_FORMATS,
                    "title": "Response Format",
                    "description": "Expected response format",
                    "default": "auto"
                },
                "validation": {
                    "type": "object",
                    "title": "Response Validation",
                    "description": "Response validation rules",
                    "properties": {
                        "expected_status_code": {"type": "integer"},
                        "required_fields": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "caching": {
                    "type": "object",
                    "title": "Response Caching",
                    "description": "Response caching configuration",
                    "properties": {
                        "enabled": {"type": "boolean", "default": false},
                        "ttl_seconds": {
                            "type": "integer",
                            "minimum": 60,
                            "maximum": 3600,
                            "default": 300
                        }
                    }
                }
            },
            "required": ["url"],
            "additionalProperties": False
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Expected input data schema."""
        return {
            "type": "object",
            "description": "Any data from previous nodes (available for template substitution)",
            "additionalProperties": True
        }
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Output data schema."""
        return {
            "type": "object",
            "properties": {
                "http_response": {
                    "type": "object",
                    "description": "HTTP response data and metadata",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "status_text": {"type": "string"},
                        "headers": {"type": "object"},
                        "data": {"description": "Response data in requested format"},
                        "success": {"type": "boolean"},
                        "response_time_ms": {"type": "integer"}
                    }
                },
                "from_cache": {
                    "type": "boolean",
                    "description": "Whether response was served from cache"
                }
            },
            "additionalProperties": True,
            "description": "All input data plus http_response with request results"
        }