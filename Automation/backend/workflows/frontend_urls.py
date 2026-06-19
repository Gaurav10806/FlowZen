from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
import os
from . import views
from . import ai_assistant_api
from .template_utils import serve_frontend_template

# Test debug view
@login_required
def test_debug_view(request):
    return serve_frontend_template("workflows/test_debug.html", request)

@login_required
def test_workflows_view(request):
    return serve_frontend_template("workflows/test_workflows.html", request)

# NEW: Simple test view to debug authentication
@login_required
def simple_test_view(request):
    """Simple test view with no authentication"""
    return HttpResponse("<h1>SIMPLE TEST VIEW</h1><p>This view has no authentication requirements.</p>")

# NEW: Serve the user interface (light theme)
@login_required
def user_workflow_app_view(request):
    """Serve the user workflow app (light theme)"""
    # In Docker container, frontend files are at /app/frontend/
    frontend_path = "/app/frontend/user/index.html"
    
    if os.path.exists(frontend_path):
        with open(frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    else:
        return HttpResponse(
            '<h1>User Interface Not Found</h1><p>User frontend files not available at: {}</p>'.format(frontend_path),
            content_type='text/html'
        )

# NEW: Serve the original frontend (legacy)
@login_required
def workflow_builder_new_view(request):
    """Serve the original n8n-style workflow builder"""
    # In Docker container, frontend files are at /app/frontend/
    frontend_path = "/app/frontend/index.html"
    
    if os.path.exists(frontend_path):
        with open(frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    else:
        return HttpResponse(
            '<h1>Frontend not found</h1><p>Frontend files not available at: {}</p>'.format(frontend_path),
            content_type='text/html'
        )

# NEW: Revolutionary Enhanced Automation Platform
@login_required
def enhanced_workflow_builder_view(request):
    """Serve the revolutionary enhanced automation platform with all god-level features"""
    # Standardize on the single builder HTML
    return serve_frontend_template("workflows/builder.html", request)

# NEW: Template management interface
@login_required
def template_management_view(request):
    """Serve the template management interface"""
    return serve_frontend_template("workflows/templates_list.html", request)

# NEW: Unified Credential management interface
@login_required
def credential_management_view(request):
    """Serve the unified credential management interface"""
    return serve_frontend_template("workflows/credentials.html", request)

# NEW: Notifications interface
@login_required
def notifications_view(request):
    """Serve the notifications inbox"""
    return redirect("/settings/#notifications")

# NEW: Settings interface
@login_required
def settings_view(request):
    """Serve the settings interface"""
    return serve_frontend_template("workflows/settings.html", request)

# NEW: Execution Details Page
@login_required
def execution_detail_page_view(request, execution_id):
    """Serve the dedicated execution details page with context"""
    from .models import WorkflowExecution
    from django.shortcuts import get_object_or_404, render
    
    # Fetch execution to populate template context (e.g. for back button)
    execution = get_object_or_404(WorkflowExecution, id=execution_id)
    return render(request, "workflows/execution_detail.html", {"execution": execution})

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    
    # Maximum Width Builder (Auth Corrected)
    path("maximum-width-builder/", views.maximum_width_builder_view, name="maximum-width-builder"),
    path("test-builder/", views.maximum_width_builder_view, name="test-builder"),
    
    # Execution Details Page
    path("executions/<uuid:execution_id>/", execution_detail_page_view, name="execution-detail-page"),
    
    # 🚀 REVOLUTIONARY ENHANCED AUTOMATION PLATFORM
    path("revolutionary/", enhanced_workflow_builder_view, name="revolutionary-platform"),
    path("enhanced/", enhanced_workflow_builder_view, name="enhanced-platform"),
    path("god-level/", enhanced_workflow_builder_view, name="god-level-platform"),
    
    # Enhanced Workflow Builder (Main Interface) - FIXED TO USE WORKING TEMPLATE
    path("workflows/builder/", enhanced_workflow_builder_view, name="enhanced-workflow-builder"),
    path("workflows/new/", enhanced_workflow_builder_view, name="new-workflow"),
    path("builder/", enhanced_workflow_builder_view, name="workflow-builder-enhanced"),
    
    # Template Management Interface
    path("templates/", template_management_view, name="templates-management"),
    path("templates/new/", template_management_view, name="new-template"),
    path("templates/manage/", template_management_view, name="manage-templates"),
    
    # Credential Management Interface
    path("credentials/", credential_management_view, name="credentials-management"),
    # Old separate create/manage routes removed as now unified in /credentials/
    # path("credentials/new/", credential_create_view, name="new-credential"),
    # path("credentials/create/", credential_create_view, name="credentials_create"),
    # path("credentials/manage/", credential_management_view, name="manage-credentials"),

    # Notification Interface
    path("notifications/", notifications_view, name="notifications-inbox"),

    # Settings Interface
    path("settings/", settings_view, name="settings"),
    
    # User Interface (Light Theme)  
    path("app/", user_workflow_app_view, name="user-workflow-app"),
    path("app/workflows/", user_workflow_app_view, name="user-workflows"),
    path("app/builder/", user_workflow_app_view, name="user-builder"),
    
    # Legacy/Original Interface
    path("legacy/builder/", workflow_builder_new_view, name="workflow-builder-legacy"),
    path("user-app/", views.user_app_view, name="user-app-legacy"),
    
    # Existing paths (legacy Django templates)
    path("workflows/", views.workflows_list_view, name="workflows"),
    path("credentials-legacy/", views.credentials_list_view, name="credentials-legacy"),
    path("test-workflows/", test_workflows_view, name="test-workflows"),
    path("test-debug/", test_debug_view, name="test-debug"),
    path("create-workflow/", views.create_workflow_view, name="create-workflow"),
    path("workflow/<uuid:workflow_id>/", views.workflow_detail_view, name="workflow-detail"),
    path("workflow/<uuid:workflow_id>/builder/", views.workflow_builder_view, name="workflow-builder"),
    path("executions/", views.execution_list_view, name="executions"),
    path("executions/<uuid:execution_id>/", views.execution_detail_view, name="execution-detail"),
    path("dlq/", views.dlq_view, name="dlq"),
    path("credentials/<uuid:credential_id>/", views.credential_detail_view, name="credential-detail"),
    path("debug/", views.debug_view, name="debug"),
    
    # 🤖 AI ASSISTANT API ENDPOINTS
    path("api/ai/chat/", ai_assistant_api.ai_chat, name="ai-chat"),
    path("api/ai/suggestions/", ai_assistant_api.ai_suggestions, name="ai-suggestions"),
    path("api/ai/generate-workflow/", ai_assistant_api.ai_generate_workflow, name="ai-generate-workflow"),
]

