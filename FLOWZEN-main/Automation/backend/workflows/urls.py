"""
Workflow URLs - Core Execution Engine and Node System
Minimal working configuration for testing
"""

from django.urls import path, include
print("LOADING UPDATED URLS.PY ------------------------------------")
from rest_framework.routers import DefaultRouter
from django.http import JsonResponse

# Import main viewsets from views.py
from .views import (
    WorkflowViewSet, WorkflowExecutionViewSet, CredentialViewSet,
    WorkflowTemplateViewSet, webhook_trigger, UserProfileView,
    get_execution_engine_info, create_sample_workflow, get_node_types,
    get_node_schemas, get_node_schema,
    current_user_info, node_health_check, delete_workflow, get_missing_handles
)

# Import execution history views directly
from .view_modules.execution_history_views import (
    execution_history, execution_detail, execution_logs,
    execution_metrics, workflow_execution_summary
)

# Import trigger management views
from .view_modules.trigger_views import (
    list_trigger_types, get_workflow_trigger_status, validate_trigger_config,
    get_schedule_info, sync_schedule, test_schedule, trigger_manual_execution,
    get_trigger_activity
)

# Import Gmail OAuth views
from .view_modules.gmail_oauth_views import (
    start_gmail_oauth, gmail_oauth_callback, save_gmail_credential, gmail_oauth_status
)

from .view_modules.google_calendar_oauth_views import (
    save_google_calendar_credential, start_google_calendar_oauth, google_calendar_oauth_callback,
    google_calendar_oauth_status
)

# Import other trigger views that were missing
from .view_modules.trigger_views import (
    activate_trigger, deactivate_trigger, get_webhook_info, test_webhook
)

# Import enhanced webhook handler
from .triggers.webhook_handler import webhook_trigger_view
from .triggers.whatsapp_handler import handle_whatsapp_webhook
from .triggers.telegram_handler import telegram_webhook_view, telegram_health_view, telegram_register_view

# Import DEV API views (simple implementation)
from .dev_api_simple import (
    system_status_simple, refresh_node_registry_simple,
    node_list_simple, node_detail_simple, node_test_simple,
    update_node_status_simple
)

# Import chat API views
from .chat_api import (
    ChatSessionViewSet, ChatMessageViewSet,
    ChatSessionViewSet, ChatMessageViewSet,
    handle_workflow_response, chat_health
)
from .view_modules.debug_views import debug_ai_agent_inputs
from .view_modules.analytics_views import ExecutionAnalyticsView

# Create router for viewsets
router = DefaultRouter()
router.register(r'workflows', WorkflowViewSet, basename='workflow')
router.register(r'executions', WorkflowExecutionViewSet, basename='execution')
router.register(r'credentials', CredentialViewSet, basename='credential')
router.register(r'templates', WorkflowTemplateViewSet, basename='template')
router.register(r'chat/sessions', ChatSessionViewSet, basename='chat-session')
router.register(r'chat/messages', ChatMessageViewSet, basename='chat-message')

# DEV API router (separate for security)
dev_router = DefaultRouter()
# Note: Using simple function-based views instead of ViewSets for now

app_name = 'workflows'

