"""
Base Node System for Workflow Automation

This module defines the core BaseNode class that all workflow nodes must inherit from.
It provides the foundation for the pluggable node system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging


class NodeExecutionError(Exception):
    """Raised when node execution fails."""
    
    def __init__(self, message: str, node_type: str = None, node_id: str = None):
        super().__init__(message)
        self.node_type = node_type
        self.node_id = node_id
        self.message = message


class BaseNode(ABC):
    """
    Base class for all workflow nodes.
    
    This is the FOUNDATION of the node system.
    Every node type MUST inherit from this class.
    
    The node system follows these principles:
    1. Each node type maps to exactly ONE Python class
    2. Node 'type' in JSON MUST match Python class registration
    3. Nodes are pluggable and extensible
    4. No hardcoded node logic inside the execution engine
    5. Node code is isolated from UI logic
    """
    
    def __init__(self, node_data: Any = None, **kwargs):
        """
        Initialize the node.
        
        Args:
            node_data: Dictionary or Node object containing node configuration data
            **kwargs: Additional keyword arguments
        """
        self.node_data = node_data
        
        # Fallback: Check kwargs for 'node' if node_data is None (Engine uses named args)
        if self.node_data is None:
            self.node_data = kwargs.get('node')
        
        # Safely handle config extraction from dict or object
        if isinstance(node_data, dict):
            self.config = node_data.get('config', {})
        elif hasattr(node_data, 'config'):
            self.config = node_data.config
        else:
            self.config = {}
            
        # Ensure config is a dict (handle potential None)
        if self.config is None:
            self.config = {}
            
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node logic.
        
        This is the CORE method that every node must implement.
        
        Args:
            input_data: Data from previous nodes or trigger
                       - For trigger nodes: initial webhook/event data
                       - For regular nodes: output from parent nodes
                       - Example: {"customer": {"name": "John", "email": "john@example.com"}}
                       
            params: Node configuration from workflow JSON 'params' field
                   - Static configuration set by user in workflow builder
                   - Example: {"url": "https://api.example.com", "method": "POST"}
                   
            context: Execution environment and shared resources
                    - Contains credentials, environment variables, execution metadata
                    - Example: {"credentials": {...}, "execution_id": "uuid", "workflow_id": "uuid"}
            
        Returns:
            Dict containing output data for next nodes
            - Must be JSON serializable
            - Will be merged with input_data for next nodes
            
        Raises:
            NodeExecutionError: When node execution fails
        """
        pass
    
    @classmethod
    def get_node_type(cls) -> str:
        """
        Return the node type identifier.
        
        This MUST match the 'type' field in workflow JSON.
        Override this method to customize the node type string.
        
        Returns:
            String identifier for this node type
        """
        return getattr(cls, 'NODE_TYPE', cls.__name__.lower().replace('node', ''))
    
    @classmethod
    def get_display_name(cls) -> str:
        """
        Return human-readable display name for UI.
        
        Returns:
            Display name for workflow builder UI
        """
        return getattr(cls, 'DISPLAY_NAME', cls.__name__.replace('Node', ''))
    
    @classmethod
    def get_description(cls) -> str:
        """
        Return description for UI.
        
        Returns:
            Description text for workflow builder UI
        """
        return getattr(cls, 'DESCRIPTION', '')
    
    @classmethod
    def get_category(cls) -> str:
        """
        Return node category for UI organization.
        
        Returns:
            Category name (e.g., 'triggers', 'actions', 'utilities')
        """
        return getattr(cls, 'CATEGORY', 'actions')
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """
        Return parameter schema for UI generation.
        
        Override this to define node parameters for the workflow builder UI.
        Uses JSON Schema format for form generation.
        
        Returns:
            JSON Schema object defining node parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate node parameters before execution.
        
        Override for custom validation logic.
        Called by execution engine before run().
        
        Args:
            params: Node parameters from workflow JSON
            
        Returns:
            True if parameters are valid, False otherwise
        """
        return True
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Return expected input data schema.
        
        Override to define what input data this node expects.
        Used for workflow validation and UI hints.
        
        Returns:
            JSON Schema object defining expected input
        """
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": True
        }
    
    def get_output_schema(self) -> Dict[str, Any]:
        """
        Return output data schema.
        
        Override to define what output data this node produces.
        Used for workflow validation and UI hints.
        
        Returns:
            JSON Schema object defining output structure
        """
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": True
        }
    
    def supports_retry(self) -> bool:
        """
        Return whether this node supports retry on failure.
        
        Returns:
            True if node can be safely retried, False otherwise
        """
        return getattr(self, 'SUPPORTS_RETRY', True)
    
    
    def get_timeout(self) -> Optional[int]:
        """
        Return default timeout in seconds for this node.
        
        Returns:
            Timeout in seconds, or None for no timeout
        """
        return getattr(self, 'DEFAULT_TIMEOUT', 30)
    
    def _resolve_template(self, template: str, input_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Resolve template variables using the robust ExpressionEvaluator.
        
        Args:
            template: Template string (e.g., "Hello {{ $node('AI').json.text }}")
            input_data: Data from previous nodes
            context: Execution context
            
        Returns:
            Resolved value (string, dict, list, etc.)
        """
        # LAZY IMPORT to avoid circular dependency
        from ..expression_evaluator import evaluate_expression
        
        # CORE FIX: ALWAYS EVALUATE, NEVER FALLBACK
        # We implicitly trust the Evaluator to handle missing nodes/data gracefully (returning None or empty).
        # We do NOT return the original template if evaluation fails, unless Evaluator itself does.
        # We do NOT pre-validate node existence (Evaluator does fuzzy matching).
        
        return evaluate_expression(
            template,
            items=[{'json': input_data}], # n8n style: expressions run against items
            node_outputs=context.get('node_outputs', {}),
            execution_context=context 
        )
    
    def _resolve_templates(self, obj: Any, input_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Recursively resolve templates in nested objects.
        
        Args:
            obj: Object that may contain template strings
            input_data: Data from previous nodes
            context: Execution context
            
        Returns:
            Object with all template strings resolved
        """
        if isinstance(obj, str):
            return self._resolve_template(obj, input_data, context)
        elif isinstance(obj, dict):
            return {k: self._resolve_templates(v, input_data, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_templates(item, input_data, context) for item in obj]
        else:
            return obj
    
    def _get_nested_value(self, path: str, input_data: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Get nested value from input_data or context using dot notation.
        
        Args:
            path: Dot-separated path like "customer.email"
            input_data: Data from previous nodes
            context: Execution context
            
        Returns:
            Value at the specified path, or original path if not found
        """
        parts = path.split('.')
        
        # Try input_data first
        try:
            value = input_data
            for part in parts:
                if isinstance(value, dict):
                    value = value[part]
                elif isinstance(value, list) and part.isdigit():
                    value = value[int(part)]
                else:
                    raise KeyError(f"Cannot access {part} on {type(value)}")
            return value
        except (KeyError, TypeError, IndexError, ValueError):
            pass
        
        
        # Try context
        try:
            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value[part]
                elif isinstance(value, list) and part.isdigit():
                    value = value[int(part)]
                else:
                    raise KeyError
            return value
        except (KeyError, TypeError, IndexError, ValueError):
            pass
            
        # If we got here, simple dot usage failed.
        # But BaseNode usage suggests we should primarily rely on _resolve_template which uses evaluate_expression.
        # Keeping this strictly as a minimal fallback for non-template strings that might just be "keys".
        return f"{{{{{path}}}}}"


class TriggerNode(BaseNode):
    """
    Base class for trigger nodes.
    
    Trigger nodes start workflow execution and have special handling.
    """
    
    CATEGORY = "triggers"
    
    def is_trigger(self) -> bool:
        """Return True since this is a trigger node."""
        return True


class ActionNode(BaseNode):
    """
    Base class for action nodes.
    
    Action nodes perform operations and transform data.
    """
    
    CATEGORY = "actions"
    
    def is_trigger(self) -> bool:
        """Return False since this is an action node."""
        return False


class UtilityNode(BaseNode):
    """
    Base class for utility nodes.
    
    Utility nodes provide helper functionality like delays, conditions, etc.
    """
    
    CATEGORY = "utilities"
    
    def is_trigger(self) -> bool:
        """Return False since this is a utility node."""
        return False


class LogicNode(BaseNode):
    """
    Base class for logic nodes.
    
    Logic nodes control workflow execution flow.
    """
    
    CATEGORY = "logic"
    
    def is_trigger(self) -> bool:
        """Return False since this is a logic node."""
        return False