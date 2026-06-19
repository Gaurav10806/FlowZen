"""
Django management command to create a safe test workflow.
"""
import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workflows.models import Workflow, Node


class Command(BaseCommand):
    help = 'Create a safe test workflow with manual trigger and delay'

    def handle(self, *args, **options):
        try:
            # Get or create a user for the workflow
            user, created = User.objects.get_or_create(
                username='admin',
                defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}
            )
            
            # Create the workflow
            workflow_data = {
                "name": "Safe Test Workflow",
                "description": "Minimal workflow for testing - manual trigger + 1 second delay",
                "nodes": [
                    {
                        "id": "trigger-1",
                        "type": "manual_trigger",
                        "position": {"x": 100, "y": 100},
                        "data": {
                            "label": "Manual Trigger",
                            "description": "Start workflow manually"
                        }
                    },
                    {
                        "id": "delay-1", 
                        "type": "delay",
                        "position": {"x": 300, "y": 100},
                        "data": {
                            "label": "Wait 1 Second",
                            "duration": 1
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "trigger-1",
                        "target": "delay-1"
                    }
                ]
            }
            
            # Check if workflow already exists
            existing_workflow = Workflow.objects.filter(name="Safe Test Workflow").first()
            if existing_workflow:
                self.stdout.write(
                    self.style.WARNING(f'Workflow "Safe Test Workflow" already exists with ID: {existing_workflow.id}')
                )
                return
            
            # Create the workflow
            workflow = Workflow.objects.create(
                name=workflow_data["name"],
                description=workflow_data["description"],
                owner=user,
                definition=workflow_data,
                status='draft'
            )
            
            # Create individual nodes
            for node_data in workflow_data["nodes"]:
                Node.objects.create(
                    workflow=workflow,
                    node_id=node_data["id"],
                    label=node_data["data"]["label"],
                    action_type=node_data["type"],
                    position_x=node_data["position"]["x"],
                    position_y=node_data["position"]["y"],
                    config=node_data["data"]
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created workflow "{workflow.name}" with ID: {workflow.id}')
            )
            self.stdout.write(f'Workflow contains {len(workflow_data["nodes"])} nodes and {len(workflow_data["edges"])} edges')
            self.stdout.write(f'Access it at: http://localhost:8000/admin/workflows/workflow/{workflow.id}/change/')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating workflow: {str(e)}')
            )