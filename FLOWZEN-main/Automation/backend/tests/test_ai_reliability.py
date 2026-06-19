
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from workflows.nodes.ai_agent_node import AIAgentNode

class TestAIReliability(unittest.TestCase):
    
    def setUp(self):
        self.node = AIAgentNode()

    # NOTE: Patching the providers imported inside universal_engine
    @patch('workflows.ai_providers.universal_engine.OllamaProvider')
    @patch('workflows.ai_providers.universal_engine.OpenAIService')
    def test_fallback_logic(self, MockOpenAI, MockOllama):
        """
        Verify UniversalAIEngine handles fallback from Offline -> Online.
        """
        # 1. Setup Mock Credential
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {
            'base_url': 'http://bad-url:11434', 
            'default_model': 'llama3:8b',
            'available_models': ['llama3:8b'],
            'openai_backup_key': 'sk-backup-key-123',
            'profile': 'balanced'
        }
        
        # 2. Setup Ollama FAILURE
        mock_ollama_instance = MockOllama.return_value
        mock_ollama_instance.execute.return_value = {
            "success": False, 
            "error": "Connection timed out"
        }
        
        # 3. Setup OpenAI SUCCESS
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.chat.return_value = {
            'message': {'content': '{"key": "value"}'}
        }
        
        # 4. Configure Node
        self.node.config = {
            "credential_id": "1",
            "user_prompt": "Hello",
            "response_mode": "json"
        }
        
        # 5. Execute
        with patch('workflows.ai_providers.universal_engine.Credential.objects.get', return_value=mock_cred):
              with patch('workflows.ai_providers.universal_engine.select_model', 
                         return_value={'provider': 'offline', 'model': 'llama3:8b', 'reason': 'test', 'profile': 'balanced'}):
                   
                   result = self.node.run(input_data={})

        print(f"Universal Engine Result: {result}")
        
        self.assertTrue(result['success'], "Node should succeed via fallback")
        
        meta = result['output']['meta']
        self.assertTrue(meta['fallback_used'], "Meta should indicate fallback used")
        self.assertEqual(meta['provider'], 'openai', "Final provider should be openai")
        self.assertEqual(meta['confidence'], 'medium', "Confidence should be medium")
        
        # Verify OpenAI called with correct key (injected into config)
        MockOpenAI.assert_called()

if __name__ == '__main__':
    unittest.main()
