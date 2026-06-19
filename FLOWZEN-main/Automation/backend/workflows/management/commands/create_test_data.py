from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workflows.models import Workflow
import uuid


class Command(BaseCommand):
    help = 'Create test data for debugging'

    def handle(self, *args, **options):
        # Get or create admin user
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(f'Created admin user')
        else:
            self.stdout.write(f'Admin user already exists')

        # Create test workflows
        test_workflows = [
            {
                'name': 'Simple Test Workflow',
                'description': 'A basic workflow for testing',
                'graph': {
                    'meta': {'name': 'Simple Test Workflow', 'version': '1.0'},
                    'trigger': {'id': 'trigger1', 'type': 'manual_trigger', 'params': {}},
                    'nodes': {
                        'node1': {'type': 'delay', 'params': {'delay_seconds': 1}}
                    },
                    'connections': {'trigger1': ['node1']}
                }
            },
            {
                'name': 'HTTP Request Workflow',
                'description': 'A workflow that makes HTTP requests',
                'graph': {
                    'meta': {'name': 'HTTP Request Workflow', 'version': '1.0'},
                    'trigger': {'id': 'trigger1', 'type': 'manual_trigger', 'params': {}},
                    'nodes': {
                        'node1': {'type': 'http_request', 'params': {'url': 'https://httpbin.org/get', 'method': 'GET'}}
                    },
                    'connections': {'trigger1': ['node1']}
                }
            },
            {
                'name': 'Multi-Node Workflow',
                'description': 'A workflow with multiple nodes',
                'graph': {
                    'meta': {'name': 'Multi-Node Workflow', 'version': '1.0'},
                    'trigger': {'id': 'trigger1', 'type': 'manual_trigger', 'params': {}},
                    'nodes': {
                        'node1': {'type': 'delay', 'params': {'delay_seconds': 1}},
                        'node2': {'type': 'delay', 'params': {'delay_seconds': 2}}
                    },
                    'connections': {'trigger1': ['node1'], 'node1': ['node2']}
                }
            }
        ]

        created_count = 0
        for workflow_data in test_workflows:
            workflow, created = Workflow.objects.get_or_create(
                name=workflow_data['name'],
                owner=user,
                defaults={
                    'description': workflow_data['description'],
                    'graph': workflow_data['graph'],
                    'status': 'draft',
                    'created_by': user
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created workflow: {workflow.name}')
            else:
                self.stdout.write(f'Workflow already exists: {workflow.name}')

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new workflows')
        )

        # List all workflows
        workflows = Workflow.objects.filter(owner=user)
        self.stdout.write(f'Total workflows for admin user: {workflows.count()}')
        for wf in workflows:
            self.stdout.write(f'  - {wf.name} ({wf.id}) - {wf.status}')