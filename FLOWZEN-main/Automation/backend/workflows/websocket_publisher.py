"""
WebSocket event publisher for real-time execution monitoring.
"""
import json
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def publish_execution_event(execution_id: str, event_type: str, data: dict):
    """
    Publish execution event to WebSocket channel.
    
    Args:
        execution_id: Workflow execution ID
        event_type: Event type (node_started, node_completed, node_failed, etc.)
        data: Event data
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("Channel layer not configured")
            return
        
        channel_name = f"execution_{execution_id}"
        
        message = {
            "type": "execution_event",
            "event_type": event_type,
            "data": data,
        }
        
        async_to_sync(channel_layer.group_send)(
            channel_name,
            {
                "type": "execution_event",
                "event_type": event_type,
                "data": data,
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to publish WebSocket event: {e}")

