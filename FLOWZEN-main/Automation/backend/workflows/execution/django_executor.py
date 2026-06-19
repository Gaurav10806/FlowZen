"""
Django Integration for Workflow Execution Engine

This module provides Django-specific integration for the core execution engine.
It handles database operations, model updates, and Django-specific concerns.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from ..models import Workflow, WorkflowExecution, NodeExecution, ExecutionLog
from ..websocket_publisher import publish_execution_event
from .core_engine import (
    WorkflowExecutionEngine, ExecutionContext, WorkflowExecutionResult,
    NodeExecutionResult, ExecutionHooks, execute_workflow as core_execute_workflow
)

from ..utils.json_utils import sanitize_payload


logger = logging.getLogger(__name__)


class DjangoExecutionHooks(ExecutionHooks):
    """
    Django-specific execution hooks for comprehensive logging and observability.
    
    These hooks integrate with Django models to provide:
    - Detailed execution logging via ExecutionLog
    - Node execution tracking via NodeExecution
    - WebSocket event publishing for real-time updates
    - Celery-safe database operations
    """
    
    def __init__(self, execution: WorkflowExecution):
        """Initialize Django hooks with execution context."""
        super().__init__()
        self.execution = execution
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Set up hook callbacks
        self.on_execution_start = self._on_execution_start
        self.on_execution_complete = self._on_execution_complete
        self.on_execution_error = self._on_execution_error
        self.on_node_start = self._on_node_start
        self.on_node_complete = self._on_node_complete
        self.on_node_error = self._on_node_error
    
    def _sanitize_json_log(self, data: Any) -> Any:
        """Helper to sanitize data for JSON logging."""
        if isinstance(data, dict):
            return {k: self._sanitize_json_log(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_json_log(v) for v in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif hasattr(data, 'isoformat'):  # datetime
            return data.isoformat()
        else:
            return str(data)  # Fallback to string representation

    def _on_execution_start(self, context: ExecutionContext, workflow_json: Dict[str, Any]) -> None:
        """Handle execution start."""
        try:
            # Create execution start log
            self._create_execution_log(
                level='info',
                message=f"Workflow execution started: {self.execution.workflow.name}",
                metadata={
                    'workflow_id': context.workflow_id,
                    'execution_id': context.execution_id,
                    'user_id': context.user_id,
                    'environment': context.environment,
                    'node_count': len(workflow_json.get('nodes', {})),
                    'trigger_type': workflow_json.get('trigger', {}).get('type')
                }
            )
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'execution_started',
                self._sanitize_json_log({
                    'workflow_id': str(self.execution.workflow.id),
                    'workflow_name': self.execution.workflow.name,
                    'started_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle execution start: {e}")
    
    def _on_execution_complete(self, context: ExecutionContext, result: WorkflowExecutionResult) -> None:
        """Handle execution completion."""
        try:
            # Create execution completion log
            self._create_execution_log(
                level='info',
                message=f"Workflow execution completed successfully",
                metadata={
                    'execution_time_ms': result.total_execution_time_ms,
                    'node_count': len(result.node_results),
                    'success_count': sum(1 for r in result.node_results if r.success),
                    'final_output_keys': list(result.final_output.keys()) if result.final_output else []
                }
            )
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'execution_completed',
                self._sanitize_json_log({
                    'execution_time_ms': result.total_execution_time_ms,
                    'node_count': len(result.node_results),
                    'completed_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle execution completion: {e}")
    
    def _on_execution_error(self, context: ExecutionContext, error: Exception, result: WorkflowExecutionResult) -> None:
        """Handle execution error."""
        try:
            # Create execution error log
            self._create_execution_log(
                level='error',
                message=f"Workflow execution failed: {str(error)}",
                metadata={
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                    'execution_time_ms': result.total_execution_time_ms,
                    'completed_nodes': len([r for r in result.node_results if r.success]),
                    'failed_nodes': len([r for r in result.node_results if not r.success])
                }
            )
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'execution_failed',
                self._sanitize_json_log({
                    'error_message': str(error),
                    'error_type': type(error).__name__,
                    'execution_time_ms': result.total_execution_time_ms,
                    'failed_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle execution error: {e}")
    
    def _on_node_start(self, context: ExecutionContext, node_id: str, node_type: str, input_data: Dict[str, Any]) -> None:
        """Handle node execution start."""
        try:
            # Create node start log
            self._create_execution_log(
                level='info',
                message=f"Starting node: {node_id} ({node_type})",
                metadata={
                    'node_id': node_id,
                    'node_type': node_type,
                    'input_data_keys': list(input_data.keys()) if input_data else [],
                    'input_data_size': len(str(input_data)) if input_data else 0
                }
            )
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'node_started',
                self._sanitize_json_log({
                    'node_id': node_id,
                    'node_type': node_type,
                    'started_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle node start: {e}")
    
    def _on_node_complete(self, context: ExecutionContext, result: NodeExecutionResult) -> None:
        """Handle node execution completion."""
        try:
            # Create node completion log
            self._create_execution_log(
                level='info',
                message=f"Node completed: {result.node_id} ({result.node_type})",
                metadata={
                    'node_id': result.node_id,
                    'node_type': result.node_type,
                    'execution_time_ms': result.execution_time_ms,
                    'output_data_keys': list(result.output_data.keys()) if result.output_data else [],
                    'output_data_size': len(str(result.output_data)) if result.output_data else 0
                }
            )
            
            # Create or update NodeExecution record
            self._create_or_update_node_execution(result, 'completed')
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'node_completed',
                self._sanitize_json_log({
                    'node_id': result.node_id,
                    'node_type': result.node_type,
                    'execution_time_ms': result.execution_time_ms,
                    'completed_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle node completion: {e}")
    
    def _on_node_error(self, context: ExecutionContext, node_id: str, node_type: str, error: Exception) -> None:
        """Handle node execution error."""
        try:
            # Create node error log
            self._create_execution_log(
                level='error',
                message=f"Node failed: {node_id} ({node_type}) - {str(error)}",
                metadata={
                    'node_id': node_id,
                    'node_type': node_type,
                    'error_type': type(error).__name__,
                    'error_message': str(error)
                }
            )
            
            # Create or update NodeExecution record with error
            node_result = NodeExecutionResult(
                node_id=node_id,
                node_type=node_type,
                success=False,
                output_data={},
                error_message=str(error)
            )
            self._create_or_update_node_execution(node_result, 'failed')
            
            # Publish WebSocket event
            publish_execution_event(
                str(self.execution.id),
                'node_failed',
                self._sanitize_json_log({
                    'node_id': node_id,
                    'node_type': node_type,
                    'error_message': str(error),
                    'error_type': type(error).__name__,
                    'failed_at': timezone.now().isoformat()
                })
            )
            
        except Exception as e:
            self.logger.error(f"Failed to handle node error: {e}")
    
    def _create_execution_log(self, level: str, message: str, metadata: Dict[str, Any] = None) -> None:
        """Create an execution log entry safely."""
        try:
            # Get tenant from execution if available
            tenant = getattr(self.execution, 'tenant', None)
            
            ExecutionLog.objects.create(
                execution=self.execution,
                tenant=tenant,
                level=level,
                message=message,
                metadata=self._sanitize_json_log(metadata or {})
            )
        except Exception as e:
            # Don't fail execution due to logging issues
            self.logger.error(f"Failed to create execution log: {e}")
    
    def _create_or_update_node_execution(self, result: NodeExecutionResult, status: str) -> None:
        """Create or update NodeExecution record safely."""
        try:
            # Get tenant from execution if available
            tenant = getattr(self.execution, 'tenant', None)
            
            # Try to find existing NodeExecution by graph_node_id
            node_execution = None
            try:
                node_execution = NodeExecution.objects.get(
                    workflow_execution=self.execution,
                    graph_node_id=result.node_id
                )
            except NodeExecution.DoesNotExist:
                pass
            
            if node_execution:
                # Update existing record
                node_execution.status = status
                node_execution.result = sanitize_payload(result.output_data)
                node_execution.error_message = result.error_message or ''
                node_execution.finished_at = timezone.now()
                node_execution.save()
            else:
                # Create new record
                NodeExecution.objects.create(
                    workflow_execution=self.execution,
                    tenant=tenant,
                    graph_node_id=result.node_id,
                    status=status,
                    input_data={},  # Could be enhanced to store actual input
                    output=sanitize_payload(result.output_data),  # Fixed: Match model field name
                    error_message=result.error_message or '',
                    started_at=timezone.now(),
                    finished_at=timezone.now()
                )
                
        except Exception as e:
            # Don't fail execution due to database issues
            self.logger.error(f"Failed to create/update node execution: {e}")


class DjangoWorkflowExecutor:
    """
    Django-integrated workflow executor.
    
    This class provides Django-specific functionality on top of the core engine:
    - Database model integration
    - Comprehensive execution logging
    - WebSocket event publishing
    - Transaction management
    - Celery-safe operations
    """
    
    def __init__(self):
        """Initialize the Django executor."""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def execute_workflow_execution(self, execution: WorkflowExecution) -> WorkflowExecutionResult:
        """
        Execute a WorkflowExecution using Django models with comprehensive logging.
        
        This is the main entry point for Django-based workflow execution.
        
        Args:
            execution: WorkflowExecution model instance
            
        Returns:
            WorkflowExecutionResult with execution details
        """
        workflow = execution.workflow
        
        try:
            # Update execution status
            execution.status = 'running'
            execution.started_at = timezone.now()
            execution.save(update_fields=['status', 'started_at'])
            
            # Create Django-specific hooks for comprehensive logging
            hooks = DjangoExecutionHooks(execution)
            
            # Create core engine with hooks
            core_engine = WorkflowExecutionEngine(hooks=hooks)
            
            # Create execution context from Django models
            context = self._create_execution_context(execution)
            
            # Get trigger input from execution
            trigger_input = execution.input_payload or {}
            
            # Determine which graph to use (prioritize ephemeral graph for testing)
            execution_graph = workflow.graph
            if trigger_input.get('graph'):
                logger.info(f"Using ephemeral graph for execution {execution.id}")
                execution_graph = trigger_input.get('graph')
            
            # Execute workflow using core engine with hooks
            # Normalize graph structure (List -> Dict, Edges -> Connections)
            execution_graph = self._normalize_graph(execution_graph)
            result = core_engine.run(execution_graph, trigger_input, context)
            
            # Update execution with results
            self._update_execution_with_result(execution, result)
            
            self.logger.info(f"Workflow execution {execution.id} completed with status: {result.success}")
            return result
            
        except Exception as e:
            self.logger.error(f"Django workflow execution failed: {e}")
            
            # Update execution with error
            execution.status = 'failed'
            execution.completed_at = timezone.now()
            execution.error_message = str(e)
            execution.save(update_fields=['status', 'completed_at', 'error_message'])
            
            # Publish failure event
            publish_execution_event(
                str(execution.id),
                'execution_failed',
                {'error_message': str(e)}
            )
            
            raise
    
    def _create_execution_context(self, execution: WorkflowExecution) -> ExecutionContext:
        """
        Create execution context from Django models.
        
        Args:
            execution: WorkflowExecution model instance
            
        Returns:
            ExecutionContext with Django model data
        """
        # Get user information
        user_id = str(execution.created_by.id) if getattr(execution, 'created_by', None) else None
        
        # Fallback to input_payload (set by API) if created_by is missing
        if not user_id and execution.input_payload:
            user_id = execution.input_payload.get('_user_id') or execution.input_payload.get('user_id')
        
        # Get tenant information (if available)
        tenant_id = None
        if hasattr(execution, 'tenant') and execution.tenant:
            tenant_id = str(execution.tenant.id)
        
        # Create context
        context = ExecutionContext(
            workflow_id=str(execution.workflow.id),
            execution_id=str(execution.id),
            user_id=user_id,
            tenant_id=tenant_id,
            variables=self._get_execution_variables(execution),
            secrets=self._get_execution_secrets(execution),
            environment=self._get_environment_name(),
            debug_mode=self._is_debug_mode(),
            triggered_by=execution.triggered_by
        )
        
        return context
    
    def _get_execution_variables(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """
        Get runtime variables for execution.
        
        Args:
            execution: WorkflowExecution model instance
            
        Returns:
            Dictionary of runtime variables
        """
        variables = {}
        
        # Add execution metadata
        variables['execution'] = {
            'id': str(execution.id),
            'created_at': execution.created_at.isoformat() if execution.created_at else None,
            'status': execution.status
        }
        
        # Add workflow metadata
        variables['workflow'] = {
            'id': str(execution.workflow.id),
            'name': execution.workflow.name,
            'version': getattr(execution.workflow, 'version', '1.0.0')
        }
        
        # Add user metadata
        if getattr(execution, 'created_by', None):
            variables['user'] = {
                'id': str(execution.created_by.id),
                'username': execution.created_by.username,
                'email': execution.created_by.email
            }
            
        # Merge global context (e.g. injected credentials from webhook)
        if execution.root_context:
            variables.update(execution.root_context)
        
        return variables
    
    def _get_execution_secrets(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """
        Get secrets and credentials for execution.
        
        Args:
            execution: WorkflowExecution model instance
            
        Returns:
            Dictionary of available secrets (placeholder for now)
        """
        # TODO: Integrate with credential system
        # For now, return empty dict
        return {}
    
    def _get_environment_name(self) -> str:
        """Get current environment name."""
        from django.conf import settings
        return getattr(settings, 'ENVIRONMENT', 'development')
    
    def _is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        from django.conf import settings
        return settings.DEBUG
    
    def _update_execution_with_result(self, execution: WorkflowExecution, 
                                    result: WorkflowExecutionResult) -> None:
        """
        Update WorkflowExecution model with execution result.
        
        Args:
            execution: WorkflowExecution model instance
            result: WorkflowExecutionResult from core engine
        """
        execution.status = 'completed' if result.success else 'failed'
        execution.completed_at = timezone.now()
        execution.result = sanitize_payload(result.final_output)
        execution.error_message = result.error_message
        
        # Store execution metadata
        execution_metadata = {
            'total_execution_time_ms': result.total_execution_time_ms,
            'node_count': len(result.node_results),
            'success_count': sum(1 for r in result.node_results if r.success),
            'failure_count': sum(1 for r in result.node_results if not r.success)
        }
        
        # Update or create metadata field if it exists
        if hasattr(execution, 'metadata'):
            execution.metadata = execution_metadata
        
        # Store node results for debugging
        if hasattr(execution, 'node_results'):
            execution.node_results = sanitize_payload([
                r.to_dict() for r in result.node_results
            ])
        
        # Ensure validation constraints are met
        if execution.error_message is None:
            execution.error_message = ""
            
        execution.save()
    
    def _create_node_execution_records(self, execution: WorkflowExecution, 
                                     node_results: list[NodeExecutionResult]) -> None:
        """
        Create NodeExecution records for each executed node.
        
        NOTE: This method is now primarily for legacy compatibility.
        The DjangoExecutionHooks handle node execution tracking more comprehensively.
        
        Args:
            execution: WorkflowExecution model instance
            node_results: List of NodeExecutionResult from core engine
        """
        # This is now handled by DjangoExecutionHooks._create_or_update_node_execution
        # but we keep this method for any additional processing needed
        self.logger.debug(f"Node execution records handled by hooks for {len(node_results)} nodes")
    
    def create_execution_log(self, execution: WorkflowExecution, level: str, 
                           message: str, data: Dict[str, Any] = None) -> None:
        """
        Create an execution log entry.
        
        NOTE: This method is now primarily for legacy compatibility.
        The DjangoExecutionHooks handle logging more comprehensively.
        
        Args:
            execution: WorkflowExecution model instance
            level: Log level (info, warning, error)
            message: Log message
            data: Additional log data
        """
        try:
            # Get tenant from execution if available
            tenant = getattr(execution, 'tenant', None)
            
            try:
                ExecutionLog.objects.create(
                    execution=execution,
                    tenant=tenant,
                    level=level,
                    message=message,
                    metadata=data or {}
                )
            except Exception as e:
                # MANDATORY SAFETY PATCH: Warn but do not crash
                self.logger.warning(f"Failed to persist ExecutionLog: {e}")
        except Exception as e:
            # Don't fail execution due to logging issues
            self.logger.error(f"Failed to create execution log: {e}")


    def _normalize_graph(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize graph from frontend format (ReactFlow) to core engine format.
        """
        if not graph:
            self.logger.warning("Normalization received empty graph")
            return {'meta': {}, 'trigger': {}, 'nodes': {}, 'connections': {}}
            
        # Create copy to avoid mutating original
        norm_graph = graph.copy()
        self.logger.info(f"Normalizing graph with keys: {list(norm_graph.keys())}")
        
        # 1. Normalize Nodes (List -> Dict) and normalize node types
        nodes = norm_graph.get('nodes', {})
        if isinstance(nodes, list):
            self.logger.info(f"Normalizing {len(nodes)} nodes from list to dict")
            nodes_dict = {}
            for n in nodes:
                if isinstance(n, dict) and 'id' in n:
                    # NORMALIZE NODE TYPE: Hyphen to Underscore or vice versa
                    if 'type' in n:
                        n['type'] = n['type'].replace('_', '-')
                    nodes_dict[n['id']] = n
            norm_graph['nodes'] = nodes_dict
        elif isinstance(nodes, dict):
            # Also normalize types if already a dict
            for nid, n in nodes.items():
                if isinstance(n, dict) and 'type' in n:
                    n['type'] = n['type'].replace('_', '-')
        
        self.logger.info(f"Nodes count after normalization: {len(norm_graph.get('nodes', {}))}")
            
        # 2. Normalize Connections (Edges List -> Connections Dict)
        # 2. Normalize Connections (Edges List -> Connections Dict)
        # Always re-normalize from edges if they exist to avoid stale connections
        if 'edges' in norm_graph:
            self.logger.info("Normalizing edges to connections (forcing update)")
            self.logger.info("Normalizing edges to connections")
            connections = {}
            edges = norm_graph.get('edges', [])
            if isinstance(edges, list):
                for edge in edges:
                    if not isinstance(edge, dict): 
                        continue
                    source = edge.get('source') or edge.get('from')
                    target = edge.get('target') or edge.get('to')
                    
                    if source and target:
                        if source not in connections:
                            connections[source] = []
                        if target not in connections[source]:
                            connections[source].append(target)
            norm_graph['connections'] = connections
            
        # 3. Ensure Connections exists
        if 'connections' not in norm_graph:
            norm_graph['connections'] = {}
            
        # 4. Extract Trigger if missing
        if not norm_graph.get('trigger'):
            self.logger.info("Trigger missing, attempting extraction from nodes")
            nodes_map = norm_graph.get('nodes', {})
            for nid, node in nodes_map.items():
                node_type = node.get('type', '')
                if (node_type == 'trigger' or 
                    node_type.endswith('-trigger') or 
                    node_type.endswith('_trigger') or
                    node_type == 'webhook' or 
                    node_type == 'manual'):
                    self.logger.info(f"Detected trigger node: {nid} ({node_type})")
                    norm_graph['trigger'] = node
                    break
        
        # 5. Ensure Meta
        if 'meta' not in norm_graph:
            norm_graph['meta'] = {'version': '1.0.0', 'generated': True}
            
        self.logger.info(f"Normalization complete. Final keys: {list(norm_graph.keys())}")
        if 'trigger' in norm_graph:
            self.logger.info(f"Final trigger type: {norm_graph['trigger'].get('type')}")
        else:
            self.logger.error("DANGER: Normalization FINISHED but 'trigger' is STILL MISSING")
            self.logger.error(f"Nodes available: {list(norm_graph.get('nodes', {}).keys())}")
        return norm_graph


