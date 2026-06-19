"""
Production Security Middleware
Critical security controls for production deployment
"""
import time
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from .models import Membership

logger = logging.getLogger('security')


class TenantIsolationMiddleware(MiddlewareMixin):
    """
    CRITICAL: Enforce strict tenant isolation for all authenticated requests
    Prevents cross-tenant data access
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Get user's tenant from membership
            try:
                membership = Membership.objects.select_related('organization', 'organization__tenant').filter(
                    user=request.user
                ).first()
                
                if membership:
                    request.tenant = membership.organization.tenant
                    request.organization = membership.organization
                    request.user_role = membership.role
                else:
                    # User without tenant access - deny
                    logger.warning(f"User {request.user.id} has no tenant membership")
                    return JsonResponse({
                        'error': 'Access denied - no tenant membership'
                    }, status=403)
                    
            except Exception as e:
                logger.error(f"Tenant isolation check failed: {e}")
                return JsonResponse({
                    'error': 'Access denied - tenant check failed'
                }, status=403)


class PayloadSizeLimitMiddleware(MiddlewareMixin):
    """
    CRITICAL: Prevent large payload attacks
    Configurable limits per endpoint type
    """
    
    def process_request(self, request):
        # Skip for GET requests
        if request.method == 'GET':
            return None
            
        # Different limits for different endpoints
        limits = {
            '/api/v1/executions/': 10 * 1024 * 1024,  # 10MB for executions
            '/webhook/': 5 * 1024 * 1024,             # 5MB for generic webhooks
            '/api/webhooks/': 5 * 1024 * 1024,        # 5MB for Telegram/Integrations
            '/api/v1/workflows/': 2 * 1024 * 1024,    # 2MB for workflows
            '/api/user/profile/': 10 * 1024 * 1024,   # 10MB for profiles/photos
            'default': 1 * 1024 * 1024                # 1MB default
        }
        
        # Find matching limit
        max_size = limits['default']
        for path, limit in limits.items():
            if path != 'default' and request.path.startswith(path):
                max_size = limit
                break
        
        # Check content length
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                size = int(content_length)
                if size > max_size:
                    logger.warning(
                        f"Payload too large: {size} bytes (max: {max_size}) "
                        f"from {request.META.get('REMOTE_ADDR')} to {request.path}"
                    )
                    return JsonResponse({
                        'error': 'Payload too large',
                        'max_size_mb': max_size // (1024 * 1024),
                        'received_size_mb': size // (1024 * 1024)
                    }, status=413)
            except (ValueError, TypeError):
                pass


class SecurityAuditMiddleware(MiddlewareMixin):
    """
    CRITICAL: Log security-relevant events
    Audit trail for compliance and incident response
    """
    
    def process_request(self, request):
        # Log sensitive operations
        sensitive_paths = [
            '/api/v1/credentials/',
            '/api/v1/executions/',
            '/webhook/',
            '/admin/'
        ]
        
        if any(request.path.startswith(path) for path in sensitive_paths):
            logger.info(
                f"AUDIT: {request.method} {request.path} "
                f"user={getattr(request.user, 'id', 'anonymous')} "
                f"ip={request.META.get('REMOTE_ADDR')} "
                f"user_agent={request.META.get('HTTP_USER_AGENT', '')[:100]}"
            )
    
    def process_response(self, request, response):
        # Log failed authentication attempts
        if response.status_code == 401:
            logger.warning(
                f"SECURITY: Authentication failed for {request.path} "
                f"from {request.META.get('REMOTE_ADDR')}"
            )
        
        # Log permission denied
        elif response.status_code == 403:
            logger.warning(
                f"SECURITY: Permission denied for {request.path} "
                f"user={getattr(request.user, 'id', 'anonymous')} "
                f"from {request.META.get('REMOTE_ADDR')}"
            )
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    CRITICAL: Basic rate limiting protection
    Prevents brute force and DoS attacks
    """
    
    def process_request(self, request):
        # Skip for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health/':
            return None
        
        # Get client identifier
        client_ip = request.META.get('REMOTE_ADDR')
        user_id = getattr(request.user, 'id', None) if request.user.is_authenticated else None
        
        # Create cache key
        # Create cache key
        if user_id:
            cache_key = f"rate_limit:user:{user_id}"
            limit = 50000  # High limit for auth users
        else:
            cache_key = f"rate_limit:ip:{client_ip}"
            limit = 5000   # High limit for IP (dev friendly)
        
        # Check current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            logger.warning(
                f"SECURITY: Rate limit exceeded for {cache_key} "
                f"({current_count}/{limit}) on {request.path}"
            )
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'retry_after': 60  # 1 minute retry
            }, status=429)
        
        # Increment counter
        cache.set(cache_key, current_count + 1, 60)  # 1 minute window


class CSRFEnhancementMiddleware(MiddlewareMixin):
    """
    CRITICAL: Enhanced CSRF protection
    Additional validation for API endpoints
    """
    
    def process_request(self, request):
        # Skip for safe methods or if DEBUG is enabled for local testing
        if request.method in ['GET', 'HEAD', 'OPTIONS'] or settings.DEBUG:
            return None
        
        # Skip for webhook endpoints (they use HMAC/BotToken)
        if request.path.startswith('/webhook/') or request.path.startswith('/api/webhooks/'):
            return None
        
        # Skip for auth endpoints (login/OTP - no token available yet, rate-limited at view level)
        if request.path.startswith('/api/auth/'):
            return None
        
        # For API endpoints, require either CSRF token or proper API authentication
        if request.path.startswith('/api/'):
            # Check for API authentication
            auth_header = request.META.get('HTTP_AUTHORIZATION')
            if auth_header and auth_header.startswith('Bearer '):
                return None  # API token authentication
            
            # Otherwise, require CSRF token
            csrf_token = request.META.get('HTTP_X_CSRFTOKEN')
            if not csrf_token:
                logger.warning(
                    f"SECURITY: Missing CSRF token for API request to {request.path} "
                    f"from {request.META.get('REMOTE_ADDR')}"
                )
                return JsonResponse({
                    'error': 'CSRF token required for API requests'
                }, status=403)

class InputSanitizationMiddleware(MiddlewareMixin):
    """
    CRITICAL: Global Input Sanitization
    Strips dangerous characters from input to prevent XSS/Injection
    """
    
    def process_request(self, request):
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Sanitize POST data if it's form-encoded (JSON is handled by parsers/validation)
            if request.content_type == 'application/x-www-form-urlencoded':
                request.POST = request.POST.copy()
                for key, value in request.POST.items():
                    if isinstance(value, str):
                        # Basic sanitization - strip null bytes and potential script tags
                        cleaned = value.replace('\0', '').replace('<script>', '')
                        request.POST[key] = cleaned
