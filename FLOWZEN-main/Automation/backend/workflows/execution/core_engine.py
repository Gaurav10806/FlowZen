"""
Core Workflow Execution Engine

This is the HEART of the n8n-like workflow automation system.
It provides a simple, safe, and extensible execution engine that:

1. Uses the Node Registry to load nodes (no hardcoded logic)
2. Supports DAG execution with topological sorting
3. Passes outputs between nodes seamlessly
4. Handles errors gracefully with detailed capture
5. Maintains execution context throughout the flow

DESIGN PRINCIPLES:
- Simple and deterministic
- Framework-agnostic core logic
- Fail-fast with detailed error capture
- Extensible for future enhancements
- Non-intrusive observability hooks
"""

import logging
from typing import Dict, List, Any, Optional, Set, Callable
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
import uuid

from ..nodes import node_registry, BaseNode, NodeExecutionError


logger = logging.getLogger(__name__)


class ExecutionHooks:
    """
    Non-intrusive hooks for execution observability.
    
    These hooks allow external systems (like Django) to observe execution
    without modifying the core execution logic.
    """
    
    def __init__(self):
        """Initialize empty hooks."""
        self.on_execution_start: Optional[Callable] = None
        self.on_execution_complete: Optional[Callable] = None
        self.on_execution_error: Optional[Callable] = None
        self.on_node_start: Optional[Callable] = None
        self.on_node_complete: Optional[Callable] = None
        self.on_node_error: Optional[Callable] = None
    
    def execution_started(self, context: 'ExecutionContext', workflow_json: Dict[str, Any]) -> None:
        """Hook called when execution starts."""
        if self.on_execution_start:
            try:
                self.on_execution_start(context, workflow_json)
            except Exception as e:
                logger.warning(f"Execution start hook failed: {e}")
    
    def execution_completed(self, context: 'ExecutionContext', result: 'WorkflowExecutionResult') -> None:
        """Hook called when execution completes successfully."""
        if self.on_execution_complete:
            try:
                self.on_execution_complete(context, result)
            except Exception as e:
                logger.warning(f"Execution complete hook failed: {e}")
    
    def execution_failed(self, context: 'ExecutionContext', error: Exception, result: 'WorkflowExecutionResult') -> None:
        """Hook called when execution fails."""
        if self.on_execution_error:
            try:
                self.on_execution_error(context, error, result)
            except Exception as e:
                logger.warning(f"Execution error hook failed: {e}")
    
    def node_started(self, context: 'ExecutionContext', node_id: str, node_type: str, input_data: Dict[str, Any]) -> None:
        """Hook called when node execution starts."""
        if self.on_node_start:
            try:
                self.on_node_start(context, node_id, node_type, input_data)
            except Exception as e:
                logger.warning(f"Node start hook failed: {e}")
    
    def node_completed(self, context: 'ExecutionContext', result: 'NodeExecutionResult') -> None:
        """Hook called when node execution completes successfully."""
        if self.on_node_complete:
            try:
                self.on_node_complete(context, result)
            except Exception as e:
                logger.warning(f"Node complete hook failed: {e}")
    
    def node_failed(self, context: 'ExecutionContext', node_id: str, node_type: str, error: Exception) -> None:
        """Hook called when node execution fails."""
        if self.on_node_error:
            try:
                self.on_node_error(context, node_id, node_type, error)
            except Exception as e:
                logger.warning(f"Node error hook failed: {e}")


@dataclass
class ExecutionContext:
    """
    Execution context that flows between all nodes.
    
    This context contains all the runtime information that nodes
    need to execute properly.
    """
    # Core identifiers
    workflow_id: str
    execution_id: str
    
    # User context
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    # Runtime variables
    variables: Dict[str, Any] = None

    # Node Output Tracking (CRITICAL for $node() expressions)
    node_outputs: Dict[str, List[Dict[str, Any]]] = None
    
    # Secrets and credentials (placeholder for future)
    secrets: Dict[str, Any] = None
    
    # Execution metadata
    started_at: Optional[datetime] = None
    current_node_id: Optional[str] = None
    triggered_by: Optional[str] = None # NEW: Track execution source
    
    # Environment
    environment: str = "development"
    debug_mode: bool = False
    
    def __post_init__(self):
        """Initialize default values."""
        if self.variables is None:
            self.variables = {}
        if self.node_outputs is None:
            self.node_outputs = {}
        if self.secrets is None:
            self.secrets = {}
        if self.started_at is None:
            self.started_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for node consumption."""
        return {
            'workflow_id': self.workflow_id,
            'execution_id': self.execution_id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'variables': self.variables,
            'node_outputs': self.node_outputs,
            'secrets': self.secrets,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'current_node_id': self.current_node_id,
            'triggered_by': self.triggered_by,
            'environment': self.environment,
            'debug_mode': self.debug_mode
        }


@dataclass
class NodeExecutionResult:
    """Result of executing a single node."""
    node_id: str
    node_type: str
    success: bool
    output_data: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'success': self.success,
            'status': 'success' if self.success else 'failed',
            'output': self.output_data,
            'output_data': self.output_data,
            'error': self.error_message,
            'error_message': self.error_message,
            'execution_time_ms': self.execution_time_ms,
            'timestamp': datetime.utcnow().isoformat()
        }


@dataclass
class WorkflowExecutionResult:
    """Final result of workflow execution."""
    success: bool
    final_output: Dict[str, Any]
    node_results: List[NodeExecutionResult]
    error_message: Optional[str] = None
    total_execution_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'success': self.success,
            'final_output': self.final_output,
            'node_results': [result.to_dict() for result in self.node_results],
            'error_message': self.error_message,
            'total_execution_time_ms': self.total_execution_time_ms
        }


class WorkflowExecutionEngine:
    """
    Core workflow execution engine.
    
    This engine is the HEART of the workflow automation system.
    It executes workflows using the pluggable node system.
    
    Key Features:
    - Framework-agnostic core logic
    - Uses Node Registry for all node operations
    - DAG-based execution with topological sorting
    - Seamless data flow between nodes
    - Comprehensive error handling
    - Extensible design for future enhancements
    - Non-intrusive observability hooks
    """
    
    def __init__(self, hooks: Optional[ExecutionHooks] = None):
        """Initialize the execution engine."""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.hooks = hooks or ExecutionHooks()
    
    def run(self, workflow_json: Dict[str, Any], trigger_input: Dict[str, Any], 
            context: ExecutionContext) -> WorkflowExecutionResult:
        """
        Execute a complete workflow.
        
        This is the MAIN ENTRY POINT for workflow execution.
        
        Args:
            workflow_json: Complete workflow definition (JSON contract)
            trigger_input: Input data for the trigger node
            context: Execution context with runtime information
            
        Returns:
            WorkflowExecutionResult with complete execution details
            
        Raises:
            ValueError: If workflow definition is invalid
            NodeExecutionError: If node execution fails critically
        """
        start_time = datetime.utcnow()
        node_results = []
        
        try:
            self.logger.info(f"Starting workflow execution {context.execution_id}")
            
            # HOOK: Execution started
            self.hooks.execution_started(context, workflow_json)
            
            # STEP 1: Validate workflow structure
            self._validate_workflow_structure(workflow_json)
            
            # STEP 2: Extract workflow components
            trigger = workflow_json['trigger']
            nodes = workflow_json['nodes']
            connections = workflow_json['connections']
            
            # DEBUG
            print(f"DEBUG: Resolving execution order. Nodes type: {type(nodes)}")
            print(f"DEBUG: Nodes keys: {list(nodes.keys()) if isinstance(nodes, dict) else 'NOT A DICT'}")
            print(f"DEBUG: Connections: {connections}")
            
            self._validate_dag_structure(nodes, connections)
            
            # CRITICAL LOG: Execution Flow
            self.logger.critical(f"🚀 EXECUTION ENGINE START: {context.execution_id}")
            self.logger.critical(f"🚀 USER ID: {context.user_id}")
            self.logger.critical(f"🚀 TRIGGER NODE: {trigger.get('id')} ({trigger.get('type')})")
            
            # STEP 4: Execute trigger node
            trigger_result = self._execute_trigger(trigger, trigger_input, context)
            
            # CRITICAL LOG: Trigger Result
            self.logger.critical(f"🚀 TRIGGER RESULT: Success={trigger_result.success}")
            
            node_results.append(trigger_result)
            
            # CRITICAL: TRACK TRIGGER OUTPUT FOR EXPRESSIONS
            # 1. Prepare Payload (Unwrapped)
            raw_output = trigger_result.output_data
            payload = raw_output
            if isinstance(raw_output, dict) and "output" in raw_output:
                    payload = raw_output["output"]
            
            # 2. Create Entry
            node_entry = {
                "json": payload,
                "binary": raw_output.get("binary", {}) if isinstance(raw_output, dict) else {}, # NEW: Binary Support
                "raw": raw_output
            }
            
            # 3. Store by ID (Mandatory)
            context.node_outputs[trigger.get('id')] = node_entry
            
            # 4. Store by Name/Label (Standardize to reduce duplication)
            # Priority: Label > Name > Display Name
            primary_key = trigger.get('label') or trigger.get('name') or trigger.get('display_name') or trigger.get('type')
            if primary_key:
                context.node_outputs[primary_key] = node_entry
            
            # Always ensure 'trigger' is available
            context.node_outputs["trigger"] = node_entry
            self.logger.debug(f"Mapped output for trigger node '{primary_key}' and 'trigger'")
            
            if not trigger_result.success:
                result = WorkflowExecutionResult(
                    success=False,
                    final_output={},
                    node_results=node_results,
                    error_message=f"Trigger execution failed: {trigger_result.error_message}"
                )
                
                # HOOK: Execution failed
                error = Exception(result.error_message)
                self.hooks.execution_failed(context, error, result)
                
                return result
            
            # STEP 5: Dynamic Execution Loop (n8n-style)
            # Instead of topological sort, we traverse dynamically based on handles.
            # We use a queue to track nodes ready to execute.
            from collections import deque
            pending_nodes = deque()
            
            # Initial nodes are those connected to the trigger
            trigger_targets = connections.get(trigger['id'], [])
            for target_id in trigger_targets:
                pending_nodes.append(target_id)
            
            # To track which nodes have been visited (avoid cycles)
            visited_nodes = set()
            
            # TRACKING ENGINE STATE
            self.logger.critical(f"🚀 ENGINE: Starting dynamic traversal from trigger. initial queue: {list(pending_nodes)}")
            
            # STEP 6: Execute nodes in order
            current_data = trigger_result.output_data.copy()
            
            # --- GLOBAL EXECUTION TIMEOUT CONFIG ---
            from django.conf import settings
            # Default to 300 seconds (5 minutes) if not configured
            execution_timeout = int(getattr(settings, "WORKFLOW_EXECUTION_TIME_LIMIT", "300"))

            while pending_nodes:
                # --- CHECK TIMEOUT ---
                elapsed_seconds = (datetime.utcnow() - start_time).total_seconds()
                if elapsed_seconds > execution_timeout:
                    timeout_error_msg = f"Workflow execution timed out after {elapsed_seconds:.1f}s (Limit: {execution_timeout}s)"
                    self.logger.error(f"❌ {timeout_error_msg}")
                    raise TimeoutError(timeout_error_msg)

                node_id = pending_nodes.popleft()
                
                if node_id in visited_nodes:
                    self.logger.debug(f"Node {node_id} already executed, skipping to prevent cycles")
                    continue
                
                node_def = nodes[node_id]
                
                # Update context with current node
                context.current_node_id = node_id
                
                # CRITICAL LOG: Node Start
                self.logger.critical(f"🚀 EXECUTING NODE: {node_id} (Type: {node_def.get('type')})")
                
                # Execute node
                node_result = self._execute_node(node_id, node_def, current_data, context)
                
                # CRITICAL LOG: Node Result
                self.logger.critical(f"🚀 NODE RESULT: {node_id} Success={node_result.success}")
                
                node_results.append(node_result)
                
                if not node_result.success:
                    result = WorkflowExecutionResult(
                        success=False,
                        final_output=current_data,
                        node_results=node_results,
                        error_message=f"Node {node_id} failed: {node_result.error_message}"
                    )
                    error = Exception(result.error_message)
                    self.hooks.execution_failed(context, error, result)
                    return result

                # 🚀 BRANCH-AWARE ROUTING 🚀
                # Check for "branch" in output (n8n standard)
                branch = None
                raw_node_output = node_result.output_data
                if isinstance(raw_node_output, dict):
                    branch = raw_node_output.get("branch")
                
                self.logger.info(f"Node {node_id} returned branch: {branch}")
                
                # Identify next nodes based on handles
                outgoing_targets = connections.get(node_id, [])
                
                # In our system (contract), connections is {sourceId: [targetIds]}
                # BUT for branching, we need the connection OBJECT with handles.
                # If connections is just a list of IDs, we can't do handle matching.
                
                # STEP 5.1: Resolve next nodes from workflow_json edges
                # (Assuming 'edges' exist in workflow_json, standard for professional flows)
                edges = workflow_json.get('edges', [])
                
                next_nodes = []
                if edges:
                    # Professional mode: filter edges by handle
                    for edge in edges:
                        if edge.get('source') == node_id:
                            source_handle = edge.get('sourceHandle', 'output')
                            
                            # If node specified a branch, only follow matching handle
                            if branch:
                                if source_handle == branch:
                                    next_nodes.append(edge.get('target'))
                                    self.logger.debug(f"Found matching branch edge: {source_handle} -> {edge.get('target')}")
                            else:
                                # Standard node, follow all outgoing primary handles
                                if source_handle == 'output' or not source_handle:
                                    next_nodes.append(edge.get('target'))
                                    self.logger.debug(f"Following standard edge -> {edge.get('target')}")
                else:
                    # Legacy fallback: connections dict (old simple flows)
                    next_nodes = outgoing_targets

                # Add unique next nodes to pending
                for next_id in next_nodes:
                    if next_id not in visited_nodes:
                        pending_nodes.append(next_id)
                
                visited_nodes.add(node_id)
                
                # Merge node output
                current_data.update(node_result.output_data)

                # TRACK OUTPUT FOR EXPRESSIONS
                raw_output = node_result.output_data
                payload = raw_output
                if isinstance(raw_output, dict) and "output" in raw_output:
                     payload = raw_output["output"]
                
                node_entry = { "json": payload, "raw": raw_output }
                context.node_outputs[node_id] = node_entry
                
                # 4. Store by Name/Label (Standardize to reduce duplication)
                primary_key = node_def.get('label') or node_def.get('name') or node_def.get('display_name') or node_def.get('type')
                if primary_key:
                    context.node_outputs[primary_key] = node_entry
            
            # STEP 7: Return successful result
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            self.logger.info(f"Workflow execution {context.execution_id} completed successfully")
            
            result = WorkflowExecutionResult(
                success=True,
                final_output=current_data,
                node_results=node_results,
                total_execution_time_ms=execution_time
            )
            
            # HOOK: Execution completed
            self.hooks.execution_completed(context, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Workflow execution {context.execution_id} failed: {e}")
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            result = WorkflowExecutionResult(
                success=False,
                final_output={},
                node_results=node_results,
                error_message=str(e),
                total_execution_time_ms=execution_time
            )
            
            # HOOK: Execution failed
            self.hooks.execution_failed(context, e, result)
            
            return result
        
        finally:
            # SAFETY NET: Ensure logic always returns a result or logs critical failure
            if 'result' not in locals():
                 self.logger.critical(f"🔥 CRITICAL: Execution {context.execution_id} exited without result!")
    
    def _validate_workflow_structure(self, workflow_json: Dict[str, Any]) -> None:
        """
        Validate that workflow JSON has required structure.
        
        Args:
            workflow_json: Workflow definition to validate
            
        Raises:
            ValueError: If workflow structure is invalid
        """
        required_keys = ['meta', 'trigger', 'nodes', 'connections']
        
        for key in required_keys:
            if key not in workflow_json:
                raise ValueError(f"Workflow missing required key: {key}")
        
        # Validate trigger structure
        trigger = workflow_json['trigger']
        if not isinstance(trigger, dict) or 'type' not in trigger or 'id' not in trigger:
            raise ValueError("Trigger must have 'type' and 'id' fields")
        
        # Validate nodes structure
        nodes = workflow_json['nodes']
        if not isinstance(nodes, dict):
            raise ValueError("Nodes must be a dictionary")
        
        for node_id, node_def in nodes.items():
            if not isinstance(node_def, dict) or 'type' not in node_def:
                raise ValueError(f"Node {node_id} must have 'type' field")
        
        # Validate connections structure
        connections = workflow_json['connections']
        if not isinstance(connections, dict):
            raise ValueError("Connections must be a dictionary")
        
        self.logger.debug("Workflow structure validation passed")
    
    def _validate_dag_structure(self, nodes: Dict[str, Any], connections: Dict[str, List[str]]) -> None:
        """
        Validate that the workflow forms a valid DAG (no cycles).
        
        Args:
            nodes: Dictionary of node definitions
            connections: Dictionary mapping node IDs to their targets
            
        Raises:
            ValueError: If workflow contains cycles or invalid references
        """
        # Check that all connection targets exist
        all_node_ids = set(nodes.keys())
        
        for source_id, targets in connections.items():
            if not isinstance(targets, list):
                raise ValueError(f"Connections for {source_id} must be a list")
            
            for target_id in targets:
                if target_id not in all_node_ids:
                    raise ValueError(f"Connection target {target_id} does not exist in nodes")
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            if node_id in rec_stack:
                return True
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for target_id in connections.get(node_id, []):
                if has_cycle(target_id):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node_id in all_node_ids:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise ValueError(f"Workflow contains cycle involving node {node_id}")
        
        self.logger.debug("DAG structure validation passed")
    
    def _execute_trigger(self, trigger: Dict[str, Any], trigger_input: Dict[str, Any], 
                        context: ExecutionContext) -> NodeExecutionResult:
        """
        Execute the workflow trigger node.
        
        Args:
            trigger: Trigger node definition
            trigger_input: Input data for trigger
            context: Execution context
            
        Returns:
            NodeExecutionResult with trigger execution details
        """
        trigger_id = trigger['id']
        trigger_type = trigger['type']
        
        # Standardize parameter retrieval (params vs config)
        trigger_params = trigger.get('params') or trigger.get('config', {})
        
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Executing trigger {trigger_id} (type: {trigger_type})")
            
            # CRITICAL BYPASS: If execution is triggered by webhook, skip manual execution check
            # and seed the output with the webhook payload.
            if context.triggered_by == 'webhook':
                 self.logger.critical(f"🚀 SKIPPING TRIGGER EXECUTION (Source: Webhook) - Seeding Input Data")
                 
                 # Treat trigger_input as the Output of the trigger
                 self.hooks.node_started(context, trigger_id, trigger_type, trigger_input)
                 
                 result = NodeExecutionResult(
                    node_id=trigger_id,
                    node_type=trigger_type,
                    success=True,
                    output_data=trigger_input, # Pass the webhook payload directly
                    execution_time_ms=0
                 )
                 
                 self.hooks.node_completed(context, result)
                 return result

            # HOOK: Node started
            self.hooks.node_started(context, trigger_id, trigger_type, trigger_input)
            
            # Get trigger node class from registry
            trigger_node_class = node_registry.get_node_class(trigger_type)
            trigger_instance = trigger_node_class(node_data=trigger)
            
            # Validate trigger parameters
            if not trigger_instance.validate_params(trigger_params):
                raise NodeExecutionError(f"Invalid parameters for trigger {trigger_id}")
            
            # Execute trigger
            context.current_node_id = trigger_id
            output_data = trigger_instance.run(trigger_input, trigger_params, context.to_dict())
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            self.logger.info(f"Trigger {trigger_id} executed successfully")
            
            result = NodeExecutionResult(
                node_id=trigger_id,
                node_type=trigger_type,
                success=True,
                output_data=output_data,
                execution_time_ms=execution_time
            )
            
            # HOOK: Node completed
            self.hooks.node_completed(context, result)
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            error_msg = f"Trigger {trigger_id} execution failed: {e}"
            self.logger.error(error_msg)
            
            # HOOK: Node failed
            self.hooks.node_failed(context, trigger_id, trigger_type, e)
            
            return NodeExecutionResult(
                node_id=trigger_id,
                node_type=trigger_type,
                success=False,
                output_data={},
                error_message=error_msg,
                execution_time_ms=execution_time
            )
    
    def _execute_node(self, node_id: str, node_def: Dict[str, Any], 
                     input_data: Dict[str, Any], context: ExecutionContext) -> NodeExecutionResult:
        """
        Execute a single workflow node.
        
        Args:
            node_id: ID of the node to execute
            node_def: Node definition from workflow JSON
            input_data: Input data from previous nodes
            context: Execution context
            
        Returns:
            NodeExecutionResult with node execution details
        """
        node_type = node_def['type']
        
        # Standardize parameter retrieval (params vs config)
        node_params = node_def.get('params') or node_def.get('config', {})
        
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Executing node {node_id} (type: {node_type})")
            
            # HOOK: Node started
            self.hooks.node_started(context, node_id, node_type, input_data)
            
            # Get node class from registry
            node_class = node_registry.get_node_class(node_type)
            node_instance = node_class(node_data=node_def)
            
            # Validate node parameters
            if not node_instance.validate_params(node_params):
                raise NodeExecutionError(f"Invalid parameters for node {node_id}")
            
            # Retrieve Retry Configuration from Node Definition OR Parameters
            # Priority: Node Def > Params (standard n8n style)
            retry_on_fail = node_def.get('retryOnFail', False)
            max_tries = int(node_def.get('maxTries', 1)) 
            wait_between_tries = int(node_def.get('waitBetweenTries', 1000)) # Default 1s
            
            # Check params for overrides (optional, for dynamic control)
            if node_params.get('retryOnFail'): retry_on_fail = True
            if node_params.get('maxTries'): max_tries = int(node_params.get('maxTries'))
            
            current_try = 0
            last_error = None
            output_data = None
            
            while current_try < max_tries:
                current_try += 1
                try:
                    if current_try > 1:
                        self.logger.info(f"Retry attempt {current_try}/{max_tries} for node {node_id}")
                    
                    # Execute node
                    output_data = node_instance.run(input_data, node_params, context.to_dict())
                    
                    # If we got here, execution was successful
                    break
                    
                except Exception as e:
                    last_error = e
                    if retry_on_fail and current_try < max_tries:
                        self.logger.warning(f"Node {node_id} failed attempt {current_try}: {e}. Retrying in {wait_between_tries}ms...")
                        time.sleep(wait_between_tries / 1000.0)
                    else:
                        raise e # Re-raise if no retries left or retries disabled
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            # Determine success from output if available (e.g. AI Agent returns success: False)
            node_success = True
            if isinstance(output_data, dict) and 'success' in output_data:
                node_success = output_data['success']
            
            if node_success:
                self.logger.info(f"Node {node_id} executed successfully")
            else:
                self.logger.warning(f"Node {node_id} reported failure")

            result = NodeExecutionResult(
                node_id=node_id,
                node_type=node_type,
                success=node_success,
                output_data=output_data,
                execution_time_ms=execution_time,
                error_message=output_data.get('error') if isinstance(output_data, dict) else None
            )
            
            # HOOK: Node completed
            self.hooks.node_completed(context, result)
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            error_msg = f"Node {node_id} execution failed: {e}"
            self.logger.error(error_msg)
            
            # HOOK: Node failed
            self.hooks.node_failed(context, node_id, node_type, e)
            
            return NodeExecutionResult(
                node_id=node_id,
                node_type=node_type,
                success=False,
                output_data={},
                error_message=error_msg,
                execution_time_ms=execution_time
            )
    
    def _resolve_execution_order(self, nodes: Dict[str, Any], connections: Dict[str, List[str]], 
                                trigger_id: str) -> List[str]:
        """
        Resolve the order in which nodes should be executed using topological sort.
        
        Args:
            nodes: Dictionary of node definitions
            connections: Dictionary mapping node IDs to their targets
            trigger_id: ID of the trigger node
            
        Returns:
            List of node IDs in execution order (excluding trigger)
        """
        # Build adjacency list and in-degree count
        adjacency = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Initialize all nodes
        for node_id in nodes.keys():
            in_degree[node_id] = 0
        
        # Check that all nodes in connections exist in nodes dict
        missing_nodes = set()
        for source, targets in connections.items():
            print(f"DEBUG: Checking source '{source}' in nodes: {source in nodes}")
            if source not in nodes:
                missing_nodes.add(source)
            for target in targets:
                print(f"DEBUG: Checking target '{target}' in nodes: {target in nodes}")
                if target not in nodes:
                    missing_nodes.add(target)
        
        # Build graph from connections (excluding trigger)
        for source_id, targets in connections.items():
            if source_id == trigger_id:
                # Trigger connections go to first nodes
                for target_id in targets:
                    if target_id in nodes:
                        # Nodes connected to trigger have in-degree 0
                        pass
            else:
                # Regular node connections
                for target_id in targets:
                    if target_id in nodes:
                        adjacency[source_id].append(target_id)
                        in_degree[target_id] += 1
        
        # Find nodes connected directly to trigger (starting nodes)
        queue = deque()
        trigger_targets = connections.get(trigger_id, [])
        
        for node_id in trigger_targets:
            if node_id in nodes:
                queue.append(node_id)
        
        # If no trigger connections, find nodes with in-degree 0
        if not queue:
            for node_id in nodes.keys():
                if in_degree[node_id] == 0:
                    queue.append(node_id)
        
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
        
        # Verify all expected nodes are included (excluding trigger)
        expected_node_ids = set(nodes.keys()) - {trigger_id}
        if set(result) != expected_node_ids:
            missing_nodes = expected_node_ids - set(result)
            # RELAXED STRICTNESS: Warn instead of failing for orphaned nodes
            self.logger.warning(f"Workflow contains unreachable (orphaned) nodes: {missing_nodes}")
            # We explicitly allow partial execution for robustness
            
        self.logger.debug(f"Resolved execution order: {result}")
        return result


# Convenience function for simple execution
def execute_workflow(workflow_json: Dict[str, Any], trigger_input: Dict[str, Any] = None,
                    workflow_id: str = None, execution_id: str = None,
                    user_id: str = None, hooks: Optional[ExecutionHooks] = None) -> WorkflowExecutionResult:
    """
    Execute a workflow with minimal setup.
    
    This is a convenience function for simple workflow execution.
    
    Args:
        workflow_json: Complete workflow definition
        trigger_input: Input data for trigger (default: empty dict)
        workflow_id: Workflow ID (default: generated UUID)
        execution_id: Execution ID (default: generated UUID)
        user_id: User ID (optional)
        hooks: Execution hooks for observability (optional)
        
    Returns:
        WorkflowExecutionResult with execution details
    """
    if trigger_input is None:
        trigger_input = {}
    
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())
    
    if execution_id is None:
        execution_id = str(uuid.uuid4())
    
    # Create execution context
    context = ExecutionContext(
        workflow_id=workflow_id,
        execution_id=execution_id,
        user_id=user_id
    )
    
    # Create and run engine
    engine = WorkflowExecutionEngine(hooks=hooks)
    return engine.run(workflow_json, trigger_input, context)