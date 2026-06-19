from typing import Dict, Any
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from workflows.services.discord_service import DiscordService
from workflows.models import Credential

@register_node
class DiscordNode(ActionNode):
    """
    Discord Action Node.
    Supports Webhook and Bot modes.
    """
    
    NODE_TYPE = "discord"
    DISPLAY_NAME = "Discord"
    DESCRIPTION = "Send messages via Webhook or Bot"
    CATEGORY = "social"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Discord operation.
        """
        config = self.config.copy()
        if params:
            config.update(params)
        params = config

        mode = params.get('mode', 'webhook')
        message = self._resolve_template(params.get('message', ''), input_data, context)
        
        if not message:
            raise NodeExecutionError("Message content is required")

        result = {}
        
        try:
            if mode == 'webhook':
                webhook_url = self._resolve_template(params.get('webhook_url', ''), input_data, context)
                if not webhook_url:
                    raise NodeExecutionError("Webhook URL required for Webhook mode")
                    
                service = DiscordService() # No token needed for webhook
                username = params.get('username')
                avatar_url = params.get('avatar_url')
                
                result = service.execute_webhook(webhook_url, message, username, avatar_url)
                
            elif mode == 'bot':
                credential_id = params.get('credential_id')
                if not credential_id:
                     raise NodeExecutionError("Discord Bot Token (Credential) required for Bot mode")
                
                # Resolve Credential
                try:
                    credential = Credential.objects.get(
                        id=credential_id, 
                        provider='discord', 
                        type='discord_bot'
                    )
                except Exception as e:
                    raise NodeExecutionError(f"Error resolving Discord Credential: {str(e)}")
                
                # Decrypt
                try:
                    from workflows.services.credential_encryption import get_encryption_service
                    svc = get_encryption_service()
                    token = credential.encrypted_data
                    if svc and isinstance(token, str):
                         # Assuming raw token might be encrypted string
                         pass 
                    
                    # For simplicty assume encrypted_data IS the token string in dict or direct
                    if isinstance(token, dict):
                        token = token.get('token')
                        
                except Exception as e:
                    raise NodeExecutionError(f"Failed to decrypt credential: {str(e)}")
                
                channel_id = self._resolve_template(params.get('channel_id', ''), input_data, context)
                if not channel_id:
                     raise NodeExecutionError("Channel ID required for Bot mode")
                     
                service = DiscordService(bot_token=token)
                result = service.send_channel_message(channel_id, message)
                
            else:
                raise NodeExecutionError(f"Unknown mode: {mode}")

            return {
                "success": True,
                "output": result
            }

        except Exception as e:
            self.logger.error(f"Discord Node Execution Failed: {e}")
            raise NodeExecutionError(f"Discord Error: {str(e)}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "title": "Mode",
                    "enum": ["webhook", "bot"],
                    "default": "webhook"
                },
                "credential_id": {
                    "type": "string",
                    "title": "Bot Token",
                    "widget": "credential_select",
                    "credential_type": "discord_bot",
                    "description": "Required for Bot Mode"
                },
                "webhook_url": {
                    "type": "string",
                    "title": "Webhook URL",
                    "description": "Required for Webhook Mode"
                },
                "channel_id": {
                    "type": "string",
                    "title": "Channel ID",
                    "description": "Required for Bot Mode"
                },
                "message": {
                    "type": "string",
                    "title": "Message",
                    "widget": "textarea"
                },
                "username": {
                    "type": "string",
                    "title": "Username Override",
                    "description": "Webhook only"
                }
            },
            "required": ["mode", "message"]
        }
