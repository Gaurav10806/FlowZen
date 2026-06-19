from django.core.management.base import BaseCommand
from workflows.actions import ACTION_REGISTRY
from workflows.models import Node, Credential
import inspect

class Command(BaseCommand):
    help = 'Verify node installation and configuration'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== VERIFYING NODE INSTALLATION ==="))

        # 1. Check Registry
        self.stdout.write(f"\n[1] Check Action Registry")
        missing_handlers = []
        
        # List of critical nodes we expect
        expected_nodes = [
            "google_sheets", "google_drive", "youtube", 
            "model_openai", "whatsapp_send", "telegram_send", 
            "slack-message", "sentiment-analysis", "json-processor", 
            "csv-processor", "switch", "date_time", "crypto",
            "markdown", "rss_read", "random_generator"
        ]
        
        for node in expected_nodes:
            handler = ACTION_REGISTRY.get(node)
            if handler:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {node}: Found ({handler.__name__})"))
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ {node}: MISSING"))
                missing_handlers.append(node)

        # 2. Check Credential Types (Inspect source code of models.py roughly via choices if accessible, or just try to create one)
        self.stdout.write(f"\n[2] Check Credential Types")
        
        # We can inspect the choices on the Credential.type field if available
        try:
             # Assuming Credential model is available and has type field with choices
             # Since I couldn't find the definition easily, let's inspect the field options
             type_field = Credential._meta.get_field('type')
             choices = dict(type_field.choices)
             
             expected_creds = [
                 "openai_api", "telegram_bot", "whatsapp_cloud", "slack_bot", "gmail_oauth"
             ]
             
             for cred in expected_creds:
                 if cred in choices:
                     self.stdout.write(self.style.SUCCESS(f"  ✓ {cred}: Supported"))
                 else:
                     self.stdout.write(self.style.WARNING(f"  ? {cred}: Not found in choices (might be valid if field is just CharField without restrictive choices)"))
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"  ! Error checking credential types: {e}"))

        # 3. Check Existing Credentials
        self.stdout.write(f"\n[3] Check Existing Credentials")
        try:
            creds = Credential.objects.all()
            if not creds:
                self.stdout.write(self.style.WARNING("  ! No credentials found in database."))
            for c in creds:
                self.stdout.write(self.style.SUCCESS(f"  - [{c.id}] {c.name} ({c.type})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ! Error listing credentials: {e}"))

        # 4. Test Utility Nodes (Proof of Life)
        self.stdout.write(f"\n[4] Execute Utility Nodes (No Creds Required)")
        from workflows.context import ActionContext
        
        # Mock Context
        ctx = ActionContext(execution_id="test", execution_context={})
        
        # Test Date Node
        try:
            date_handler = ACTION_REGISTRY.get("date_time")
            if date_handler:
                node_mock = type('Node', (), {'config': {'operation': 'format', 'date': 'now', 'format': '%Y-%m-%d'}})
                res = date_handler(node_mock, [{"json": {}}], ctx)
                if res and res[0]['success']:
                     self.stdout.write(self.style.SUCCESS(f"  ✓ Date Node Executed: {res[0]['json']['formatted']}"))
                else:
                     self.stdout.write(self.style.ERROR(f"  ✗ Date Node Failed: {res}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Date Node Error: {e}"))

        # Test Random Node
        try:
            rand_handler = ACTION_REGISTRY.get("random_generator")
            if rand_handler:
                node_mock = type('Node', (), {'config': {'data_type': 'number', 'min': 1, 'max': 10}})
                res = rand_handler(node_mock, [{"json": {}}], ctx)
                if res and res[0]['success'] and isinstance(res[0]['json']['output'], int):
                     self.stdout.write(self.style.SUCCESS(f"  ✓ Random Node Executed: {res[0]['json']['output']}"))
                else:
                     self.stdout.write(self.style.ERROR(f"  ✗ Random Node Failed: {res}"))
        except Exception as e:
             self.stdout.write(self.style.ERROR(f"  ✗ Random Node Error: {e}"))

        self.stdout.write(self.style.SUCCESS("\n=== VERIFICATION COMPLETE ==="))
