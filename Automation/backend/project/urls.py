"""
URL configuration for project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.shortcuts import render

# Import from the main views.py file
from workflows import views as workflow_views
from workflows.stripe_webhooks import stripe_webhook
from workflows.view_modules.gmail_oauth_views import (
    save_gmail_credential,
    start_gmail_oauth,
    gmail_oauth_callback,
    gmail_oauth_status,
    gmail_oauth_test,
    gmail_oauth_disconnect
)
from workflows.view_modules.google_calendar_oauth_views import (
    save_google_calendar_credential,
    start_google_calendar_oauth,
    google_calendar_oauth_callback,
    google_calendar_oauth_status
)
from workflows.view_modules.execution_history_views import execution_metrics
from workflows.triggers.telegram_handler import telegram_webhook_view, telegram_health_view

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
   openapi.Info(
      title="FlowZen API",
      default_version='v1',
      description="Ethereal Automation Platform API",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@flowzen.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)


# REST API router
router = DefaultRouter()
router.register(r"workflows", workflow_views.WorkflowViewSet, basename="workflow")
router.register(r"executions", workflow_views.WorkflowExecutionViewSet, basename="execution")
router.register(r"credentials", workflow_views.CredentialViewSet, basename="credential")
router.register(r"templates", workflow_views.WorkflowTemplateViewSet, basename="template")
router.register(r"organizations", workflow_views.OrganizationViewSet, basename="organization")
router.register(r"teams", workflow_views.TeamViewSet, basename="team")
router.register(r"memberships", workflow_views.MembershipViewSet, basename="membership")
router.register(r"subscription-plans", workflow_views.SubscriptionPlanViewSet, basename="subscription-plan")
router.register(r"subscriptions", workflow_views.SubscriptionViewSet, basename="subscription")
router.register(r"invoices", workflow_views.InvoiceViewSet, basename="invoice")
router.register(r"security/secret-access-logs", workflow_views.SecretAccessLogViewSet, basename="secret-access-log")
router.register(r"security/ip-allowlist", workflow_views.IPAllowlistViewSet, basename="ip-allowlist")
router.register(r"gdpr/requests", workflow_views.GDPRDataRequestViewSet, basename="gdpr-request")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("login/", lambda request: render(request, "login.html"), name="login"),
    
    # 1. Dashboard (Highest Priority for root and /dashboard/)
    path("", workflow_views.dashboard_view, name="dashboard"),
    path("dashboard/", workflow_views.dashboard_view, name="dashboard_explicit"),
    
    # 2. Analytics / Metrics (High Priority)
    path("api/v1/analytics/stats/", execution_metrics, name="execution-metrics-v1"),
    path("api/v1/system/metrics/", execution_metrics, name="system-metrics-alias"),
    
    # 3. App-Specific URLs
    path("", include("workflows.urls")),
    path("", include("workflows.frontend_urls")),
    
    # 4. Auth & Notifications
    path("api/auth/", include("authentication.urls")),
    path('api/notifications/', include('notifications.urls')),
    
    # 5. Core REST API (Lower Priority)
    path("api/v1/", include(router.urls)),
    path("api/", include(router.urls)),
    
    # Public Shared View
    path("workflow/share/<uuid:workflow_id>/", workflow_views.public_workflow_view, name="public-workflow-view"),

    # Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    path("api/v1/dlq/items/", workflow_views.DLQListView.as_view(), name="dlq-items"),
    path("api/v1/dlq/items/<uuid:dlq_id>/", workflow_views.DLQDetailView.as_view(), name="dlq-item-detail"),
    path("api/v1/dlq/replay/", workflow_views.DLQReplayView.as_view(), name="dlq-replay"),
    path("api/v1/dlq/bulk/replay/", workflow_views.DLQBulkReplayView.as_view(), name="dlq-bulk-replay"),
    path("api/v1/dlq/bulk/delete/", workflow_views.DLQBulkDeleteView.as_view(), name="dlq-bulk-delete"),
    path("api/v1/dlq/bulk/replay_combined/", workflow_views.DLQBulkReplayCombinedView.as_view(), name="dlq-bulk-replay-combined"),
    path("webhook/<uuid:workflow_id>/", workflow_views.webhook_trigger, name="webhook"),
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    path("health/", lambda request: JsonResponse({"status": "ok", "message": "Automation Platform Online"}), name="root-health"),
    path("api/v1/system/info/", workflow_views.get_execution_engine_info, name="system-info-alias"),
    
    # Prometheus Metrics
    path("metrics/", include("django_prometheus.urls")),
    
    path("api/user/profile/", workflow_views.UserProfileView.as_view(), name="user_profile_root"),

    
    path("api/webhooks/telegram/", telegram_webhook_view, name="telegram-webhook"),
    path("api/health/telegram/", telegram_health_view, name="telegram-health"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
