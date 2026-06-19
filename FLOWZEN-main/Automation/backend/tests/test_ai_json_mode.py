
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
from workflows.ai_providers.ollama_provider import OllamaProvider
from workflows.ai_services import OpenAIService

class TestAIAgentJSONMode(unittest.TestCase):
    
    def setUp(self):
        self.node = AIAgentNode()

    @patch('requests.post')
    def test_openai_json_mode(self, mock_post):
        # Mock _get_full_credential on the instance
        mock_cred = MagicMock()
        mock_cred.type = 'ai_provider'
        mock_cred.encrypted_data = {'api_key': 'sk-test', 'default_model': 'gpt-4'}
        
        # Configure Node
        self.node.config = {
            "credential_id": "1",
            "system_prompt": "You are a bot.",
            "user_prompt": "Hello",
            "response_mode": "json"
        }

        with patch.object(self.node, '_get_full_credential', return_value=mock_cred):
            # Run Node
            result = self.node.run(
                input_data={"some": "input"}
            )
        print(f"OpenAI Result: {result}")
        
        # Verify response_format was passed
        if mock_post.call_args:
             call_kwargs = mock_post.call_args[1]
             payload = call_kwargs['json']
             self.assertIn('response_format', payload)
             self.assertEqual(payload['response_format'], {"type": "json_object"})
             # Verify system prompt updated with safety message
             system_msg = next(m for m in payload['messages'] if m['role'] == 'system')
             self.assertIn("Respond in JSON", system_msg['content'])
             print("\n✅ OpenAI JSON Mode Verified: response_format passed and prompt updated.")
        else:
             self.fail("OpenAI requests.post was NOT called.")

    @patch('workflows.ai_providers.ollama_provider.requests.request')
    def test_ollama_json_mode(self, mock_request):
        # Mock Credential
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {'base_url': 'http://localhost:11434', 'default_model': 'llama3:8b'}
        
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'response': '{"key": "value"}', 'done': True}
        mock_request.return_value = mock_response

        # Configure Node
        self.node.config = {
            "credential_id": "1",
            "user_prompt": "Hello",
            "response_mode": "json"
        }

        # Mock result capture
        result = None
        
        # Mock Provider.get_installed_models to force validation success
        with patch.object(self.node, '_get_full_credential', return_value=mock_cred):
            with patch.object(OllamaProvider, 'get_installed_models', return_value=['llama3:8b']):
                 result = self.node.run(
                    input_data={"some": "input"}
                )
        
        print(f"Ollama Result: {result}")

        # Verify 'format': 'json' was passed in payload
        if mock_request.call_args:
            call_kwargs = mock_request.call_args[1]
            payload = call_kwargs['json']
            
            self.assertIn('format', payload)
            self.assertEqual(payload['format'], 'json')
            print("\n✅ Ollama JSON Mode Verified: format='json' passed to API.")
        else:
             self.fail("Ollama requests.request was NOT called.")

if __name__ == '__main__':
    unittest.main()
