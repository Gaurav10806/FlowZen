"""
Node-based Execution Engine

This module provides the execution engine that uses the new node system.
It replaces the old action-based system with the pluggable node system.
"""

import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from ..models import Workflow, WorkflowExecution, NodeExecution, ExecutionLog
from ..nodes import node_registry, BaseNode, NodeExecutionError
from ..websocket_publisher import publish_execution_event


logger = logging.getLogger(__name__)


class NodeBasedExecutor:
    """
    Execution engine that uses the new pluggable node system.
    
    This executor:
    1. Reads workflow JSON contract directly
    2. Uses node registry to find and instantiate nodes
    3. Executes nodes according to the DAG structure
    4. Handles errors and retries
    5. Publishes real-time updates
    """
    
    def __init__(self, workflow: Workflow, execution: WorkflowExecution):
        self.workflow = workflow
        self.execution = execution
        self.workflow_definition = workflow.definition  # Direct JSON contract
        
        # Extract workflow components
        self.trigger = self.workflow_definition.get('trigger', {})
        self.nodes = self.workflow_definition.get('nodes', {})
        self.connections = self.workflow_definition.get('connections', {})
        
        # Execution state
        self.node_outputs: Dict[str, Dict[str, Any]] = {}
        self.node_executions: Dict[str, NodeExecution] = {}
        self.ordered_node_results: List[Dict[str, Any]] = []
        self.execution_context = self._build_execution_context()
        
        logger.info(f"Initialized executor for workflow {workflow.id} with {len(self.nodes)} nodes")
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the complete workflow.
        
        Returns:
            Final execution result
        """
        try:
            self.execution.status = 'running'
            self.execution.started_at = timezone.now()
            self.execution.save(update_fields=['status', 'started_at'])
            
            # Publish start event
            publish_execution_event(
                str(self.execution.id),
                'execution_started',
                {'workflow_id': str(self.workflow.id)}
            )
            
            # Execute trigger first
            trigger_output = self._execute_trigger()
            
            # Execute workflow nodes in DAG order
            final_output = self._execute_workflow_dag(trigger_output)
            
            # Mark execution as completed
            self.execution.status = 'completed'
            self.execution.completed_at = timezone.now()
            self.execution.output_data = final_output
            self.execution.node_results = self.ordered_node_results
            self.execution.save(update_fields=['status', 'completed_at', 'output_data', 'node_results'])
            
            # Publish completion event
            publish_execution_event(
                str(self.execution.id),
                'execution_completed',
                {'final_output': final_output}
            )
            
            logger.info(f"Workflow execution {self.execution.id} completed successfully")
            return final_output
            
        except Exception as e:
            logger.error(f"Workflow execution {self.execution.id} failed: {e}")
            
            # Mark execution as failed
            self.execution.status = 'failed'
            self.execution.completed_at = timezone.now()
            self.execution.error_message = str(e)
            self.execution.node_results = self.ordered_node_results
            self.execution.save(update_fields=['status', 'completed_at', 'error_message', 'node_results'])
            
            # Publish failure event
            publish_execution_event(
                str(self.execution.id),
                'execution_failed',
                {'error': str(e)}
            )
            
            raise
    
    def _execute_trigger(self) -> Dict[str, Any]:
        """
        Execute the workflow trigger.
        
        Returns:
            Trigger output data
        """
        if not self.trigger:
            raise ValueError("Workflow has no trigger defined")
        
        trigger_type = self.trigger.get('type')
        trigger_params = self.trigger.get('params', {})
        trigger_id = self.trigger.get('id', 'trigger')
        
        logger.info(f"Executing trigger: {trigger_type}")
        
        try:
            # Get trigger node class
            trigger_node_class = node_registry.get_node_class(trigger_type)
            trigger_instance = trigger_node_class()
            
            # Prepare trigger input data (from execution input)
            trigger_input = self.execution.input_data or {}
            
            # Execute trigger
            trigger_output = trigger_instance.run(
                trigger_input,
                trigger_params,
                self.execution_context
            )
            
            # Store trigger output
            self.node_outputs[trigger_id] = trigger_output
            
            # Update context for downstream nodes
            self._update_context_outputs()
            
            # Create node execution record
            self._create_node_execution_record(
                trigger_id,
                trigger_type,
                trigger_input,
                trigger_output,
                'completed'
            )
            
            logger.info(f"Trigger {trigger_type} executed successfully")
            return trigger_output
            
        except Exception as e:
            logger.error(f"Trigger execution failed: {e}")
            self._create_node_execution_record(
                trigger_id,
                trigger_type,
                {},
                {},
                'failed',
                str(e)
            )
            raise NodeExecutionError(f"Trigger execution failed: {e}")
    
    def _execute_workflow_dag(self, trigger_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute workflow nodes in DAG order.
        
        Args:
            trigger_output: Output from trigger execution
            
        Returns:
            Final workflow output
        """
        # Build execution order using topological sort
        execution_order = self._topological_sort()
        
        # Start with trigger output as current data
        current_data = trigger_output.copy()
        
        # Execute nodes in order
        for node_id in execution_order:
            if node_id not in self.nodes:
                logger.warning(f"Node {node_id} not found in workflow definition")
                continue
            
            try:
                node_output = self._execute_node(node_id, current_data)
                
                # Merge node output with current data
                current_data.update(node_output)
                
                # Store node output for potential use by other nodes
                self.node_outputs[node_id] = node_output
                
            except NodeExecutionError as e:
                logger.error(f"Node {node_id} execution failed: {e}")
                
                # Handle node failure based on configuration
                if self._should_continue_on_error(node_id):
                    logger.info(f"Continuing execution despite {node_id} failure")
                    continue
                else:
                    raise
        
        return current_data
    
    def _execute_node(self, node_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single workflow node.
        
        Args:
            node_id: ID of the node to execute
            input_data: Input data for the node
            
        Returns:
            Node output data
        """
        node_definition = self.nodes[node_id]
        node_type = node_definition.get('type')
        node_params = node_definition.get('params', {})
        
        logger.info(f"Executing node {node_id} (type: {node_type})")
        
        try:
            # Get node class from registry
            node_class = node_registry.get_node_class(node_type)
            node_instance = node_class()
            
            # Validate parameters
            if not node_instance.validate_params(node_params):
                raise NodeExecutionError(f"Invalid parameters for node {node_id}")
            
            # Prepare node-specific input data
            node_input = self._prepare_node_input(node_id, input_data)
            
            # Update context with current node outputs (mapped by ID and Label)
            self._update_context_outputs()
            
            # Execute node
            node_output = node_instance.run(
                node_input,
                node_params,
                self.execution_context
            )
            
            # Create successful execution record
            self._create_node_execution_record(
                node_id,
                node_type,
                node_input,
                node_output,
                'completed'
            )
            
            # Publish node completion event
            publish_execution_event(
                str(self.execution.id),
                'node_completed',
                {
                    'node_id': node_id,
                    'node_type': node_type,
                    'output_keys': list(node_output.keys())
                }
            )
            
            logger.info(f"Node {node_id} executed successfully")
            return node_output
            
        except NodeExecutionError as e:
            logger.error(f"Node {node_id} execution failed: {e}")
            
            # Create failed execution record
            self._create_node_execution_record(
                node_id,
                node_type,
                input_data,
                {},
                'failed',
                str(e)
            )
            
            # Publish node failure event
            publish_execution_event(
                str(self.execution.id),
                'node_failed',
                {
                    'node_id': node_id,
                    'node_type': node_type,
                    'error': str(e)
                }
            )
            
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error in node {node_id}: {e}")
            
            # Create failed execution record
            self._create_node_execution_record(
                node_id,
                node_type,
                input_data,
                {},
                'failed',
                f"Unexpected error: {e}"
            )
            
            raise NodeExecutionError(f"Node {node_id} failed: {e}")
    
    def _prepare_node_input(self, node_id: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare input data for a specific node.
        
        This method can be extended to handle more complex input preparation,
        such as filtering data from specific parent nodes.
        
        Args:
            node_id: ID of the node
            current_data: Current workflow data
            
        Returns:
            Input data for the node
        """
        # For now, pass all current data to the node
        # In the future, this could be enhanced to:
        # 1. Only pass data from direct parent nodes
        # 2. Apply input mappings/transformations
        # 3. Filter sensitive data based on node permissions
        
        return current_data.copy()
    
    def _topological_sort(self) -> List[str]:
        """
        Perform topological sort to determine node execution order.
        
        Returns:
            List of node IDs in execution order
        """
        # Build adjacency list and in-degree count
        adjacency = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Initialize all nodes
        for node_id in self.nodes.keys():
            in_degree[node_id] = 0
        
        # Build graph from connections
        for source_id, target_ids in self.connections.items():
            if source_id == self.trigger.get('id', 'trigger'):
                # Skip trigger in node execution
                continue
            
            for target_id in target_ids:
                if target_id in self.nodes:
                    adjacency[source_id].append(target_id)
                    in_degree[target_id] += 1
        
        # Find nodes with no dependencies (connected to trigger)
        trigger_id = self.trigger.get('id', 'trigger')
        queue = deque()
        
        if trigger_id in self.connections:
            for target_id in self.connections[trigger_id]:
                if target_id in self.nodes:
                    queue.append(target_id)
        
        # Perform topological sort
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            # Reduce in-degree for neighbors
            for neighbor_id in adjacency[node_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)
        
        # Check for cycles
        if len(result) != len(self.nodes):
            remaining_nodes = set(self.nodes.keys()) - set(result)
            raise ValueError(f"Workflow contains cycles or unreachable nodes: {remaining_nodes}")
        
        logger.info(f"Node execution order: {result}")
        return result
    
    def _should_continue_on_error(self, node_id: str) -> bool:
        """
        Determine if execution should continue when a node fails.
        
        Args:
            node_id: ID of the failed node
            
        Returns:
            True if execution should continue, False otherwise
        """
        node_definition = self.nodes.get(node_id, {})
        
        # Check node-specific configuration
        continue_on_error = node_definition.get('continue_on_error', False)
        
        # Check workflow-level configuration
        workflow_continue_on_error = self.workflow_definition.get('meta', {}).get('continue_on_error', False)
        
        return continue_on_error or workflow_continue_on_error
    
    def _build_execution_context(self) -> Dict[str, Any]:
        """
        Build execution context for nodes.
        
        Returns:
            Context dictionary with execution metadata and resources
        """
        return {
            'execution_id': str(self.execution.id),
            'workflow_id': str(self.workflow.id),
            'execution_timestamp': timezone.now().isoformat(),
            'user_id': str(self.execution.created_by.id) if self.execution.created_by else None,
            'tenant_id': str(self.execution.tenant.id) if hasattr(self.execution, 'tenant') else None,
            'credentials': self._get_credentials_context(),
            'environment': self._get_environment_context()
        }
    
    def _get_credentials_context(self) -> Dict[str, Any]:
        """
        Get credentials available to this execution.
        
        Returns:
            Dictionary of available credentials
        """
        # This would integrate with the credential system
        # For now, return empty dict
        return {}
    
    def _get_environment_context(self) -> Dict[str, Any]:
        """
        Get environment variables and settings.
        
        Returns:
            Dictionary of environment context
        """
        from django.conf import settings
        
            'debug_mode': settings.DEBUG,
            'environment': getattr(settings, 'ENVIRONMENT', 'development')
        }
    
    def _update_context_outputs(self):
        """Update execution context with node outputs mapped by ID and Label."""
        outputs_map = {}
        for nid, output in self.node_outputs.items():
            outputs_map[nid] = output # Support lookup by ID
            
            # Find label
            node_def = self.nodes.get(nid)
            # Handle trigger case
            if not node_def and self.trigger and nid == self.trigger.get('id', 'trigger'):
                node_def = self.trigger
                
            if node_def:
                # Add Label as key
                if node_def.get('label'):
                    outputs_map[node_def['label']] = output
                
                # Add Name as key (legacy)
                if node_def.get('name'):
                    outputs_map[node_def['name']] = output
                    
        self.execution_context['node_outputs'] = outputs_map
    
    def _create_node_execution_record(
        self,
        node_id: str,
        node_type: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str,
        error_message: str = None
    ) -> NodeExecution:
        """
        Create a database record for node execution.
        
        Args:
            node_id: ID of the executed node
            node_type: Type of the node
            input_data: Input data for the node
            output_data: Output data from the node
            status: Execution status
            error_message: Error message if failed
            
        Returns:
            Created NodeExecution instance
        """
        try:
            node_execution = NodeExecution.objects.create(
                execution=self.execution,
                node_id=node_id,
                node_type=node_type,
                input_data=input_data,
                output=output_data,  # Fixed: Match model field name
                status=status,
                error_message=error_message,
                started_at=timezone.now(),
                completed_at=timezone.now() if status in ['completed', 'failed'] else None
            )
            
            self.node_executions[node_id] = node_execution
            
            # Add to ordered results for UI trace
            # Try to get label
            node_def = self.nodes.get(node_id, {}) if hasattr(self, 'nodes') else {}
            if not node_def and node_id == (self.trigger.get('id') if self.trigger else 'trigger'):
                node_def = self.trigger
            
            trace_item = {
                "node_id": node_id,
                "label": node_def.get("label", node_id),
                "type": node_type,
                "status": "success" if status == "completed" else "failed",
                "success": status == "completed",
                "output": output_data,
                "error": error_message,
                "timestamp": timezone.now().isoformat()
            }
            self.ordered_node_results.append(trace_item)
            
            return node_execution
            
        except Exception as e:
            logger.error(f"Failed to create node execution record: {e}")
            # Don't fail the workflow execution due to logging issues
            return None


def execute_workflow_with_nodes(workflow: Workflow, execution: WorkflowExecution) -> Dict[str, Any]:
    """
    Execute a workflow using the new node-based system.
    
    This is the main entry point for workflow execution.
    
    Args:
        workflow: Workflow instance
        execution: WorkflowExecution instance
        
    Returns:
        Final execution result
    """
    executor = NodeBasedExecutor(workflow, execution)
    return executor.execute()