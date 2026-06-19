"""
Telegram Chatbot Nodes - Reply, Buttons, Set Commands, Answer Callback
"""
from typing import Dict, Any
import requests
import json
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node


def _get_bot_token(credential_id, input_data, context):
    # Normalize context to dict
    if hasattr(context, 'to_dict'):
        context = context.to_dict()
    if not isinstance(context, dict):
        context = {}

    if not credential_id:
        credential_id = (
            input_data.get("telegram_bot_credential_id")
            or (context.get("variables") or {}).get("telegram_bot_credential_id")
        )
    if not credential_id:
        raise NodeExecutionError("Telegram Bot Credential is required.")

    # Lazy import to avoid circular dependency
    from workflows.models import Credential
    from workflows.services.credential_encryption import get_encryption_service

    try:
        credential = Credential.objects.get(id=credential_id)
    except Credential.DoesNotExist:
        raise NodeExecutionError(f"Credential {credential_id} not found.")

    creds = credential.encrypted_data
    enc = get_encryption_service()

    # Try all decryption strategies
    parsed = None
    if isinstance(creds, dict):
        parsed = creds
    elif isinstance(creds, str):
        # Strategy 1: decrypt then parse
        if enc:
            try:
                parsed = json.loads(enc.decrypt_credential_str(creds))
            except Exception:
                pass
        # Strategy 2: plain JSON string
        if parsed is None:
            try:
                parsed = json.loads(creds)
            except Exception:
                pass
        # Strategy 3: raw string search for token pattern
        if parsed is None:
            import re
            match = re.search(r'(\d{8,12}:[A-Za-z0-9_-]{35,})', creds)
            if match:
                return match.group(1)

    if not isinstance(parsed, dict):
        raise NodeExecutionError("Could not read bot token from credential. Please re-save the Telegram credential.")

    token = parsed.get("bot_token") or parsed.get("token")
    if not token:
        raise NodeExecutionError("Bot token missing in credential.")
    return token


@register_node
class TelegramReplyNode(ActionNode):
    NODE_TYPE = "telegram_reply"
    DISPLAY_NAME = "Telegram Reply"
    DESCRIPTION = "Reply to the incoming Telegram message"
    CATEGORY = "Messaging"
    credential_type = "telegram_bot"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "title": "Telegram Bot Credential", "widget": "credential_select", "widgetOptions": {"credentialType": ["telegram_bot"]}, "required": True},
                "message_text": {"type": "string", "title": "Reply Text", "widget": "textarea", "required": True},
                "parse_mode": {"type": "string", "title": "Parse Mode", "enum": ["Markdown", "HTML", "None"], "default": "Markdown"},
                "disable_web_preview": {"type": "boolean", "title": "Disable Web Preview", "default": False},
            },
            "required": ["credential_id", "message_text"],
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = {**self.config, **(params or {})}
        token = _get_bot_token(config.get("credential_id"), input_data, context)

        chat_id = input_data.get("chat_id")
        if not chat_id:
            raise NodeExecutionError("chat_id not found. Connect after a Telegram Trigger.")

        reply_to = input_data.get("message_id")
        message = self._resolve_template(config.get("message_text", ""), input_data, context)
        if not message:
            message = (
                input_data.get("response") or input_data.get("text") or
                (input_data.get("output") or {}).get("response") or
                (input_data.get("output") or {}).get("text") or
                "[Empty Reply]"
            )

        parse_mode = config.get("parse_mode", "Markdown")
        if parse_mode == "None":
            parse_mode = None

        payload = {"chat_id": str(chat_id), "text": str(message), "disable_web_page_preview": config.get("disable_web_preview", False)}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_to:
            payload["reply_to_message_id"] = reply_to

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json=payload, timeout=30).json()

        if not resp.get("ok") and parse_mode:
            payload.pop("parse_mode", None)
            resp = requests.post(url, json=payload, timeout=30).json()

        if not resp.get("ok"):
            raise NodeExecutionError(f"Telegram API Error: {resp.get('description', 'Unknown')}")

        # Log outbound message
        try:
            from workflows.models import TelegramConversation, TelegramMessage
            conv = TelegramConversation.objects.filter(chat_id=str(chat_id)).first()
            if conv:
                TelegramMessage.objects.create(
                    credential=conv.credential, conversation=conv, direction="outbound",
                    chat_id=str(chat_id), message_id=str(resp.get("result", {}).get("message_id", "")),
                    message_type="text", text=str(message), raw_payload=resp,
                )
        except Exception:
            pass

        return {"success": True, "output": {"status": "replied", "chat_id": str(chat_id), "message_id": resp.get("result", {}).get("message_id")}}


