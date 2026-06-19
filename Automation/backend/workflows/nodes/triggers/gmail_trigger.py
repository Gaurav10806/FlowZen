from typing import Dict, Any, List
from ..base_node import TriggerNode, NodeExecutionError
from ..registry import register_node

@register_node
class GmailTriggerNode(TriggerNode):
    """
    Gmail Trigger Node - starts workflow when new emails arrive matching criteria.
    """
    NODE_TYPE = "gmail_trigger"
    DISPLAY_NAME = "Gmail Trigger"
    DESCRIPTION = "Triggers workflow on incoming Gmail messages"
    CATEGORY = "TRIGGERS"
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "watch_type": {
                    "type": "select",
                    "title": "Watch Type",
                    "options": ["inbox", "sent", "label"],
                    "default": "inbox"
                },
                "label_name": {
                    "type": "string",
                    "title": "Label Name",
                    "description": "Only if Watch Type is Label",
                    "placeholder": "INBOX",
                    "visible_if": {
                        "field": "watch_type",
                        "equals": "label"
                    }
                },
                "only_unread": {
                    "type": "boolean",
                    "title": "Only Unread",
                    "default": True
                },
                "from_filter": {
                    "type": "string",
                    "title": "From Filter",
                    "description": "Filter by sender email",
                    "placeholder": "example@gmail.com",
                    "default": ""
                }
            }
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation for Gmail Trigger processing
        return {
            "email": input_data,
            "success": True
        }
