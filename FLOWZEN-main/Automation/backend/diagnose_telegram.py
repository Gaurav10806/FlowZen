
import os
import django
import requests
import json
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from workflows.models import Credential, WorkflowExecution

def check_webhook_info():
    print("\n--- 1. Checking Telegram Webhook Info ---")
    try:
        cred = Credential.objects.filter(type__in=['telegram_bot', 'telegram']).order_by('-created_at').first()
        if not cred:
            print("No Telegram credential found.")
            return None
            
        token = cred.encrypted_data.get('bot_token')
        if not token:
            print("No token found.")
            return None
            
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        print(f"Requesting: {url.replace(token, '******')}...")
        resp = requests.get(url, timeout=10)
        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {resp.text}")
        return resp.json()
    except Exception as e:
        print(f"Error checking webhook: {e}")
        return None

def simulate_webhook_payload():
    print("\n--- 2. Simulating Local Webhook Payload ---")
    payload = {
        "update_id": 99999,
        "message": {
            "message_id": 1234,
            "from": {
                "id": 6484311805,
                "is_bot": False,
                "first_name": "Test",
                "username": "tester"
            },
            "chat": {
                "id": 6484311805,
                "first_name": "Test",
                "username": "tester",
                "type": "private"
            },
            "date": int(time.time()),
            "text": "hii"
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'X-Telegram-Bot-Api-Secret-Token': 'flowzen_secure_v1' # Assuming this matches or is ignored if not set in credential
    }
    
    try:
        print("Sending POST to http://127.0.0.1:8000/api/webhooks/telegram/")
        resp = requests.post('http://127.0.0.1:8000/api/webhooks/telegram/', json=payload, headers=headers)
        print(f"Local Simulation Status: {resp.status_code}")
        print(f"Local Simulation Response: {resp.text}")
        return resp.status_code
    except Exception as e:
        print(f"Error simulating webhook: {e}")
        return None

if __name__ == "__main__":
    check_webhook_info()
    simulate_webhook_payload()
