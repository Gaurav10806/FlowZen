from typing import Dict, Any
from workflows.ai_providers.universal_engine import UniversalAIEngine
from workflows.ai_providers.prompts import UNIVERSAL_AGENT_SYSTEM_PROMPT, UNIVERSAL_CONTROL_PLANE_SYSTEM_PROMPT
import json
import logging
import time
from datetime import datetime
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..expression_evaluator import evaluate_expression
from workflows.ai_tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

@register_node
class AIAgentNode(ActionNode):
    NODE_TYPE = "ai_agent"
    CATEGORY = "AI"
    DISPLAY_NAME = "AI Agent"
    DESCRIPTION = "Autonomous AI Agent powered by Ollama or OpenAI"

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Upgraded AI Agent Execution:
        1. Resolve handle-aware inputs (Main, Tools, Memory, System)
        2. Consolidate prompts and conversation history
        3. Standardize execution and output
        """
        try:
            # --- 1. CONFIG & CONTEXT ---
            cfg = self.config or {}
            # context is now passed directly
            
            # IDENTITY
            agent_name = cfg.get("agent_name", "AI Agent")
            
            # PROMPT TEMPLATES
            system_template = cfg.get("system_prompt", "You are a helpful AI agent.")
            user_template = cfg.get("user_prompt", "")
            
            # --- 2. INPUT PROCESSING (HANDLE-AWARE) ---
            # Resolve templates
            def safe_evaluate(expr):
                if not expr: return ""
                try:
                    if hasattr(context, 'evaluate'): return context.evaluate(expr)
                    if isinstance(context, dict) and 'evaluator' in context:
                         return context['evaluator'].evaluate(expr)
                    # Fallback to simple expression evaluator if needed
                    from ..expression_evaluator import evaluate_expression
                    return evaluate_expression(expr, execution_context=context if isinstance(context, dict) else getattr(context, 'execution_context', {}))
                except: return expr

            base_user_prompt = safe_evaluate(user_template)
            base_system_prompt = safe_evaluate(system_template) or "You are a helpful AI agent."

            # Extract handle inputs from context
            if hasattr(context, 'inputs'):
                handle_inputs = context.inputs
            elif isinstance(context, dict):
                handle_inputs = context.get('inputs', {})
            else:
                handle_inputs = {}
                
            main_items = handle_inputs.get("main", [])
            system_items = handle_inputs.get("system", [])
            tool_items = handle_inputs.get("tools", [])
            memory_items = handle_inputs.get("memory", [])

            # FALLBACK: If no main items but input_data exists (Legacy Executor Support)
            if not main_items and input_data:
                # Wrap existing input_data as a main item
                main_items = [{"json": input_data}]

            # REQUIREMENT 9: Validation
            if not base_user_prompt and not main_items and not system_items:
                 return {"success": False, "error": "AI Agent requires a User Prompt or Main Input"}

            # REQUIREMENT 5: Conditional Merge Logic
            # Main Input: Concatenate into user prompt
            main_text = "\n".join([str(it.get("json", "")) for it in main_items if it.get("json")])
            full_user_prompt = base_user_prompt
            if main_text:
                full_user_prompt = f"{base_user_prompt}\n\nAdditional User Context:\n{main_text}" if base_user_prompt else main_text

            # System Input: Concatenate into system prompt
            system_text = "\n".join([str(it.get("json", "")) for it in system_items if it.get("json")])
            full_system_prompt = base_system_prompt
            if system_text:
                full_system_prompt = f"{base_system_prompt}\n\nAdditional System Instructions:\n{system_text}" if base_system_prompt else system_text

            # IDENTITY Injection
            full_system_prompt = f"IDENTITY: {agent_name}\n\n{full_system_prompt}"
            full_system_prompt += f"\n\nCURRENT TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Memory Input: Merge into conversation history (Requirement 5)
            # Expect memory_items to be objects with role/content
            history = []
            for m_item in memory_items:
                msg = m_item.get("json")
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    history.append(msg)
                elif isinstance(msg, list):
                    history.extend([m for m in msg if isinstance(m, dict) and "role" in m])

            # Tools Input: Structured JSON (Requirement 5)
            config_tools = cfg.get("enabled_tools", [])
            dynamic_tools = []
            for t_item in tool_items:
                tool_data = t_item.get("json")
                if isinstance(tool_data, str): dynamic_tools.append(tool_data)
                elif isinstance(tool_data, dict): dynamic_tools.append(tool_data.get("name") or str(tool_data))
            
            all_tools = list(set(config_tools + dynamic_tools))

            # --- 3. LLM EXECUTION ---
            credential_id = cfg.get("credential_id")
            if not credential_id:
                return {"success": False, "error": "Brain (Credential) required."}

            logger.info(f"🤖 Agent '{agent_name}' executing with {len(history)} history turns and {len(all_tools)} tools.")

            # Resolve final context dict
            exec_ctx = {}
            if hasattr(context, 'execution_context'): exec_ctx = context.execution_context
            elif isinstance(context, dict): exec_ctx = context.get('execution_context', context)

            model_res = UniversalAIEngine.run(
                user_prompt=full_user_prompt,
                system_prompt=full_system_prompt,
                response_mode="text",
                credential_id=credential_id,
                tools=all_tools,
                context=exec_ctx,
                chat_history=history
            )

            if not model_res.get("success"):
                err = model_res.get("error") or model_res.get("details") or "AI provider returned an error"
                raise NodeExecutionError(f"AI Agent failed: {err}")

            final_text = model_res.get("output", {}).get("text", "")
            
            # DEBUG LOGGING
            try:
                logger.critical(f"🤖 [DEBUG] Model Res: {json.dumps(model_res, default=str)}")
                logger.critical(f"🤖 [DEBUG] Final Text: '{final_text}'")
            except:
                pass

            # --- 4. OUTPUT STANDARDIZATION (Requirement 6) ---
            return {
                "success": True,
                "response": final_text, # Top-level alias
                "text": final_text,     # Top-level alias
                "content": final_text,  # Top-level alias
                "output": {
                    "response": final_text,
                    "text": final_text,
                    "content": final_text
                },
                "meta": model_res.get("output", {}).get("meta", {}),
                "conversation": history + [
                    {"role": "user", "content": full_user_prompt},
                    {"role": "assistant", "content": final_text}
                ]
            }

        except NodeExecutionError:
            raise
        except Exception as e:
            logger.error(f"Agent Execution Error: {e}", exc_info=True)
            raise NodeExecutionError(f"AI Agent crashed: {str(e)}")

    @classmethod
    def get_schema(cls):
        return {
            "credential_id": {
                "widget": "credential_select",
                "credential_type": "ai_provider",
                "label": "Brain (AI Provider)",
                "required": True
            },
            "user_prompt": {
                "widget": "textarea",
                "label": "User Prompt",
                "placeholder": "What should the agent do?",
                "required": True
            },
            "system_prompt": {
                "widget": "textarea",
                "label": "System Prompt",
                "default": "You are a helpful AI assistant."
            },
            "agent_name": {
                "widget": "text",
                "label": "Agent Name",
                "default": "AI Agent"
            }
        }
