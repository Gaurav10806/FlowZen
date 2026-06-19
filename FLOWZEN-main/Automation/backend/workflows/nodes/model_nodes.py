from typing import Dict, Any, List
from .base_node import ActionNode
from .registry import register_node
from .agent_tools import ToolRegistry

@register_node
class OpenAIChatModelNode(ActionNode):
    NODE_TYPE = "model_openai"
    CATEGORY = "ai"
    
    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Outputs model configuration for AI Agent.
        """
        config = self.config or {}
        
        return {
            "success": True,
            "output": {
                "model": config.get("model", "gpt-4o"),
                "temperature": float(config.get("temperature", 0.7)),
                "provider": "openai",
                "credential_id": config.get("credential_id")
            }
        }

# --- Web Search Tool Implementation ---

def google_search_handler(args: Dict, input_data: Any, context: Any) -> str:
    query = args.get("query") or args.get("input")
    return f"Search Results for '{query}': [1] Top result for {query}... [2] Another result."

# Register globally so AI Agent can execute it
ToolRegistry.register(
    "google_search",
    google_search_handler,
    "Search the web for information."
)

@register_node
class WebSearchToolNode(ActionNode):
    NODE_TYPE = "tool_websearch"
    CATEGORY = "tools"
    
    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Outputs tool definition.
        """
        # Defines the schema
        tool_def = {
            "name": "google_search",
            "description": "Search the web for current events or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            },
            # "handler": google_search_handler -- Handler is registered globally by name
        }
        
        return {
            "success": True,
            "output": tool_def
        }
