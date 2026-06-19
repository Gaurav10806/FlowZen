
import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from workflows.nodes.ai_agent_node import AIAgentNode
from workflows.ai_providers.model_router import select_model
from workflows.ai_providers.ollama_provider import OllamaProvider

class TestModelRouterPhase2(unittest.TestCase):
    
    def setUp(self):
        self.node = AIAgentNode()
        self.credential = {
            "default_model": "llama3:8b", 
            "available_models": ["llama3:8b", "gemma:7b", "mistral:7b"]
        }

    def test_router_keywords(self):
        # 1. Formatting = Strict JSON -> Llama3
        m = select_model(prompt="hi", system_prompt="", credential=self.credential, response_mode="json")
        self.assertEqual(m, "llama3:8b", "Strict JSON mode must prioritize Llama3")

        # 2. Reasoning -> Llama3
        m = select_model(prompt="Plan a trip", system_prompt="", credential=self.credential, response_mode="text")
        self.assertEqual(m, "llama3:8b", "Planning keywords should use Llama3")
        
        # 3. Creative / Email -> Gemma
        m = select_model(prompt="Write an email", system_prompt="", credential=self.credential, response_mode="text")
        self.assertEqual(m, "gemma:7b", "Email/Writing should use Gemma")

        # 4. Short Prompt -> Gemma
        m = select_model(prompt="Hi", system_prompt="", credential=self.credential, response_mode="text")
        self.assertEqual(m, "gemma:7b", "Short prompts should use Gemma")

    @patch('workflows.ai_providers.ollama_provider.requests.request')
    def test_node_integration(self, mock_request):
        # Mock Credential
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {
            'base_url': 'http://localhost:11434', 
            'default_model': 'llama3:8b',
            'available_models': ['llama3:8b']
        }
        
        # Mock Ollama Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'response': '{"key": "val"}', 'done': True, 'model': 'llama3:8b'}
        mock_request.return_value = mock_response

        # Config Node
        self.node.config = {
            "credential_id": "1",
            "user_prompt": "Plan a database",
            "response_mode": "json"
        }
        
        with patch.object(self.node, '_get_full_credential', return_value=mock_cred):
            with patch.object(OllamaProvider, 'get_installed_models', return_value=['llama3:8b']):
                result = self.node.run(input_data={})
        
        print(f"Node Result: {result}")
        self.assertTrue(result['success'])
        output = result['output']
        
        # Verify Schema
        self.assertIn('json', output)
        self.assertIn('meta', output)
        self.assertEqual(output['meta']['model_used'], 'llama3:8b')
        self.assertEqual(output['meta']['provider'], 'ollama')
        
        print("✅ Node Integration Verified: Router + Schema correct.")

if __name__ == '__main__':
    unittest.main()
