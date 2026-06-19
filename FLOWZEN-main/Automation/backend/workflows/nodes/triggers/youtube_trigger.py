from typing import Dict, Any, List
from ..base_node import TriggerNode, NodeExecutionError
from ..registry import register_node

@register_node
class YouTubeTriggerNode(TriggerNode):
    """
    YouTube Trigger Node - starts workflow when new videos are posted or search results change.
    """
    NODE_TYPE = "youtube_trigger"
    DISPLAY_NAME = "YouTube Trigger"
    DESCRIPTION = "Triggers workflow on YouTube events"
    CATEGORY = "TRIGGERS"
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "trigger_type": {
                    "type": "select",
                    "title": "Trigger Type",
                    "options": ["channel", "playlist", "search"],
                    "default": "channel"
                },
                "channel_id": {
                    "type": "string",
                    "title": "Channel ID",
                    "visible_if": {
                        "field": "trigger_type",
                        "equals": "channel"
                    }
                },
                "playlist_id": {
                    "type": "string",
                    "title": "Playlist ID",
                    "visible_if": {
                        "field": "trigger_type",
                        "equals": "playlist"
                    }
                },
                "search_query": {
                    "type": "string",
                    "title": "Search Query",
                    "visible_if": {
                        "field": "trigger_type",
                        "equals": "search"
                    }
                }
            }
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation for YouTube Trigger processing
        return {
            "video": input_data,
            "success": True
        }
