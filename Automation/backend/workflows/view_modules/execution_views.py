"""
Execution Engine API Views

This module provides API endpoints for testing and managing the execution engine.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from typing import Dict, Any
import logging
import uuid

from ..execution.core_engine import execute_workflow
from ..execution.django_executor import test_workflow_execution, execute_workflow_by_id
from ..models import Workflow, WorkflowExecution
from ..nodes import node_registry


logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_workflow_execution_api(request):
    """
    Test workflow execution without creating database records.
    
    This endpoint allows testing workflows using the core execution engine
    without persisting anything to the database.
    
    Request body:
        {
            "workflow_definition": {
                "meta": {...},
                "trigger": {...},
                "nodes": {...},
                "connections": {...}
            },
            "trigger_input": {...}
        }
        
    Returns:
        Complete execution result with node details
    """
    try:
        workflow_definition = request.data.get('workflow_definition')
        trigger_input = request.data.get('trigger_input', {})
        
        if not workflow_definition:
            return Response(
                {'error': 'workflow_definition is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate workflow structure
        required_keys = ['meta', 'trigger', 'nodes', 'connections']
        for key in required_keys:
            if key not in workflow_definition:
                return Response(
                    {'error': f'workflow_definition missing required key: {key}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Test execution using core engine
        result = test_workflow_execution(workflow_definition, trigger_input)
        
        return Response({
            'success': result.success,
            'final_output': result.final_output,
            'execution_time_ms': result.total_execution_time_ms,
            'node_results': [
                {
                    'node_id': nr.node_id,
                    'node_type': nr.node_type,
                    'success': nr.success,
                    'output_data': nr.output_data,
                    'error_message': nr.error_message,
                    'execution_time_ms': nr.execution_time_ms
                }
                for nr in result.node_results
            ],
            'error_message': result.error_message,
            'test_mode': True
        })
        
    except Exception as e:
        logger.error(f"Test workflow execution failed: {e}")
        return Response(
            {'error': f'Test execution failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_workflow_api(request, workflow_id: str):
    """
    Execute a workflow by ID, creating a new execution.
    
    Args:
        workflow_id: UUID of the workflow to execute
        
    Request body:
        {
            "trigger_input": {...}  # Optional input data for trigger
        }
        
    Returns:
        Execution result with database record created
    """
    try:
        trigger_input = request.data.get('trigger_input', {})
        user_id = str(request.user.id)
        
        # Execute workflow
        result = execute_workflow_by_id(
            workflow_id=workflow_id,
            trigger_input=trigger_input,
            user_id=user_id
        )
        
        return Response({
            'success': result.success,
            'final_output': result.final_output,
            'execution_time_ms': result.total_execution_time_ms,
            'node_count': len(result.node_results),
            'success_count': sum(1 for nr in result.node_results if nr.success),
            'failure_count': sum(1 for nr in result.node_results if not nr.success),
            'error_message': result.error_message
        })
        
    except Workflow.DoesNotExist:
        return Response(
            {'error': f'Workflow {workflow_id} not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return Response(
            {'error': f'Execution failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_workflow_definition(request):
    """
    Validate a workflow definition without executing it.
    
    Query parameters:
        workflow_definition: JSON string of workflow definition
        
    Returns:
        Validation result with any errors
    """
    try:
        import json
        
        workflow_definition_str = request.GET.get('workflow_definition')
        if not workflow_definition_str:
            return Response(
                {'error': 'workflow_definition query parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            workflow_definition = json.loads(workflow_definition_str)
        except json.JSONDecodeError as e:
            return Response(
                {'error': f'Invalid JSON in workflow_definition: {e}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate structure
        from ..execution.core_engine import WorkflowExecutionEngine
        engine = WorkflowExecutionEngine()
        
        validation_errors = []
        
        try:
            engine._validate_workflow_structure(workflow_definition)
        except ValueError as e:
            validation_errors.append(f"Structure validation: {e}")
        
        try:
            nodes = workflow_definition.get('nodes', {})
            connections = workflow_definition.get('connections', {})
            engine._validate_dag_structure(nodes, connections)
        except ValueError as e:
            validation_errors.append(f"DAG validation: {e}")
        
        # Validate node types
        node_errors = node_registry.validate_workflow_nodes(workflow_definition)
        validation_errors.extend(node_errors)
        
        return Response({
            'valid': len(validation_errors) == 0,
            'errors': validation_errors,
            'node_count': len(workflow_definition.get('nodes', {})),
            'connection_count': sum(len(targets) for targets in workflow_definition.get('connections', {}).values())
        })
        
    except Exception as e:
        logger.error(f"Workflow validation failed: {e}")
        return Response(
            {'error': f'Validation failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_execution_engine_info(request):
    """
    Get information about the execution engine.
    
    Returns:
        Engine information and statistics
    """
    try:
        # Get node registry stats
        registry_stats = node_registry.get_registry_stats()
        
        # Get recent execution stats (if available)
        recent_executions = WorkflowExecution.objects.filter(
            created_by=request.user
        ).order_by('-created_at')[:10]
        
        execution_stats = {
            'recent_count': recent_executions.count(),
            'recent_executions': [
                {
                    'id': str(exec.id),
                    'workflow_name': exec.workflow.name,
                    'status': exec.status,
                    'created_at': exec.created_at.isoformat() if exec.created_at else None,
                    'completed_at': exec.completed_at.isoformat() if exec.completed_at else None
                }
                for exec in recent_executions
            ]
        }
        
        return Response({
            'engine_info': {
                'name': 'Core Workflow Execution Engine',
                'version': '1.0.0',
                'features': [
                    'DAG-based execution',
                    'Node registry integration',
                    'Fail-fast error handling',
                    'Execution context flow',
                    'Django model integration'
                ]
            },
            'node_registry': registry_stats,
            'execution_stats': execution_stats
        })
        
    except Exception as e:
        logger.error(f"Failed to get engine info: {e}")
        return Response(
            {'error': f'Failed to get engine info: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_sample_workflow(request):
    """
    Create a sample workflow for testing the execution engine.
    
    Returns:
        Created workflow definition
    """
    try:
        sample_workflow = {
            "meta": {
                "name": "Sample Test Workflow",
                "description": "A sample workflow for testing the execution engine",
                "version": "1.0.0",
                "active": True
            },
            "trigger": {
                "id": "manual_trigger_1",
                "type": "manual_trigger",
                "name": "Manual Start",
                "params": {
                    "test_data": {
                        "message": "Hello from sample workflow!",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }
            },
            "nodes": {
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "name": "Log Message",
                    "params": {
                        "message": "Processing: {{message}}",
                        "level": "info",
                        "include_data": True
                    }
                },
                "delay_1": {
                    "id": "delay_1",
                    "type": "delay",
                    "name": "Short Delay",
                    "params": {
                        "type": "seconds",
                        "value": 1
                    }
                },
                "transform_1": {
                    "id": "transform_1",
                    "type": "data_transform",
                    "name": "Add Metadata",
                    "params": {
                        "transformations": [
                            {
                                "type": "set_field",
                                "field": "processed_by",
                                "value": "sample_workflow"
                            },
                            {
                                "type": "set_field",
                                "field": "processed_at",
                                "value": "{{variables.execution.created_at}}"
                            }
                        ]
                    }
                }
            },
            "connections": {
                "manual_trigger_1": ["logger_1"],
                "logger_1": ["delay_1"],
                "delay_1": ["transform_1"],
                "transform_1": []
            }
        }
        
        return Response({
            'workflow_definition': sample_workflow,
            'description': 'Sample workflow with manual trigger, logger, delay, and transform nodes',
            'node_count': len(sample_workflow['nodes']),
            'estimated_execution_time': '~1-2 seconds'
        })
        
    except Exception as e:
        logger.error(f"Failed to create sample workflow: {e}")
        return Response(
            {'error': f'Failed to create sample workflow: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )