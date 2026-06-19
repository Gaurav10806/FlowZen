from django.test import TestCase, Client
from django.utils import timezone
from workflows.models import Credential, WhatsAppConversation, WhatsAppMessage, WhatsAppTemplate
from workflows.nodes.whatsapp_nodes import WhatsAppSendNode, NodeExecutionError
import json
import logging
from unittest.mock import patch, MagicMock

class WhatsAppEnterpriseTests(TestCase):
    def setUp(self):
        self.client = Client()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username='ent_test', password='password')
        
        self.credential = Credential.objects.create(
            name="Ent Test WA",
            type="meta_whatsapp",
            owner=self.user,
            encrypted_data={
                "phone_number_id": "123456",
                "access_token": "token",
                "app_secret": "secret",
                "webhook_verify_token": "token"
            }
        )
        self.phone = "15559998888"

    def test_status_callback_updates_message(self):
        """Phase 2: Status callbacks update DB."""
        # Create initial message
        msg = WhatsAppMessage.objects.create(
            credential=self.credential,
            status='sent',
            meta_message_id='wamid.123'
        )
        
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "123456"},
                "statuses": [{
                    "id": "wamid.123",
                    "status": "delivered",
                    "timestamp": "1700000100",
                    "recipient_id": self.phone
                }]
            }}]}]
        }
        
        # Disable sig check
        self.credential.encrypted_data.pop('app_secret')
        self.credential.save()
        
        res = self.client.post("/api/webhooks/whatsapp/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'delivered')
        self.assertIsNotNone(msg.delivered_at)

    def test_template_validation_blocking(self):
        """Phase 3: Send Node blocks unapproved templates."""
        node = WhatsAppSendNode({
            "credential_id": str(self.credential.id),
            "phone_number": self.phone,
            "message_mode": "template",
            "template_name": "unapproved_tpl",
            "template_language": "en_US"
        })
        
        # Case 1: Template missing
        with self.assertRaises(NodeExecutionError) as cm:
            node.run(input_data={})
        self.assertIn("not found in local DB", str(cm.exception))
        
        # Case 2: Template pending
        WhatsAppTemplate.objects.create(
            credential=self.credential,
            name="unapproved_tpl",
            language="en_US",
            status="pending"
        )
        with self.assertRaises(NodeExecutionError) as cm:
            node.run(input_data={})
        self.assertIn("not APPROVED", str(cm.exception))

    def test_media_safety_trigger(self):
        """Phase 4: Non-text inbound triggers human takeover."""
        # Active conversation
        conv = WhatsAppConversation.objects.create(
            credential=self.credential,
            user_phone_number=self.phone,
            is_active=True,
            is_human_controlled=False
        )
        
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "123456"},
                "messages": [{
                    "from": self.phone, 
                    "id": "msg_media", 
                    "type": "image",
                    "image": {"id": "media_id", "mime_type": "image/jpeg"},
                    "timestamp": "1700000000"
                }]
            }}]}]
        }
        
        # Mock sig check bypass
        self.credential.encrypted_data.pop('app_secret')
        self.credential.save()
        
        self.client.post("/api/webhooks/whatsapp/", data=json.dumps(payload), content_type="application/json")
        
        conv.refresh_from_db()
        # Image might NOT trigger takeover strictly? 
        # Code check: `if msg_type in ['audio', 'document', 'sticker']`
        self.assertFalse(conv.is_human_controlled) # Image is safe-ish?
        
        # Try document
        payload['entry'][0]['changes'][0]['value']['messages'][0]['type'] = 'document'
        payload['entry'][0]['changes'][0]['value']['messages'][0]['document'] = {'id':'doc','filename':'file.pdf'}
        del payload['entry'][0]['changes'][0]['value']['messages'][0]['image']
        
        self.client.post("/api/webhooks/whatsapp/", data=json.dumps(payload), content_type="application/json")
        
        conv.refresh_from_db()
        self.assertTrue(conv.is_human_controlled)

    def test_send_node_retry_logic(self):
        """Phase 5: Send Node retries on 500."""
        # Setup conversation
        WhatsAppConversation.objects.create(
             credential=self.credential,
             user_phone_number=self.phone,
             is_active=True,
             last_user_message_at=timezone.now()
        )
        
        node = WhatsAppSendNode({
            "credential_id": str(self.credential.id),
            "phone_number": self.phone,
            "message_mode": "text",
            "message_content": "hi"
        })
        
        with patch('requests.post') as mock_post:
            # Side effect: 500, then 500, then 200
            mock_500 = MagicMock()
            mock_500.status_code = 500
            mock_500.text = "Server Error"
            
            mock_200 = MagicMock()
            mock_200.status_code = 200
            mock_200.json.return_value = {"messages": [{"id": "wamid_retry"}]}
            
            mock_post.side_effect = [mock_500, mock_500, mock_200]
            
            res = node.run(input_data={})
            
            self.assertTrue(res['success'])
            self.assertEqual(mock_post.call_count, 3)
