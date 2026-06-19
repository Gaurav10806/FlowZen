
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

class TestAIFinalPolishV2(unittest.TestCase):
    
    def setUp(self):
        self.factory = RequestFactory()
        UniversalAIEngine._response_cache = {}
        
    @patch('workflows.ai_policy.policy_engine.PolicyEngine')
    @patch('workflows.ai_providers.universal_engine.UniversalAIEngine.run')
    def test_api_endpoint(self, mock_run, mock_policy):
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

    def test_simulation_mode(self):
        """Phase 17: Test Simulation Mode"""
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {'simulation_mode': True}
        
        # We assume Policy check passes or we mock it
        with patch('workflows.ai_policy.policy_engine.PolicyEngine.check_policy'):
            with patch('workflows.ai_policy.policy_engine.PolicyEngine.estimate_cost', return_value=0.0):
                with patch('workflows.ai_providers.universal_engine.Credential.objects.get', return_value=mock_cred):
                     res = UniversalAIEngine.run(
                         user_prompt="test", system_prompt="", response_mode="text", credential_id="1"
                     )
                     self.assertEqual(res['output']['text'], "SIMULATED RESPONSE")
                     self.assertEqual(res['output']['meta']['provider'], "simulated")

    @patch('workflows.ai_providers.ollama_provider.requests.request')
    def test_caching(self, mock_request):
        """Phase 15: Test Cache"""
        # Mock requests response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}]} # for get_installed_models
        mock_request.return_value = mock_resp
        mock_resp.status_code = 200
        
        # When called with POST (generate), return cached result
        def side_effect(method, url, **kwargs):
             if method == 'POST':
                 m = MagicMock()
                 m.json.return_value = {"response": "Cached Result"}
                 m.status_code = 200
                 return m
             return mock_resp
        
        mock_request.side_effect = side_effect
        
        mock_cred = MagicMock()
        mock_cred.type = 'ai_offline'
        mock_cred.encrypted_data = {'optimization': {'cache_enabled': True}, 'base_url': 'http://localhost'}
        
        with patch('workflows.ai_policy.policy_engine.PolicyEngine.check_policy'):
             with patch('workflows.ai_policy.policy_engine.PolicyEngine.estimate_cost', return_value=0.0):
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

if __name__ == '__main__':
    unittest.main()
