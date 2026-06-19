import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from workflows.models import WorkflowExecution
ex = WorkflowExecution.objects.order_by('-created_at').first()
print(f"ID: {ex.id}")
print(f"Status: {ex.status}")
print(f"Error Message: {ex.error_message}")
print(f"Traceback: {ex.traceback}")
