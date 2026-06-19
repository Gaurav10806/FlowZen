"""
WebSocket consumer for real-time log streaming.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ExecutionLogConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for streaming execution logs."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.execution_id = self.scope["url_route"]["kwargs"]["execution_id"]
        self.group_name = f"execution_{self.execution_id}"
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection message
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to execution {self.execution_id}",
            "execution_id": self.execution_id,
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages received from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            if message_type == "ping":
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "execution_id": self.execution_id,
                }))
        except json.JSONDecodeError:
            pass
    
    async def log_message(self, event):
        """Receive log message from group and send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type": "log",
            "level": event.get("level", "info"),
            "message": event.get("message", ""),
            "data": event.get("data", {}),
            "execution_id": self.execution_id,
        }))
    
    async def execution_event(self, event):
        """Receive execution event from group and send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type": event.get("event_type", "event"),
            "data": event.get("data", {}),
            "execution_id": self.execution_id,
            "timestamp": event.get("timestamp"),
        }))

