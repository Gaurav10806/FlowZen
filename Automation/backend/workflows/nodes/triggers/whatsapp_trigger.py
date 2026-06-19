from typing import Dict, Any
from ..base_node import TriggerNode, NodeExecutionError
from ..registry import register_node
from workflows.models import Credential
import logging

logger = logging.getLogger(__name__)

@register_node
class WhatsAppTriggerNode(TriggerNode):
    """
    WhatsApp Trigger - Check Human Takeover & Output standardized fields
    """
    NODE_TYPE = "whatsapp_trigger"
    CATEGORY = "TRIGGERS"  # Matches System Standard
    DISPLAY_NAME = "WhatsApp Trigger"
    DESCRIPTION = "Triggers when a WhatsApp message is received"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "WhatsApp Account",
                    "widget": "credential_select",
                    "widgetOptions": {"credentialType": ["meta_whatsapp"]},
                    "required": True
                }
            },
            "required": ["credential_id"]
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Input data comes from the Webhook View (whatsapp_handler.py)
        # It should already be formatted.
        
        # 0. Manual Execution / Test Button Check
        # If input_data is empty or missing keys, it's likely a manual test run.
        if not input_data or not input_data.get('object') and not input_data.get('entry'):
             # Allow if it's already processed data (check for message_text)
             if not input_data.get('message_text'):
                 raise NodeExecutionError("WhatsApp Trigger can only be tested by sending a real WhatsApp message.")
        
        # 1. Human Takeover Check
        is_human = input_data.get('is_human_controlled', False)
        if is_human:
            logger.info("⛔ WhatsApp Trigger stopped: Conversation is Human Controlled.")
            # Stop execution by raising error or returning specific flag?
            # Based on user instruction "Check Human Takeover", we stop.
            raise NodeExecutionError("Conversation is managed by a human agent. Automation paused.")
            
        # Return the payload as is (text, phone, contact_name, etc.)
        return input_data
