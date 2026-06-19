import os
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)

class MaintenanceModeMiddleware:
    """
    Middleware to block access when Maintenance Mode is enabled.
    Checks for a file 'MAINTENANCE_MODE' in the base directory or an env var.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow admin access even during maintenance
        if request.path.startswith('/admin/'):
             return self.get_response(request)
             
        # Check maintenance flag
        maintenance_file = settings.BASE_DIR / "MAINTENANCE_MODE"
        maintenance_env = os.environ.get("MAINTENANCE_MODE", "False") == "True"
        
        if maintenance_file.exists() or maintenance_env:
             if request.path.startswith('/api/'):
                 return JsonResponse({
                     "error": "Service Unavailable", 
                     "message": "System is currently under maintenance. Please try again later."
                 }, status=503)
             else:
                 return HttpResponse("<h1>System under Maintenance</h1><p>We'll be back shortly.</p>", status=503)
                 
        return self.get_response(request)
