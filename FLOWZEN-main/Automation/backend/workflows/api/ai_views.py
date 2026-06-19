
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
from workflows.ai_providers.universal_engine import UniversalAIEngine

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def run_ai(request):
    """
    Phase 19: Universal AI API Endpoint.
    Public-facing API to run AI workflows.
    Authentication: Basic Token (Placeholder).
    """
    try:
        data = json.loads(request.body)
        
        # 1. Parse Payload
        brain_id = data.get('brain_id')
        user_prompt = data.get('user_prompt')
        system_prompt = data.get('system_prompt', '')
        response_mode = data.get('response_mode', 'text')
        
        if not brain_id or not user_prompt:
             return JsonResponse({"success": False, "error": "Missing brain_id or user_prompt"}, status=400)
             
        # 2. Execute via Universal Engine
        result = UniversalAIEngine.run(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            response_mode=response_mode,
            credential_id=brain_id,
            context={"api_request": True}
        )
        
        # 3. Return Standardized Response
        if result['success']:
             return JsonResponse(result['output'])
        else:
             return JsonResponse({"error": result['error']}, status=500)

    except Exception as e:
        logger.error(f"API Error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
