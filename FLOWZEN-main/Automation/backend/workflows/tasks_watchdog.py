"""
PHASE-1: Watchdog tasks for stuck execution detection and recovery.
These tasks run periodically via Celery Beat to detect and recover from stuck states.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from .models import (
    WorkflowExecution, NodeExecution, RunRequest, WorkerHeartbeat
)
from .services.node_execution_queue import NodeExecutionQueue

logger = logging.getLogger(__name__)


@shared_task
def watchdog_stuck_executions():
    """
    PHASE-1: Detect and recover from stuck workflow executions.
    
    An execution is considered stuck if:
    - Status is "running" for longer than workflow.timeout_minutes (default: 60 minutes)
    - Status is "queued" for longer than 5 minutes (likely capacity issue)
    """
    try:
        now = timezone.now()
        
        # Check for executions stuck in "running" state
        default_timeout_minutes = 60
        running_threshold = now - timedelta(minutes=default_timeout_minutes)
        
        stuck_running = WorkflowExecution.objects.filter(
            status="running",
            started_at__lte=running_threshold
        ).select_related("workflow", "tenant")
        
        for execution in stuck_running:
            # Check workflow-specific timeout
            workflow_timeout_minutes = execution.workflow.settings.get("timeout_minutes", default_timeout_minutes)
            if execution.started_at:
                elapsed_minutes = (now - execution.started_at).total_seconds() / 60
                if elapsed_minutes >= workflow_timeout_minutes:
                    logger.warning(
                        f"Execution {execution.id} stuck in running state for {elapsed_minutes:.1f} minutes - marking as timed_out"
                    )
                    with transaction.atomic():
                        execution.status = "failed"
                        execution.finished_at = now
                        execution.error_message = f"Execution timeout after {elapsed_minutes:.1f} minutes"
                        execution.save(update_fields=["status", "finished_at", "error_message"])
                        
                        # Release capacity
                        try:
                            NodeExecutionQueue.release_execution_capacity(execution)
                        except Exception as e:
                            logger.error(f"Failed to release capacity for execution {execution.id}: {e}")
        
        # Check for executions stuck in "queued" state (likely capacity issue)
        queued_threshold = now - timedelta(minutes=5)
        stuck_queued = WorkflowExecution.objects.filter(
            status="queued",
            created_at__lte=queued_threshold
        ).select_related("workflow", "tenant")
        
        for execution in stuck_queued:
            logger.warning(
                f"Execution {execution.id} stuck in queued state for {(now - execution.created_at).total_seconds() / 60:.1f} minutes"
            )
            # Don't auto-fail queued executions - they might be legitimately waiting for capacity
            # But log them for monitoring
        
        logger.info(f"Watchdog checked {stuck_running.count()} running and {stuck_queued.count()} queued executions")
        
    except Exception as e:
        logger.error(f"Watchdog task failed: {e}", exc_info=True)


@shared_task
def watchdog_stuck_node_executions():
    """
    PHASE-1: Detect and recover from stuck node executions.
    
    A node execution is considered stuck if:
    - Status is "running" for longer than node.timeout (default: 30 seconds)
    """
    try:
        now = timezone.now()
        default_timeout_seconds = 30
        
        # Check for nodes stuck in "running" state
        running_threshold = now - timedelta(seconds=default_timeout_seconds)
        
        stuck_nodes = NodeExecution.objects.filter(
            status="running",
            started_at__lte=running_threshold
        ).select_related("node", "workflow_execution", "workflow_execution__workflow", "tenant")
        
        for node_exec in stuck_nodes:
            # Check node-specific timeout
            node_timeout_seconds = default_timeout_seconds
            if node_exec.node:
                node_timeout_seconds = node_exec.node.timeout or default_timeout_seconds
            
            if node_exec.started_at:
                elapsed_seconds = (now - node_exec.started_at).total_seconds()
                if elapsed_seconds >= node_timeout_seconds:
                    logger.warning(
                        f"Node execution {node_exec.id} ({node_exec.graph_node_id}) stuck in running state for {elapsed_seconds:.1f} seconds - marking as timed_out"
                    )
                    with transaction.atomic():
                        node_exec.status = "failed"
                        node_exec.finished_at = now
                        node_exec.error_message = f"Node timeout after {elapsed_seconds:.1f} seconds"
                        node_exec.save(update_fields=["status", "finished_at", "error_message"])
        
        logger.info(f"Watchdog checked {stuck_nodes.count()} running node executions")
        
    except Exception as e:
        logger.error(f"Node watchdog task failed: {e}", exc_info=True)


@shared_task
def watchdog_reclaim_run_requests():
    """
    PHASE-1: Reclaim RunRequests from dead workers.
    
    A RunRequest is considered expired if:
    - Status is "running" and expires_at is in the past
    - Worker hasn't sent heartbeat in last 5 minutes
    """
    try:
        now = timezone.now()
        
        # Find expired RunRequests
        expired_requests = RunRequest.objects.filter(
            status="running",
            expires_at__lte=now
        ).select_related("execution", "node_execution", "tenant")
        
        # Also check for requests from dead workers
        worker_timeout = now - timedelta(minutes=5)
        dead_workers = WorkerHeartbeat.objects.filter(
            last_heartbeat__lte=worker_timeout
        ).values_list("worker_id", flat=True)
        
        dead_worker_requests = RunRequest.objects.filter(
            status="running",
            worker_id__in=dead_workers
        ).select_related("execution", "node_execution", "tenant")
        
        all_expired = list(expired_requests) + list(dead_worker_requests)
        
        for run_request in all_expired:
            logger.warning(
                f"Reclaiming RunRequest {run_request.id} for node {run_request.node_id} "
                f"(worker: {run_request.worker_id}, expires_at: {run_request.expires_at})"
            )
            
            with transaction.atomic():
                # Reset node execution to "ready" so it can be retried
                node_exec = run_request.node_execution
                if node_exec and node_exec.status == "running":
                    node_exec.status = "ready"
                    node_exec.save(update_fields=["status"])
                
                # Mark RunRequest as expired
                run_request.status = "expired"
                run_request.completed_at = now
                run_request.save(update_fields=["status", "completed_at"])
        
        logger.info(f"Reclaimed {len(all_expired)} expired RunRequests")
        
    except Exception as e:
        logger.error(f"RunRequest reclaim task failed: {e}", exc_info=True)


@shared_task
def worker_heartbeat(worker_id: str):
    """
    PHASE-1: Worker heartbeat for crash detection.
    
    Workers should call this periodically (every 30 seconds) to indicate they're alive.
    """
    try:
        WorkerHeartbeat.objects.update_or_create(
            worker_id=worker_id,
            defaults={
                "last_heartbeat": timezone.now(),
                "metadata": {
                    "worker_id": worker_id,
                }
            }
        )
    except Exception as e:
        logger.error(f"Worker heartbeat failed: {e}", exc_info=True)

