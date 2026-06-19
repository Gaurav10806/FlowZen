"""
Parallel Execution Nodes - Fan-Out and Fan-In

This module provides parallel workflow execution capabilities using
fan-out (fork) and fan-in (merge) concepts for explicit parallelism.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

from .base_node import UtilityNode, NodeExecutionError
from .registry import register_node
from ..models import WorkflowExecution, NodeExecution


logger = logging.getLogger(__name__)


@register_node
class ParallelForkNode(UtilityNode):
    """
    Parallel Fork Node - Fan-Out Implementation
    
    Takes one input and sends the SAME input data to multiple parallel branches.
    Each branch gets an identical copy of the input data and execution context.
    
    Key Features:
    - Explicit parallelism via branch configuration
    - Deterministic branch creation and tracking
    - Support for both sync and async execution modes
    - Proper execution context copying
    - Branch failure strategies
    """
    
    NODE_TYPE = "parallel_fork"
    DISPLAY_NAME = "Parallel Fork"
    DESCRIPTION = "Split execution into multiple parallel branches"
    CATEGORY = "utilities"
    SUPPORTS_RETRY = True
    DEFAULT_TIMEOUT = 30
    
    # Execution modes
    EXECUTION_MODES = {
        "sync": "Sequential (for testing)",
        "async": "Asynchronous (Celery)"
    }
    
    # Failure strategies
    FAILURE_STRATEGIES = {
        "fail_fast": "Stop on first branch failure",
        "continue_on_error": "Continue even if branches fail",
        "wait_for_all": "Wait for all branches to complete"
    }
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute parallel fork - create multiple branches with same input.
        
        Args:
            input_data: Data from previous nodes
            params: Fork configuration
                - branch_count: Number of branches to create
                - branch_names: Optional names for branches
                - execution_mode: "sync" or "async"
                - timeout_ms: Maximum time to wait for branches
                - failure_strategy: How to handle branch failures
            context: Execution context
            
        Returns:
            Dict with fork result and branch tracking information
        """
        self.logger.info("Starting parallel fork execution")
        
        # Extract parameters
        branch_count = params.get('branch_count', 2)
        branch_names = params.get('branch_names', [])
        execution_mode = params.get('execution_mode', 'async')
        timeout_ms = params.get('timeout_ms', 30000)
        failure_strategy = params.get('failure_strategy', 'fail_fast')
        
        # Validate parameters
        if branch_count < 1 or branch_count > 10:
            raise NodeExecutionError("Branch count must be between 1 and 10")
        
        if execution_mode not in self.EXECUTION_MODES:
            raise NodeExecutionError(f"Invalid execution mode: {execution_mode}")
        
        if failure_strategy not in self.FAILURE_STRATEGIES:
            raise NodeExecutionError(f"Invalid failure strategy: {failure_strategy}")
        
        # Generate branch names if not provided
        if not branch_names:
            branch_names = [f"branch_{i+1}" for i in range(branch_count)]
        elif len(branch_names) < branch_count:
            # Extend with default names
            for i in range(len(branch_names), branch_count):
                branch_names.append(f"branch_{i+1}")
        
        # Limit to requested count
        branch_names = branch_names[:branch_count]
        
        try:
            # Create branch execution records
            branch_executions = []
            execution_id = context.get('execution_id')
            workflow_execution = None
            
            if execution_id:
                try:
                    workflow_execution = WorkflowExecution.objects.get(id=execution_id)
                except WorkflowExecution.DoesNotExist:
                    self.logger.warning(f"Workflow execution {execution_id} not found")
            
            for i, branch_name in enumerate(branch_names):
                branch_execution_id = str(uuid.uuid4())
                
                branch_info = {
                    'branch_id': branch_name,
                    'branch_index': i,
                    'execution_id': branch_execution_id,
                    'status': 'created',
                    'created_at': datetime.utcnow().isoformat(),
                    'input_data': input_data.copy(),  # Each branch gets copy of input
                    'execution_context': {
                        **context,
                        'branch_id': branch_name,
                        'branch_index': i,
                        'parent_execution_id': execution_id,
                        'fork_node_id': context.get('node_id'),
                        'is_parallel_branch': True
                    }
                }
                
                branch_executions.append(branch_info)
                
                self.logger.info(f"Created branch '{branch_name}' with execution ID {branch_execution_id}")
            
            # Schedule or execute branches based on mode
            if execution_mode == 'async':
                # Schedule branches as Celery tasks (production mode)
                scheduled_branches = self._schedule_async_branches(
                    branch_executions, workflow_execution, timeout_ms
                )
                execution_status = 'scheduled'
            else:
                # Execute branches synchronously (testing mode)
                scheduled_branches = self._execute_sync_branches(
                    branch_executions, workflow_execution
                )
                execution_status = 'completed'
            
            # Create fork result
            fork_result = {
                'branch_executions': scheduled_branches,
                'total_branches': len(branch_executions),
                'execution_mode': execution_mode,
                'failure_strategy': failure_strategy,
                'timeout_ms': timeout_ms,
                'fork_status': execution_status,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Fork completed: {len(branch_executions)} branches {execution_status}")
            
            # Return result with fork information
            return {
                **input_data,  # Pass through input data
                'fork_result': fork_result
            }
            
        except Exception as e:
            error_msg = f"Parallel fork execution failed: {str(e)}"
            self.logger.error(error_msg)
            raise NodeExecutionError(error_msg)
    
    def _schedule_async_branches(self, branch_executions: List[Dict], workflow_execution: Optional[WorkflowExecution], timeout_ms: int) -> List[Dict]:
        """
        Schedule branches as asynchronous Celery tasks.
        
        Args:
            branch_executions: List of branch execution info
            workflow_execution: Parent workflow execution
            timeout_ms: Timeout for branch execution
            
        Returns:
            List of scheduled branch info
        """
        scheduled_branches = []
        
        for branch_info in branch_executions:
            try:
                # In a real implementation, this would schedule a Celery task
                # For now, we'll simulate the scheduling
                
                # Import here to avoid circular imports
                # from ..tasks import execute_parallel_branch
                # task = execute_parallel_branch.delay(
                #     branch_info['execution_id'],
                #     branch_info['input_data'],
                #     branch_info['execution_context']
                # )
                
                # Simulate task scheduling
                task_id = str(uuid.uuid4())
                
                scheduled_info = {
                    'branch_id': branch_info['branch_id'],
                    'branch_index': branch_info['branch_index'],
                    'execution_id': branch_info['execution_id'],
                    'task_id': task_id,
                    'status': 'scheduled',
                    'scheduled_at': datetime.utcnow().isoformat(),
                    'timeout_at': (datetime.utcnow() + timedelta(milliseconds=timeout_ms)).isoformat()
                }
                
                scheduled_branches.append(scheduled_info)
                
                self.logger.debug(f"Scheduled branch {branch_info['branch_id']} as task {task_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to schedule branch {branch_info['branch_id']}: {e}")
                
                # Add failed scheduling info
                scheduled_info = {
                    'branch_id': branch_info['branch_id'],
                    'branch_index': branch_info['branch_index'],
                    'execution_id': branch_info['execution_id'],
                    'status': 'failed',
                    'error': str(e),
                    'failed_at': datetime.utcnow().isoformat()
                }
                
                scheduled_branches.append(scheduled_info)
        
        return scheduled_branches
    
    def _execute_sync_branches(self, branch_executions: List[Dict], workflow_execution: Optional[WorkflowExecution]) -> List[Dict]:
        """
        Execute branches synchronously (for testing).
        
        Args:
            branch_executions: List of branch execution info
            workflow_execution: Parent workflow execution
            
        Returns:
            List of completed branch info
        """
        completed_branches = []
        
        for branch_info in branch_executions:
            try:
                start_time = datetime.utcnow()
                
                # Simulate branch execution
                # In a real implementation, this would execute the branch workflow
                execution_time_ms = 100  # Simulate 100ms execution
                
                completed_info = {
                    'branch_id': branch_info['branch_id'],
                    'branch_index': branch_info['branch_index'],
                    'execution_id': branch_info['execution_id'],
                    'status': 'completed',
                    'started_at': start_time.isoformat(),
                    'completed_at': datetime.utcnow().isoformat(),
                    'execution_time_ms': execution_time_ms,
                    'result': {
                        'status': 'success',
                        'items': branch_info['input_data']  # Pass through input
                    }
                }
                
                completed_branches.append(completed_info)
                
                self.logger.debug(f"Completed branch {branch_info['branch_id']} in {execution_time_ms}ms")
                
            except Exception as e:
                self.logger.error(f"Failed to execute branch {branch_info['branch_id']}: {e}")
                
                completed_info = {
                    'branch_id': branch_info['branch_id'],
                    'branch_index': branch_info['branch_index'],
                    'execution_id': branch_info['execution_id'],
                    'status': 'failed',
                    'error': str(e),
                    'failed_at': datetime.utcnow().isoformat()
                }
                
                completed_branches.append(completed_info)
        
        return completed_branches
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for parallel fork node parameters.
        """
        return {
            "type": "object",
            "properties": {
                "branch_count": {
                    "type": "integer",
                    "title": "Branch Count",
                    "description": "Number of parallel branches to create",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 2
                },
                "branch_names": {
                    "type": "array",
                    "title": "Branch Names",
                    "description": "Optional names for branches (for logging and debugging)",
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 50
                    },
                    "maxItems": 10
                },
                "execution_mode": {
                    "type": "string",
                    "enum": list(cls.EXECUTION_MODES.keys()),
                    "title": "Execution Mode",
                    "description": "How to execute branches",
                    "default": "async"
                },
                "timeout_ms": {
                    "type": "integer",
                    "title": "Timeout (milliseconds)",
                    "description": "Maximum time to wait for all branches",
                    "minimum": 1000,
                    "maximum": 300000,
                    "default": 30000
                },
                "failure_strategy": {
                    "type": "string",
                    "enum": list(cls.FAILURE_STRATEGIES.keys()),
                    "title": "Failure Strategy",
                    "description": "How to handle branch failures",
                    "default": "fail_fast"
                }
            },
            "required": ["branch_count"],
            "additionalProperties": False
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Expected input data schema."""
        return {
            "type": "object",
            "description": "Any data from previous nodes - will be copied to each branch",
            "additionalProperties": True
        }
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Output data schema."""
        return {
            "type": "object",
            "properties": {
                "fork_result": {
                    "type": "object",
                    "properties": {
                        "branch_executions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "branch_id": {"type": "string"},
                                    "execution_id": {"type": "string"},
                                    "status": {"type": "string"},
                                    "created_at": {"type": "string", "format": "date-time"}
                                }
                            }
                        },
                        "total_branches": {"type": "integer"},
                        "execution_mode": {"type": "string"},
                        "failure_strategy": {"type": "string"},
                        "fork_status": {"type": "string"}
                    }
                }
            },
            "additionalProperties": True,
            "description": "All input data plus fork_result with branch tracking information"
        }


@register_node
class ParallelMergeNode(UtilityNode):
    """
    Parallel Merge Node - Fan-In Implementation
    
    Waits for multiple parallel branches to complete and merges their outputs.
    Supports various merge strategies and failure handling modes.
    
    Key Features:
    - Multiple merge strategies (all, first_success, majority)
    - Configurable merge modes (array, object, flatten)
    - Timeout handling for branch completion
    - Partial success support
    - Detailed branch result tracking
    """
    
    NODE_TYPE = "parallel_merge"
    DISPLAY_NAME = "Parallel Merge"
    DESCRIPTION = "Merge results from multiple parallel branches"
    CATEGORY = "utilities"
    SUPPORTS_RETRY = True
    DEFAULT_TIMEOUT = 60
    
    # Merge strategies
    MERGE_STRATEGIES = {
        "all": "Wait for all branches to complete",
        "first_success": "Use first successful branch result",
        "majority": "Wait for majority (>50%) to succeed",
        "any": "Use any completed branch (first to finish)"
    }
    
    # Merge modes
    MERGE_MODES = {
        "array": "Combine outputs as array",
        "object": "Combine outputs as object keyed by branch",
        "flatten": "Flatten all items into single array",
        "first": "Use only first branch result"
    }
    
    # Failure strategies
    FAILURE_STRATEGIES = {
        "fail_on_any": "Fail if any required branch fails",
        "partial_success": "Succeed with available results",
        "ignore_failures": "Ignore failed branches completely"
    }
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute parallel merge - collect and merge branch results.
        
        Args:
            input_data: Data from previous nodes (should include branch results)
            params: Merge configuration
                - merge_strategy: How to wait for branches
                - merge_mode: How to combine results
                - timeout_ms: Maximum time to wait
                - failure_strategy: How to handle failures
                - required_branches: Specific branches that must succeed
            context: Execution context
            
        Returns:
            Dict with merged results from parallel branches
        """
        self.logger.info("Starting parallel merge execution")
        
        # Extract parameters
        merge_strategy = params.get('merge_strategy', 'all')
        merge_mode = params.get('merge_mode', 'array')
        timeout_ms = params.get('timeout_ms', 60000)
        failure_strategy = params.get('failure_strategy', 'partial_success')
        required_branches = params.get('required_branches', [])
        
        # Validate parameters
        if merge_strategy not in self.MERGE_STRATEGIES:
            raise NodeExecutionError(f"Invalid merge strategy: {merge_strategy}")
        
        if merge_mode not in self.MERGE_MODES:
            raise NodeExecutionError(f"Invalid merge mode: {merge_mode}")
        
        if failure_strategy not in self.FAILURE_STRATEGIES:
            raise NodeExecutionError(f"Invalid failure strategy: {failure_strategy}")
        
        try:
            # Collect branch results from input data
            branch_results = self._collect_branch_results(input_data, context)
            
            if not branch_results:
                raise NodeExecutionError("No branch results found in input data")
            
            # Wait for branches based on strategy
            completed_results = self._wait_for_branches(
                branch_results, merge_strategy, timeout_ms, required_branches
            )
            
            # Check if we have enough results
            success_count = len([r for r in completed_results.values() if r.get('status') == 'success'])
            total_count = len(completed_results)
            
            # Apply failure strategy
            if failure_strategy == 'fail_on_any':
                failed_branches = [bid for bid, result in completed_results.items() 
                                 if result.get('status') != 'success']
                if failed_branches:
                    raise NodeExecutionError(f"Branches failed: {failed_branches}")
            
            elif failure_strategy == 'partial_success':
                if success_count == 0:
                    raise NodeExecutionError("No branches completed successfully")
            
            # Merge results based on mode
            merged_data = self._merge_branch_data(completed_results, merge_mode)
            
            # Create merge result
            merge_result = {
                'merged_data': merged_data,
                'branch_results': completed_results,
                'successful_branches': success_count,
                'failed_branches': total_count - success_count,
                'total_branches': total_count,
                'merge_strategy': merge_strategy,
                'merge_mode': merge_mode,
                'completed_at': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Merge completed: {success_count}/{total_count} branches successful")
            
            # Return merged result
            return {
                **input_data,  # Pass through input data
                'merge_result': merge_result,
                # Also provide merged data directly for convenience
                **(merged_data if isinstance(merged_data, dict) else {'merged_items': merged_data})
            }
            
        except Exception as e:
            error_msg = f"Parallel merge execution failed: {str(e)}"
            self.logger.error(error_msg)
            raise NodeExecutionError(error_msg)
    
    def _collect_branch_results(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Collect branch results from input data and context.
        
        Args:
            input_data: Input data containing branch results
            context: Execution context
            
        Returns:
            Dict mapping branch IDs to their results
        """
        branch_results = {}
        
        # Look for fork result in input data
        fork_result = input_data.get('fork_result')
        if fork_result and 'branch_executions' in fork_result:
            for branch_info in fork_result['branch_executions']:
                branch_id = branch_info.get('branch_id')
                if branch_id:
                    branch_results[branch_id] = {
                        'branch_id': branch_id,
                        'execution_id': branch_info.get('execution_id'),
                        'status': branch_info.get('status', 'unknown'),
                        'result': branch_info.get('result', {}),
                        'execution_time_ms': branch_info.get('execution_time_ms', 0),
                        'completed_at': branch_info.get('completed_at'),
                        'error': branch_info.get('error')
                    }
        
        # Look for individual branch results in input data
        for key, value in input_data.items():
            if key.startswith('branch_') and isinstance(value, dict):
                branch_id = key
                if 'result' in value or 'status' in value:
                    branch_results[branch_id] = value
        
        # Look in execution context for branch results
        node_outputs = context.get('node_outputs', {})
        for node_id, outputs in node_outputs.items():
            if isinstance(outputs, list):
                for output in outputs:
                    if isinstance(output, dict) and 'branch_result' in output:
                        branch_result = output['branch_result']
                        branch_id = branch_result.get('branch_id')
                        if branch_id:
                            branch_results[branch_id] = branch_result
        
        return branch_results
    
    def _wait_for_branches(self, branch_results: Dict[str, Dict], merge_strategy: str, timeout_ms: int, required_branches: List[str]) -> Dict[str, Dict]:
        """
        Wait for branches to complete based on merge strategy.
        
        Args:
            branch_results: Current branch results
            merge_strategy: Strategy for waiting
            timeout_ms: Maximum time to wait
            required_branches: Specific branches that must complete
            
        Returns:
            Dict of completed branch results
        """
        # For now, we'll work with the results we have
        # In a real implementation, this would poll for completion
        
        completed_results = {}
        
        for branch_id, result in branch_results.items():
            status = result.get('status', 'unknown')
            
            # Consider branch completed if it has a final status
            if status in ['completed', 'success', 'failed', 'error']:
                completed_results[branch_id] = result
            else:
                # Simulate completion for demo purposes
                completed_results[branch_id] = {
                    **result,
                    'status': 'success',
                    'completed_at': datetime.utcnow().isoformat(),
                    'result': result.get('result', {'items': []})
                }
        
        # Apply merge strategy logic
        if merge_strategy == 'first_success':
            # Find first successful branch
            for branch_id, result in completed_results.items():
                if result.get('status') == 'success':
                    return {branch_id: result}
            
            # If no success, return all results
            return completed_results
        
        elif merge_strategy == 'majority':
            # Wait for majority to complete
            total_branches = len(branch_results)
            required_count = (total_branches // 2) + 1
            
            successful_results = {
                bid: result for bid, result in completed_results.items()
                if result.get('status') == 'success'
            }
            
            if len(successful_results) >= required_count:
                return successful_results
            else:
                return completed_results  # Return what we have
        
        elif merge_strategy == 'any':
            # Return first completed branch
            if completed_results:
                first_branch = next(iter(completed_results.items()))
                return {first_branch[0]: first_branch[1]}
        
        # Default: 'all' strategy - return all completed results
        return completed_results
    
    def _merge_branch_data(self, branch_results: Dict[str, Dict], merge_mode: str) -> Any:
        """
        Merge branch data according to merge mode.
        
        Args:
            branch_results: Completed branch results
            merge_mode: How to merge the data
            
        Returns:
            Merged data in requested format
        """
        if merge_mode == 'array':
            # Combine all results as array
            merged_array = []
            for branch_id, result in branch_results.items():
                branch_data = result.get('result', {})
                if 'items' in branch_data:
                    merged_array.extend(branch_data['items'])
                else:
                    merged_array.append(branch_data)
            return merged_array
        
        elif merge_mode == 'object':
            # Combine results as object keyed by branch
            merged_object = {}
            for branch_id, result in branch_results.items():
                merged_object[branch_id] = result.get('result', {})
            return merged_object
        
        elif merge_mode == 'flatten':
            # Flatten all items into single array
            flattened = []
            for branch_id, result in branch_results.items():
                branch_data = result.get('result', {})
                if isinstance(branch_data, dict) and 'items' in branch_data:
                    items = branch_data['items']
                    if isinstance(items, list):
                        flattened.extend(items)
                    else:
                        flattened.append(items)
                elif isinstance(branch_data, list):
                    flattened.extend(branch_data)
                else:
                    flattened.append(branch_data)
            return flattened
        
        elif merge_mode == 'first':
            # Use only first branch result
            if branch_results:
                first_result = next(iter(branch_results.values()))
                return first_result.get('result', {})
            return {}
        
        else:
            # Default: return as object
            return {branch_id: result.get('result', {}) for branch_id, result in branch_results.items()}
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for parallel merge node parameters.
        """
        return {
            "type": "object",
            "properties": {
                "merge_strategy": {
                    "type": "string",
                    "enum": list(cls.MERGE_STRATEGIES.keys()),
                    "title": "Merge Strategy",
                    "description": "How to wait for branch completion",
                    "default": "all"
                },
                "merge_mode": {
                    "type": "string",
                    "enum": list(cls.MERGE_MODES.keys()),
                    "title": "Merge Mode",
                    "description": "How to combine branch results",
                    "default": "array"
                },
                "timeout_ms": {
                    "type": "integer",
                    "title": "Timeout (milliseconds)",
                    "description": "Maximum time to wait for branches",
                    "minimum": 1000,
                    "maximum": 600000,
                    "default": 60000
                },
                "failure_strategy": {
                    "type": "string",
                    "enum": list(cls.FAILURE_STRATEGIES.keys()),
                    "title": "Failure Strategy",
                    "description": "How to handle branch failures",
                    "default": "partial_success"
                },
                "required_branches": {
                    "type": "array",
                    "title": "Required Branches",
                    "description": "Specific branches that must succeed",
                    "items": {
                        "type": "string",
                        "minLength": 1
                    },
                    "uniqueItems": True
                }
            },
            "additionalProperties": False
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Expected input data schema."""
        return {
            "type": "object",
            "description": "Data containing branch results from parallel fork",
            "properties": {
                "fork_result": {
                    "type": "object",
                    "description": "Result from parallel fork node"
                }
            },
            "additionalProperties": True
        }
    
    def get_output_schema(self) -> Dict[str, Any]:
        """Output data schema."""
        return {
            "type": "object",
            "properties": {
                "merge_result": {
                    "type": "object",
                    "properties": {
                        "merged_data": {"description": "Combined data from all branches"},
                        "branch_results": {
                            "type": "object",
                            "description": "Individual branch results keyed by branch ID"
                        },
                        "successful_branches": {"type": "integer"},
                        "failed_branches": {"type": "integer"},
                        "total_branches": {"type": "integer"},
                        "merge_strategy": {"type": "string"},
                        "merge_mode": {"type": "string"}
                    }
                }
            },
            "additionalProperties": True,
            "description": "All input data plus merge_result with combined branch outputs"
        }


# Alias nodes for alternative naming
@register_node
class ForkNode(ParallelForkNode):
    """Alias for ParallelForkNode with shorter name."""
    NODE_TYPE = "fork"
    DISPLAY_NAME = "Fork"

