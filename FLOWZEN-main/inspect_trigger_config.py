import os
import django
import sys
import json

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from workflows.models import Workflow

print("Checking WhatsApp Workflow Configurations...")
workflows = Workflow.objects.filter(status='published')
for wf in workflows:
    print(f"Workflow: {wf.name} (ID: {wf.id})")
    nodes = wf.graph.get('nodes', [])
    for node in nodes:
        if node.get('type') == 'WhatsAppTriggerNode' or node.get('action_type') == 'whatsapp_trigger':
            print(f"  - Found WhatsApp Trigger Node")
            print(f"    - Config Credential ID: {node.get('config', {}).get('credential_id')}")
    print("-" * 30)
