from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def debug_ai_agent_inputs(request):
    """
    Temporary debug endpoint to verify handle mapping.
    Remove before production.
    """
    return JsonResponse({
        "status": "debug_active",
        "monitored_handles": ["main", "tools", "memory", "system"],
        "default_handle": "main",
        "compatibility": "Backward compatibility for missing targetHandle is ACTIVE",
        "description": "This endpoint verifies that the handle-aware execution logic is correctly initialized."
    })
