import os
import sys
import django
import json

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from workflows.models import Workflow, Credential, Tenant
from django.contrib.auth.models import User

def create_e2e_workflow():
    print("🚀 Setting up E2E Google Ecosystem Test...")

    # 1. Ensure Admin User
    user = User.objects.first()
    if not user:
        user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        print("Created admin user.")

    # 2. Find or Create Tenant
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Default Tenant")

    # 3. Create Placeholder Google Credential
    # The user must Authenticate this in UI!
    cred, created = Credential.objects.get_or_create(
        name="Test Google Account",
        owner=user,
        type="google_oauth",
        defaults={
            "provider": "google",
            "encrypted_data": json.dumps({"client_id": os.environ.get("GOOGLE_CLIENT_ID")}) # Placeholder
        }
    )
    if created:
        print(f"⚠️  Created Credential '{cred.name}' (ID: {cred.id}).")
        print("PLEASE AUTHENTICATE THIS CREDENTIAL IN THE UI BEFORE RUNNING!")
    else:
        print(f"✅ Found existing Credential '{cred.name}' (ID: {cred.id}).")

    # 4. Create Placeholder AI Credential
    ai_cred, _ = Credential.objects.get_or_create(
        name="Local AI (Ollama)",
        owner=user,
        type="ai_provider",
        defaults={
            "provider": "ollama",
            "encrypted_data": json.dumps({"base_url": "http://localhost:11434"})
        }
    )

    # 5. Build The Mega Workflow
    workflow_data = {
        "name": "E2E Google Ecosystem Test",
        "description": "Verifies YouTube, Drive, Sheet, and AI Agent.",
        "tenant": tenant,
        "owner": user,
        "graph": {
            "nodes": [
                {
                    "id": "trigger",
                    "type": "manual_trigger",
                    "position": {"x": 100, "y": 100},
                    "data": {}
                },
                {
                    "id": "node-yt",
                    "type": "youtube",
                    "position": {"x": 400, "y": 100},
                    "config": {
                        "credential_id": str(cred.id),
                        "operation": "search",
                        "query": "OpenAI Swarm",
                        "max_results": 3
                    }
                },
                {
                    "id": "node-ai",
                    "type": "ai_agent",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "credential_id": str(ai_cred.id),
                        "system_prompt": "You are a research assistant. Summarize the video titles passed to you.",
                        "user_prompt": "Found these videos: {{ $node.node-yt.json.items }}",
                        "response_mode": "text"
                    }
                },
                # Adding Drive List as parallel branch
                {
                    "id": "node-drive",
                    "type": "google_drive",
                    "position": {"x": 400, "y": 300},
                    "config": {
                        "credential_id": str(cred.id),
                        "operation": "list_files",
                        "query": "mimeType = 'application/vnd.google-apps.spreadsheet'",
                        "limit": 5
                    }
                },
                # Adding Sheets Read
                {
                    "id": "node-sheets",
                    "type": "google_sheets",
                    "position": {"x": 700, "y": 300},
                    "config": {
                        "credential_id": str(cred.id),
                        "operation": "read_range",
                        "spreadsheet_id": "{{ $node.node-drive.json.files[0].id }}", # Dynamic linking
                        "range_name": "Sheet1!A1:B10"
                    }
                }
            ],
            "edges": [
                {"source": "trigger", "target": "node-yt"},
                {"source": "trigger", "target": "node-drive"},
                {"source": "node-yt", "target": "node-ai"},
                {"source": "node-drive", "target": "node-sheets"}
            ]
        }
    }

    wf, created = Workflow.objects.update_or_create(
        name="E2E Google Ecosystem Test",
        defaults=workflow_data
    )
    
    print(f"✅ Workflow '{wf.name}' Created/Updated (ID: {wf.id})")
    print("\nNext Steps:")
    print(1, f"Go to http://localhost:8000/credentials/ and authenticate '{cred.name}'.")
    print(2, f"Open http://localhost:8000/workflow/{wf.id}/builder/")
    print(3, "Click 'Test' (Play Button).")
    print(4, "Check execution logs for success.")

if __name__ == "__main__":
    create_e2e_workflow()
