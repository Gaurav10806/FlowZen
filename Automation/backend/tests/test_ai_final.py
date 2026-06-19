
import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from workflows.ai_providers.universal_engine import UniversalAIEngine
from workflows.api.ai_views import run_ai
from django.test import RequestFactory

@patch('workflows.ai_providers.universal_engine.OllamaProvider')
@patch('workflows.ai_policy.policy_engine.PolicyEngine')
class TestAIFinalPolish(unittest.TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        # Reset Cache
        UniversalAIEngine._response_cache = {}
        
    @patch('workflows.ai_providers.universal_engine.UniversalAIEngine.run')
    def test_api_endpoint(self, mock_run, MockPolicy, MockOllama):
        """Phase 19: Test API Endpoint"""
        mock_run.return_value = {"success": True, "output": {"text": "API OK"}}
        
        request = self.factory.post(
            '/api/ai/run', 
            data=json.dumps({"brain_id": "1", "user_prompt": "hi"}),
            content_type='application/json'
        )
        response = run_ai(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("API OK", str(response.content))

    def test_simulation_mode(self, MockPolicy, MockOllama):
        """Phase 17: Test Simulation Mode"""
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {'simulation_mode': True}
        
        with patch('workflows.ai_providers.universal_engine.Credential.objects.get', return_value=mock_cred):
             res = UniversalAIEngine.run(
                 user_prompt="test", system_prompt="", response_mode="text", credential_id="1"
             )
             self.assertEqual(res['output']['text'], "SIMULATED RESPONSE")
             self.assertEqual(res['output']['meta']['provider'], "simulated")

    @patch('workflows.ai_policy.policy_engine.PolicyEngine.check_policy')
    @patch('workflows.ai_policy.policy_engine.PolicyEngine.estimate_cost', return_value=0.0)
    @patch('workflows.ai_providers.universal_engine.OllamaProvider')
    def test_caching(self, MockOllamaClass, mock_est, mock_check):
        """Phase 15: Test Cache"""
        try:
            # Mock Ollama success
            MockOllamaClass.return_value.get_installed_models.return_value = ['llama3:8b']
            MockOllamaClass.return_value.execute.return_value = {"success": True, "output": {"text": "Cached Result"}}
            
            # Mock Policy
            # mock_est is already set by patch
            
            mock_cred = MagicMock()
            mock_cred.type = 'ai_offline'
            mock_cred.encrypted_data = {'optimization': {'cache_enabled': True}, 'base_url': 'http://localhost'}
            
            with patch('workflows.ai_providers.universal_engine.Credential.objects.get', return_value=mock_cred):
                 with patch('workflows.ai_providers.universal_engine.select_model', return_value={'provider': 'offline', 'model': 'llama3:8b', 'reason': 'test', 'profile': 'balanced'}):
                      
                      # Call 1 (Miss)
                      res1 = UniversalAIEngine.run(
                          user_prompt="cache_me", system_prompt="", response_mode="text", credential_id="1"
                      )
                      self.assertFalse(res1['output']['meta'].get('cached', False))
                      
                      # Call 2 (Hit)
                      res2 = UniversalAIEngine.run(
                          user_prompt="cache_me", system_prompt="", response_mode="text", credential_id="1"
                      )
                      self.assertTrue(res2['output']['meta'].get('cached', False))
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

if __name__ == '__main__':
    unittest.main()
