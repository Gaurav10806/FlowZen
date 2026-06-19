from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class BaseTool:
    name: str = "base_tool"
    description: str = "Base tool"
    parameters: Dict = {}

    def run(self, **kwargs) -> Any:
        raise NotImplementedError

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for information."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }

    def run(self, query: str) -> str:
        # Mock implementation for now - replace with SerpAPI later if needed
        return f"[Mock Search Result] Found information about: {query}"

class HttpRequestTool(BaseTool):
    name = "http_request"
    description = "Make generic HTTP requests."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "method": {"type": "string", "enum": ["GET", "POST"]},
            "body": {"type": "object"}
        },
        "required": ["url"]
    }

    def run(self, url: str, method: str = "GET", body: dict = None) -> str:
        return f"[Mock HTTP] {method} request to {url} successful"

class DatabaseQueryTool(BaseTool):
    name = "database_query"
    description = "Execute a SQL query."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        },
        "required": ["query"]
    }

    def run(self, query: str) -> str:
        return f"[Mock DB] Executed: {query}. Result: []"

class GoogleSheetsTool(BaseTool):
    name = "google_sheets"
    description = "Read or write to Google Sheets."
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["read", "write"]},
            "range": {"type": "string"}
        },
        "required": ["operation"]
    }

    def run(self, operation: str, range: str = "A1") -> str:
        return f"[Mock Sheets] {operation} on {range} successful"

class TelegramTool(BaseTool):
    name = "telegram_send"
    description = "Send a Telegram message."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string"}
        },
        "required": ["message"]
    }

    def run(self, message: str) -> str:
        return f"[Mock Telegram] Sent: {message}"

class WhatsAppTool(BaseTool):
    name = "whatsapp_send"
    description = "Send a WhatsApp message."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string"}
        },
        "required": ["message"]
    }

    def run(self, message: str) -> str:
        return f"[Mock WhatsApp] Sent: {message}"

class FileStorageTool(BaseTool):
    name = "file_storage"
    description = "Read/Write files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["path"]
    }

    def run(self, path: str, content: str = None) -> str:
         return f"[Mock File] Accessing {path}"

# STARTUP REGISTRY
TOOL_REGISTRY = {
    "Web Search": WebSearchTool(),
    "HTTP Request": HttpRequestTool(),
    "Database Query": DatabaseQueryTool(),
    "Google Sheets": GoogleSheetsTool(),
    "Telegram": TelegramTool(),
    "WhatsApp": WhatsAppTool(),
    "File Storage": FileStorageTool()
}

class ToolRegistry:
    """
    Central registry for AI tools.
    """
    
    @staticmethod
    def resolve(tool_names: List[str]) -> List[Dict]:
        """
        Convert UI tool names to OpenAI function definitions.
        """
        definitions = []
        for name in tool_names: # UI names: "Web Search"
            tool = TOOL_REGISTRY.get(name)
            if tool:
                definitions.append({
                    "type": "function",
                    "function": {
                        "name": tool.name, # Internal ID: "web_search"
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                })
        return definitions

    @staticmethod
    def execute(tool_name: str, arguments: Dict) -> str:
        """
        Execute a tool by internal name.
        """
        # Linear search for now (registry keys are UI names, values have .name attr)
        for tool_instance in TOOL_REGISTRY.values():
            if tool_instance.name == tool_name:
                try:
                    return str(tool_instance.run(**arguments))
                except Exception as e:
                    return f"Error executing {tool_name}: {str(e)}"
        
        return f"Tool {tool_name} not found."