@register_node
class TelegramSendButtonsNode(ActionNode):
    NODE_TYPE = "telegram_send_buttons"
    DISPLAY_NAME = "Telegram Send Buttons"
    DESCRIPTION = "Send a message with inline keyboard buttons"
    CATEGORY = "Messaging"
    credential_type = "telegram_bot"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "title": "Telegram Bot Credential", "widget": "credential_select", "widgetOptions": {"credentialType": ["telegram_bot"]}, "required": True},
                "chat_id": {"type": "string", "title": "Chat ID", "required": True},
                "message_text": {"type": "string", "title": "Message Text", "widget": "textarea", "required": True},
                "buttons": {"type": "string", "title": "Buttons (JSON)", "widget": "textarea", "required": True, "placeholder": '[[{"text":"Yes","callback_data":"yes"},{"text":"No","callback_data":"no"}]]'},
                "parse_mode": {"type": "string", "title": "Parse Mode", "enum": ["Markdown", "HTML", "None"], "default": "Markdown"},
            },
            "required": ["credential_id", "chat_id", "message_text", "buttons"],
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = {**self.config, **(params or {})}
        token = _get_bot_token(config.get("credential_id"), input_data, context)

        chat_id = self._resolve_template(config.get("chat_id", ""), input_data, context) or input_data.get("chat_id")
        if not chat_id:
            raise NodeExecutionError("chat_id is required.")

        message = self._resolve_template(config.get("message_text", ""), input_data, context)
        buttons_raw = self._resolve_template(config.get("buttons", "[]"), input_data, context)
        try:
            keyboard = json.loads(buttons_raw) if isinstance(buttons_raw, str) else buttons_raw
        except json.JSONDecodeError as e:
            raise NodeExecutionError(f"Invalid buttons JSON: {e}")

        parse_mode = config.get("parse_mode", "Markdown")
        if parse_mode == "None":
            parse_mode = None

        payload = {"chat_id": str(chat_id), "text": message, "reply_markup": {"inline_keyboard": keyboard}}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=30).json()
        if not resp.get("ok"):
            raise NodeExecutionError(f"Telegram API Error: {resp.get('description', 'Unknown')}")

        return {"success": True, "output": {"status": "sent", "chat_id": str(chat_id), "message_id": resp.get("result", {}).get("message_id")}}


@register_node
class TelegramSetCommandsNode(ActionNode):
    NODE_TYPE = "telegram_set_commands"
    DISPLAY_NAME = "Telegram Set Commands"
    DESCRIPTION = "Register bot commands shown in Telegram command menu"
    CATEGORY = "Messaging"
    credential_type = "telegram_bot"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string", "title": "Telegram Bot Credential", "widget": "credential_select", "widgetOptions": {"credentialType": ["telegram_bot"]}, "required": True},
                "commands": {"type": "string", "title": "Commands (JSON)", "widget": "textarea", "required": True, "placeholder": '[{"command":"start","description":"Start the bot"}]'},
            },
            "required": ["credential_id", "commands"],
        }

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        config = {**self.config, **(params or {})}
        token = _get_bot_token(config.get("credential_id"), input_data, context)

        commands_raw = config.get("commands", "[]")
        try:
            commands = json.loads(commands_raw) if isinstance(commands_raw, str) else commands_raw
        except json.JSONDecodeError as e:
            raise NodeExecutionError(f"Invalid commands JSON: {e}")

        resp = requests.post(f"https://api.telegram.org/bot{token}/setMyCommands", json={"commands": commands}, timeout=30).json()
        if not resp.get("ok"):
            raise NodeExecutionError(f"Telegram API Error: {resp.get('description', 'Unknown')}")

        return {"success": True, "output": {"status": "commands_set", "commands_count": len(commands)}}
