import os
import sys
import django
import time
import json

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from workflows.models import Workflow, WorkflowExecution

def run_test():
    print("🚀 Triggering E2E Google Ecosystem Test...")
    
    try:
        wf = Workflow.objects.get(name="E2E Google Ecosystem Test")
    except Workflow.DoesNotExist:
        print("❌ Workflow not found! Did you run setup_e2e_google.py?")
        return

    # Trigger Execution
    from workflows.engine.core_engine import WorkflowEngine
    engine = WorkflowEngine()
    
    # Run in Test Mode
    execution = engine.run_workflow(wf, input_payload={"test_mode": True})
    print(f"▶️  Execution Started: {execution.id}")
    
    # Poll for completion
    timeout = 60
    start = time.time()
    while True:
        execution.refresh_from_db()
        print(f"   Status: {execution.status}...")
        
        if execution.status in ['COMPLETED', 'FAILED', 'ERROR']:
            break
            
        if time.time() - start > timeout:
            print("⏰ Timeout waiting for execution.")
            break
        
        time.sleep(2)

    print(f"\n🏁 Finished with status: {execution.status}")
    
    # Print Result Summary
    if execution.status == 'COMPLETED':
        print("\n✅ Verification Successful!")
        print("Outputs:")
        # execution.result is a dict of node_id -> result
        # We want to see the AI Agent output mostly
        results = execution.result
        for node_id, res in results.items():
            if 'node-ai' in node_id:
                print(f"🤖 AI Summary:\n{res.get('output', {}).get('text', 'No Text')}")
            elif 'node-yt' in node_id:
                items = res.get('output', [])
                print(f"📺 Found {len(items)} Videos.")
            elif 'node-drive' in node_id:
                items = res.get('output', [])
                print(f"📂 Found {len(items)} Files.")

    else:
        print(f"\n❌ Execution Failed: {execution.error_message}")
        print("Logs:")
        for log in execution.logs.all():
            print(f"[{log.level}] {log.node_id}: {log.message}")

if __name__ == "__main__":
    run_test()
