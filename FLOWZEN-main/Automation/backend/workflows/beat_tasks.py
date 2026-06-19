"""
Celery Beat periodic tasks for scheduled workflows.
"""
import uuid
import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from .models import Workflow, WorkflowExecution
from .tasks import run_workflow_execution

logger = logging.getLogger(__name__)


@shared_task
def check_scheduled_workflows():
    """
    Periodic task to check and trigger scheduled workflows.
    Uses croniter for cron expression parsing.
    """
    try:
        from croniter import croniter
    except ImportError:
        logger.warning("croniter not installed, using basic schedule check")
        croniter = None
    
    # Get active workflows with schedule enabled
    workflows = Workflow.objects.filter(
        status="published",  # Only published workflows
        schedule_enabled=True
    ).exclude(schedule={})
    
    current_time = timezone.now()
    
    for workflow in workflows:
        schedule = workflow.schedule
        
        if not schedule.get("enabled", False):
            continue
        
        # Get cron expression or interval
        cron_expression = schedule.get("cron")
        interval_seconds = schedule.get("interval_seconds")
        
        # Check last run time
        last_run_key = f"workflow_schedule_last_run_{workflow.id}"
        from django.core.cache import cache
        last_run = cache.get(last_run_key)
        
        should_run = False
        
        if cron_expression and croniter:
            # Parse cron expression
            try:
                cron = croniter(cron_expression, current_time)
                next_run = cron.get_prev(timezone.datetime)
                
                if last_run is None or (current_time - last_run).total_seconds() >= 60:
                    # Check if it's time to run (within last minute)
                    if (current_time - next_run).total_seconds() < 60:
                        should_run = True
            except Exception as e:
                logger.error(f"Error parsing cron expression for workflow {workflow.id}: {e}")
        
        elif interval_seconds:
            # Interval-based schedule
            if last_run is None:
                should_run = True
            else:
                elapsed = (current_time - last_run).total_seconds()
                if elapsed >= interval_seconds:
                    should_run = True
        
        if should_run:
            # Create execution
            input_payload = schedule.get("payload", {})
            if isinstance(input_payload, list):
                input_items = [{"json": item} for item in input_payload]
            else:
                input_items = [{"json": input_payload}]
            
            # PHASE-1: Ensure tenant is set
            if not workflow.tenant:
                logger.error(f"Workflow {workflow.id} has no tenant, skipping scheduled execution")
                continue
            
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=workflow.tenant,  # PHASE-1: Explicit tenant FK
                input_payload=input_payload,
                input_items=input_items,
                triggered_by="schedule",
                correlation_id=str(uuid.uuid4()),
            )
            
            # Enqueue workflow execution
            execution.status = "queued"
            execution.save(update_fields=["status"])
            transaction.on_commit(lambda: run_workflow_execution.delay(str(execution.id)))
            
            # Update last run time
            cache.set(last_run_key, current_time, 86400)  # Cache for 24 hours
            
            logger.info(f"Scheduled workflow {workflow.id} triggered")


def sync_workflow_schedules():
    """
    Sync workflow schedules with django-celery-beat PeriodicTask.
    Creates/updates PeriodicTask for each scheduled workflow.
    Checks workflow.graph.meta.cron for cron expressions.
    """
    try:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule
    except ImportError:
        logger.warning("django-celery-beat not installed, skipping schedule sync")
        return
    
    workflows = Workflow.objects.filter(
        status__in=["published", "draft"],  # Allow draft workflows too
        schedule_enabled=True
    )
    
    for workflow in workflows:
        # Check graph.meta.cron first, then workflow.schedule
        graph = workflow.graph or {}
        meta = graph.get("meta", {})
        cron_expression = meta.get("cron") or workflow.schedule.get("cron")
        
        if not cron_expression:
            # Remove existing task if cron is removed
            task_name = f"workflow_schedule_{workflow.id}"
            PeriodicTask.objects.filter(name=task_name).delete()
            continue
        
        # Parse cron expression (format: "minute hour day month day_of_week")
        parts = cron_expression.split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression for workflow {workflow.id}: {cron_expression}")
            continue
        
        minute, hour, day_of_month, month, day_of_week = parts
        
        # Get or create CrontabSchedule
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month,
        )
        
        # Get or create PeriodicTask
        task_name = f"workflow_schedule_{workflow.id}"
        import json
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "workflows.beat_tasks.trigger_scheduled_workflow",
                "crontab": crontab,
                "args": json.dumps([str(workflow.id)]),
                "enabled": True,
            }
        )
        logger.info(f"Synced schedule for workflow {workflow.id}: {cron_expression}")


@shared_task
def trigger_scheduled_workflow(workflow_id: str):
    """Task triggered by Celery Beat for a specific workflow."""
    try:
        workflow = Workflow.objects.get(id=workflow_id, schedule_enabled=True)
        
        schedule = workflow.schedule
        input_payload = schedule.get("payload", {})
        if isinstance(input_payload, list):
            input_items = [{"json": item} for item in input_payload]
        else:
            input_items = [{"json": input_payload}]
        
        # PHASE-1: Ensure tenant is set
        if not workflow.tenant:
            logger.error(f"Workflow {workflow_id} has no tenant, skipping scheduled execution")
            return
        
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,  # PHASE-1: Explicit tenant FK
            input_payload=input_payload,
            input_items=input_items,
            triggered_by="schedule",
            correlation_id=str(uuid.uuid4()),
        )
        
        execution.status = "queued"
        execution.save(update_fields=["status"])
        transaction.on_commit(lambda: run_workflow_execution.delay(str(execution.id)))
        logger.info(f"Scheduled workflow {workflow_id} triggered via PeriodicTask")
        
    except Workflow.DoesNotExist:
        logger.warning(f"Workflow {workflow_id} not found or schedule disabled")
    except Exception as e:
        logger.error(f"Error triggering scheduled workflow {workflow_id}: {e}", exc_info=True)

