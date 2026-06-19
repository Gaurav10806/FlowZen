import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from workflows.models import WorkflowExecution, NodeExecution

def print_last_results():
    exec = WorkflowExecution.objects.order_by('-created_at').first()
    if not exec:
        return print("NONE")
        
    print(f"ID:{exec.id}")
    print(f"STATUS:{exec.status}")
    
    node_execs = NodeExecution.objects.filter(workflow_execution=exec)
    print(f"COUNT:{node_execs.count()}")
    for ne in node_execs:
        print(f"NODE:{ne.graph_node_id}|ST:{ne.status}|OUT:{str(ne.output_items)[:100]}")

if __name__ == "__main__":
    print_last_results()
