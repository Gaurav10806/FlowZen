import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')
django.setup()
from workflows.models import Workflow, Credential
from workflows.utils.credential_resolver import resolve_credential_data

print("--- ALL WHATSAPP CREDS ---")
for c in Credential.objects.filter(type='meta_whatsapp'):
    data = resolve_credential_data(c)
    print(f"ID: {c.id} | Name: {c.name} | PhoneID: {data.get('phone_number_id')}")

print("\n--- ASSISTENAT WF ---")
wf = Workflow.objects.filter(name__icontains='Assistenat').first()
if wf:
    nodes = wf.graph.get('nodes', [])
    for n in nodes:
        if n.get('type') == 'whatsapp_send':
            cid = n.get('config', {}).get('credential_id')
            print(f"NODE_ID: {n.get('id')} | LINKED_TO: {cid}")
else:
    print("NOT FOUND")
