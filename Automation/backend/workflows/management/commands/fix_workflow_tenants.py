"""
Management command to fix workflows with missing tenant assignments.
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from workflows.models import Workflow, Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix workflows with missing tenant assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--default-tenant-slug',
            type=str,
            default='default',
            help='Slug of the default tenant to assign to workflows without tenants',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        default_tenant_slug = options['default_tenant_slug']
        
        self.stdout.write(f"Checking for workflows with missing tenants...")
        
        # Find workflows without tenants
        workflows_without_tenant = Workflow.objects.filter(tenant__isnull=True)
        count = workflows_without_tenant.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ All workflows have tenant assignments")
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f"Found {count} workflows without tenant assignments")
        )
        
        # Get or create default tenant
        try:
            default_tenant = Tenant.objects.get(slug=default_tenant_slug)
            self.stdout.write(f"Using default tenant: {default_tenant.name} ({default_tenant.slug})")
        except Tenant.DoesNotExist:
            if dry_run:
                self.stdout.write(
                    self.style.ERROR(f"❌ Default tenant '{default_tenant_slug}' not found")
                )
                return
            
            # Create default tenant
            default_tenant = Tenant.objects.create(
                name="Default Organization",
                slug=default_tenant_slug,
                settings={}
            )
            self.stdout.write(
                self.style.SUCCESS(f"✅ Created default tenant: {default_tenant.name}")
            )
        
        if dry_run:
            self.stdout.write("\n🔍 DRY RUN - Workflows that would be fixed:")
            for workflow in workflows_without_tenant[:10]:  # Show first 10
                self.stdout.write(f"  - {workflow.name} ({workflow.id}) - Owner: {workflow.owner.username}")
            
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
            
            self.stdout.write(f"\nRun without --dry-run to fix {count} workflows")
            return
        
        # Fix workflows
        self.stdout.write("Fixing workflows...")
        
        with transaction.atomic():
            updated_count = workflows_without_tenant.update(tenant=default_tenant)
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Fixed {updated_count} workflows")
            )
        
        # Verify fix
        remaining = Workflow.objects.filter(tenant__isnull=True).count()
        if remaining == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ All workflows now have tenant assignments")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ {remaining} workflows still missing tenants")
            )