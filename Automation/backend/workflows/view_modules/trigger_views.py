"""
Trigger Management API Views

This module provides REST API endpoints for managing workflow triggers.
It includes endpoints for configuration, status, activation, and testing.
"""

import logging
import uuid
from typing import Dict, Any
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Workflow, WorkflowExecution
from ..triggers.trigger_registry import (
    trigger_registry, get_available_trigger_types, get_trigger_status
)
from ..triggers.webhook_handler import get_webhook_url, test_webhook_configuration
from ..triggers.schedule_manager import sync_workflow_schedule, get_workflow_schedule_status
from ..tasks import execute_workflow_with_core_engine


logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_trigger_types(request):
    """
    Get list of available trigger types.
    
    Returns:
        List of trigger types with their metadata and schemas
    """
    try:
        trigger_types = get_available_trigger_types()
        return Response({
            'trigger_types': trigger_types,
            'count': len(trigger_types)
        })
        
    except Exception as e:
        logger.error(f"Failed to list trigger types: {e}")
        return Response(
            {'error': 'Failed to retrieve trigger types'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_workflow_trigger_status(request, workflow_id):
    """
    Get comprehensive trigger status for a workflow.
    
    Args:
        workflow_id: UUID of the workflow
        
    Returns:
        Trigger status information including configuration and activity
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        trigger_status = get_trigger_status(workflow)
        
        return Response(trigger_status)
        
    except Exception as e:
        logger.error(f"Failed to get trigger status for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to retrieve trigger status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_trigger_config(request, workflow_id):
    """
    Validate trigger configuration for a workflow.
    
    Request Body:
        {
            "trigger": {
                "type": "webhook_trigger",
                "params": {...}
            }
        }
    
    Returns:
        Validation result with errors if any
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        trigger_config = request.data.get('trigger')
        if not trigger_config:
            return Response(
                {'error': 'Trigger configuration is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validation_result = trigger_registry.validate_trigger_configuration(
            workflow, trigger_config
        )
        
        return Response(validation_result)
        
    except Exception as e:
        logger.error(f"Failed to validate trigger config for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to validate trigger configuration'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_trigger(request, workflow_id):
    """
    Activate a trigger for a workflow.
    
    Request Body:
        {
            "trigger_type": "webhook_trigger"
        }
    
    Returns:
        Activation result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        trigger_type = request.data.get('trigger_type')
        if not trigger_type:
            return Response(
                {'error': 'Trigger type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = trigger_registry.activate_trigger(workflow, trigger_type)
        
        if result.get('success'):
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Failed to activate trigger for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to activate trigger'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_trigger(request, workflow_id):
    """
    Deactivate a trigger for a workflow.
    
    Request Body:
        {
            "trigger_type": "webhook_trigger"
        }
    
    Returns:
        Deactivation result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        trigger_type = request.data.get('trigger_type')
        if not trigger_type:
            return Response(
                {'error': 'Trigger type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = trigger_registry.deactivate_trigger(workflow, trigger_type)
        
        if result.get('success'):
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Failed to deactivate trigger for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to deactivate trigger'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_webhook_info(request, workflow_id):
    """
    Get webhook information for a workflow.
    
    Returns:
        Webhook URL, configuration, and test results
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        webhook_info = {
            'webhook_url': get_webhook_url(workflow, request),
            'webhook_enabled': workflow.webhook_enabled,
            'has_secret': bool(workflow.webhook_secret),
            'configuration': workflow.webhook_config or {}
        }
        
        # Test webhook configuration
        test_result = test_webhook_configuration(workflow)
        webhook_info['test_result'] = test_result
        
        return Response(webhook_info)
        
    except Exception as e:
        logger.error(f"Failed to get webhook info for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to retrieve webhook information'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_webhook(request, workflow_id):
    """
    Test webhook trigger with sample data.
    
    Request Body:
        {
            "test_data": {...}
        }
    
    Returns:
        Test execution result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        if not workflow.webhook_enabled:
            return Response(
                {'error': 'Webhook is not enabled for this workflow'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        test_data = request.data.get('test_data', {
            'test': True,
            'message': 'Webhook test from API'
        })
        
        # Create test execution
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            status='pending',
            triggered_by='webhook',
            input_payload={
                'body': test_data,
                'headers': {'Content-Type': 'application/json'},
                'query': {},
                'method': 'POST',
                'test_mode': True
            },
            fingerprint=f"webhook_test_{uuid.uuid4().hex}",
            # created_by=request.user
        )
        
        # Queue execution
        execution.status = 'queued'
        execution.save(update_fields=['status'])
        
        transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(str(execution.id)))
        
        return Response({
            'success': True,
            'execution_id': str(execution.id),
            'message': 'Webhook test execution queued'
        })
        
    except Exception as e:
        logger.error(f"Failed to test webhook for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to test webhook'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_schedule_info(request, workflow_id):
    """
    Get schedule information for a workflow.
    
    Returns:
        Schedule configuration, status, and next execution times
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        schedule_status = get_workflow_schedule_status(workflow)
        
        return Response(schedule_status)
        
    except Exception as e:
        logger.error(f"Failed to get schedule info for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to retrieve schedule information'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_schedule(request, workflow_id):
    """
    Sync workflow schedule with Celery Beat.
    
    Returns:
        Sync result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        sync_result = sync_workflow_schedule(workflow)
        
        return Response({
            'success': True,
            'sync_result': sync_result,
            'message': 'Schedule synchronized with Celery Beat'
        })
        
    except Exception as e:
        logger.error(f"Failed to sync schedule for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to sync schedule'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_schedule(request, workflow_id):
    """
    Test schedule trigger by creating a manual execution with schedule data.
    
    Returns:
        Test execution result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        if not workflow.schedule_enabled:
            return Response(
                {'error': 'Schedule is not enabled for this workflow'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedule_config = workflow.schedule or {}
        
        # Create test execution with schedule data
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            status='pending',
            triggered_by='schedule',
            input_payload={
                'trigger_type': 'schedule',
                'scheduled_time': 'test_execution',
                'cron_expression': schedule_config.get('cron_expression', ''),
                'static_data': schedule_config.get('static_data', {}),
                'test_mode': True
            },
            fingerprint=f"webhook_test_{uuid.uuid4().hex}",
            # created_by=request.user
        )
        
        # Queue execution
        execution.status = 'queued'
        execution.save(update_fields=['status'])
        
        transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(str(execution.id)))
        
        return Response({
            'success': True,
            'execution_id': str(execution.id),
            'message': 'Schedule test execution queued'
        })
        
    except Exception as e:
        logger.error(f"Failed to test schedule for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to test schedule'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_manual_execution(request, workflow_id):
    """
    Trigger manual execution of a workflow.
    
    Request Body:
        {
            "input_data": {...}  // Optional test data
        }
    
    Returns:
        Execution result
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        input_data = request.data.get('input_data', {
            'test': True,
            'manual_execution': True
        })
        
        # Capture ephemeral graph for testing
        graph_snapshot = request.data.get('graph')
        if graph_snapshot:
            input_data['graph'] = graph_snapshot
        
        # Create manual execution
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            status='pending',
            triggered_by='manual',
            input_payload={**input_data, '_user_id': request.user.id},
            fingerprint=f"manual_{uuid.uuid4().hex}",
            created_by=request.user
        )
        
        # Queue execution
        execution.status = 'queued'
        execution.save(update_fields=['status'])
        
        transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(str(execution.id)))
        
        return Response({
            'success': True,
            'execution_id': str(execution.id),
            'message': 'Manual execution queued'
        })
        
    except Exception as e:
        import traceback
        import os
        with open('debug_err.log', 'w') as f:
            f.write(traceback.format_exc())
        
        logger.error(f"Failed to trigger manual execution for workflow {workflow_id}: {e}")
        return Response(
            {'error': f'Failed to trigger manual execution: {e} (Check debug_err.log)'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trigger_activity(request, workflow_id):
    """
    Get recent trigger activity for a workflow.
    
    Query Parameters:
        - trigger_type: Filter by trigger type (optional)
        - limit: Number of executions to return (default 10, max 50)
    
    Returns:
        List of recent executions triggered by various triggers
    """
    try:
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        # Get query parameters
        trigger_type = request.GET.get('trigger_type')
        limit = min(int(request.GET.get('limit', 10)), 50)
        
        # Build query
        executions_query = workflow.executions.all()
        
        if trigger_type:
            executions_query = executions_query.filter(triggered_by=trigger_type)
        
        # Get recent executions
        executions = executions_query.order_by('-created_at')[:limit]
        
        # Format response
        activity = []
        for execution in executions:
            activity.append({
                'id': str(execution.id),
                'triggered_by': execution.triggered_by,
                'status': execution.status,
                'created_at': execution.created_at.isoformat(),
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'finished_at': execution.finished_at.isoformat() if execution.finished_at else None,
                'created_by': getattr(execution, 'created_by', None).username if getattr(execution, 'created_by', None) else None,
                'error_message': execution.error_message if execution.error_message else None
            })
        
        return Response({
            'activity': activity,
            'count': len(activity),
            'total_executions': workflow.executions.count()
        })
        
    except Exception as e:
        logger.error(f"Failed to get trigger activity for workflow {workflow_id}: {e}")
        return Response(
            {'error': 'Failed to retrieve trigger activity'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )