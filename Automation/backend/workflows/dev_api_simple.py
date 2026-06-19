"""
Simple API views for system status and node management.
These provide basic admin functionality for monitoring the system.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_status_simple(request):
    """Return basic system status information."""
    return Response({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_node_registry_simple(request):
    """Refresh the node registry."""
    try:
        from .nodes import node_registry
        node_types = list(node_registry.get_all_nodes().keys()) if hasattr(node_registry, 'get_all_nodes') else []
        return Response({
            'status': 'refreshed',
            'node_count': len(node_types),
            'nodes': node_types,
        })
    except Exception as e:
        logger.error(f"Failed to refresh node registry: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def node_list_simple(request):
    """List all registered nodes."""
    try:
        from .nodes import node_registry
        nodes = node_registry.get_all_nodes() if hasattr(node_registry, 'get_all_nodes') else {}
        node_list = []
        for node_type, node_class in nodes.items():
            node_list.append({
                'type': node_type,
                'name': getattr(node_class, 'display_name', node_type),
                'description': getattr(node_class, 'description', ''),
            })
        return Response({'nodes': node_list, 'count': len(node_list)})
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def node_detail_simple(request, node_type):
    """Get details for a specific node type."""
    try:
        from .nodes import node_registry
        nodes = node_registry.get_all_nodes() if hasattr(node_registry, 'get_all_nodes') else {}
        node_class = nodes.get(node_type)
        if not node_class:
            return Response({'error': f'Node type "{node_type}" not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'type': node_type,
            'name': getattr(node_class, 'display_name', node_type),
            'description': getattr(node_class, 'description', ''),
        })
    except Exception as e:
        logger.error(f"Failed to get node detail: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def node_test_simple(request):
    """Test a node with sample data."""
    node_type = request.data.get('node_type')
    if not node_type:
        return Response({'error': 'node_type is required'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'status': 'test_complete',
        'node_type': node_type,
        'message': f'Node {node_type} test placeholder',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_node_status_simple(request, node_type):
    """Update a node's status (enable/disable)."""
    enabled = request.data.get('enabled', True)
    return Response({
        'status': 'updated',
        'node_type': node_type,
        'enabled': enabled,
    })
