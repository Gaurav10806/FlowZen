"""
Tool Registry - Dynamic Tool Abstraction for AI Agents

This module provides a tool abstraction layer that exposes workflow nodes
as AI tools with safety controls, permission enforcement, and usage logging.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from ..nodes.registry import NodeRegistry
from ..security_validators import PayloadSecurityValidator
from ..models import WorkflowExecution, NodeExecution


logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


class ToolPermissionLevel(Enum):
    """Tool permission levels for safety control."""
    READ_ONLY = "read_only"      # Can only read data, no external calls
    SAFE_ACTIONS = "safe_actions"  # Can perform safe actions (email, notifications)
    EXTERNAL_API = "external_api"  # Can make external API calls
    SYSTEM_ACCESS = "system_access"  # Can access system resources
    ADMIN_ONLY = "admin_only"    # Requires admin privileges


@dataclass
class ToolDefinition:
    """Defines a tool that AI agents can use."""
    name: str
    display_name: str
    description: str
    node_type: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permission_level: ToolPermissionLevel
    safety_constraints: Dict[str, Any]
    usage_examples: List[Dict[str, Any]]
    cost_estimate: int  # Estimated cost in tokens/credits
    execution_time_estimate: int  # Estimated time in milliseconds


@dataclass
class ToolExecution:
    """Records a tool execution for logging and auditing."""
    execution_id: str
    tool_name: str
    agent_id: str
    user_id: str
    tenant_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    success: bool
    error_message: Optional[str]
    execution_time_ms: int
    tokens_used: int
    timestamp: str


class ToolRegistry:
    """
    Registry for AI tools with safety controls and permission enforcement.
    
    This class manages the dynamic registration of workflow nodes as AI tools,
    enforces safety constraints, and provides comprehensive logging.
    """
    
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.registered_tools: Dict[str, ToolDefinition] = {}
        self.tool_executions: List[ToolExecution] = []
        self.safety_validator = PayloadSecurityValidator()
        
        # Initialize built-in tools
        self._register_built_in_tools()
    
    def register_tool(self, tool_definition: ToolDefinition) -> None:
        """
        Register a new tool in the registry.
        
        Args:
            tool_definition: Complete tool definition with safety constraints
        """
        # Validate tool definition
        self._validate_tool_definition(tool_definition)
        
        # Check if node type exists
        if not self.node_registry.is_registered(tool_definition.node_type):
            raise ValueError(f"Node type '{tool_definition.node_type}' is not registered")
        
        # Register the tool
        self.registered_tools[tool_definition.name] = tool_definition
        
        logger.info(f"Registered tool: {tool_definition.name} -> {tool_definition.node_type}")
    
    def get_available_tools(self, context: Dict[str, Any], safety_level: str = "moderate") -> List[Dict[str, Any]]:
        """
        Get list of tools available to an agent based on context and safety level.
        
        Args:
            context: Execution context with user and tenant information
            safety_level: Safety level for tool filtering
            
        Returns:
            List of available tool definitions
        """
        available_tools = []
        user_permissions = self._get_user_permissions(context)
        
        for tool_name, tool_def in self.registered_tools.items():
            # Check permission level
            if self._check_tool_permission(tool_def, user_permissions, safety_level):
                # Convert to agent-friendly format
                tool_info = {
                    'name': tool_def.name,
                    'display_name': tool_def.display_name,
                    'description': tool_def.description,
                    'input_schema': tool_def.input_schema,
                    'output_schema': tool_def.output_schema,
                    'usage_examples': tool_def.usage_examples,
                    'cost_estimate': tool_def.cost_estimate,
                    'execution_time_estimate': tool_def.execution_time_estimate
                }
                available_tools.append(tool_info)
        
        return available_tools
    
    def get_tool_info(self, tool_name: str, context: Dict[str, Any], safety_level: str = "moderate") -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool.
        
        Args:
            tool_name: Name of the tool
            context: Execution context
            safety_level: Safety level for permission check
            
        Returns:
            Tool information if accessible, None otherwise
        """
        if tool_name not in self.registered_tools:
            return None
        
        tool_def = self.registered_tools[tool_name]
        user_permissions = self._get_user_permissions(context)
        
        if not self._check_tool_permission(tool_def, user_permissions, safety_level):
            return None
        
        return {
            'name': tool_def.name,
            'display_name': tool_def.display_name,
            'description': tool_def.description,
            'input_schema': tool_def.input_schema,
            'output_schema': tool_def.output_schema,
            'usage_examples': tool_def.usage_examples,
            'cost_estimate': tool_def.cost_estimate,
            'execution_time_estimate': tool_def.execution_time_estimate
        }
    
    def execute_tool(self, tool_name: str, input_data: Dict[str, Any], 
                    context: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """
        Execute a tool with safety controls and logging.
        
        Args:
            tool_name: Name of the tool to execute
            input_data: Input data for the tool
            context: Execution context
            agent_id: ID of the agent executing the tool
            
        Returns:
            Tool execution result
            
        Raises:
            ToolExecutionError: If tool execution fails or is not permitted
        """
        start_time = datetime.utcnow()
        execution_id = f"tool_{start_time.strftime('%Y%m%d_%H%M%S')}_{tool_name}"
        
        # Validate tool exists
        if tool_name not in self.registered_tools:
            raise ToolExecutionError(f"Tool '{tool_name}' not found")
        
        tool_def = self.registered_tools[tool_name]
        
        # Check permissions
        user_permissions = self._get_user_permissions(context)
        if not self._check_tool_permission(tool_def, user_permissions, context.get('safety_level', 'moderate')):
            raise ToolExecutionError(f"Permission denied for tool '{tool_name}'")
        
        try:
            # Validate and sanitize input
            validated_input = self._validate_tool_input(tool_def, input_data)
            
            # Apply safety constraints
            self._apply_safety_constraints(tool_def, validated_input, context)
            
            # Execute the underlying node
            result = self._execute_node(tool_def.node_type, validated_input, context)
            
            # Validate and sanitize output
            validated_output = self._validate_tool_output(tool_def, result)
            
            # Calculate execution metrics
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Log successful execution
            execution_record = ToolExecution(
                execution_id=execution_id,
                tool_name=tool_name,
                agent_id=agent_id,
                user_id=context.get('user_id', ''),
                tenant_id=context.get('tenant_id', ''),
                input_data=validated_input,
                output_data=validated_output,
                success=True,
                error_message=None,
                execution_time_ms=execution_time_ms,
                tokens_used=result.get('tokens_used', 0),
                timestamp=start_time.isoformat()
            )
            
            self._log_tool_execution(execution_record)
            
            return {
                'success': True,
                'result': validated_output,
                'execution_id': execution_id,
                'execution_time_ms': execution_time_ms,
                'tokens_used': result.get('tokens_used', 0)
            }
            
        except Exception as e:
            # Log failed execution
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            execution_record = ToolExecution(
                execution_id=execution_id,
                tool_name=tool_name,
                agent_id=agent_id,
                user_id=context.get('user_id', ''),
                tenant_id=context.get('tenant_id', ''),
                input_data=input_data,
                output_data={},
                success=False,
                error_message=str(e),
                execution_time_ms=execution_time_ms,
                tokens_used=0,
                timestamp=start_time.isoformat()
            )
            
            self._log_tool_execution(execution_record)
            
            raise ToolExecutionError(f"Tool execution failed: {str(e)}")
    
    def get_tool_usage_stats(self, context: Dict[str, Any], 
                           time_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Get tool usage statistics for monitoring and optimization.
        
        Args:
            context: Execution context for filtering
            time_range: Optional time range filter
            
        Returns:
            Usage statistics
        """
        tenant_id = context.get('tenant_id')
        user_id = context.get('user_id')
        
        # Filter executions by context
        filtered_executions = [
            exec_record for exec_record in self.tool_executions
            if (not tenant_id or exec_record.tenant_id == tenant_id) and
               (not user_id or exec_record.user_id == user_id)
        ]
        
        # Calculate statistics
        total_executions = len(filtered_executions)
        successful_executions = len([e for e in filtered_executions if e.success])
        failed_executions = total_executions - successful_executions
        
        tool_usage = {}
        for execution in filtered_executions:
            tool_name = execution.tool_name
            if tool_name not in tool_usage:
                tool_usage[tool_name] = {
                    'count': 0,
                    'success_count': 0,
                    'total_time_ms': 0,
                    'total_tokens': 0
                }
            
            tool_usage[tool_name]['count'] += 1
            if execution.success:
                tool_usage[tool_name]['success_count'] += 1
            tool_usage[tool_name]['total_time_ms'] += execution.execution_time_ms
            tool_usage[tool_name]['total_tokens'] += execution.tokens_used
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'success_rate': successful_executions / total_executions if total_executions > 0 else 0,
            'tool_usage': tool_usage,
            'most_used_tools': sorted(tool_usage.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
        }
    
    def _register_built_in_tools(self) -> None:
        """Register built-in tools from existing nodes."""
        
        # HTTP Request Tool
        self.register_tool(ToolDefinition(
            name="http_request",
            display_name="HTTP Request",
            description="Make HTTP requests to external APIs",
            node_type="http_request",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                    "headers": {"type": "object"},
                    "body": {"type": "object"}
                },
                "required": ["url", "method"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer"},
                    "response_data": {"type": "object"},
                    "headers": {"type": "object"}
                }
            },
            permission_level=ToolPermissionLevel.EXTERNAL_API,
            safety_constraints={
                "allowed_domains": ["api.example.com", "webhook.site"],
                "max_response_size": 1024 * 1024,  # 1MB
                "timeout_seconds": 30
            },
            usage_examples=[
                {
                    "description": "Get user data from API",
                    "input": {
                        "url": "https://api.example.com/users/123",
                        "method": "GET",
                        "headers": {"Authorization": "Bearer token"}
                    }
                }
            ],
            cost_estimate=10,
            execution_time_estimate=2000
        ))
        
        # Email Tool
        self.register_tool(ToolDefinition(
            name="send_email",
            display_name="Send Email",
            description="Send email notifications",
            node_type="email",
            input_schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "format": "email"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "template": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "status": {"type": "string"}
                }
            },
            permission_level=ToolPermissionLevel.SAFE_ACTIONS,
            safety_constraints={
                "max_recipients": 10,
                "max_body_length": 10000,
                "allowed_domains": ["company.com"]
            },
            usage_examples=[
                {
                    "description": "Send notification email",
                    "input": {
                        "to": "user@company.com",
                        "subject": "Task Completed",
                        "body": "Your task has been completed successfully."
                    }
                }
            ],
            cost_estimate=5,
            execution_time_estimate=1000
        ))
        
        # Data Processing Tool
        self.register_tool(ToolDefinition(
            name="process_data",
            display_name="Process Data",
            description="Transform and process data",
            node_type="code",
            input_schema={
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                    "operation": {"type": "string", "enum": ["filter", "transform", "aggregate"]},
                    "parameters": {"type": "object"}
                },
                "required": ["data", "operation"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "processed_data": {"type": "object"},
                    "operation_applied": {"type": "string"}
                }
            },
            permission_level=ToolPermissionLevel.READ_ONLY,
            safety_constraints={
                "max_data_size": 100000,  # 100KB
                "allowed_operations": ["filter", "transform", "aggregate"]
            },
            usage_examples=[
                {
                    "description": "Filter data by criteria",
                    "input": {
                        "data": {"items": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]},
                        "operation": "filter",
                        "parameters": {"criteria": "value > 1"}
                    }
                }
            ],
            cost_estimate=2,
            execution_time_estimate=500
        ))
    
    def _validate_tool_definition(self, tool_def: ToolDefinition) -> None:
        """Validate tool definition for completeness and safety."""
        if not tool_def.name or not tool_def.name.isidentifier():
            raise ValueError("Tool name must be a valid identifier")
        
        if not tool_def.description or len(tool_def.description) < 10:
            raise ValueError("Tool description must be at least 10 characters")
        
        if not tool_def.input_schema or not isinstance(tool_def.input_schema, dict):
            raise ValueError("Tool must have valid input schema")
        
        if not tool_def.output_schema or not isinstance(tool_def.output_schema, dict):
            raise ValueError("Tool must have valid output schema")
    
    def _get_user_permissions(self, context: Dict[str, Any]) -> List[ToolPermissionLevel]:
        """Get user permissions based on context."""
        # In a real implementation, this would check user roles and permissions
        user_role = context.get('user_role', 'user')
        
        if user_role == 'admin':
            return list(ToolPermissionLevel)
        elif user_role == 'power_user':
            return [ToolPermissionLevel.READ_ONLY, ToolPermissionLevel.SAFE_ACTIONS, ToolPermissionLevel.EXTERNAL_API]
        else:
            return [ToolPermissionLevel.READ_ONLY, ToolPermissionLevel.SAFE_ACTIONS]
    
    def _check_tool_permission(self, tool_def: ToolDefinition, user_permissions: List[ToolPermissionLevel], 
                              safety_level: str) -> bool:
        """Check if user has permission to use the tool."""
        # Check basic permission level
        if tool_def.permission_level not in user_permissions:
            return False
        
        # Apply safety level restrictions
        if safety_level == "strict":
            return tool_def.permission_level in [ToolPermissionLevel.READ_ONLY, ToolPermissionLevel.SAFE_ACTIONS]
        elif safety_level == "moderate":
            return tool_def.permission_level != ToolPermissionLevel.ADMIN_ONLY
        else:  # permissive
            return True
    
    def _validate_tool_input(self, tool_def: ToolDefinition, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize tool input data."""
        # Validate against schema (simplified)
        validated_input = self.safety_validator.validate_json_payload(input_data)
        
        # Apply tool-specific constraints
        constraints = tool_def.safety_constraints
        
        # Check data size limits
        if 'max_data_size' in constraints:
            data_size = len(json.dumps(validated_input))
            if data_size > constraints['max_data_size']:
                raise ToolExecutionError(f"Input data too large: {data_size} > {constraints['max_data_size']}")
        
        return validated_input
    
    def _validate_tool_output(self, tool_def: ToolDefinition, output_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize tool output data."""
        # Validate against output schema (simplified)
        validated_output = self.safety_validator.validate_json_payload(output_data)
        
        return validated_output
    
    def _apply_safety_constraints(self, tool_def: ToolDefinition, input_data: Dict[str, Any], 
                                 context: Dict[str, Any]) -> None:
        """Apply safety constraints before tool execution."""
        constraints = tool_def.safety_constraints
        
        # Check domain restrictions for HTTP requests
        if tool_def.node_type == "http_request" and 'allowed_domains' in constraints:
            url = input_data.get('url', '')
            allowed_domains = constraints['allowed_domains']
            
            if not any(domain in url for domain in allowed_domains):
                raise ToolExecutionError(f"Domain not allowed. Allowed domains: {allowed_domains}")
        
        # Check email restrictions
        if tool_def.node_type == "email" and 'allowed_domains' in constraints:
            to_email = input_data.get('to', '')
            allowed_domains = constraints['allowed_domains']
            
            if not any(to_email.endswith(f"@{domain}") for domain in allowed_domains):
                raise ToolExecutionError(f"Email domain not allowed. Allowed domains: {allowed_domains}")
    
    def _execute_node(self, node_type: str, input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the underlying workflow node."""
        # Get node class from registry
        node_class = self.node_registry.get_node_class(node_type)
        if not node_class:
            raise ToolExecutionError(f"Node type '{node_type}' not found")
        
        # Create node instance and execute
        node_instance = node_class()
        
        # Extract parameters from input_data (simplified)
        params = input_data.get('params', {})
        node_input = {k: v for k, v in input_data.items() if k != 'params'}
        
        try:
            result = node_instance.run(node_input, params, context)
            return result
        except Exception as e:
            raise ToolExecutionError(f"Node execution failed: {str(e)}")
    
    def _log_tool_execution(self, execution_record: ToolExecution) -> None:
        """Log tool execution for auditing and monitoring."""
        self.tool_executions.append(execution_record)
        
        # Log to standard logging
        logger.info(f"Tool executed: {execution_record.tool_name} by agent {execution_record.agent_id} "
                   f"(success: {execution_record.success}, time: {execution_record.execution_time_ms}ms)")
        
        # In a real implementation, this would also save to database
        # ToolExecutionLog.objects.create(**asdict(execution_record))