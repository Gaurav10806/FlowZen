"""
Schedule Trigger Manager

This module manages workflow scheduling using Celery Beat and django-celery-beat.
It provides the bridge between workflow schedules and Celery periodic tasks.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from croniter import croniter

from django.utils import timezone
from django.db import transaction
from celery import shared_task

try:
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
    CELERY_BEAT_AVAILABLE = True
except ImportError:
    CELERY_BEAT_AVAILABLE = False
    PeriodicTask = None
    CrontabSchedule = None
    IntervalSchedule = None

from ..models import Workflow, WorkflowExecution
from ..tasks import execute_workflow_with_core_engine


logger = logging.getLogger(__name__)


class ScheduleManager:
    """
    Manages workflow scheduling with Celery Beat integration.
    
    This class handles the synchronization between workflow schedule
    configurations and Celery Beat periodic tasks.
    """
    
    def __init__(self):
        """Initialize the schedule manager."""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        if not CELERY_BEAT_AVAILABLE:
            self.logger.warning("django-celery-beat not available, scheduling disabled")
    
    def sync_all_schedules(self) -> Dict[str, Any]:
        """
        Sync all workflow schedules with Celery Beat.
        
        Returns:
            Dictionary with sync results
        """
        if not CELERY_BEAT_AVAILABLE:
            return {'error': 'django-celery-beat not available'}
        
        results = {
            'synced': 0,
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'errors': []
        }
        
        try:
            # Get all workflows with schedules
            workflows = Workflow.objects.filter(schedule_enabled=True)
            
            for workflow in workflows:
                try:
                    result = self.sync_workflow_schedule(workflow)
                    results['synced'] += 1
                    if result.get('created'):
                        results['created'] += 1
                    elif result.get('updated'):
                        results['updated'] += 1
                except Exception as e:
                    self.logger.error(f"Failed to sync schedule for workflow {workflow.id}: {e}")
                    results['errors'].append({
                        'workflow_id': str(workflow.id),
                        'error': str(e)
                    })
            
            # Clean up orphaned tasks
            deleted_count = self._cleanup_orphaned_tasks()
            results['deleted'] = deleted_count
            
            self.logger.info(f"Schedule sync completed: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Schedule sync failed: {e}")
            results['errors'].append({'error': str(e)})
            return results
    
    def sync_workflow_schedule(self, workflow: Workflow) -> Dict[str, Any]:
        """
        Sync a single workflow's schedule with Celery Beat.
        
        Args:
            workflow: Workflow instance
            
        Returns:
            Dictionary with sync result
        """
        if not CELERY_BEAT_AVAILABLE:
            return {'error': 'django-celery-beat not available'}
        
        task_name = f"workflow_schedule_{workflow.id}"
        
        # If schedule is disabled, remove the task
        if not workflow.schedule_enabled:
            deleted_count = PeriodicTask.objects.filter(name=task_name).delete()[0]
            if deleted_count > 0:
                self.logger.info(f"Deleted periodic task for disabled workflow {workflow.id}")
                return {'deleted': True}
            return {'skipped': True}
        
        # Get schedule configuration
        schedule_config = workflow.schedule or {}
        cron_expression = schedule_config.get('cron_expression')
        
        if not cron_expression:
            self.logger.warning(f"Workflow {workflow.id} has schedule enabled but no cron expression")
            return {'error': 'No cron expression configured'}
        
        try:
            # Validate cron expression
            self._validate_cron_expression(cron_expression)
            
            # Parse cron expression
            cron_schedule = self._create_cron_schedule(cron_expression)
            
            # Create or update periodic task
            task, created = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    'task': 'workflows.triggers.schedule_manager.trigger_scheduled_workflow',
                    'crontab': cron_schedule,
                    'args': f'["{workflow.id}"]',
                    'enabled': True,
                    'description': f"Scheduled execution for workflow: {workflow.name}",
                    'kwargs': '{}',
                    'expires': None,
                    'one_off': False
                }
            )
            
            action = 'created' if created else 'updated'
            self.logger.info(f"{action.title()} periodic task for workflow {workflow.id}")
            
            return {action: True, 'task_name': task_name}
            
        except Exception as e:
            self.logger.error(f"Failed to sync schedule for workflow {workflow.id}: {e}")
            raise
    
    def _validate_cron_expression(self, cron_expression: str) -> None:
        """
        Validate cron expression format.
        
        Args:
            cron_expression: Cron expression string
            
        Raises:
            ValueError: If cron expression is invalid
        """
        try:
            # Test with croniter
            croniter(cron_expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{cron_expression}': {e}")
    
    def _create_cron_schedule(self, cron_expression: str) -> CrontabSchedule:
        """
        Create or get CrontabSchedule for cron expression.
        
        Args:
            cron_expression: Cron expression (e.g., "0 9 * * 1-5")
            
        Returns:
            CrontabSchedule instance
        """
        # Parse cron expression
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron expression must have 5 parts, got {len(parts)}")
        
        minute, hour, day_of_month, month_of_year, day_of_week = parts
        
        # Get or create CrontabSchedule
        crontab, created = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
            timezone=timezone.get_current_timezone()
        )
        
        return crontab
    
    def _cleanup_orphaned_tasks(self) -> int:
        """
        Clean up periodic tasks for workflows that no longer exist or have scheduling disabled.
        
        Returns:
            Number of tasks deleted
        """
        if not CELERY_BEAT_AVAILABLE:
            return 0
        
        # Find all workflow schedule tasks
        schedule_tasks = PeriodicTask.objects.filter(
            name__startswith='workflow_schedule_'
        )
        
        deleted_count = 0
        
        for task in schedule_tasks:
            # Extract workflow ID from task name
            try:
                workflow_id = task.name.replace('workflow_schedule_', '')
                
                # Check if workflow exists and has scheduling enabled
                try:
                    workflow = Workflow.objects.get(id=workflow_id)
                    if not workflow.schedule_enabled:
                        task.delete()
                        deleted_count += 1
                        self.logger.info(f"Deleted task for disabled workflow {workflow_id}")
                except Workflow.DoesNotExist:
                    task.delete()
                    deleted_count += 1
                    self.logger.info(f"Deleted task for non-existent workflow {workflow_id}")
                    
            except Exception as e:
                self.logger.warning(f"Failed to process task {task.name}: {e}")
        
        return deleted_count
    
    def get_next_executions(self, workflow: Workflow, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get next scheduled execution times for a workflow.
        
        Args:
            workflow: Workflow instance
            count: Number of next executions to return
            
        Returns:
            List of execution time dictionaries
        """
        if not workflow.schedule_enabled:
            return []
        
        schedule_config = workflow.schedule or {}
        cron_expression = schedule_config.get('cron_expression')
        
        if not cron_expression:
            return []
        
        try:
            # Use croniter to calculate next executions
            now = timezone.now()
            cron = croniter(cron_expression, now)
            
            executions = []
            for _ in range(count):
                next_time = cron.get_next(datetime)
                executions.append({
                    'scheduled_time': next_time.isoformat(),
                    'local_time': next_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'relative_time': self._format_relative_time(next_time - now)
                })
            
            return executions
            
        except Exception as e:
            self.logger.error(f"Failed to calculate next executions for workflow {workflow.id}: {e}")
            return []
    
    def _format_relative_time(self, delta: timedelta) -> str:
        """Format timedelta as human-readable relative time."""
        total_seconds = int(delta.total_seconds())
        
        if total_seconds < 60:
            return f"in {total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"in {minutes} minutes"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"in {hours} hours"
        else:
            days = total_seconds // 86400
            return f"in {days} days"
    
    def disable_workflow_schedule(self, workflow: Workflow) -> bool:
        """
        Disable scheduling for a workflow.
        
        Args:
            workflow: Workflow instance
            
        Returns:
            True if task was disabled/deleted, False otherwise
        """
        if not CELERY_BEAT_AVAILABLE:
            return False
        
        task_name = f"workflow_schedule_{workflow.id}"
        
        try:
            task = PeriodicTask.objects.get(name=task_name)
            task.delete()
            self.logger.info(f"Deleted periodic task for workflow {workflow.id}")
            return True
        except PeriodicTask.DoesNotExist:
            return False
    
    def get_schedule_status(self, workflow: Workflow) -> Dict[str, Any]:
        """
        Get scheduling status for a workflow.
        
        Args:
            workflow: Workflow instance
            
        Returns:
            Dictionary with schedule status
        """
        if not CELERY_BEAT_AVAILABLE:
            return {
                'available': False,
                'error': 'django-celery-beat not available'
            }
        
        status = {
            'available': True,
            'enabled': workflow.schedule_enabled,
            'configured': bool(workflow.schedule),
            'cron_expression': None,
            'task_exists': False,
            'task_enabled': False,
            'next_executions': [],
            'last_execution': None
        }
        
        if workflow.schedule:
            status['cron_expression'] = workflow.schedule.get('cron_expression')
        
        # Check if periodic task exists
        task_name = f"workflow_schedule_{workflow.id}"
        try:
            task = PeriodicTask.objects.get(name=task_name)
            status['task_exists'] = True
            status['task_enabled'] = task.enabled
        except PeriodicTask.DoesNotExist:
            pass
        
        # Get next executions if enabled
        if workflow.schedule_enabled:
            status['next_executions'] = self.get_next_executions(workflow)
        
        # Get last scheduled execution
        last_execution = WorkflowExecution.objects.filter(
            workflow=workflow,
            triggered_by='schedule'
        ).order_by('-created_at').first()
        
        if last_execution:
            status['last_execution'] = {
                'id': str(last_execution.id),
                'created_at': last_execution.created_at.isoformat(),
                'status': last_execution.status
            }
        
        return status


