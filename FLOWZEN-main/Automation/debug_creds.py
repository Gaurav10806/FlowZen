import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')
django.setup()
from workflows.models import Credential
from workflows.utils.credential_resolver import resolve_credential_data
creds = Credential.objects.filter(type='meta_whatsapp')
for c in creds:
    data = resolve_credential_data(c)
    print(f"NAME: {c.name} | ID: {c.id} | PHONE_ID: {data.get('phone_number_id')}")
