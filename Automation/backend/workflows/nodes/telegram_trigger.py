from typing import Dict, Any, List
from .base_node import TriggerNode, NodeExecutionError
from .registry import register_node

@register_node
class TelegramTriggerNode(TriggerNode):
    NODE_TYPE = "telegram_trigger"
    DISPLAY_NAME = "Telegram Trigger"
    DESCRIPTION = "Triggers workflow on incoming Telegram events"
    CATEGORY = "TRIGGERS"
    credential_type = "telegram_bot"  # Standardized type
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Telegram Bot Credential",
                    "widget": "credential_select",
                    "widgetOptions": {"credentialType": ["telegram_bot"]},
                    "required": True
                },
                "events": {
                    "type": "multiselect",
                    "title": "Trigger On",
                    "options": ["message", "command", "callback_query"],
                    "default": ["message"]
                },
                "chatbot_mode": {
                    "type": "boolean",
                    "title": "Chatbot Mode",
                    "description": "Pass conversation context to AI nodes",
                    "default": False
                },
                "allow_groups": {
                    "type": "boolean",
                    "title": "Allow Group Messages",
                    "default": False
                },
                "allowed_chat_ids": {
                    "type": "string",
                    "title": "Allowed Chat IDs",
                    "description": "Comma-separated list (leave empty for all)",
                    "placeholder": "123456789, -987654321",
                    "default": ""
                },
                "trigger_keywords": {
                    "type": "string",
                    "title": "Trigger Keywords",
                    "description": "Comma-separated keywords",
                    "placeholder": "start, help",
                    "default": ""
                }
            },
            "required": ["credential_id"]
        }
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strict Output Contract:
        {
          "chat_id": "<string>",
          "user_id": "<string>",
          "username": "<string|null>",
          "is_group": "<boolean>",
          "message_id": "<string>",
          "raw_text": "<string>",
          "clean_text": "<string>",      
          "command": "<string|null>",
          "conversation_id": "<uuid>",
          "provider": "telegram"
        }
        """
        payload = input_data.get("payload")
        if not payload:
             raise NodeExecutionError("Telegram Trigger cannot be executed manually. Please send a message to your bot to test.")
        
        if not isinstance(payload, dict):
             if isinstance(payload, str):
                 import json
                 try: payload = json.loads(payload)
                 except: pass
        
        if not isinstance(payload, dict):
             raise NodeExecutionError(f"Invalid payload type: {type(payload)}. Expected dict from webhook.")

        chat_id = input_data.get("chat_id")
        
        if not chat_id:
            msg = (
                payload.get("message") or 
                payload.get("edited_message") or 
                payload.get("channel_post") or
                payload.get("my_chat_member")
            )
            
            if msg and isinstance(msg, dict) and "chat" in msg:
                chat_id = msg["chat"].get("id")
            elif "callback_query" in payload:
                cb = payload["callback_query"]
                if isinstance(cb, dict) and "message" in cb:
                     chat_id = cb["message"].get("chat", {}).get("id")

        if not chat_id:
            payload_keys = list(payload.keys())
            raise NodeExecutionError(f"Telegram Trigger failed: chat_id missing. Payload keys found: {payload_keys}")

        return {
            "chat_id": str(chat_id),
            "user_id": str(input_data.get("user_id", "")),
            "username": input_data.get("username"),
            "is_group": input_data.get("is_group", False),
            "message_id": str(input_data.get("message_id", "")),
            "raw_text": input_data.get("message", ""),
            "clean_text": input_data.get("clean_text", ""),
            "command": input_data.get("command"),
            "conversation_id": input_data.get("conversation_id"),
            "telegram_bot_credential_id": input_data.get("telegram_bot_credential_id"), # Passthrough for downstream nodes
            "provider": "telegram"
        }
