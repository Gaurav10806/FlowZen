from django.core.management.base import BaseCommand
from workflows.models import WorkflowTemplate
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Populates the marketplace with dummy community nodes/workflows'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        # Ensure a system user exists
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})

        templates = [
            {
                "name": "Email Parser Logic",
                "description": "Extracts order details from incoming emails using Regex.",
                "category": "automation",
                "tags": ["email", "regex", "parser"],
                "template_json": {
                    "nodes": [
                        {
                            "id": "node_1",
                            "type": "trigger",
                            "action_type": "email_trigger",
                            "label": "Email Trigger",
                            "position": {"x": 100, "y": 100}
                        },
                        {
                            "id": "node_2",
                            "type": "action",
                            "action_type": "code",
                            "label": "Regex Parser",
                            "position": {"x": 300, "y": 100},
                            "config": {
                                "code": "import re\n# Logic here"
                            }
                        }
                    ],
                    "edges": [
                        {"source": "node_1", "target": "node_2"}
                    ]
                }
            },
            {
                "name": "Slack Notification",
                "description": "Sends a formatted Slack message on new leads.",
                "category": "notifications",
                "tags": ["slack", "leads", "alert"],
                "template_json": {
                    "nodes": [],
                    "edges": []
                }
            },
            {
                "name": "Daily Report Generator",
                "description": "Aggregates database metrics and sends a PDF report.",
                "category": "reporting",
                "tags": ["report", "pdf", "schedule"],
                "template_json": {
                     "nodes": [],
                     "edges": []
                }
            }
        ]

        for t in templates:
            WorkflowTemplate.objects.get_or_create(
                name=t["name"],
                defaults={
                    "description": t["description"],
                    "category": t["category"],
                    "tags": t["tags"],
                    "template_json": t["template_json"],
                    "is_public": True,
                    "created_by": admin_user,
                    "usage_count": 42
                }
            )
            self.stdout.write(self.style.SUCCESS(f'Created template: {t["name"]}'))
