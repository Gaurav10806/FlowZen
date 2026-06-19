import os
import django
import sys
import json

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from workflows.models import Workflow, Node

def create_seed_data():
    if Workflow.objects.filter(name="Hello World").exists():
        print("✅ 'Hello World' workflow already exists. Skipping.")
        return

    print("🌱 Seeding 'Hello World' workflow...")
    
    # Create Workflow
    workflow = Workflow.objects.create(
        name="Hello World",
        description="A simple starter workflow",
        is_active=True
    )
    
    # Trigger: Manual
    trigger_data = {
        "id": "trigger",
        "type": "manual_trigger",
        "position": {"x": 100, "y": 200},
        "data": {}
    }
    
    # Action: HTTP Request (Echo)
    action_data = {
        "id": "http_request",
        "type": "http-request",
        "position": {"x": 400, "y": 200},
        "data": {
            "url": "https://httpbin.org/get",
            "method": "GET"
        }
    }
    
    # Construct Graph
    graph = {
        "meta": {"version": "1.0"},
        "trigger": trigger_data,
        "nodes": {
            "trigger": trigger_data,
            "http_request": action_data
        },
        "connections": {
            "trigger": ["http_request"]
        }
    }
    
    workflow.graph = graph
    workflow.save()
    
    print(f"✅ Created workflow: {workflow.id}")

if __name__ == "__main__":
    create_seed_data()
