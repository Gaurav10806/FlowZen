"""
Memory Node (Redis).
Provides Key-Value storage operations (Set, Get, Increment, Delete).
"""

from typing import Dict, Any
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from django.core.cache import cache
import json

@register_node
class MemoryNode(ActionNode):
    """
    Memory Node (Redis).
    Provides Key-Value storage operations (Set, Get, Increment, Delete).
    """
    
    NODE_TYPE = "memory"
    DISPLAY_NAME = "Memory (Redis)"
    DESCRIPTION = "Store and retrieve data using Redis (Key-Value)"
    CATEGORY = "data"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Memory operation.
        """
        operation = params.get('operation', 'set')
        key_raw = self._resolve_template(params.get('key', ''), input_data, context)
        scope = params.get('scope', 'workflow')
        
        if not key_raw:
             raise NodeExecutionError("Key is required for Memory operations")

        # Construct Scoped Key
        full_key = self._get_scoped_key(key_raw, scope, context)
        
        try:
            if operation == 'set':
                value_raw = params.get('value')
                # If value is a string template, resolve it
                if isinstance(value_raw, str):
                    value = self._resolve_template(value_raw, input_data, context)
                else:
                    value = value_raw
                    
                # Store in cache (default timeout 24h for now, or configurable)
                ttl = int(params.get('ttl', 86400)) # 24 hours
                cache.set(full_key, value, ttl)
                
                return {
                    "success": True,
                    "operation": "set",
                    "key": key_raw,
                    "scope": scope,
                    "value": value
                }
                
            elif operation == 'get':
                value = cache.get(full_key)
                return {
                    "success": True,
                    "operation": "get",
                    "key": key_raw,
                    "scope": scope,
                    "value": value,
                    "found": value is not None
                }
            
            elif operation == 'increment':
                delta = int(params.get('delta', 1))
                try:
                    # Django cache.incr raises ValueError if key doesn't exist in some backends
                    # So we try to get first
                    if cache.get(full_key) is None:
                        cache.set(full_key, 0, int(params.get('ttl', 86400)))
                    
                    new_value = cache.incr(full_key, delta)
                    return {
                        "success": True,
                        "operation": "increment",
                        "key": key_raw,
                        "new_value": new_value
                    }
                except ValueError:
                    # Key exists but is not an integer
                    raise NodeExecutionError(f"Key '{key_raw}' contains non-integer value, cannot increment.")
                    
            elif operation == 'delete':
                cache.delete(full_key)
                return {
                    "success": True,
                    "operation": "delete",
                    "key": key_raw
                }

            else:
                 raise NodeExecutionError(f"Unknown operation: {operation}")

        except Exception as e:
            self.logger.error(f"Memory Node Error: {e}")
            raise NodeExecutionError(f"Memory Error: {str(e)}")

    def _get_scoped_key(self, key: str, scope: str, context: Dict[str, Any]) -> str:
        """
        Generate a namespaced key based on scope.
        """
        if scope == 'global':
            return f"global:{key}"
        elif scope == 'user':
            user_id = context.get('user_id')
            if not user_id:
                raise NodeExecutionError("User scope requires user_id in context")
            return f"user:{user_id}:{key}"
        elif scope == 'workflow':
            # Shared by all runs of this workflow
            workflow_id = context.get('workflow_id')
            if not workflow_id:
                 workflow_id = context.get('execution_id', 'unknown')
            return f"wf:{workflow_id}:{key}"
        else:
            return f"default:{key}"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "title": "Operation",
                    "enum": ["set", "get", "increment", "delete"],
                    "default": "set"
                },
                "key": {
                    "type": "string",
                    "title": "Key",
                    "description": "Storage Key"
                },
                "value": {
                    "type": "string",
                    "title": "Value",
                    "description": "Value to store (for SET)",
                    "widget": "textarea"
                },
                "delta": {
                    "type": "integer",
                    "title": "Increment By",
                    "default": 1,
                    "description": "Amount to increment (for INCREMENT)"
                },
                "scope": {
                    "type": "string",
                    "title": "Scope",
                    "enum": ["workflow", "user", "global"],
                    "default": "workflow",
                    "description": "Workflow: Shared by this workflow. User: Shared by user. Global: Shared by all."
                },
                "ttl": {
                    "type": "integer",
                    "title": "TTL (Seconds)",
                    "default": 86400,
                    "description": "Time to live in seconds (default 24h)"
                }
            },
            "required": ["operation", "key"]
        }
