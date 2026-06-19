"""
Enhanced Execution History and Monitoring Views

This module provides comprehensive APIs for execution observability:
- Execution history with filtering and pagination
- Real-time execution status monitoring
- Detailed execution logs and timeline
- Node-level execution tracking
- Performance metrics and analytics
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from ..models import (
    WorkflowExecution, NodeExecution, ExecutionLog, 
    Workflow, Tenant
)
from ..serializers import (
    WorkflowExecutionSerializer, NodeExecutionSerializer, 
    ExecutionLogSerializer
)


logger = logging.getLogger(__name__)


class ExecutionHistoryPagination(PageNumberPagination):
    """Custom pagination for execution history."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def execution_history(request):
    """
    Get paginated execution history with filtering and search.
    
    Query Parameters:
    - workflow_id: Filter by workflow ID
    - status: Filter by execution status (pending, running, completed, failed)
    - triggered_by: Filter by trigger type (manual, webhook, schedule)
    - date_from: Filter executions from date (ISO format)
    - date_to: Filter executions to date (ISO format)
    - search: Search in workflow names and execution IDs
    - page: Page number
    - page_size: Items per page (max 100)
    
    Returns:
        Paginated list of workflow executions with summary data
    """
    try:
        # Get query parameters
        workflow_id = request.GET.get('workflow_id')
        status_filter = request.GET.get('status')
        triggered_by = request.GET.get('triggered_by')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search = request.GET.get('search')
        
        # Start with base queryset
        queryset = WorkflowExecution.objects.select_related(
            'workflow', 'created_by', 'tenant'
        ).prefetch_related('node_executions')
        
        # Apply filters
        if workflow_id:
            queryset = queryset.filter(workflow_id=workflow_id)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if triggered_by:
            queryset = queryset.filter(triggered_by=triggered_by)
        
        if date_from:
            try:
                date_from_parsed = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date_from_parsed)
            except ValueError:
                return Response(
                    {'error': 'Invalid date_from format. Use ISO format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if date_to:
            try:
                date_to_parsed = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=date_to_parsed)
            except ValueError:
                return Response(
                    {'error': 'Invalid date_to format. Use ISO format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if search:
            queryset = queryset.filter(
                Q(workflow__name__icontains=search) |
                Q(id__icontains=search) |
                Q(correlation_id__icontains=search)
            )
        
        # Order by most recent first
        queryset = queryset.order_by('-created_at')
        
        # Apply pagination
        paginator = ExecutionHistoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            # Serialize with additional computed fields
            serialized_data = []
            for execution in page:
                data = WorkflowExecutionSerializer(execution).data
                
                # Add computed fields
                data['duration_ms'] = None
                if execution.started_at and execution.finished_at:
                    duration = execution.finished_at - execution.started_at
                    data['duration_ms'] = int(duration.total_seconds() * 1000)
                
                # Add node execution summary
                node_executions = execution.node_executions.all()
                data['node_summary'] = {
                    'total': node_executions.count(),
                    'completed': node_executions.filter(status='completed').count(),
                    'failed': node_executions.filter(status='failed').count(),
                    'running': node_executions.filter(status='running').count()
                }
                
                serialized_data.append(data)
            
            return paginator.get_paginated_response(serialized_data)
        
        # Fallback without pagination
        serializer = WorkflowExecutionSerializer(queryset, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Failed to get execution history: {e}")
        return Response(
            {'error': 'Failed to retrieve execution history'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def execution_detail(request, execution_id):
    """
    Get detailed execution information including logs and node executions.
    
    Args:
        execution_id: UUID of the workflow execution
        
    Returns:
        Detailed execution data with logs and node executions
    """
    try:
        execution = WorkflowExecution.objects.select_related(
            'workflow', 'created_by', 'tenant'
        ).prefetch_related(
            'node_executions', 'execution_logs'
        ).get(id=execution_id)
        
        # Serialize main execution data
        execution_data = WorkflowExecutionSerializer(execution).data
        
        # Add duration
        execution_data['duration_ms'] = None
        if execution.started_at and execution.finished_at:
            duration = execution.finished_at - execution.started_at
            execution_data['duration_ms'] = int(duration.total_seconds() * 1000)
        
        # Add node executions
        node_executions = execution.node_executions.order_by('created_at')
        execution_data['node_executions'] = NodeExecutionSerializer(
            node_executions, many=True
        ).data
        
        # Add execution logs
        logs = execution.execution_logs.order_by('timestamp')
        execution_data['logs'] = ExecutionLogSerializer(logs, many=True).data
        
        # Add execution timeline (combined logs and node events)
        timeline = []
        
        # Add logs to timeline
        for log in logs:
            timeline.append({
                'timestamp': log.timestamp.isoformat(),
                'type': 'log',
                'level': log.level,
                'message': log.message,
                'metadata': log.metadata,
                'node_execution_id': str(log.node_execution.id) if log.node_execution else None
            })
        
        # Add node execution events to timeline
        for node_exec in node_executions:
            if node_exec.started_at:
                timeline.append({
                    'timestamp': node_exec.started_at.isoformat(),
                    'type': 'node_start',
                    'message': f"Started node: {node_exec.graph_node_id}",
                    'node_execution_id': str(node_exec.id),
                    'node_id': node_exec.graph_node_id
                })
            
            if node_exec.finished_at:
                timeline.append({
                    'timestamp': node_exec.finished_at.isoformat(),
                    'type': 'node_complete' if node_exec.status == 'completed' else 'node_error',
                    'message': f"{'Completed' if node_exec.status == 'completed' else 'Failed'} node: {node_exec.graph_node_id}",
                    'node_execution_id': str(node_exec.id),
                    'node_id': node_exec.graph_node_id
                })
        
        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        execution_data['timeline'] = timeline
        
        return Response(execution_data)
        
    except WorkflowExecution.DoesNotExist:
        return Response(
            {'error': 'Execution not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to get execution detail: {e}")
        return Response(
            {'error': 'Failed to retrieve execution details'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def execution_logs(request, execution_id):
    """
    Get execution logs with filtering and pagination.
    
    Query Parameters:
    - level: Filter by log level (debug, info, warning, error)
    - node_id: Filter by node ID
    - since: Get logs since timestamp (ISO format)
    - limit: Limit number of logs (default 100, max 1000)
    
    Args:
        execution_id: UUID of the workflow execution
        
    Returns:
        Filtered and paginated execution logs
    """
    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
        
        # Get query parameters
        level_filter = request.GET.get('level')
        node_id = request.GET.get('node_id')
        since = request.GET.get('since')
        limit = min(int(request.GET.get('limit', 100)), 1000)
        
        # Start with execution logs
        queryset = ExecutionLog.objects.filter(execution=execution)
        
        # Apply filters
        if level_filter:
            queryset = queryset.filter(level=level_filter)
        
        if node_id:
            queryset = queryset.filter(
                node_execution__graph_node_id=node_id
            )
        
        if since:
            try:
                since_parsed = datetime.fromisoformat(since.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=since_parsed)
            except ValueError:
                return Response(
                    {'error': 'Invalid since format. Use ISO format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Order by timestamp and limit
        logs = queryset.order_by('timestamp')[:limit]
        
        serializer = ExecutionLogSerializer(logs, many=True)
        return Response({
            'logs': serializer.data,
            'count': len(serializer.data),
            'has_more': queryset.count() > limit
        })
        
    except WorkflowExecution.DoesNotExist:
        return Response(
            {'error': 'Execution not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to get execution logs: {e}")
        return Response(
            {'error': 'Failed to retrieve execution logs'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def execution_metrics(request):
    """
    Get execution metrics and analytics.
    
    Query Parameters:
    - workflow_id: Filter by workflow ID
    - days: Number of days to include (default 7, max 90)
    - granularity: Time granularity (hour, day, week) - default day
    
    Returns:
        Execution metrics including success rates, performance, and trends
    """
    try:
        # Get query parameters
        workflow_id = request.GET.get('workflow_id')
        days = min(int(request.GET.get('days', 7)), 90)
        granularity = request.GET.get('granularity', 'day')
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base queryset - Filtered by owner for security and correctness
        queryset = WorkflowExecution.objects.filter(
            workflow__owner=request.user,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        if workflow_id:
            queryset = queryset.filter(workflow_id=workflow_id)
        
        # Overall metrics
        total_executions = queryset.count()
        successful_executions = queryset.filter(status='completed').count()
        failed_executions = queryset.filter(status='failed').count()
        running_executions = queryset.filter(status='running').count()
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        
        # Performance metrics
        completed_executions = queryset.filter(
            status='completed',
            started_at__isnull=False,
            finished_at__isnull=False
        )
        
        performance_metrics = {}
        if completed_executions.exists():
            # Calculate durations in Python since we can't easily do it in DB
            durations = []
            for execution in completed_executions:
                if execution.started_at and execution.finished_at:
                    duration = (execution.finished_at - execution.started_at).total_seconds() * 1000
                    durations.append(duration)
            
            if durations:
                performance_metrics = {
                    'avg_duration_ms': sum(durations) / len(durations),
                    'min_duration_ms': min(durations),
                    'max_duration_ms': max(durations),
                    'median_duration_ms': sorted(durations)[len(durations) // 2]
                }
        
        # Status distribution
        status_distribution = {
            'completed': successful_executions,
            'failed': failed_executions,
            'running': running_executions,
            'pending': queryset.filter(status='pending').count()
        }
        
        # Trigger type distribution
        trigger_distribution = {}
        for trigger_type in ['manual', 'webhook', 'schedule', 'event']:
            count = queryset.filter(triggered_by=trigger_type).count()
            if count > 0:
                trigger_distribution[trigger_type] = count
        
        # Time series data
        time_series = []
        if granularity == 'day':
            for i in range(days):
                day_start = start_date + timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                day_executions = queryset.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end
                )
                
                time_series.append({
                    'timestamp': day_start.date().isoformat(),
                    'total': day_executions.count(),
                    'successful': day_executions.filter(status='completed').count(),
                    'failed': day_executions.filter(status='failed').count()
                })
        elif granularity == 'hour':
            # For hourly, we usually look at the last 24 hours
            hours_to_show = 24 if days == 1 else days * 24
            current_time = end_date.replace(minute=0, second=0, microsecond=0)
            
            for i in range(hours_to_show, -1, -1):
                hour_start = current_time - timedelta(hours=i)
                hour_end = hour_start + timedelta(hours=1)
                hour_executions = queryset.filter(
                    created_at__gte=hour_start,
                    created_at__lt=hour_end
                )
                
                time_series.append({
                    'timestamp': hour_start.isoformat(),
                    'label': hour_start.strftime('%H:00'),
                    'total': hour_executions.count(),
                    'successful': hour_executions.filter(status='completed').count(),
                    'failed': hour_executions.filter(status='failed').count()
                })
        
        return Response({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'summary': {
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'failed_executions': failed_executions,
                'running_executions': running_executions,
                'success_rate': round(success_rate, 2)
            },
            'performance': performance_metrics,
            'status_distribution': status_distribution,
            'trigger_distribution': trigger_distribution,
            'time_series': time_series
        })
        
    except Exception as e:
        logger.error(f"Failed to get execution metrics: {e}")
        return Response(
            {'error': 'Failed to retrieve execution metrics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workflow_execution_summary(request, workflow_id):
    """
    Get execution summary for a specific workflow.
    
    Args:
        workflow_id: UUID of the workflow
        
    Returns:
        Workflow execution summary with recent executions and metrics
    """
    try:
        workflow = Workflow.objects.get(id=workflow_id)
        
        # Get recent executions (last 10)
        recent_executions = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-created_at')[:10]
        
        # Get execution counts by status
        total_executions = WorkflowExecution.objects.filter(workflow=workflow).count()
        status_counts = {
            'completed': WorkflowExecution.objects.filter(workflow=workflow, status='completed').count(),
            'failed': WorkflowExecution.objects.filter(workflow=workflow, status='failed').count(),
            'running': WorkflowExecution.objects.filter(workflow=workflow, status='running').count(),
            'pending': WorkflowExecution.objects.filter(workflow=workflow, status='pending').count()
        }
        
        # Calculate success rate
        success_rate = 0
        if total_executions > 0:
            success_rate = (status_counts['completed'] / total_executions) * 100
        
        # Get last execution
        last_execution = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-created_at').first()
        
        return Response({
            'workflow': {
                'id': str(workflow.id),
                'name': workflow.name,
                'status': workflow.status
            },
            'summary': {
                'total_executions': total_executions,
                'success_rate': round(success_rate, 2),
                'status_counts': status_counts
            },
            'last_execution': WorkflowExecutionSerializer(last_execution).data if last_execution else None,
            'recent_executions': WorkflowExecutionSerializer(recent_executions, many=True).data
        })
        
    except Workflow.DoesNotExist:
        return Response(
            {'error': 'Workflow not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to get workflow execution summary: {e}")
        return Response(
            {'error': 'Failed to retrieve workflow execution summary'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )