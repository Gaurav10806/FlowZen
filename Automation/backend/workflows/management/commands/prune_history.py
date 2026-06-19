from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from workflows.models import WorkflowExecution
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Prune workflow execution history older than specified days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days of history to keep (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate deletion without deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f"Pruning executions older than {cutoff} ({days} days)...")
        
        queryset = WorkflowExecution.objects.filter(started_at__lt=cutoff)
        count = queryset.count()
        
        if count == 0:
             self.stdout.write(self.style.SUCCESS('No executions to prune.'))
             return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would delete {count} executions."))
        else:
            # Delete in batches if needed, but standard delete is okay for now
            deleted_count, _ = queryset.delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} executions."))
            logger.info(f"Pruned {deleted_count} workflow executions older than {days} days.")
