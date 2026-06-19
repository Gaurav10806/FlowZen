
import os
import django
import sys
from django.core.serializers.json import DjangoJSONEncoder
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from workflows.models import WorkflowExecution

try:
    e = WorkflowExecution.objects.filter(triggered_by='webhook').order_by('-created_at').first()
    with open('/app/debug_output.txt', 'w') as f:
        f.write(f"--- Execution ID: {e.id} ---\n")
        f.write(f"Status: {e.status}\n")
        
        # Try to get trigger output
        trigger_output = "N/A"
        if e.node_results and len(e.node_results) > 0:
            trigger_output = json.dumps(e.node_results[0].get('output'), indent=2)
        
        f.write(f"Trigger Output: {trigger_output}\n")
        f.write("Node Results Summary:\n")
        for res in e.node_results:
             f.write(f"  {res.get('node_type')}: Success={res.get('success')} Error={res.get('error')}\n")
        f.write("-" * 20 + "\n")

except Exception as ex:
    with open('/app/debug_output.txt', 'w') as f:
        f.write(f"Error: {ex}\n")
