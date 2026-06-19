import logging
import functools
import json
from django.http import JsonResponse
from pydantic import ValidationError, BaseModel

logger = logging.getLogger('validation')

def validate_input(schema_model):
    """
    Decorator to validate request body against a Pydantic model.
    Usage:
        @validate_input(UserSignupSchema)
        def my_view(request):
            data = request.validated_data
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Handle standard Django requests
                if request.content_type == 'application/json':
                    try:
                        data = json.loads(request.body)
                    except json.JSONDecodeError:
                        return JsonResponse({
                            "success": False,
                            "error": {
                                "code": "INVALID_JSON",
                                "message": "Invalid JSON payload"
                            }
                        }, status=400)
                else:
                    data = request.POST.dict()

                # Validate data
                validated = schema_model(**data)
                
                # Attach validated object to request
                request.validated_data = validated
                
                return view_func(request, *args, **kwargs)
                
            except ValidationError as e:
                # Format Pydantic errors
                errors = []
                for err in e.errors():
                    loc = ".".join(str(l) for l in err['loc'])
                    errors.append({
                        "field": loc,
                        "message": err['msg'],
                        "type": err['type']
                    })
                
                logger.warning(f"Validation failed for {request.path}: {errors}")
                
                return JsonResponse({
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Input validation failed",
                        "details": errors
                    }
                }, status=400)
                
            except Exception as e:
                logger.error(f"Validation decorator error: {e}")
                return JsonResponse({
                    "success": False,
                    "error": {
                        "code": "SERVER_ERROR",
                        "message": "Internal server error during validation"
                    }
                }, status=500)
                
        return wrapper
    return decorator

# --- Standard Schemas ---

class PaginationSchema(BaseModel):
    page: int = 1
    page_size: int = 50
    search: str = ""
