
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

def evaluate_expression_safe(template, items, item_index, node_outputs, execution_context):
    try:
        from workflows.expression_evaluator import evaluate_expression
        return evaluate_expression(template, items, item_index, node_outputs, execution_context)
    except Exception as e:
        return f"EVAL ERROR: {e}"

def debug_reproduction():
    print("🔍 --- START ROBUST DEBUG REPRODUCTION (GRAPH AWARE) ---")
    
    # 1. Get Latest Execution
    latest_exec = WorkflowExecution.objects.order_by('-created_at').first()
    if not latest_exec:
        print("❌ No executions found.")
        return

    print(f"📄 Latest Execution ID: {latest_exec.id}")
    
    # 2. Get Node Labels from Workflow Graph
    workflow = latest_exec.workflow
    node_labels = {} # id -> label
    
    if workflow.graph and "nodes" in workflow.graph:
        nodes_dict = workflow.graph["nodes"]
        # Handle dict or list format
        if isinstance(nodes_dict, list):
            for n in nodes_dict:
                if isinstance(n, dict):
                    node_id = n.get("id")
                    label = n.get("label") or n.get("name") or n.get("data", {}).get("label")
                    if node_id and label:
                        node_labels[node_id] = label
        elif isinstance(nodes_dict, dict):
             for node_id, n in nodes_dict.items():
                   label = n.get("label") or n.get("name") or n.get("display_name")
                   if label:
                       node_labels[node_id] = label
    
    print(f"🗺️  Mapped {len(node_labels)} node labels from Graph: {node_labels}")
    
    # 3. Build Context
    context_data = {
        "node_outputs": {},
        "env": {}, 
        "inputs": latest_exec.input_payload or {}
    }
    
    # Get NodeExecutions (Legacy + New)
    node_execs = latest_exec.node_executions.all().order_by('created_at')
    
    whatsapp_node_config = None
    
    for ne in node_execs:
        # Try to find node ID from relation or raw?
        # NodeExecution.node might be None, but is there a node_id field?
        # Checking fields... model doesn't store raw node_id if FK is null?
        # Wait, if FK is null, we can't get ID?
        # Core Engine might rely on memory. But we need to link NE to ID.
        # Check logs/result json if available?
        
        # Fallback: Check 'node_results' JSON in WorkflowExecution
        pass

    # Better approach: Use WorkflowExecution.node_results JSON
    print("\n📦 --- BUILDING CONTEXT FROM JSON RESULT ---")
    
    node_results = latest_exec.node_results or []
    # If node_results is list
    if isinstance(node_results, list):
        for nr in node_results:
            # nr is dict
            nid = nr.get("node_id")
            output = nr.get("output", {})
            
            # Map Output Logic (Core Engine Parity)
            payload = output
            if isinstance(output, dict) and "output" in output:
                payload = output["output"]
            
            node_entry = {"json": payload, "raw": output}
            
            # Store by ID
            if nid:
                context_data["node_outputs"][nid] = node_entry
                
                # Store by Label
                label = node_labels.get(nid)
                if label:
                    context_data["node_outputs"][label] = node_entry
                    print(f"   🔹 Mapped '{label}' ({nid})")
                    
                    if "whatsapp" in str(label).lower() or "send" in str(label).lower():
                        # Try to find config in graph
                        nodes_container = workflow.graph.get("nodes", [])
                        if isinstance(nodes_container, dict):
                            node_data = nodes_container.get(nid, {})
                            whatsapp_node_config = node_data.get("data", {})
                        elif isinstance(nodes_container, list):
                            for n in nodes_container:
                                if isinstance(n, dict) and n.get("id") == nid:
                                    whatsapp_node_config = n.get("data", {})
                                    break

    print(f"\n   ℹ️ Context Keys: {list(context_data['node_outputs'].keys())}")

    # 4. Test Expression Evaluation
    print("\n🧪 --- EXPRESSION TEST ---")
    
    test_patterns = [
        '{{ $node["AI Agent"].json.text }}',
        '{{ $node["AI Agent"].json.response }}',
        '{{ $node["AI Agent"].output.text }}',
        '{{ $node["AI Agent"].json.output.text }}', # If nested
        '{{ $node["If/Else"].json.text }}',
        '{{ $json.text }}', # Context dependent
    ]
    
    for pattern in test_patterns:
        # Mock item index 0
        result = evaluate_expression_safe(pattern, [{}], 0, context_data["node_outputs"], context_data)
        print(f"   Testing '{pattern}' => {repr(result)}")
        
    print("\n🔍 --- END DEBUG ---")

if __name__ == "__main__":
    debug_reproduction()
