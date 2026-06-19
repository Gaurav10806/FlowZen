
import json
import logging
from typing import Dict, Any, List
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    Phase 12: Tool Execution Engine.
    Executes tools requested by the AI.
    """

    @classmethod
    def execute_tool_calls(cls, tool_calls: List[Dict], context: Dict = None) -> List[Dict]:
        """
        Executes a list of OpenAI-style tool calls.
        Returns messages to append to chat history (Tool Outputs).
        """
        results = []
        
        for call in tool_calls:
            call_id = call.get('id')
            func_name = call['function']['name']
            args_str = call['function']['arguments']
            
            try:
                # 1. Parse Args
                args = json.loads(args_str)
                
                # 2. Lookup Tool
                func = ToolRegistry.get_tool(func_name)
                if not func:
                    raise ValueError(f"Tool '{func_name}' not found.")
                
                # 3. Execute
                logger.info(f"🛠️ Executing Tool: {func_name}({args})")
                output = func(**args)
                
                # 4. Format Result
                results.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "name": func_name,
                    "content": str(output)
                })
                
            except Exception as e:
                logger.error(f"Tool Execution Failed: {e}")
                results.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "name": func_name,
                    "content": f"Error: {str(e)}"
                })
                
        return results
