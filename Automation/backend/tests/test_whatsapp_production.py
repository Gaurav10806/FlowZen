from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from workflows.models import Credential, WhatsAppConversation, WhatsAppUsage, WhatsAppMessage
from workflows.nodes.whatsapp_nodes import WhatsAppSendNode, NodeExecutionError
import json
import logging

class WhatsAppProductionTests(TestCase):
    def setUp(self):
        self.client = Client()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='password')
        
        self.credential = Credential.objects.create(
            name="Test WA",
            type="meta_whatsapp",
            owner=self.user,
            encrypted_data={
                "phone_number_id": "12345",
                "access_token": "token",
                "webhook_verify_token": "verify_me",
                "app_secret": "secret"
            }
        )
        self.phone = "15551234567"
        
    def test_webhook_inbound_does_not_create_conversation(self):
        """Phase 1/2: Inbound messages must NOT create conversations."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "12345"},
                "messages": [{"from": self.phone, "id": "msg_1", "type": "text", "text": {"body": "Hello"}, "timestamp": "1700000000"}]
            }}]}]
        }
        
        # We skip signature validation in this specific test or mock it? 
        # The handler requires signature if app_secret is present.
        # Let's simple-test the logic by calling a helper or mocking validation or removing app_secret temporarily.
        self.credential.encrypted_data.pop('app_secret')
        self.credential.save()
        
        response = self.client.post(
            "/api/webhooks/whatsapp/", 
            data=json.dumps(payload), 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Check DB
        self.assertEqual(WhatsAppConversation.objects.count(), 0)
        self.assertEqual(WhatsAppMessage.objects.count(), 1)
        msg = WhatsAppMessage.objects.first()
        self.assertEqual(msg.user_phone_number, self.phone)

    def test_send_node_cold_start_text_blocked(self):
        """Phase 4: Cold start text message must be blocked."""
        node = WhatsAppSendNode({
            "credential_id": str(self.credential.id),
            "phone_number": self.phone,
            "message_mode": "text",
            "message_content": "Hello"
        })
        
        # No previous messages
        try:
            node.run(input_data={})
            self.fail("Should have raised NodeExecutionError")
        except NodeExecutionError as e:
            self.assertIn("Cannot send Text message outside 24h window", str(e))

    def test_send_node_cold_start_template_allowed(self):
        """Phase 4: Cold start template allowed & starts conversation."""
        # Mock requests.post
        import requests
        from unittest.mock import patch
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid_new"}]}
            
            node = WhatsAppSendNode({
                "credential_id": str(self.credential.id),
                "phone_number": self.phone,
                "message_mode": "template",
                "template_name": "hello_world"
            })
            
            node.run(input_data={})
            
            # Check created conversation
            self.assertEqual(WhatsAppConversation.objects.count(), 1)
            conv = WhatsAppConversation.objects.first()
            self.assertTrue(conv.is_active)
            
            # Check usage
            usage = WhatsAppUsage.objects.first()
            self.assertEqual(usage.conversation_count, 1)

    def test_warm_start_text_allowed(self):
        """Phase 4: Warm start (active window via Log) allowed."""
        # Log an inbound message < 24h ago
        WhatsAppMessage.objects.create(
            credential=self.credential,
            direction='inbound',
            user_phone_number=self.phone,
            timestamp=timezone.now()
        )
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"messages": [{"id": "wamid_reply"}]}
            
            node = WhatsAppSendNode({
                "credential_id": str(self.credential.id),
                "phone_number": self.phone,
                "message_mode": "text",
                "message_content": "Reply"
            })
            
            node.run(input_data={})
            
            # Should create conversation (since none existed, but window open)
            self.assertEqual(WhatsAppConversation.objects.count(), 1)
            # Usage should increment
            self.assertEqual(WhatsAppUsage.objects.first().conversation_count, 1)

    def test_usage_limit_blocking(self):
        """Phase 6: Hard limit blocking."""
        WhatsAppUsage.objects.create(
            credential=self.credential,
            month=timezone.now().strftime('%Y-%m'),
            conversation_count=1000
        )
        
        # Log inbound so window is open (otherwise it blocks for "Cold Text")
        WhatsAppMessage.objects.create(
             credential=self.credential,
             direction='inbound',
             user_phone_number=self.phone,
             timestamp=timezone.now()
        )
        
        node = WhatsAppSendNode({
            "credential_id": str(self.credential.id),
            "phone_number": self.phone,
            "message_mode": "text",
            "message_content": "Test"
        })
        
        try:
            node.run(input_data={})
            self.fail("Should block due to limit")
        except NodeExecutionError as e:
            self.assertIn("Limit Exceeded", str(e))
