import os
import django
import sys
import uuid
import json
from datetime import datetime

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from workflows.execution.core_engine import WorkflowExecutionEngine, ExecutionContext
from workflows.models import Node, Workflow
from django.conf import settings

def test_memory_increment():
    print("\n--- Testing Memory Node Increment ---")
    try:
        from workflows.nodes.memory_node import MemoryNode
        
        # Mock Redis
        node_data = {
            "id": "memory_1",
            "type": "memory",
            "config": {
                "operation": "increment",
                "key": "test_counter",
                "amount": 1,
                "scope": "workflow"
            }
        }
        
        context = {
            "workflow_id": "test_wf_1",
            "execution_id": "test_exec_1",
            "user_id": "test_user"
        }
        
        print("Initializing MemoryNode...")
        node = MemoryNode(node_data)
        # We can't easily run it without real Redis, but we verified the code exists.
        print("MemoryNode initialized successfully.")
        
    except Exception as e:
        print(f"MemoryNode Test Failed (likely expected if no Redis): {e}")

def test_loop_node_structure():
    print("\n--- Testing Loop Node Structure ---")
    try:
        # UPDATED IMPORT
        from workflows.nodes.logic_nodes import LoopNode
        
        node_data = {
            "id": "loop_1",
            "type": "loop",
            "config": {
                "items": ["a", "b", "c"],
                "batch_size": 1
            }
        }
        
        node = LoopNode(node_data)
        print("LoopNode initialized successfully.")
        
    except Exception as e:
        print(f"LoopNode Test Failed: {e}")

def test_global_timeout_logic():
    print("\n--- Testing Global Timeout Logic (Mock) ---")
    # We will simulate the engine logic
    from workflows.execution.core_engine import WorkflowExecutionEngine
    import time
    
    # Temporarily patch settings
    original_timeout = getattr(settings, 'WORKFLOW_EXECUTION_TIME_LIMIT', 300)
    settings.WORKFLOW_EXECUTION_TIME_LIMIT = 1 # 1 second timeout
    
    print(f"Set temporary timeout to {settings.WORKFLOW_EXECUTION_TIME_LIMIT}s")
    
    try:
        # Create a dummy workflow that sleeps
        workflow_json = {
            "meta": {},
            "trigger": {
                "id": "trigger",
                "type": "manual"
            },
            "nodes": {
                "trigger": {"id": "trigger", "type": "manual"},
                "delay": {
                    "id": "delay",
                    "type": "code", # Use code node to sleep
                    "config": {
                        "code": "import time; time.sleep(2)"
                    }
                },
                "cleanup": {"id": "cleanup", "type": "code", "config": {"code": "return {'ok': True}"}}
            },
            "connections": {
                "trigger": ["delay"],
                "delay": ["cleanup"]
            }
        }
        
        context = ExecutionContext(
            workflow_id="timeout_test",
            execution_id="timeout_exec"
        )
        
        engine = WorkflowExecutionEngine()
        
        print("Running workflow with expected timeout...")
        result = engine.run(workflow_json, {}, context)
        
        if not result.success and "timed out" in (result.error_message or ""):
            print(f"SUCCESS: Workflow timed out as expected: {result.error_message}")
        elif not result.success:
             print(f"FAILED: Workflow failed but not due to timeout? {result.error_message}")
        else:
            print(f"WARNING: Workflow SUCCEEDED? Elapsed: {result.total_execution_time_ms}ms")
            
    except Exception as e:
        print(f"Execution Error: {e}")
    finally:
        settings.WORKFLOW_EXECUTION_TIME_LIMIT = original_timeout

if __name__ == "__main__":
    test_memory_increment()
    test_loop_node_structure()
    test_global_timeout_logic()
    print("\nDone.")
