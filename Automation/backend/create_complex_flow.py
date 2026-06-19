import os
import django
import json
import uuid
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from workflows.models import Workflow, WorkflowVersion, WorkflowExecution, Tenant
from django.contrib.auth.models import User
from workflows.services.enhanced_execution_engine import EnhancedExecutionEngine

def create_and_test():
    user = User.objects.first()
    if not user:
        print("No user found")
        return
    
    tenant = Tenant.objects.first() # May be None, engine handles it

    # 1. Create Workflow
    workflow = Workflow.objects.create(
        name="Autonomous Power Test v2",
        owner=user,
        tenant=tenant,
        status="published",
        graph={
            "nodes": [
                {
                    "id": "start",
                    "type": "manual", # Match engine's trigger_types
                    "position": {"x": 100, "y": 100},
                    "config": {}
                },
                {
                    "id": "gen",
                    "type": "code",
                    "position": {"x": 400, "y": 100},
                    "config": {
                        "code": "return [{'name': 'Product A', 'price': 50}, {'name': 'Product B', 'price': 150}, {'name': 'Product C', 'price': 200}]"
                    }
                },
                {
                    "id": "proc",
                    "type": "code",
                    "position": {"x": 700, "y": 100},
                    "config": {
                        "code": "filtered = []\nfor item in items:\n    data = item.get('json', item)\n    if data.get('price', 0) > 100:\n        data['status'] = 'READY_TO_SHIP'\n        filtered.append(data)\n\nreturn {'count': len(filtered), 'total_value': sum(i['price'] for i in filtered), 'processed_items': filtered}"
                    }
                },
                {
                    "id": "log",
                    "type": "logger",
                    "position": {"x": 1000, "y": 100},
                    "config": {
                        "message": "Processed {{ count }} items with total value: {{ total_value }}",
                        "level": "info",
                        "include_data": True
                    }
                }
            ],
            "edges": [
                {"source": "start", "target": "gen"},
                {"source": "gen", "target": "proc"},
                {"source": "proc", "target": "log"}
            ]
        }
    )
    
    # 2. Setup Version
    version = WorkflowVersion.objects.create(
        workflow=workflow,
        version_number=1,
        graph=workflow.graph,
        name="Initial Polish Test"
    )
    
    print(f"✅ Workflow created: {workflow.id}")
    
    # 3. Create Execution
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        tenant=tenant,
        input_payload={
            'test': True,
            '_user_id': str(user.id),
        },
        input_items=[{"json": {"test": True}}],
        triggered_by='manual',
        correlation_id=str(uuid.uuid4()),
        fingerprint=str(uuid.uuid4())
    )
    
    print(f"🚀 Starting execution: {execution.id}")
    
    try:
        engine = EnhancedExecutionEngine(execution)
        engine.initialize_execution()
        
        # Engine run usually executes nodes that are READY
        result = engine.run()
        
        # Refresh from DB
        execution.refresh_from_db()
        print(f"📊 Execution Status: {execution.status}")
        
        if execution.status == 'completed':
            print("✨ WORKFLOW TEST PASSED!")
            from workflows.models import NodeExecution
            node_execs = NodeExecution.objects.filter(workflow_execution=execution)
            print(f"Node Executions Found: {node_execs.count()}")
            for ne in node_execs:
                print(f"  - Node: {ne.graph_node_id} | Status: {ne.status} | Output: {json.dumps(ne.output_items, indent=2)[:500]}")
            
            print("Final Output:", json.dumps(execution.final_output, indent=2))
        else:
            print(f"❌ Execution failed. Error: {execution.error_message}")
            
    except Exception as e:
        import traceback
        print(f"❌ FAIL: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    create_and_test()
