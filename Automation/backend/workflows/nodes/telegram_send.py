
from typing import Dict, Any
import requests
import json
import time
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..models import Credential

@register_node
class TelegramSendNode(ActionNode):
    NODE_TYPE = "telegram_send"
    DISPLAY_NAME = "Telegram Send"
    DESCRIPTION = "Send a message via Telegram Bot"
    CATEGORY = "communication"
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
                "chat_id": {
                    "type": "string",
                    "title": "Chat ID",
                    "description": "User or Group Chat ID (e.g. 12345678 or @channel). Supports templates.",
                    "required": True
                },
                "message_text": {
                    "type": "string",
                    "title": "Message Text",
                    "widget": "textarea",
                    "description": "If empty, uses incoming data from previous node. Supports templates."
                },
                "parse_mode": {
                    "type": "string",
                    "title": "Parse Mode",
                    "enum": ["None", "Markdown", "HTML"],
                    "default": "Markdown"
                },
                "disable_web_preview": {
                    "type": "boolean",
                    "title": "Disable Web Preview",
                    "default": False
                },
                "send_as_silent": {
                    "type": "boolean",
                    "title": "Send Silently",
                    "description": "Send message without notification",
                    "default": False
                },
                "reply_to_message_id": {
                    "type": "string",
                    "title": "Reply To Message ID",
                    "description": "ID of the message to reply to. Supports templates."
                }
            },
            "required": ["credential_id", "chat_id"]
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # 1. Resolve Config
            config = self.config.copy()
            if params: config.update(params)

            # 2. Resolve Credential ID
            credential_id = config.get("credential_id")
            if not credential_id:
                # Fallback to context/input check from Trigger
                credential_id = input_data.get("telegram_bot_credential_id") or context.get("variables", {}).get("telegram_bot_credential_id")

            if not credential_id:
                raise ValueError("Telegram Bot Credential is required. Please select a credential or ensure the trigger passes it.")

            # 3. Fetch and Decrypt Credential
            from workflows.models import Credential
            from workflows.services.credential_encryption import get_encryption_service
            
            try:
                credential = Credential.objects.get(id=credential_id)
            except Credential.DoesNotExist:
                raise ValueError(f"Credential with ID {credential_id} not found.")

            encryption_service = get_encryption_service()
            
            creds = credential.encrypted_data
            if isinstance(creds, str) and encryption_service:
                try:
                    decrypted = encryption_service.decrypt_credential_str(creds)
                    creds = json.loads(decrypted)
                except Exception as e:
                    self.logger.error(f"Failed to decrypt credential: {e}")
                    # Try to parse as raw JSON if decryption fails (fallback for unencrypted dev data)
                    try:
                        creds = json.loads(creds)
                    except:
                        pass
            
            if isinstance(creds, str):
                 try: creds = json.loads(creds)
                 except: pass

            token = creds.get("bot_token") or creds.get("token")
            if not token:
                raise ValueError("Telegram Bot Token is missing in credential data.")

            # 4. Resolve Fields
            chat_id = self._resolve_template(config.get("chat_id"), input_data, context)
            message = self._resolve_template(config.get("message_text") or config.get("message"), input_data, context)
            
            # --- SMART FALLBACK ---
            if not message:
                # Priority order: AI Agent output fields → generic text fields → full JSON
                message = (
                    input_data.get('response') or
                    input_data.get('text') or
                    input_data.get('content') or
                    # Nested inside 'output' dict (AI Agent standard output)
                    (input_data.get('output') or {}).get('response') or
                    (input_data.get('output') or {}).get('text') or
                    (input_data.get('output') or {}).get('content')
                )

                # Try context main input
                if not message:
                    main_input = context.get('inputs', {}).get('main', [])
                    if main_input and isinstance(main_input, list):
                        first = main_input[0]
                        if isinstance(first, dict):
                            message = (
                                first.get('response') or first.get('text') or
                                first.get('content') or
                                (first.get('output') or {}).get('response') or
                                (first.get('output') or {}).get('text')
                            )

                # Last resort: dump input_data but skip internal keys
                if not message and input_data:
                    skip_keys = {'success', 'error', 'meta', 'conversation', 'telegram_bot_credential_id',
                                 'payload', 'raw', 'is_bot', 'is_group'}
                    clean = {k: v for k, v in input_data.items() if k not in skip_keys and v}
                    if clean:
                        message = json.dumps(clean, indent=2, ensure_ascii=False)

            if not chat_id:
                # Last ditch effort: try input_data 'chat_id'
                chat_id = input_data.get('chat_id')
            
            if not chat_id:
                raise ValueError("Chat ID is missing. Please map it from the trigger output (e.g. {{ $json.chat_id }}).")

            if not message:
                 # Don't fail, just send a default message to indicate successful flow but no content
                 message = "[Empty Message]"

            # Validate Chat ID format (numeric or @channel)
            chat_id = str(chat_id).strip()
            
            parse_mode = config.get("parse_mode", "Markdown")
            if parse_mode == "None": parse_mode = None
            
            disable_preview = config.get("disable_web_preview", False)
            silent = config.get("send_as_silent", False)
            reply_to = self._resolve_template(config.get("reply_to_message_id"), input_data, context)

            # 5. Chunking & Sending
            chunks = self.format_for_telegram(message, parse_mode or "None")
            responses = []

            for i, chunk in enumerate(chunks):
                if not chunk.strip(): continue
                
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_preview,
                    "disable_notification": silent
                }
                if reply_to and i == 0: # Only reply to the first chunk
                    payload["reply_to_message_id"] = reply_to

                resp = requests.post(url, json=payload, timeout=30) # Increased timeout
                
                try:
                    resp_json = resp.json()
                except:
                    resp_json = {"ok": False, "description": "Invalid JSON response from Telegram", "raw": resp.text}

                if not resp_json.get("ok"):
                    # Quick retry if parse_mode error
                    description = resp_json.get("description", "").lower()
                    if ("can't parse" in description or "markdown" in description or "entity" in description) and parse_mode:
                        self.logger.warning(f"Markdown parsing failed. Retrying as plain text. Error: {description}")
                        payload["parse_mode"] = None
                        resp = requests.post(url, json=payload, timeout=30)
                        try:
                             resp_json = resp.json()
                        except:
                             resp_json = {"ok": False, "description": "Invalid JSON from Telegram on retry"}
                    
                    if not resp_json.get("ok"):
                        error_desc = resp_json.get('description', 'Unknown error')
                        raise NodeExecutionError(f"Telegram API Error: {error_desc} (Chat ID: {chat_id})")

                responses.append(resp_json)
                
                # Small delay to prevent rate limiting (30 msgs/sec standard)
                if len(chunks) > 1:
                    time.sleep(0.1)

            # 6. Success Output
            last_resp = responses[-1] if responses else {}
            return {
                "success": True,
                "output": {
                    "status": "sent",
                    "chat_id": chat_id,
                    "message_id": last_resp.get("result", {}).get("message_id"),
                    "sent_count": len(responses),
                    "raw": last_resp
                }
            }

        except Exception as e:
            self.logger.error(f"Telegram Send Logic Crash: {str(e)}")
            return {"success": False, "error": str(e)}

    # Phase T11: Response Shaper
    @staticmethod
    def format_for_telegram(text: str, parse_mode: str) -> list:
        """
        Shaped AI response for Telegram:
        1. Split into 4096 chunks.
        2. Ensure we don't break markdown entities across chunks (simplified).
        """
        if not text: return [""]
        text = str(text)
        
        # 2. Chunking (Max 4096)
        MAX_LEN = 4090 # Safety buffer
        chunks = []
        
        while len(text) > MAX_LEN:
            # Find nearest newline to split
            split_idx = text.rfind('\n', 0, MAX_LEN)
            
            # If no nice break point, force break at MAX_LEN
            if split_idx == -1: 
                split_idx = MAX_LEN
            else:
                # Include the newline in the first chunk, or exclude?
                # rfind gives index of \n. Python slice [:idx] excludes it.
                # Actually, better to include it in the first chunk so line breaks happen naturally.
                split_idx += 1 
            
            chunk = text[:split_idx]
            text = text[split_idx:]
            chunks.append(chunk)
            
        if text: chunks.append(text)
        
        return chunks