urlpatterns = [
    # Explicit API routes (Must be before router.urls to avoid shadowing)
    path('api/user/profile/', UserProfileView.as_view(), name='user_profile'),
    path('api/user/info/', current_user_info, name='current_user_info'),
    path('api/engine/info/', get_execution_engine_info, name='get_execution_engine_info'),
    path('api/engine/sample/', create_sample_workflow, name='create_sample_workflow'),    # Workflow Management
    path("workflow/<uuid:workflow_id>/delete/", delete_workflow, name="workflow_delete"),
    path("api/nodes/types/", get_node_types, name="get_node_types"),
    path("api/nodes/schemas/", get_node_schemas, name="get_node_schemas"),
    path("api/nodes/schema/<str:node_type>/", get_node_schema, name="get_node_schema"),
    path('api/nodes/healthcheck/', node_health_check, name='node_health_check'),

    # Enhanced Execution History and Monitoring API (MUST be before router to avoid shadowing)
    path('api/executions/history/', execution_history, name='execution_history'),
    path('api/executions/<uuid:execution_id>/detail/', execution_detail, name='execution_detail'),
    path('api/executions/<uuid:execution_id>/logs/', execution_logs, name='execution_logs'),
    path('api/v1/analytics/stats/', execution_metrics, name='execution_metrics_v1'),
    path('api/workflows/<uuid:workflow_id>/execution-summary/', workflow_execution_summary, name='workflow_execution_summary'),

    # Manual Trigger API (MUST be before router to avoid shadowing)
    path('api/workflows/<uuid:workflow_id>/manual/trigger/', trigger_manual_execution, name='trigger_manual_execution'),

    # Core API routes (Router)
    path('api/', include(router.urls)),

    # Trigger Management API
    path('api/triggers/types/', list_trigger_types, name='list_trigger_types'),
    path('api/workflows/<uuid:workflow_id>/trigger/status/', get_workflow_trigger_status, name='workflow_trigger_status'),
    path('api/workflows/<uuid:workflow_id>/trigger/validate/', validate_trigger_config, name='validate_trigger_config'),
    path('api/workflows/<uuid:workflow_id>/trigger/activate/', activate_trigger, name='activate_trigger'),
    path('api/workflows/<uuid:workflow_id>/trigger/deactivate/', deactivate_trigger, name='deactivate_trigger'),
    path('api/workflows/<uuid:workflow_id>/trigger/activity/', get_trigger_activity, name='trigger_activity'),

    # Webhook Trigger API
    path('api/workflows/<uuid:workflow_id>/webhook/info/', get_webhook_info, name='webhook_info'),
    path('api/workflows/<uuid:workflow_id>/webhook/test/', test_webhook, name='test_webhook'),

    # Schedule Trigger API
    path('api/workflows/<uuid:workflow_id>/schedule/info/', get_schedule_info, name='schedule_info'),
    path('api/workflows/<uuid:workflow_id>/schedule/sync/', sync_schedule, name='sync_schedule'),
    path('api/workflows/<uuid:workflow_id>/schedule/test/', test_schedule, name='test_schedule'),

    # Gmail OAuth
    # Gmail OAuth (Unified via CredentialViewSet)
    path('api/v1/credentials/gmail/start/', CredentialViewSet.as_view({'get': 'authorize_google', 'post': 'authorize_google'}), name='start-gmail-oauth-alias'),
    path('api/v1/gmail-oauth/start/', CredentialViewSet.as_view({'get': 'authorize_google', 'post': 'authorize_google'}), name='start-gmail-oauth'),
    path('api/v1/gmail-oauth/callback/', CredentialViewSet.as_view({'get': 'google_callback', 'post': 'google_callback'}), name='gmail-oauth-callback'),
    path('api/v1/credentials/gmail/save/', save_gmail_credential, name='save-gmail-credential'), # Keep save for now as it handles specific "gmail" type creation logic cleanly

    # Chat API
    path('api/chat/workflow-response/', handle_workflow_response, name='chat_workflow_response'),
    path('api/chat/health/', chat_health, name='chat_health'),

    # Health checks
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health_check'),
    path('ready/', lambda request: JsonResponse({'status': 'ready'}), name='readiness_check'),

    # Health checks
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health_check'),
    path('ready/', lambda request: JsonResponse({'status': 'ready'}), name='readiness_check'),

    # Analytics
    path('api/analytics/executions/weekly/', ExecutionAnalyticsView.as_view(), name='analytics_weekly'),

    # Enhanced Webhook Endpoints (Public - No Authentication Required)
    path('webhooks/<uuid:workflow_id>/', webhook_trigger_view, name='webhook_trigger_enhanced'),
    path('api/webhooks/whatsapp/', handle_whatsapp_webhook, name='webhook_whatsapp'),
    path('api/webhooks/telegram/', telegram_webhook_view, name='telegram-webhook'),
    path('api/health/telegram/', telegram_health_view, name='telegram-health'),
    path('api/v1/telegram/register/', telegram_register_view, name='telegram-register'),

    # Legacy webhook endpoint (for backward compatibility)
    path('webhooks/<str:webhook_id>/', webhook_trigger, name='webhook_trigger_legacy'),
    # Legacy webhook endpoint (for backward compatibility)
    path('webhooks/<str:webhook_id>/', webhook_trigger, name='webhook_trigger_legacy'),

    # Google Calendar OAuth
    path('api/v1/credentials/google-calendar/save/', save_google_calendar_credential, name='save-google-calendar-credential'),
    path('api/v1/google-calendar-oauth/start/', start_google_calendar_oauth, name='start-google-calendar-oauth'),
    path('api/v1/google-calendar-oauth/callback/', google_calendar_oauth_callback, name='google-calendar-oauth-callback'),
    path('api/v1/google-calendar-oauth/status/', google_calendar_oauth_status, name='google-calendar-oauth-status'),
]