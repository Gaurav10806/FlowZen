"""
URL configuration for User Server.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
import sys
import os

# Add the backend workflows app to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

try:
    from workflows import views as workflow_views
    from workflows.frontend_urls import urlpatterns as frontend_patterns
except ImportError:
    # Fallback views if workflows app is not available
    from django.http import HttpResponse
    
    def fallback_view(request):
        return HttpResponse("User Interface - Workflows app not available")
    
    workflow_views = type('MockViews', (), {
        'user_workflow_app_view': fallback_view,
        'workflow_list_view': fallback_view,
        'workflow_detail_view': fallback_view,
    })()
    
    frontend_patterns = []

def user_dashboard_view(request):
    """User dashboard view."""
    return TemplateView.as_view(template_name='user/index.html')(request)

urlpatterns = [
    # Admin interface (restricted)
    path('admin/', admin.site.urls),
    
    # User dashboard
    path('', user_dashboard_view, name='user-dashboard'),
    
    # API endpoints (with user restrictions)
    path('api/', include('workflows.urls')),
    
    # Frontend patterns (if available)
] + frontend_patterns

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)