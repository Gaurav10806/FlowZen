"""
URL routing for workflow export/import APIs.
"""

from django.urls import path
from .views import (
    WorkflowExportView, WorkflowImportView, WorkflowImportValidateView,
    WorkflowExportDownloadView, export_workflow_simple, import_workflow_simple,
    validate_import_simple
)

app_name = 'export_import'

urlpatterns = [
    # Full-featured API endpoints
    path('workflows/<uuid:workflow_id>/export/', WorkflowExportView.as_view(), name='export_workflow'),
    path('workflows/import/', WorkflowImportView.as_view(), name='import_workflow'),
    path('workflows/import/validate/', WorkflowImportValidateView.as_view(), name='validate_import'),
    path('exports/<uuid:workflow_id>/download/', WorkflowExportDownloadView.as_view(), name='download_export'),
    
    # Simple API endpoints
    path('workflows/<uuid:workflow_id>/export/simple/', export_workflow_simple, name='export_workflow_simple'),
    path('workflows/import/simple/', import_workflow_simple, name='import_workflow_simple'),
    path('workflows/import/validate/simple/', validate_import_simple, name='validate_import_simple'),
]