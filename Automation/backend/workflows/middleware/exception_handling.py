"""
Global Exception Handling Middleware

This middleware provides comprehensive error handling to prevent crashes
and ensure stable API responses.
"""

import logging
import traceback
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, OperationalError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


class GlobalExceptionHandlingMiddleware:
    """
    Global exception handling middleware to catch and handle all unhandled exceptions.
    
    This middleware ensures that:
    1. No raw 500 errors are returned to users
    2. All exceptions are properly logged
    3. Structured error responses are returned for API calls
    4. Admin interface errors are handled gracefully
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return self.handle_exception(request, e)
    
    def handle_exception(self, request, exception):
        """
        Handle any unhandled exception and return appropriate response.
        """
        # Log the exception with full traceback
        logger.error(
            f"Unhandled exception in {request.method} {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'user': getattr(request, 'user', None),
                'exception_type': type(exception).__name__,
            }
        )
        
        # Determine if this is an API request
        is_api_request = (
            request.path.startswith('/api/') or
            request.content_type == 'application/json' or
            'application/json' in request.META.get('HTTP_ACCEPT', '')
        )
        
        # Handle specific exception types
        if isinstance(exception, ValidationError):
            return self._handle_validation_error(request, exception, is_api_request)
        elif isinstance(exception, PermissionDenied):
            return self._handle_permission_denied(request, exception, is_api_request)
        elif isinstance(exception, IntegrityError):
            return self._handle_integrity_error(request, exception, is_api_request)
        elif isinstance(exception, OperationalError):
            return self._handle_operational_error(request, exception, is_api_request)
        else:
            return self._handle_generic_error(request, exception, is_api_request)
    
    def _handle_validation_error(self, request, exception, is_api_request):
        """Handle Django validation errors."""
        if is_api_request:
            return JsonResponse({
                'error': 'Validation failed',
                'error_type': 'VALIDATION_ERROR',
                'detail': str(exception),
                'code': 'VALIDATION_ERROR'
            }, status=400)
        else:
            return HttpResponse(
                f"Validation Error: {str(exception)}",
                status=400,
                content_type='text/plain'
            )
    
    def _handle_permission_denied(self, request, exception, is_api_request):
        """Handle permission denied errors."""
        if is_api_request:
            return JsonResponse({
                'error': 'Permission denied',
                'error_type': 'PERMISSION_DENIED',
                'detail': str(exception) or 'You do not have permission to access this resource',
                'code': 'PERMISSION_DENIED'
            }, status=403)
        else:
            return HttpResponse(
                f"Permission Denied: {str(exception)}",
                status=403,
                content_type='text/plain'
            )
    
    def _handle_integrity_error(self, request, exception, is_api_request):
        """Handle database integrity errors."""
        if is_api_request:
            return JsonResponse({
                'error': 'Database constraint violation',
                'error_type': 'INTEGRITY_ERROR',
                'detail': 'The operation violates database constraints',
                'code': 'INTEGRITY_ERROR'
            }, status=400)
        else:
            return HttpResponse(
                "Database Error: The operation could not be completed due to data constraints.",
                status=400,
                content_type='text/plain'
            )
    
    def _handle_operational_error(self, request, exception, is_api_request):
        """Handle database operational errors."""
        if is_api_request:
            return JsonResponse({
                'error': 'Database operation failed',
                'error_type': 'DATABASE_ERROR',
                'detail': 'A database error occurred. Please try again later.',
                'code': 'DATABASE_ERROR'
            }, status=503)
        else:
            return HttpResponse(
                "Database Error: The service is temporarily unavailable. Please try again later.",
                status=503,
                content_type='text/plain'
            )
    
    def _handle_generic_error(self, request, exception, is_api_request):
        """Handle all other unhandled exceptions."""
        if is_api_request:
            # For API requests, return structured JSON error
            error_response = {
                'error': 'Internal server error',
                'error_type': 'INTERNAL_ERROR',
                'detail': 'An unexpected error occurred. Please try again later.',
                'code': 'INTERNAL_ERROR'
            }
            
            # In debug mode, include more details
            if settings.DEBUG:
                error_response['debug_info'] = {
                    'exception_type': type(exception).__name__,
                    'exception_message': str(exception),
                    'traceback': traceback.format_exc()
                }
            
            return JsonResponse(error_response, status=500)
        else:
            # For regular requests, return HTML error page
            if settings.DEBUG:
                # In debug mode, show detailed error
                return HttpResponse(
                    f"Internal Server Error: {type(exception).__name__}: {str(exception)}\n\n{traceback.format_exc()}",
                    status=500,
                    content_type='text/plain'
                )
            else:
                # In production, show generic error
                return HttpResponse(
                    "Internal Server Error: An unexpected error occurred. Please try again later.",
                    status=500,
                    content_type='text/plain'
                )


class SafeAdminMiddleware:
    """
    Middleware specifically for Django Admin to handle admin-specific errors.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to admin requests
        if not request.path.startswith('/admin/'):
            return self.get_response(request)
        
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return self.handle_admin_exception(request, e)
    
    def handle_admin_exception(self, request, exception):
        """
        Handle exceptions in Django Admin interface.
        """
        logger.error(
            f"Admin exception in {request.method} {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'user': getattr(request, 'user', None),
                'exception_type': type(exception).__name__,
            }
        )
        
        # Return a safe admin error page
        error_message = "An error occurred in the admin interface."
        if settings.DEBUG:
            error_message += f" Error: {type(exception).__name__}: {str(exception)}"
        
        return HttpResponse(
            f"""
            <html>
            <head><title>Admin Error</title></head>
            <body>
                <h1>Admin Error</h1>
                <p>{error_message}</p>
                <p><a href="/admin/">Return to Admin Home</a></p>
            </body>
            </html>
            """,
            status=500,
            content_type='text/html'
        )


def custom_drf_exception_handler(exc, context):
    """
    Custom Django REST Framework exception handler.
    Returns:
        {
            "success": false,
            "error": {
                "code": "ERROR_CODE",
                "message": "Error message",
                "details": ...
            },
            "timestamp": ...
        }
    """
    import time
    
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'success': False,
            'error': {
                'code': type(exc).__name__.upper(),
                'message': str(exc) if str(exc) else "An error occurred",
                'details': response.data
            },
            'timestamp': time.time()
        }
        
        # Handle specific DRF/Django errors for cleaner messages
        if isinstance(response.data, dict) and 'detail' in response.data:
            custom_response_data['error']['message'] = response.data['detail']
            # Remove redundant detail if it's just the message
            if len(response.data) == 1:
                custom_response_data['error']['details'] = None
        
        # Add debug info if enabled
        if settings.DEBUG:
            custom_response_data['debug_info'] = {
                'exception_type': type(exc).__name__,
                'view': context.get('view').__class__.__name__ if context.get('view') else None,
                'method': context.get('request').method if context.get('request') else None,
            }
            
        response.data = custom_response_data
        
    return response