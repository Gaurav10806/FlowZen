import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workflows.models import Tenant, Organization, Membership

class Command(BaseCommand):
    help = 'Initialize default tenant and organization, and link existing users'

    def handle(self, *args, **options):
        self.stdout.write("Initializing default tenant and organization...")
        
        # 1. Ensure default Tenant exists
        tenant, created = Tenant.objects.get_or_create(
            slug='default',
            defaults={'name': 'Default Tenant'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default tenant: {tenant.name}"))
        else:
            self.stdout.write(f"Default tenant already exists: {tenant.name}")

        # 2. Ensure default Organization exists
        org, created = Organization.objects.get_or_create(
            slug='default-org',
            defaults={
                'name': 'Default Organization',
                'tenant': tenant
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default organization: {org.name}"))
        else:
            # Ensure tenant is linked if org already existed but tenant was null
            if org.tenant is None:
                org.tenant = tenant
                org.save()
                self.stdout.write(self.style.SUCCESS(f"Linked tenant to existing organization: {org.name}"))
            else:
                self.stdout.write(f"Default organization already exists: {org.name}")

        # 3. Create Membership for all active users
        users = User.objects.all()
        membership_count = 0
        for user in users:
            membership, created = Membership.objects.get_or_create(
                user=user,
                organization=org,
                defaults={'role': 'owner' if user.is_superuser else 'admin'}
            )
            if created:
                membership_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Created {membership_count} new memberships"))
        self.stdout.write(self.style.SUCCESS("Tenant initialization complete!"))
