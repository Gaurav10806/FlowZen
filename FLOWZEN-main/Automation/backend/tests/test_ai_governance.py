
import unittest
from unittest.mock import MagicMock
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from workflows.ai_policy.policy_engine import PolicyEngine, PolicyViolationError
from workflows.ai_tools.tool_registry import ToolRegistry
from workflows.ai_tools.tool_executor import ToolExecutor

# Dummy Tool
@ToolRegistry.register
def calculator(a: int, b: int) -> int:
    """Adds two numbers."""
    return int(a) + int(b)

class TestAIGovernanceAndTools(unittest.TestCase):

    def test_policy_cost_block(self):
        """Test blocking expensive requests."""
        config = {'governance': {'max_cost_per_run': 0.01}}
        
        # Free model -> Pass
        PolicyEngine.check_policy(config, "test", "", 0.0) 
        
        # Expensive -> Block
        with self.assertRaises(PolicyViolationError):
            PolicyEngine.check_policy(config, "test", "", 0.02)

    def test_policy_content_block(self):
        """Test content filtering."""
        config = {'governance': {'disallowed_patterns': ['hack', 'exploit']}}
        
        # Safe -> Pass
        PolicyEngine.check_policy(config, "hello world", "", 0.0)
        
        # Unsafe -> Block
        with self.assertRaises(PolicyViolationError):
            PolicyEngine.check_policy(config, "how to hack wifi", "", 0.0)

    def test_tool_schema_generation(self):
        """Test OpenAI schema generation."""
        schemas = ToolRegistry.get_openai_tools(['calculator'])
        self.assertEqual(len(schemas), 1)
        tool = schemas[0]['function']
        self.assertEqual(tool['name'], 'calculator')
        self.assertIn('a', tool['parameters']['properties'])

    def test_tool_execution(self):
        """Test executing a tool call."""
        call = {
            'id': 'call_123',
            'function': {
                'name': 'calculator',
                'arguments': '{"a": 5, "b": 10}'
            }
        }
        
        results = ToolExecutor.execute_tool_calls([call])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], '15')


if __name__ == '__main__':
    unittest.main()
