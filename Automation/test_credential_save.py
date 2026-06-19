
import os
import django
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from django.contrib.auth import get_user_model

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')
django.setup()

from workflows.views import CredentialViewSet
from workflows.models import Credential

User = get_user_model()

def test_credential_save():
    print("🚀 Starting Debug Script: Credential Save Response Inspection")
    
    # 1. Get a test user
    user = User.objects.first()
    if not user:
        print("❌ No users found in DB. Cannot test.")
        return

    print(f"👤 Using User: {user.username} (ID: {user.id})")

    # 2. Setup Request Factory
    factory = APIRequestFactory()
    view = CredentialViewSet.as_view({'post': 'create'})

    # 3. Define Test Payload (Valid Data used previously)
    payload = {
        "name": "Debug Credential",
        "type": "telegram_bot",
        "provider": "telegram_bot",
        "encrypted_data": {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1"
        }
    }
    
    # 4. Create Request
    request = factory.post('/api/v1/credentials/', payload, format='json')
    force_authenticate(request, user=user)

    # 5. Execute View
    try:
        response = view(request)
        print("\n📥 --- BACKEND RESPONSE ---")
        print(f"Status Code: {response.status_code}")
        
        # Parse data
        if hasattr(response, 'data'):
            import json
            print("Response Data (JSON):")
            print(json.dumps(response.data, indent=2, default=str))
        else:
            print("Response Content (Raw):")
            print(response.rendered_content)
            
    except Exception as e:
        print(f"\n❌ EXCEPTION DURING VIEW EXECUTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_credential_save()
