"""
Performance and monitoring middleware
"""
import time
import logging
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.db import connection

logger = logging.getLogger('performance')

class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Monitor request performance and log slow requests"""
    
    def process_request(self, request):
        request.start_time = time.time()
        request.queries_before = len(connection.queries)
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            queries_count = len(connection.queries) - getattr(request, 'queries_before', 0)
            
            # Log slow requests
            threshold = getattr(settings, 'PERFORMANCE_MONITORING', {}).get('SLOW_REQUEST_THRESHOLD', 2.0)
            if duration > threshold:
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {duration:.2f}s with {queries_count} queries"
                )
            
            # Log excessive queries
            max_queries = getattr(settings, 'PERFORMANCE_MONITORING', {}).get('MAX_QUERIES_PER_REQUEST', 50)
            if queries_count > max_queries:
                logger.warning(
                    f"Excessive queries: {request.method} {request.path} "
                    f"executed {queries_count} queries"
                )
            
            # Add performance headers for debugging
            if settings.DEBUG:
                response['X-Response-Time'] = f"{duration:.3f}s"
                response['X-Query-Count'] = str(queries_count)
        
        return response

class HealthCheckMiddleware(MiddlewareMixin):
    """Provide health check endpoint"""
    
    def process_request(self, request):
        if request.path == '/health/':
            try:
                # Check database connection
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                
                # Check cache
                from django.core.cache import cache
                cache.set('health_check', 'ok', 10)
                cache_status = cache.get('health_check') == 'ok'
                
                return JsonResponse({
                    'status': 'healthy',
                    'database': 'connected',
                    'cache': 'working' if cache_status else 'error',
                    'timestamp': time.time()
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': time.time()
                }, status=503)

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses"""
    
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Only add HSTS in production
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response

class MaintenanceModeMiddleware(MiddlewareMixin):
    """Handle maintenance mode"""
    
    def process_request(self, request):
        maintenance_file = settings.BASE_DIR / 'maintenance.txt'
        
        if maintenance_file.exists() and not request.path.startswith('/admin/'):
            return JsonResponse({
                'status': 'maintenance',
                'message': 'System is currently under maintenance. Please try again later.',
                'retry_after': 300  # 5 minutes
            }, status=503)