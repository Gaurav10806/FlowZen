"""
Management command to sync workflow schedules with Celery Beat.

This command ensures that all enabled workflow schedules are properly
synchronized with django-celery-beat periodic tasks.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...triggers.schedule_manager import sync_all_workflow_schedules


class Command(BaseCommand):
    help = 'Sync all workflow schedules with Celery Beat'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS(f"Starting schedule sync at {timezone.now()}")
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )
        
        try:
            # Sync all schedules
            if not dry_run:
                results = sync_all_workflow_schedules()
            else:
                # For dry run, just show what would be done
                from ...models import Workflow
                workflows = Workflow.objects.filter(schedule_enabled=True)
                results = {
                    'synced': workflows.count(),
                    'created': 0,
                    'updated': 0,
                    'deleted': 0,
                    'errors': []
                }
                
                if verbose:
                    for workflow in workflows:
                        schedule_config = workflow.schedule or {}
                        cron_expr = schedule_config.get('cron_expression', 'Not configured')
                        self.stdout.write(f"  Would sync: {workflow.name} ({cron_expr})")
            
            # Display results
            self.stdout.write("\nSync Results:")
            self.stdout.write(f"  Workflows processed: {results['synced']}")
            self.stdout.write(f"  Tasks created: {results['created']}")
            self.stdout.write(f"  Tasks updated: {results['updated']}")
            self.stdout.write(f"  Tasks deleted: {results['deleted']}")
            
            if results['errors']:
                self.stdout.write(f"  Errors: {len(results['errors'])}")
                if verbose:
                    for error in results['errors']:
                        self.stdout.write(
                            self.style.ERROR(f"    {error}")
                        )
            
            if results['errors']:
                self.stdout.write(
                    self.style.WARNING("Sync completed with errors")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Sync completed successfully")
                )
                
        except Exception as e:
            raise CommandError(f"Schedule sync failed: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Schedule sync finished at {timezone.now()}")
        )