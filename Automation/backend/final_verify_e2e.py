import os
import django
import json
import logging
import requests

# Disable logging to keep output clean
logging.disable(logging.CRITICAL)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from workflows.models import Credential, Workflow, WorkflowExecution
from django.contrib.auth.models import User

# 1. Verification
print("--- 1. Checking Credentials ---")
admin = User.objects.first()
creds = Credential.objects.filter(provider="meta_whatsapp")
if not creds.exists():
    print("❌ No meta_whatsapp credentials found!")
else:
    for c in creds:
        data = c.encrypted_data
        if isinstance(data, str): data = json.loads(data)
        stored_id = data.get("phone_number_id") or data.get("phone_id")
        print(f"✅ Credential {c.id}: stored_id={stored_id}")

# 2. Trigger Webhook Simulation
print("\n--- 2. Triggering Webhook Simulation ---")
if creds.exists():
    cred = creds.first()
    data = cred.encrypted_data
    if isinstance(data, str): data = json.loads(data)
    phone_id = data.get("phone_number_id") or data.get("phone_id")
    
    webhook_url = "http://localhost:8000/api/webhooks/whatsapp/"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "123456789",
                        "phone_number_id": phone_id
                    },
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": "9112345678"}],
                    "messages": [{
                        "from": "9112345678",
                        "id": "wamid.HBgLOTE4OD...test",
                        "timestamp": "1665555555",
                        "text": {"body": "Hello World"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        print(f"Webhook Status: {response.status_code}")
        print(f"Webhook Response: {response.text}")
    except Exception as e:
        print(f"Webhook Error: {e}")

# 3. Check for specific log signatures (Manual check via docker logs next)
print("\n--- 3. Check Log Signatures via: docker logs automation-backend ---")
print("Expected signatures:")
print("- Checking credential ...: stored_id=...")
print("- ✅ Credential Matched")
print("- 📌 Phone Number ID: ...")
print("- 📌 Token Present: True")
