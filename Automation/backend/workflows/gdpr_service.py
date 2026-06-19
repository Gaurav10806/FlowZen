"""
GDPR compliance service for data export and deletion.
"""
import json
import zipfile
import tempfile
import os
from typing import Dict, List
from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import (
    GDPRDataRequest, User, Organization, Workflow, WorkflowExecution,
    Credential, NodeExecution, ExecutionLog, AuditLog
)


@shared_task
def process_gdpr_request(request_id: str):
    """
    Process GDPR data export or deletion request.
    """
    try:
        request = GDPRDataRequest.objects.get(id=request_id)
        request.status = 'processing'
        request.save()
        
        if request.request_type == 'export':
            export_user_data(request)
        elif request.request_type == 'delete':
            delete_user_data(request)
        
        request.status = 'completed'
        request.completed_at = timezone.now()
        request.save()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"GDPR request processing failed: {e}", exc_info=True)
        request.status = 'failed'
        request.save()


def export_user_data(request: GDPRDataRequest):
    """Export all user data to a JSON file."""
    user = request.user
    organization = request.organization
    
    # Collect all user data
    data = {
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        },
        'workflows': [],
        'executions': [],
        'credentials': [],
        'audit_logs': [],
    }
    
    # Export workflows
    workflows = Workflow.objects.filter(owner=user)
    if organization:
        workflows = workflows.filter(organization=organization)
    
    for workflow in workflows:
        data['workflows'].append({
            'id': str(workflow.id),
            'name': workflow.name,
            'description': workflow.description,
            'graph': workflow.graph,
            'created_at': workflow.created_at.isoformat(),
            'updated_at': workflow.updated_at.isoformat(),
        })
    
    # Export executions
    executions = WorkflowExecution.objects.filter(workflow__owner=user)
    if organization:
        executions = executions.filter(workflow__organization=organization)
    
    for execution in executions[:1000]:  # Limit to prevent huge exports
        data['executions'].append({
            'id': str(execution.id),
            'workflow_id': str(execution.workflow.id),
            'status': execution.status,
            'input_payload': execution.input_payload,
            'result': execution.result,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'finished_at': execution.finished_at.isoformat() if execution.finished_at else None,
        })
    
    # Export credentials (without decrypted data)
    credentials = Credential.objects.filter(owner=user)
    if organization:
        credentials = credentials.filter(organization=organization)
    
    for credential in credentials:
        data['credentials'].append({
            'id': str(credential.id),
            'name': credential.name,
            'type': credential.type,
            'environment': credential.environment,
            'created_at': credential.created_at.isoformat(),
            # Note: encrypted_data is NOT exported for security
        })
    
    # Export audit logs
    audit_logs = AuditLog.objects.filter(user=user)
    if organization:
        audit_logs = audit_logs.filter(tenant=organization)
    
    for log in audit_logs[:1000]:
        data['audit_logs'].append({
            'id': str(log.id),
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': str(log.resource_id),
            'timestamp': log.timestamp.isoformat(),
        })
    
    # Create export file
    export_data = json.dumps(data, indent=2, default=str)
    
    # Save to file (in production, use S3 or similar)
    export_dir = os.path.join('exports', 'gdpr')
    os.makedirs(export_dir, exist_ok=True)
    
    filename = f"gdpr_export_{user.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(export_dir, filename)
    
    with open(filepath, 'w') as f:
        f.write(export_data)
    
    request.export_file_path = filepath
    request.save()
    
    # In production, send email with download link
    # send_export_email(user, filepath)


def delete_user_data(request: GDPRDataRequest):
    """Delete all user data (GDPR right to be forgotten)."""
    user = request.user
    organization = request.organization
    
    # Delete workflows and related data
    workflows = Workflow.objects.filter(owner=user)
    if organization:
        workflows = workflows.filter(organization=organization)
    
    for workflow in workflows:
        # Delete executions
        executions = WorkflowExecution.objects.filter(workflow=workflow)
        for execution in executions:
            # Delete node executions
            NodeExecution.objects.filter(workflow_execution=execution).delete()
            # Delete execution logs
            ExecutionLog.objects.filter(execution=execution).delete()
        executions.delete()
        
        # Delete workflow
        workflow.delete()
    
    # Delete credentials (encrypted data will be deleted)
    credentials = Credential.objects.filter(owner=user)
    if organization:
        credentials = credentials.filter(organization=organization)
    credentials.delete()
    
    # Delete audit logs
    audit_logs = AuditLog.objects.filter(user=user)
    if organization:
        audit_logs = audit_logs.filter(tenant=organization)
    audit_logs.delete()
    
    # Note: User account itself is NOT deleted (handled separately by admin)
    # Only user's data within the organization is deleted
    
    # Log deletion
    AuditLog.objects.create(
        user=user,
        tenant=organization,
        action='delete',
        resource_type='user_data',
        resource_id=user.id,
        changes={'gdpr_request_id': str(request.id)}
    )


