"""
Django management command to create a demo workflow for chatbot testing.

This creates a simple workflow that can be triggered by chat messages
and demonstrates the integration between the chatbot and workflow engine.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workflows.models import Workflow, Tenant
import uuid


class Command(BaseCommand):
    help = 'Create a demo workflow for chatbot testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username of the workflow owner (defaults to first superuser)',
        )

    def handle(self, *args, **options):
        # Get user
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User "{username}" not found')
                )
                return
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('No superuser found. Please create one first.')
                )
                return

        # Get or create tenant
        tenant, created = Tenant.objects.get_or_create(
            slug=f"{user.username}-workspace",
            defaults={
                'name': f"{user.username}'s Workspace"
            }
        )

        # Create demo workflow
        workflow_graph = {
            "nodes": [
                {
                    "id": "chat_trigger_1",
                    "type": "chat_trigger",
                    "label": "Chat Trigger",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "intent_extraction": True,
                        "context_window": 5,
                        "response_format": "text"
                    }
                },
                {
                    "id": "process_message_1",
                    "type": "code",
                    "label": "Process Message",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "code": """
# Process the chat message
user_message = input_data.get('message', '')
session_id = input_data.get('session_id', '')

# Simple message processing
if 'hello' in user_message.lower():
    response = f"Hello! I received your message: '{user_message}'"
elif 'help' in user_message.lower():
    response = "I can help you with various tasks. Try asking me about the weather, time, or just say hello!"
elif 'time' in user_message.lower():
    import datetime
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = f"The current time is: {current_time}"
elif 'weather' in user_message.lower():
    response = "I'd love to help with weather, but I need a weather API to be configured first!"
else:
    response = f"I understand you said: '{user_message}'. How can I help you with that?"

# Return processed data
output_data = {
    'processed_message': user_message,
    'response_text': response,
    'session_id': session_id
}
"""
                    }
                },
                {
                    "id": "chat_response_1",
                    "type": "chat_response",
                    "label": "Chat Response",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "message_template": "{response_text}",
                        "response_type": "text",
                        "include_data": False
                    }
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "chat_trigger_1",
                    "target": "process_message_1"
                },
                {
                    "id": "edge_2",
                    "source": "process_message_1",
                    "target": "chat_response_1"
                }
            ]
        }

        workflow = Workflow.objects.create(
            name="Chat Demo Workflow",
            description="A simple demo workflow that responds to chat messages with processed responses.",
            graph=workflow_graph,
            status="published",
            owner=user,
            tenant=tenant
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created chat demo workflow:\n'
                f'  ID: {workflow.id}\n'
                f'  Name: {workflow.name}\n'
                f'  Owner: {user.username}\n'
                f'  Tenant: {tenant.name}\n'
                f'\nTo test the chatbot:\n'
                f'1. Create a chat session\n'
                f'2. Associate it with workflow ID: {workflow.id}\n'
                f'3. Send messages like "hello", "help", "time", or "weather"\n'
            )
        )

        # Also create a more advanced demo workflow
        advanced_workflow_graph = {
            "nodes": [
                {
                    "id": "chat_trigger_2",
                    "type": "chat_trigger",
                    "label": "Advanced Chat Trigger",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "intent_extraction": True,
                        "context_window": 10,
                        "required_entities": [],
                        "response_format": "text"
                    }
                },
                {
                    "id": "condition_1",
                    "type": "condition",
                    "label": "Check Intent",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "expression": "'email' in payload.get('message', '').lower()"
                    }
                },
                {
                    "id": "send_email_1",
                    "type": "email_send",
                    "label": "Send Email",
                    "position": {"x": 500, "y": 50},
                    "config": {
                        "to": "admin@example.com",
                        "subject": "Chat Request",
                        "body": "User sent a chat message: {{message}}"
                    }
                },
                {
                    "id": "simple_response_1",
                    "type": "chat_response",
                    "label": "Simple Response",
                    "position": {"x": 500, "y": 150},
                    "config": {
                        "message_template": "I received your message: {message}",
                        "response_type": "text"
                    }
                },
                {
                    "id": "email_confirmation_1",
                    "type": "chat_response",
                    "label": "Email Confirmation",
                    "position": {"x": 700, "y": 50},
                    "config": {
                        "message_template": "I've sent an email notification about your request: {message}",
                        "response_type": "text"
                    }
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "chat_trigger_2",
                    "target": "condition_1"
                },
                {
                    "id": "edge_2",
                    "source": "condition_1",
                    "target": "send_email_1",
                    "condition": "true"
                },
                {
                    "id": "edge_3",
                    "source": "condition_1",
                    "target": "simple_response_1",
                    "condition": "false"
                },
                {
                    "id": "edge_4",
                    "source": "send_email_1",
                    "target": "email_confirmation_1"
                }
            ]
        }

        advanced_workflow = Workflow.objects.create(
            name="Advanced Chat Demo Workflow",
            description="An advanced demo workflow that processes chat messages and can send emails based on content.",
            graph=advanced_workflow_graph,
            status="published",
            owner=user,
            tenant=tenant
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nAlso created advanced chat demo workflow:\n'
                f'  ID: {advanced_workflow.id}\n'
                f'  Name: {advanced_workflow.name}\n'
                f'\nThis workflow will:\n'
                f'- Send an email if the message contains "email"\n'
                f'- Otherwise just echo the message back\n'
            )
        )