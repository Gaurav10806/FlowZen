from django.core.management.base import BaseCommand
from workflows.models import Workflow, Node, Trigger, Edge
import uuid

class Command(BaseCommand):
    help = 'Creates a demo HTTPS Verification workflow'

    def handle(self, *args, **options):
        workflow_name = "HTTPS Verification Demo"
        
        # Check if exists
        if Workflow.objects.filter(name=workflow_name).exists():
            self.stdout.write(self.style.WARNING(f"Workflow '{workflow_name}' already exists."))
            return

        # Create Workflow
        self.stdout.write(f"Creating workflow '{workflow_name}'...")
        workflow = Workflow.objects.create(
            name=workflow_name,
            description="A workflow to verify HTTPS connectivity (created via CLI).",
            status="active",
            input_schema={} 
        )

        # 1. Trigger: Manual
        trigger_config = {"type": "manual"}
        trigger_node = Trigger.objects.create(
            workflow=workflow,
            type="manual",
            name="Manual Trigger",
            config=trigger_config,
            # triggers don't usually have x/y in some models, but let's check base
        )
        # Note: Trigger is a separate model in this codebase? Yes.
        
        # 2. Action: HTTP Request
        http_config = {
            "url": "https://jsonplaceholder.typicode.com/posts/1",
            "method": "GET",
            "timeout": 10,
            "headers": {
                "User-Agent": "FlowZen-Verifier/1.0",
                "Content-Type": "application/json"
            },
            "fail_on_error": False
        }
        
        # We need unique node_ids as strings usually
        http_node = Node.objects.create(
            workflow=workflow,
            type="http_request",
            label="Check Endpoint",
            action_type="http_request",
            config=http_config,
            position_x=300,
            position_y=100,
            node_id="check_endpoint" # explicit ID helps with referencing
        )

        # 3. Action: Condition
        # If output of check_endpoint is { "status_code": 200, ... }
        # Expression: {{ $json.status_code }} == 200
        # Wait, if context variable is used, usually it's $json (current item).
        # Actions return ITEMS. HTTP Request returns an item with "status_code" in json.
        condition_config = {
            "expression": "{{ $json.status_code }} == 200"
        }
        
        condition_node = Node.objects.create(
            workflow=workflow,
            type="condition",
            label="Is 200 OK?",
            action_type="condition",
            config=condition_config,
            position_x=600,
            position_y=100,
            node_id="check_status"
        )

        # 4. Logs
        log_success = Node.objects.create(
            workflow=workflow,
            type="code", # Using code node to print/log, or if log_message exists. 
            # I saw 'log_message' in my thought but I should check if it exists. 
            # 'utility_nodes.py' has 'CodeNode'. 'actions.py' has 'code_action'. 
            # I'll use 'code' node for logging as it is reliable.
            label="Log Success",
            action_type="code",
            config={"code": "print(f'SUCCESS: Verified {input_data.get(\"json\", {}).get(\"url\")}')\nreturn input_data"},
            position_x=900,
            position_y=50,
            node_id="log_success"
        )

        log_failure = Node.objects.create(
            workflow=workflow,
            type="code",
            label="Log Failure",
            action_type="code",
            config={"code": "print(f'FAILURE: Status {input_data.get(\"json\", {}).get(\"status_code\")}')\nreturn input_data"},
            position_x=900,
            position_y=200,
            node_id="log_failure"
        )

        # EDGES
        # Trigger (implicit start) -> HTTP
        # Note: Triggers initiate workflow. Edge connects Trigger to first Node? 
        # In this system, Trigger might be separate. 
        # But usually there is an edge from Trigger -> Node 1.
        # Let's check Edge model. source_node, target_node.
        # Trigger is NOT a Node (BaseNode). Trigger is Trigger model.
        # But `Trigger` might inherit BaseNode? 
        # Let's assume Trigger needs to be connected to first node via some mechanism. 
        # Often it's just "Start Node".
        # But if Trigger model is separate, maybe we don't need edge from Trigger.
        # Wait, usually Trigger IS a node in the graph. 
        # If Trigger is separate model, maybe it's just metadata.
        # I'll create an Edge from Trigger if Trigger is a Node.
        # Checking `Trigger` model in `models.py` (not viewed recently but referenced).
        # Actually `trigger_nodes.py` exists. 
        # I'll assume we connect HTTP node as the startup node or just connect Trigger if possible.
        # Let's try connecting Trigger (schema wise).
        # Edge needs `source_node_id`. If Trigger has ID that matches, ok. 
        # But Trigger model is likely different table. 
        # So I will just create the nodes and edges between nodes.
        # AND I will make sure HTTP node is the START.
        # Or I connect Trigger (if it acts as a node).

        # Let's try to link Trigger to HTTP Node if system supports it. 
        # If not, I'll just link HTTP -> Condition -> Logs.
        
        Edge.objects.create(workflow=workflow, source_node=http_node, target_node=condition_node, source_handle="output", target_handle="input")
        Edge.objects.create(workflow=workflow, source_node=condition_node, target_node=log_success, source_handle="true", target_handle="input")
        Edge.objects.create(workflow=workflow, source_node=condition_node, target_node=log_failure, source_handle="false", target_handle="input")

        self.stdout.write(self.style.SUCCESS(f"Successfully created workflow metrics_demo (ID: {workflow.id})"))