# Celery task for scheduled workflow execution
@shared_task(bind=True, max_retries=3)
def trigger_scheduled_workflow(self, workflow_id: str):
    """
    Celery task triggered by Beat for scheduled workflow execution.
    
    Args:
        workflow_id: UUID of the workflow to execute
    """
    try:
        # Get workflow and validate it's still schedulable
        workflow = Workflow.objects.get(id=workflow_id, schedule_enabled=True)
        
        logger.info(f"Triggering scheduled execution for workflow {workflow_id}")
        
        # Create execution record
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            status='pending',
            triggered_by='schedule',
            input_data={
                'trigger_type': 'schedule',
                'scheduled_time': timezone.now().isoformat(),
                'cron_expression': workflow.schedule.get('cron_expression', ''),
                'static_data': workflow.schedule.get('static_data', {})
            },
            created_by=None  # Scheduled executions don't have users
        )
        
        # Queue execution
        execution.status = 'queued'
        execution.save(update_fields=['status'])
        
        # Use core engine task
        execute_workflow_with_core_engine.delay(str(execution.id))
        
        logger.info(f"Scheduled workflow {workflow_id} queued as execution {execution.id}")
        
        return {
            'success': True,
            'workflow_id': workflow_id,
            'execution_id': str(execution.id)
        }
        
    except Workflow.DoesNotExist:
        logger.warning(f"Scheduled workflow {workflow_id} not found or scheduling disabled")
        return {
            'success': False,
            'error': 'Workflow not found or scheduling disabled'
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger scheduled workflow {workflow_id}: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)  # 1, 2, 4 minutes
            raise self.retry(exc=e, countdown=retry_delay)
        
        return {
            'success': False,
            'error': str(e)
        }


# Convenience functions
def sync_all_workflow_schedules() -> Dict[str, Any]:
    """Sync all workflow schedules - convenience function."""
    manager = ScheduleManager()
    return manager.sync_all_schedules()


def sync_workflow_schedule(workflow: Workflow) -> Dict[str, Any]:
    """Sync single workflow schedule - convenience function."""
    manager = ScheduleManager()
    return manager.sync_workflow_schedule(workflow)


def get_workflow_schedule_status(workflow: Workflow) -> Dict[str, Any]:
    """Get workflow schedule status - convenience function."""
    manager = ScheduleManager()
    return manager.get_schedule_status(workflow)