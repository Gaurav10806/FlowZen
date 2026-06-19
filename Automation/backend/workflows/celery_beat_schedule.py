"""
PHASE-1: Celery Beat schedule configuration for watchdog tasks.
Add this to your CELERY_BEAT_SCHEDULE in settings.py.
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # PHASE-1: Watchdog tasks run every minute
    "watchdog-stuck-executions": {
        "task": "workflows.tasks_watchdog.watchdog_stuck_executions",
        "schedule": crontab(minute="*"),  # Every minute
    },
    "watchdog-stuck-node-executions": {
        "task": "workflows.tasks_watchdog.watchdog_stuck_node_executions",
        "schedule": crontab(minute="*"),  # Every minute
    },
    "watchdog-reclaim-run-requests": {
        "task": "workflows.tasks_watchdog.watchdog_reclaim_run_requests",
        "schedule": crontab(minute="*/2"),  # Every 2 minutes
    },
}

