
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from workflows.ai_memory.memory_store import MemoryStore
from workflows.ai_agents.orchestrator import AgentOrchestrator

class TestAIAdvanced(unittest.TestCase):
    
    def test_memory_storage(self):
        """Test LocalFileMemory storage and retrieval."""
        store = MemoryStore("test_brain_mem")
        # Clear
        store.memories = []
        store._save()
        
        store.store("My name is Alice", "Hello Alice")
        retrieved = store.retrieve(limit=1)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]['user'], "My name is Alice")
        
        # Cleanup
        if os.path.exists(store.file_path):
            os.remove(store.file_path)

    @patch('workflows.ai_providers.universal_engine.UniversalAIEngine.run')
    def test_agent_orchestration(self, mock_run):
        """Test Agent Planner and Execution flow."""
        
        # Mock Engine Responses
        # 1. Planner Call -> Returns Tasks JSON
        # 2. Worker 1 Call
        # 3. Worker 2 Call
        # 4. Finalizer Call
        
        mock_run.side_effect = [
            # Plan
            {"success": True, "output": {"json": [
                {"title": "Step 1", "instruction": "Do X"},
                {"title": "Step 2", "instruction": "Do Y"}
            ]}},
            # Step 1
            {"success": True, "output": {"text": "Result X"}},
            # Step 2
            {"success": True, "output": {"text": "Result Y"}},
            # Finalize
            {"success": True, "output": {"text": "Final Answer"}}
        ]
        
        # Fake Engine Class (Dependency Injection style)
        MockEngine = MagicMock()
        MockEngine.run = mock_run
        
        orch = AgentOrchestrator(MockEngine, {})
        result = orch.run_parallel("Complex Task", {}, "cred_id")
        
        self.assertEqual(result['output']['text'], "Final Answer")
        self.assertEqual(mock_run.call_count, 4)

if __name__ == '__main__':
    unittest.main()
