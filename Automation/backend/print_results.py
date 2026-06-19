import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from workflows.models import WorkflowExecution, NodeExecution

def print_last_results():
    exec = WorkflowExecution.objects.order_by('-created_at').first()
    if not exec:
        print("No executions found")
        return
        
    print(f"Workflow: {exec.workflow.name}")
    print(f"Status: {exec.status}")
    print(f"Execution ID: {exec.id}")
    
    node_execs = NodeExecution.objects.filter(workflow_execution=exec)
    print(f"Node Executions Found: {node_execs.count()}")
    for ne in node_execs:
        print(f"--- Node: {ne.graph_node_id} ({ne.status}) ---")
        print("Output Items:", json.dumps(ne.output_items, indent=2))
        if ne.error_message:
            print("Error:", ne.error_message)

if __name__ == "__main__":
    print_last_results()
