import json
from django.db import migrations

def convert_to_json(apps, schema_editor):
    Credential = apps.get_model('workflows', 'Credential')
    for cred in Credential.objects.all():
        if isinstance(cred.encrypted_data, str):
            try:
                # Try to parse string as JSON
                cred.encrypted_data = json.loads(cred.encrypted_data)
                cred.save(update_fields=['encrypted_data'])
            except (json.JSONDecodeError, TypeError):
                # If it's not JSON, set as empty dict
                cred.encrypted_data = {}
                cred.save(update_fields=['encrypted_data'])

def reverse_convert(apps, schema_editor):
    # No realistic way to reverse this as it depends on how the DB handles JSONField
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('workflows', '0012_alter_telegramconversation_user_id'),
    ]

    operations = [
        migrations.RunPython(convert_to_json, reverse_convert),
    ]
