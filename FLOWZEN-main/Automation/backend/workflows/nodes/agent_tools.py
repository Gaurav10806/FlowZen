import logging
import requests
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)

class ToolRegistry:
    _tools = {}

    @classmethod
    def register(cls, name: str, handler: Callable, description: str = ""):
        """Register a new tool handler."""
        cls._tools[name] = {
            "handler": handler,
            "description": description
        }

    @classmethod
    def resolve(cls, enabled: list):
        """
        Resolve enabled tools into a dictionary.
        Supports both string names (registry lookup) and direct tool objects.
        """
        resolved = {}
        
        for item in enabled:
            if isinstance(item, str):
                if item in cls._tools:
                    resolved[item] = cls._tools[item]
            elif isinstance(item, dict) and "name" in item:
                # Dynamic tool passed directly
                resolved[item["name"]] = item
                
        return resolved

    @classmethod
    def execute(cls, tool_call: dict, input_data: dict, context: dict):
        """Execute a tool call."""
        name = tool_call["name"]
        args = tool_call.get("arguments", {})
        
        if name not in cls._tools:
            raise ValueError(f"Tool '{name}' not found")
        
        handler = cls._tools[name]["handler"]
        return handler(args, input_data, context)

# --- Built-in Tools ---

def http_request_handler(args, input_data, context):
    method = args.get("method", "GET")
    url = args.get("url")
    body = args.get("body")
    headers = args.get("headers", {})
    
    response = requests.request(method, url, json=body, headers=headers)
    return {
        "status": response.status_code,
        "text": response.text
    }

ToolRegistry.register(
    "http", 
    http_request_handler, 
    "Make an HTTP request. Args: method, url, body, headers"
)

def email_handler(args, input_data, context):
    # This is a stub. In production, use your email service or credentials.
    # For now, we simulate success.
    recipient = args.get("to")
    subject = args.get("subject")
    body = args.get("body")
    return f"Email sent to {recipient} with subject '{subject}'"

ToolRegistry.register(
    "email", 
    email_handler, 
    "Send an email. Args: to, subject, body"
)

def calendar_handler(args, input_data, context):
    # Stub
    return "Calendar event created (Simulation)"

ToolRegistry.register(
    "calendar", 
    calendar_handler, 
    "Manage calendar events."
)
