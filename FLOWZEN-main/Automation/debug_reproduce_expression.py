
import os
import django
import json
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')
django.setup()

from workflows.models import WorkflowExecution

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def evaluate_expression_safe(template, items, node_outputs, execution_context):
    try:
        from workflows.expression_evaluator import evaluate_expression
        return evaluate_expression(template, items, node_outputs, execution_context)
    except Exception as e:
        return f"EVAL ERROR: {e}"

def debug_reproduction():
    print("🔍 --- START ROBUST DEBUG REPRODUCTION ---")
    
    # 1. Get Latest Execution
    latest_exec = WorkflowExecution.objects.order_by('-created_at').first()
    if not latest_exec:
        print("❌ No executions found.")
        return

    print(f"📄 Latest Execution ID: {latest_exec.id}")
    
    # 2. Get Node Executions Map
    node_execs = latest_exec.node_executions.all().order_by('created_at')
    
    context_data = {
        "node_outputs": {},
        "env": {}, 
        "inputs": latest_exec.input_payload or {}
    }
    
    print("\n📦 --- NODE OUTPUTS (CONTEXT) ---")
    whatsapp_node_config = None
    
    for ne in node_execs:
        # Defensive Node Access
        if not ne.node:
            print(f"   ⚠️ Skipping NodeExecution {ne.id}: Node is None")
            continue
            
        try:
            node_id = str(ne.node.id)
            node_label = ne.node.label or "UNKNOWN_LABEL"
            node_type = ne.node.action_type
            node_out = ne.output or {}
            
            # Populate context keys
            context_data["node_outputs"][node_id] = node_out
            context_data["node_outputs"][node_label] = node_out
            
            print(f"   🔹 Node '{node_label}' ({node_type}) ID={node_id}:")
            # print(f"      Output: {json.dumps(node_out, indent=2)}")
            
            if node_type == "whatsapp_send":
                whatsapp_node_config = ne.node.config
                print(f"      Config: {json.dumps(whatsapp_node_config, indent=2)}")
                
        except Exception as e:
            print(f"   ❌ Error processing step {ne.id}: {e}")

    # 3. Test Expression Evaluation
    print("\n🧪 --- EXPRESSION TEST ---")
    
    # Common patterns to test
    test_patterns = [
        '{{ $node["AI Agent"].json.text }}',
        '{{ $node["AI Agent"].json.response }}',
        '{{ $node["AI Agent"].output.text }}',
        '{{ $node["AI Agent"].output.response }}',
        '{{ $node["AI Agent"].text }}', 
    ]
    
    print(f"   ℹ️ Available Context Keys: {list(context_data['node_outputs'].keys())}")

    for pattern in test_patterns:
        result = evaluate_expression_safe(pattern, [{}], context_data["node_outputs"], context_data)
        print(f"   Testing '{pattern}' => {repr(result)}")
            
    print("\n🔍 --- END DEBUG ---")

if __name__ == "__main__":
    debug_reproduction()
