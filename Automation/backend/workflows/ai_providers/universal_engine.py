import logging
import time
import json
import os
from typing import Dict, Any, List, Optional, Union

from workflows.ai_providers.model_router import select_model
from workflows.ai_providers.ollama_provider import OllamaProvider
from workflows.ai_services import OpenAIService
from workflows.models import Credential
from workflows.services.credential_encryption import CredentialEncryptionService
from workflows.ai_tools.tool_registry import ToolRegistry
from workflows.ai_policy.policy_engine import PolicyEngine, PolicyViolationError
from workflows.ai_memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)

class UniversalAIEngine:
    """
    Phase 5: Universal AI Abstraction Layer.
    Single entry point for all AI execution.
    """

    @classmethod
    def run(cls, *,
            user_prompt: str,
            system_prompt: str,
            response_mode: str,
            credential_id: str,
            tools: List[Dict] = None,
            context: Dict = None,
            json_schema: Dict = None,
            images: List[str] = None,
            chat_history: List[Dict] = None
            ) -> Dict[str, Any]:
        
        start_time = time.time()
        cache_key = None 
        
        # 1. Load & Decrypt Brain (Credential)
        try:
            cred = Credential.objects.get(id=credential_id)
            brain_config = cred.encrypted_data
            
            # Robust Decryption Logic
            if isinstance(brain_config, str):
                 try:
                     enc = CredentialEncryptionService()
                     brain_config = enc.decrypt_credential_str(brain_config)
                 except Exception as decrypt_err:
                     # logger.warning(f"Credential decryption failed, attempting raw JSON parse: {decrypt_err}")
                     try:
                         brain_config = json.loads(brain_config)
                     except:
                         # If both fail, re-raise original decryption error or a new one
                         raise ValueError(f"Decryption failed: {decrypt_err}")

        except Exception as e:
            return cls._error_result(f"Credential Error: {str(e)}", "credential_load_failed")

        # 2. Add Live Models to Config (if offline)
        if cred.type == 'ai_offline':
             try:
                 live = OllamaProvider().get_installed_models(brain_config.get('base_url'))
                 if live: brain_config['available_models'] = live
             except: pass

        # 3. Intelligent Routing
        decision = select_model(
            prompt=user_prompt,
            system_prompt=system_prompt,
            credential=brain_config,
            response_mode=response_mode
        )
        
        provider = decision['provider']
        model = decision['model']
        
        # --- PHASE 13: MULTI-AGENT ORCHESTRATION ---
        agents_cfg = brain_config.get('agents', {})
        is_agent_subcall = "You are a " in system_prompt and "Agent" in system_prompt
        
        if agents_cfg.get('enabled', False) and not is_agent_subcall:
             from workflows.ai_agents.orchestrator import AgentOrchestrator
             orch = AgentOrchestrator(cls, context)
             logger.info("🤖 Delegating to Multi-Agent Orchestrator")
             return orch.run_parallel(user_prompt, agents_cfg, credential_id)

        # --- PHASE 14: POLICY CHECK ---
        try:
             est_cost = PolicyEngine.estimate_cost(model, len(user_prompt) + len(system_prompt))
             PolicyEngine.check_policy(brain_config, user_prompt, system_prompt, est_cost)
        except PolicyViolationError as pve:
             logger.warning(f"⛔ Policy Violation: {pve}")
             return cls._error_result(str(pve), "policy_violation")
        except Exception as e:
             logger.error(f"Policy Check Error: {e}")
             pass
        
        # --- PHASE 11: MEMORY RETRIEVAL ---
        memory = None
        if brain_config.get('memory', {}).get('enabled', False):
             try:
                 memory = MemoryStore(brain_id=credential_id)
                 past_context = memory.retrieve(limit=5)
                 if past_context:
                      formatted_mem = memory.format_for_prompt(past_context)
                      system_prompt += f"\n\nRELEVANT MEMORY:\n{formatted_mem}"
                      logger.info(f"🧠 Injected {len(past_context)} memories.")
             except Exception as e:
                 logger.error(f"Memory Retrieval Failed: {e}")

        # 4. Execution Loop (with Fallback & Self-Healing & Memory)
        result_payload = None
        fallback_occured = False
        final_provider = provider
        final_model = model
        
        # --- PHASE 20: SELF-HEALING LOOP & RETRY ---
        # Robust Retry Policy: Default 3 retries
        max_retries = 3 if brain_config.get('retry_enabled', True) else 0
        attempts = 0
        
        while attempts <= max_retries:
            attempts += 1
            try:
                 # Exponential Backoff
                 if attempts > 1:
                     sleep_time = 2 ** (attempts - 1) # 2s, 4s, 8s
                     logger.info(f"⏳ Retry {attempts}/{max_retries+1} sleeping for {sleep_time}s")
                     time.sleep(sleep_time)

                 # Attempt Execution
                 result_payload = cls._execute_adapter(
                     provider if not fallback_occured else 'online', 
                     model if not fallback_occured else ('gpt-4o' if response_mode == 'json' else 'gpt-4o-mini'), 
                     user_prompt, 
                     system_prompt, 
                     response_mode, 
                     tools, 
                     brain_config,
                     json_schema=json_schema,
                     images=images,
                     chat_history=chat_history
                 )
                 break
                 
            except Exception as e:
                 logger.warning(f"⚠️ Attempt {attempts} failed: {e}")
                 
                 # Self-Healing for JSON
                 if "json" in str(e).lower() and attempts <= max_retries:
                      logger.info("🩹 Self-Healing: Retrying with Error Correction...")
                      user_prompt += f"\n\nPREVIOUS ERROR: {str(e)}\nFIX THE JSON."
                      continue
                 
                 # Fallback Logic
                 backup_key = brain_config.get('openai_backup_key')
                 can_fallback = (provider == 'offline' and backup_key and not fallback_occured)
                 
                 if can_fallback:
                      logger.info("🔄 Initiating Silent Fallback to OpenAI...")
                      fallback_occured = True
                      final_provider = 'openai'
                      final_model = 'gpt-4o' if response_mode == 'json' else 'gpt-4o-mini'
                      brain_config['api_key'] = backup_key
                      continue
                 
                 # Final Failure
                 if attempts > max_retries:
                      return cls._error_result(str(e), "execution_failed")
        
        # --- PHASE 11: MEMORY STORAGE ---
        if memory and result_payload:
             try:
                 final_text = result_payload.get('text') or json.dumps(result_payload.get('json', {}))
                 memory.store(user_prompt, final_text, metadata={"model": final_model})
             except Exception as e:
                 logger.error(f"Memory Save Failed: {e}")

        # 5. Output Construction
        latency = int((time.time() - start_time) * 1000)
        
        meta = {
            "provider": final_provider,
            "model_used": final_model,
            "latency_ms": latency,
            "fallback_used": fallback_occured,
            "confidence": "medium" if fallback_occured else "high",
            "router_reason": decision['reason'],
            "profile": decision['profile']
        }
        
        if result_payload is None:
            return cls._error_result("Execution failed - No result payload", "execution_failed")
            
        output_payload = {
            "text": result_payload.get('text', ''),
            "json": result_payload.get('json', {}),
            "response": result_payload.get('text', ''),
            "meta": meta
        }
        output_payload['output'] = {
            "text": output_payload['text'],
            "json": output_payload['json'],
            "response": output_payload['text']
        }
        
        return {
            "success": True,
            "output": output_payload
        }

    @staticmethod
    def _execute_adapter(provider, model, prompt, sys_prompt, mode, tools, config, json_schema=None, images=None, chat_history=None):
        """Adapter Dispatcher"""
        if provider == 'offline' or provider == 'ollama':
             res = OllamaProvider().execute(
                 prompt=prompt,
                 system_prompt=sys_prompt,
                 credential_data=config,
                 model=model,
                 format='json' if mode == 'json' else None
             )
             if not res['success']: raise Exception(res.get('error'))
             
             raw = res['output']
             return {
                 "text": raw.get('text', ''),
                 "json": raw.get('json', {})
             }
             
        elif provider == 'online' or provider == 'openai':
             api_key = config.get('api_key') or os.environ.get('OPENAI_API_KEY')
             if not api_key: raise Exception("No API Key for Online Provider")
             
             ai = OpenAIService(api_key=api_key)
             msgs = [{"role": "system", "content": sys_prompt}]
             
             # CHAT HISTORY SUPPORT
             if chat_history:
                 msgs.extend(chat_history)

             # VISION SUPPORT
             user_msg_content = []
             if images:
                 user_msg_content.append({"type": "text", "text": prompt})
                 for img_url in images:
                     user_msg_content.append({
                         "type": "image_url",
                         "image_url": {"url": img_url}
                     })
                 msgs.append({"role": "user", "content": user_msg_content})
             else:
                 msgs.append({"role": "user", "content": prompt})
             
             tool_defs = ToolRegistry.resolve(tools) if tools else None
             
             # JSON SCHEMA SUPPORT
             resp_fmt = None
             if mode == 'json':
                 if json_schema:
                     resp_fmt = {
                         "type": "json_schema",
                         "json_schema": {
                             "name": "workflow_output",
                             "schema": json_schema,
                             "strict": True
                         }
                     }
                 else:
                     resp_fmt = {"type": "json_object"}
             
             # Force JSON instruction if needed
             if mode == 'json' and not json_schema and "json" not in (prompt + sys_prompt).lower():
                  msgs[0]['content'] += " Respond in JSON."

             res = ai.chat(model=model, messages=msgs, tools=tool_defs, response_format=resp_fmt)
             content = res['message']['content']
             
             json_data = {}
             if mode == 'json':
                  try: json_data = json.loads(content)
                  except: pass
             
             return {
                 "text": content,
                 "json": json_data
             }
        
        else:
             raise Exception(f"Unknown provider: {provider}")

    @classmethod
    def _error_result(cls, msg, code):
        return {
            "success": False,
            "error": msg,
            "output": {
                "text": "",
                "json": {},
                "meta": {"error": msg, "code": code}
            }
        }