# Convenience functions for Django integration
def execute_django_workflow(execution_id: str) -> WorkflowExecutionResult:
    """
    Execute a workflow by WorkflowExecution ID.
    
    This is a convenience function for Celery tasks and other Django code.
    
    Args:
        execution_id: UUID string of WorkflowExecution
        
    Returns:
        WorkflowExecutionResult with execution details
        
    Raises:
        WorkflowExecution.DoesNotExist: If execution not found
    """
    try:
        execution = WorkflowExecution.objects.select_related('workflow', 'created_by').get(
            id=execution_id
        )
    except WorkflowExecution.DoesNotExist:
        logger.error(f"WorkflowExecution {execution_id} not found")
        raise
    
    executor = DjangoWorkflowExecutor()
    return executor.execute_workflow_execution(execution)


def execute_workflow_by_id(workflow_id: str, trigger_input: Dict[str, Any] = None,
                          user_id: str = None) -> WorkflowExecutionResult:
    """
    Execute a workflow by Workflow ID, creating a new execution.
    
    Args:
        workflow_id: UUID string of Workflow
        trigger_input: Input data for trigger
        user_id: UUID string of User (optional)
        
    Returns:
        WorkflowExecutionResult with execution details
    """
    from django.contrib.auth.models import User
    
    try:
        workflow = Workflow.objects.get(id=workflow_id)
    except Workflow.DoesNotExist:
        logger.error(f"Workflow {workflow_id} not found")
        raise
    
    # Get user if provided
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found, executing without user")
    
    # Create execution
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        status='pending',
        input_payload=trigger_input or {},
        # created_by=user # Field missing
    )
    
    # Execute workflow
    executor = DjangoWorkflowExecutor()
    return executor.execute_workflow_execution(execution)


def test_workflow_execution(workflow_json: Dict[str, Any], 
                          trigger_input: Dict[str, Any] = None) -> WorkflowExecutionResult:
    """
    Test workflow execution without creating database records.
    
    This function uses the core engine directly for testing purposes.
    
    Args:
        workflow_json: Complete workflow definition
        trigger_input: Input data for trigger
        
    Returns:
        WorkflowExecutionResult with execution details
    """
    return core_execute_workflow(
        workflow_json=workflow_json,
        trigger_input=trigger_input or {}
    )