"""
Node System API Views

This module provides API endpoints for the node system.
Used by the frontend to discover available nodes and their schemas.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from typing import Dict, Any
import logging

from ..nodes import node_registry, BaseNode, NodeExecutionError


logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_node_types(request):
    """
    Get all available node types with their schemas.
    
    This endpoint is used by the frontend workflow builder to:
    1. Populate the node palette
    2. Generate parameter forms
    3. Validate workflow definitions
    
    Returns:
        Dict mapping node types to their complete schema information
    """
    try:
        # Get all node schemas from registry
        schemas = node_registry.get_node_schemas()
        
        # Add registry statistics
        stats = node_registry.get_registry_stats()
        
        return Response({
            'node_types': list(schemas.values()),  # Return List for Frontend compatibility
            'registry_stats': stats,
            'total_nodes': len(schemas)
        })
        
    except Exception as e:
        logger.error(f"Error getting node types: {e}")
        return Response(
            {'error': f'Failed to get node types: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_node_categories(request):
    """
    Get nodes organized by category.
    
    Returns:
        Dict mapping categories to lists of node types
    """
    try:
        schemas = node_registry.get_node_schemas()
        
        # Organize by category
        categories = {}
        for node_type, schema in schemas.items():
            category = schema.get('category', 'uncategorized')
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'type': node_type,
                'name': schema.get('name', node_type),
                'description': schema.get('description', ''),
                'supports_retry': schema.get('supports_retry', True),
                'default_timeout': schema.get('default_timeout', 30)
            })
        
        return Response({
            'categories': categories,
            'category_counts': {cat: len(nodes) for cat, nodes in categories.items()}
        })
        
    except Exception as e:
        logger.error(f"Error getting node categories: {e}")
        return Response(
            {'error': f'Failed to get node categories: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_node_schema(request, node_type: str):
    """
    Get detailed schema for a specific node type.
    
    Args:
        node_type: The node type to get schema for
        
    Returns:
        Complete schema information for the node type
    """
    try:
        if not node_registry.has_node_type(node_type):
            return Response(
                {'error': f'Unknown node type: {node_type}'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        schemas = node_registry.get_node_schemas()
        schema = schemas[node_type]
        
        return Response({
            'node_type': node_type,
            'schema': schema
        })
        
    except Exception as e:
        logger.error(f"Error getting schema for {node_type}: {e}")
        return Response(
            {'error': f'Failed to get schema for {node_type}: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_node_params(request):
    """
    Validate node parameters against node schema.
    
    Request body:
        {
            "node_type": "http_request",
            "params": {"url": "https://api.example.com", "method": "GET"}
        }
        
    Returns:
        Validation result with any errors
    """
    try:
        node_type = request.data.get('node_type')
        params = request.data.get('params', {})
        
        if not node_type:
            return Response(
                {'error': 'node_type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not node_registry.has_node_type(node_type):
            return Response(
                {'error': f'Unknown node type: {node_type}'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get node class and validate parameters
        node_class = node_registry.get_node_class(node_type)
        node_instance = node_class()
        
        is_valid = node_instance.validate_params(params)
        
        validation_result = {
            'valid': is_valid,
            'node_type': node_type,
            'params': params
        }
        
        if not is_valid:
            validation_result['errors'] = ['Parameter validation failed']
        
        return Response(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating node params: {e}")
        return Response(
            {'error': f'Validation failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_node_execution(request):
    """
    Test node execution with provided input data and parameters.
    
    This is used for testing nodes in the workflow builder.
    
    Request body:
        {
            "node_type": "http_request",
            "params": {"url": "https://httpbin.org/get", "method": "GET"},
            "input_data": {"test": true},
            "context": {"execution_id": "test"}
        }
        
    Returns:
        Node execution result or error
    """
    try:
        node_type = request.data.get('node_type')
        params = request.data.get('params', {})
        input_data = request.data.get('input_data', {})
        context = request.data.get('context', {})
        
        if not node_type:
            return Response(
                {'error': 'node_type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not node_registry.has_node_type(node_type):
            return Response(
                {'error': f'Unknown node type: {node_type}'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Add test context
        test_context = {
            'test_mode': True,
            'user_id': str(request.user.id),
            'execution_timestamp': '2024-01-01T00:00:00Z',
            **context
        }
        
        # Get node class and execute
        node_class = node_registry.get_node_class(node_type)
        node_instance = node_class()
        
        # Validate parameters first
        if not node_instance.validate_params(params):
            return Response(
                {'error': 'Invalid parameters'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute node
        result = node_instance.run(input_data, params, test_context)
        
        return Response({
            'success': True,
            'node_type': node_type,
            'input_data': input_data,
            'params': params,
            'output_data': result,
            'test_mode': True
        })
        
    except NodeExecutionError as e:
        logger.warning(f"Node execution failed during test: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'error_type': 'NodeExecutionError',
            'node_type': node_type,
            'test_mode': True
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error testing node execution: {e}")
        return Response(
            {'error': f'Test execution failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_workflow_nodes(request):
    """
    Validate all nodes in a workflow definition.
    
    Request body:
        {
            "workflow_definition": {
                "trigger": {"type": "webhook_trigger", "params": {...}},
                "nodes": {
                    "node1": {"type": "http_request", "params": {...}}
                }
            }
        }
        
    Returns:
        Validation result with any errors
    """
    try:
        workflow_definition = request.data.get('workflow_definition', {})
        
        if not workflow_definition:
            return Response(
                {'error': 'workflow_definition is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate using registry
        errors = node_registry.validate_workflow_nodes(workflow_definition)
        
        validation_result = {
            'valid': len(errors) == 0,
            'errors': errors,
            'nodes_checked': []
        }
        
        # Check trigger
        if 'trigger' in workflow_definition:
            trigger_type = workflow_definition['trigger'].get('type')
            validation_result['nodes_checked'].append(f"trigger:{trigger_type}")
        
        # Check nodes
        if 'nodes' in workflow_definition:
            for node_id, node_def in workflow_definition['nodes'].items():
                node_type = node_def.get('type')
                validation_result['nodes_checked'].append(f"{node_id}:{node_type}")
        
        return Response(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating workflow nodes: {e}")
        return Response(
            {'error': f'Workflow validation failed: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_registry_stats(request):
    """
    Get node registry statistics for monitoring.
    
    Returns:
        Registry statistics and health information
    """
    try:
        stats = node_registry.get_registry_stats()
        
        # Add additional health information
        health_info = {
            'registry_healthy': True,
            'auto_discovery_completed': stats.get('auto_discovered', False),
            'total_categories': len(stats.get('categories', {})),
            'largest_category': max(stats.get('categories', {}).items(), key=lambda x: x[1], default=('none', 0))
        }
        
        return Response({
            'stats': stats,
            'health': health_info,
            'timestamp': '2024-01-01T00:00:00Z'  # Would use actual timestamp
        })
        
    except Exception as e:
        logger.error(f"Error getting registry stats: {e}")
        return Response(
            {'error': f'Failed to get registry stats: {e}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Legacy compatibility endpoints (if needed)
@api_view(['GET'])
def node_types(request):
    """Legacy endpoint for node types."""
    return get_node_types(request)


@api_view(['GET'])
def node_schemas(request):
    """Legacy endpoint for node schemas."""
    return get_node_types(request)


@api_view(['POST'])
def test_node(request):
    """Legacy endpoint for node testing."""
    return test_node_execution(request)