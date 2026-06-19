import logging
import requests
import json

logger = logging.getLogger(__name__)

class DiscordService:
    """
    Service wrapper for Discord API interactions.
    Supports Webhook and Bot modes.
    """
    
    API_BASE = "https://discord.com/api/v10"

    def __init__(self, bot_token: str = None):
        """
        Initialize Discord Service.
        Args:
            bot_token: Optional token for Bot operations.
        """
        self.bot_token = bot_token
        self.headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        } if bot_token else {}

    def execute_webhook(self, webhook_url: str, content: str, username: str = None, avatar_url: str = None, embeds: list = None):
        """
        Execute a Discord Webhook.
        """
        try:
            payload = {"content": content}
            if username: payload["username"] = username
            if avatar_url: payload["avatar_url"] = avatar_url
            if embeds: payload["embeds"] = embeds
            
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("Executed Discord Webhook")
            return {"status": "success", "status_code": response.status_code}
        except Exception as e:
            logger.error(f"Discord Webhook Error: {e}")
            raise

    def send_channel_message(self, channel_id: str, content: str, embeds: list = None):
        """
        Send a message to a channel as a Bot.
        """
        if not self.bot_token:
            raise ValueError("Bot Token required for channel messages")
            
        try:
            url = f"{self.API_BASE}/channels/{channel_id}/messages"
            payload = {"content": content}
            if embeds: payload["embeds"] = embeds
            
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logger.info(f"Sent Discord message to channel {channel_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Discord Bot Message Error: {e}")
            raise
