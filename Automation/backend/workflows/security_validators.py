"""
Production Security Validators
Input validation and sanitization for security
"""
import json
import re
import logging
from typing import Dict, Any, List
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from rest_framework import serializers

logger = logging.getLogger('security')


class PayloadSecurityValidator:
    """
    CRITICAL: Validate and sanitize all input payloads
    Prevents injection attacks and malicious content
    """
    
    # Dangerous patterns to detect
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',                # JavaScript URLs
        r'data:text/html',            # Data URLs
        r'eval\s*\(',                 # eval() calls
        r'exec\s*\(',                 # exec() calls
        r'__import__',                # Python imports
        r'subprocess',                # Subprocess calls
        r'os\.system',                # OS system calls
        r'shell\s*=\s*True',          # Shell execution
        r'file://',                   # File URLs
        r'\$\{.*\}',                  # Template injection
        r'<%.*%>',                    # Template tags
    ]
    
    @classmethod
    def validate_json_payload(cls, payload: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """
        Validate and sanitize JSON payload
        
        Args:
            payload: Input payload to validate
            max_depth: Maximum nesting depth allowed
            
        Returns:
            Sanitized payload
            
        Raises:
            ValidationError: If payload is invalid or dangerous
        """
        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a dictionary")
        
        # Check payload size
        payload_str = json.dumps(payload)
        if len(payload_str) > 10 * 1024 * 1024:  # 10MB limit
            raise ValidationError("Payload too large (max 10MB)")
        
        # Check nesting depth
        if cls._get_depth(payload) > max_depth:
            raise ValidationError(f"Payload too deeply nested (max depth: {max_depth})")
        
        # Scan for dangerous patterns
        cls._scan_for_dangerous_content(payload_str)
        
        # Sanitize the payload
        return cls._sanitize_payload(payload)
    
    @classmethod
    def _get_depth(cls, obj, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of object"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(cls._get_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(cls._get_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth
    
    @classmethod
    def _scan_for_dangerous_content(cls, content: str) -> None:
        """Scan content for dangerous patterns"""
        content_lower = content.lower()
        
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                logger.warning(f"SECURITY: Dangerous pattern detected: {pattern}")
                raise ValidationError(f"Potentially dangerous content detected")
    
    @classmethod
    def _sanitize_payload(cls, obj: Any) -> Any:
        """Recursively sanitize payload content"""
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                # Sanitize key
                clean_key = cls._sanitize_string(str(key))
                if clean_key != str(key):
                    logger.info(f"SECURITY: Sanitized key: {key} -> {clean_key}")
                
                # Sanitize value
                sanitized[clean_key] = cls._sanitize_payload(value)
            return sanitized
        
        elif isinstance(obj, list):
            return [cls._sanitize_payload(item) for item in obj]
        
        elif isinstance(obj, str):
            return cls._sanitize_string(obj)
        
        else:
            return obj
    
    @classmethod
    def _sanitize_string(cls, text: str) -> str:
        """Sanitize string content"""
        if not isinstance(text, str):
            return text
        
        # Strip HTML tags
        sanitized = strip_tags(text)
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Limit length
        if len(sanitized) > 10000:  # 10KB per string
            sanitized = sanitized[:10000]
            logger.info("SECURITY: String truncated due to length")
        
        return sanitized


class WorkflowSecurityValidator:
    """
    CRITICAL: Validate workflow definitions for security
    """
    
    @classmethod
    def validate_workflow_graph(cls, graph: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow graph structure"""
        if not isinstance(graph, dict):
            raise ValidationError("Workflow graph must be a dictionary")
        
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        
        if not isinstance(nodes, list):
            raise ValidationError("Nodes must be a list")
        
        if not isinstance(edges, list):
            raise ValidationError("Edges must be a list")
        
        # Validate nodes
        cls._validate_nodes(nodes)
        
        # Validate edges
        cls._validate_edges(edges, nodes)
        
        # Check for cycles (basic check)
        cls._check_for_cycles(nodes, edges)
        
        return graph
    
    @classmethod
    def _validate_nodes(cls, nodes: List[Dict]) -> None:
        """Validate individual nodes"""
        node_ids = set()
        
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise ValidationError(f"Node {i} must be a dictionary")
            
            # Required fields
            node_id = node.get('id')
            if not node_id:
                raise ValidationError(f"Node {i} missing required 'id' field")
            
            if node_id in node_ids:
                raise ValidationError(f"Duplicate node ID: {node_id}")
            node_ids.add(node_id)
            
            # Validate node type
            node_type = node.get('type')
            if node_type not in ['trigger', 'action', 'utility']:
                raise ValidationError(f"Invalid node type: {node_type}")
            
            # Validate configuration
            config = node.get('config', {})
            if config:
                cls._validate_node_config(config, node_id)
    
    @classmethod
    def _validate_node_config(cls, config: Dict, node_id: str) -> None:
        """Validate node configuration"""
        # Check for dangerous configuration
        dangerous_keys = ['eval', 'exec', 'import', '__import__', 'subprocess']
        
        for key in config.keys():
            if key.lower() in dangerous_keys:
                raise ValidationError(f"Dangerous configuration key in node {node_id}: {key}")
        
        # Validate URLs if present
        if 'url' in config:
            cls._validate_url(config['url'], node_id)
    
    @classmethod
    def _validate_url(cls, url: str, node_id: str) -> None:
        """Validate URL for security"""
        if not isinstance(url, str):
            return
        
        url_lower = url.lower()
        
        # Block dangerous protocols
        dangerous_protocols = ['file://', 'ftp://', 'javascript:', 'data:']
        for protocol in dangerous_protocols:
            if url_lower.startswith(protocol):
                raise ValidationError(f"Dangerous URL protocol in node {node_id}: {protocol}")
        
        # Block internal/private IPs (basic check)
        import re
        private_ip_pattern = r'(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)'
        if re.search(private_ip_pattern, url):
            logger.warning(f"SECURITY: Private IP detected in URL for node {node_id}")
    
    @classmethod
    def _validate_edges(cls, edges: List[Dict], nodes: List[Dict]) -> None:
        """Validate workflow edges"""
        node_ids = {node['id'] for node in nodes}
        
        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                raise ValidationError(f"Edge {i} must be a dictionary")
            
            source = edge.get('source')
            target = edge.get('target')
            
            if not source or not target:
                raise ValidationError(f"Edge {i} missing source or target")
            
            if source not in node_ids:
                raise ValidationError(f"Edge {i} references unknown source node: {source}")
            
            if target not in node_ids:
                raise ValidationError(f"Edge {i} references unknown target node: {target}")
    
    @classmethod
    def _check_for_cycles(cls, nodes: List[Dict], edges: List[Dict]) -> None:
        """Basic cycle detection"""
        # Build adjacency list
        graph = {node['id']: [] for node in nodes}
        for edge in edges:
            graph[edge['source']].append(edge['target'])
        
        # DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node_id in graph:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise ValidationError("Workflow contains cycles")


class CredentialSecurityValidator:
    """
    CRITICAL: Validate credential data for security
    """
    
    @classmethod
    def validate_credential_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate credential data before encryption"""
        if not isinstance(data, dict):
            raise ValidationError("Credential data must be a dictionary")
        
        # Check for required fields based on credential type
        cred_type = data.get('type')
        if not cred_type:
            raise ValidationError("Credential type is required")
        
        # Validate based on type
        if cred_type == 'http_auth':
            cls._validate_http_auth(data)
        elif cred_type == 'api_key':
            cls._validate_api_key(data)
        elif cred_type == 'oauth2':
            cls._validate_oauth2(data)
        
        # General validation
        cls._validate_credential_values(data)
        
        return data
    
    @classmethod
    def _validate_http_auth(cls, data: Dict) -> None:
        """Validate HTTP authentication credentials"""
        if 'username' not in data:
            raise ValidationError("HTTP auth requires username")
        
        if 'password' not in data:
            raise ValidationError("HTTP auth requires password")
    
    @classmethod
    def _validate_api_key(cls, data: Dict) -> None:
        """Validate API key credentials"""
        if 'api_key' not in data:
            raise ValidationError("API key credential requires api_key field")
        
        api_key = data['api_key']
        if len(api_key) < 10:
            raise ValidationError("API key too short (minimum 10 characters)")
    
    @classmethod
    def _validate_oauth2(cls, data: Dict) -> None:
        """Validate OAuth2 credentials"""
        required_fields = ['client_id', 'client_secret']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"OAuth2 credential requires {field}")
    
    @classmethod
    def _validate_credential_values(cls, data: Dict) -> None:
        """Validate credential values for security"""
        for key, value in data.items():
            if isinstance(value, str):
                # Check for suspicious content
                if any(pattern in value.lower() for pattern in ['<script', 'javascript:', 'eval(']):
                    raise ValidationError(f"Suspicious content in credential field: {key}")
                
                # Check length
                if len(value) > 1000:
                    raise ValidationError(f"Credential field too long: {key}")