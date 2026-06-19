import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')
django.setup()
from workflows.models import Credential
from workflows.utils.credential_resolver import resolve_credential_data
cred = Credential.objects.get(id='fabd6664-4a12-4b2c-9497-9cb009928570')
data = resolve_credential_data(cred)
print(f"STORED_PHONE_ID: {data.get('phone_number_id')}")
print(f"LENGTH: {len(str(data.get('phone_number_id')))}")
