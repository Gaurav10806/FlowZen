import logging
import time
import json
import os
from typing import Dict, Any, List, Optional, Union
from django.conf import settings

from workflows.ai_providers.model_router import select_model
from workflows.ai_providers.ollama_provider import OllamaProvider
from workflows.ai_providers.gemini_provider import GeminiProvider
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
        
        print("ENTER UniversalAIEngine.run")
        start_time = time.time()
        cache_key = None 
        
        logger.info("--------------------------------")
        logger.info(f"UniversalAIEngine.run CALLED")
        logger.info(f"credential_id: {credential_id}")
        
        # 1. Load & Decrypt Brain (Credential)
        try:
            cred = None
            if credential_id and str(credential_id).lower() != "default":
                try:
                    cred = Credential.objects.filter(id=credential_id).first()
                except Exception as ex:
                    logger.warning(f"Credential lookup failed for {credential_id}: {ex}")
                    cred = None

            if not cred:
                cred = cls.get_or_create_default_credential()

            brain_config = getattr(cred, "encrypted_data", {})
            
            # Robust Decryption Logic
            if isinstance(brain_config, str):
                 try:
                     enc = CredentialEncryptionService()
                     brain_config = enc.decrypt_credential_str(brain_config)
                 except Exception as decrypt_err:
                     try:
                         brain_config = json.loads(brain_config)
                     except Exception:
                         brain_config = {}
            elif not isinstance(brain_config, dict):
                 brain_config = {}

            if brain_config.get('simulation_mode'):
                 return {
                     "output": {
                         "text": "SIMULATED RESPONSE",
                         "meta": {"provider": "simulated", "model": "simulated-v1"}
                     }
                 }

            if cred:
                cred_prov = getattr(cred, 'provider', None) or getattr(cred, 'type', None) or 'gemini'
                brain_config['provider'] = cred_prov
                brain_config['credential_id'] = str(cred.id)
                if not brain_config.get('api_key') and cred_prov == 'gemini':
                    brain_config['api_key'] = os.environ.get("GEMINI_API_KEY", "")

        except Exception as e:
            return cls._error_result(f"Credential Error: {str(e)}", "credential_load_failed")

        # 2. Add Live Models to Config (if offline)
        try:
            ai_provider_env = getattr(settings, "AI_PROVIDER", os.environ.get("AI_PROVIDER", "ollama")).lower()
        except Exception:
            ai_provider_env = os.environ.get("AI_PROVIDER", "ollama").lower()
        if cred.type == 'ai_offline':
             try:
                 if ai_provider_env == 'gemini':
                     brain_config['available_models'] = GeminiProvider().get_installed_models()
                 else:
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

        api_key_val = brain_config.get("api_key") or os.environ.get("GEMINI_API_KEY", "")
        key_snippet = f"api_key starts with {api_key_val[:2]}" if api_key_val else "api_key=None"
        resolved_cred_id = str(cred.id) if cred else str(credential_id)

        print("=================================")
        print(f"provider={provider}")
        print(f"credential_id={resolved_cred_id}")
        print(f"{key_snippet}")
        print(f"model={model}")
        print("=================================")

        logger.info("=================================")
        logger.info(f"provider={provider}")
        logger.info(f"credential_id={resolved_cred_id}")
        logger.info(f"{key_snippet}")
        logger.info(f"model={model}")
        logger.info("=================================")
        
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

        # 4. Execution Loop (with Retry — NO cross-provider fallback)
        result_payload = None
        final_provider = provider
        final_model = model
        
        # Robust Retry Policy: Default 3 retries
        max_retries = 3 if brain_config.get('retry_enabled', True) else 0
        attempts = 0
        
        while attempts <= max_retries:
            attempts += 1
            try:
                 # Exponential Backoff
                 if attempts > 1:
                     sleep_time = 2 ** (attempts - 1) # 2s, 4s, 8s
                     logger.info(f"Retry {attempts}/{max_retries+1} sleeping for {sleep_time}s")
                     time.sleep(sleep_time)

                 print(f"[ADAPTER DISPATCH] provider={provider}, model={model}, cred_provider={brain_config.get('provider')}")

                 # Always use the SAME provider and model — never silently switch
                 result_payload = cls._execute_adapter(
                     provider, 
                     model, 
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
                 logger.warning(f"Attempt {attempts} failed: {e}")
                 
                 # Self-Healing for JSON
                 if "json" in str(e).lower() and attempts <= max_retries:
                      logger.info("Self-Healing: Retrying with Error Correction...")
                      user_prompt += f"\n\nPREVIOUS ERROR: {str(e)}\nFIX THE JSON."
                      continue
                 
                 # Final Failure — NO silent fallback to OpenAI
                 if attempts > max_retries:
                      logger.warning(f"Execution failed after {attempts} attempts. Error: {e}")
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
            "fallback_used": False,
            "confidence": "high",
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
        """Adapter Dispatcher — credential provider is the single source of truth."""
        cred_prov = str(config.get('provider') or config.get('type') or provider).lower().strip()
        print(f"[_execute_adapter] provider={provider}, cred_prov={cred_prov}, model={model}")
        if cred_prov in ['gemini', 'google'] or provider == 'gemini':
             print(f"[_execute_adapter] DISPATCHING TO: GeminiProvider")
             print(f"[CREDENTIAL DATA BEFORE GEMINI EXECUTE] {config}")
             res = GeminiProvider().execute(
                 prompt=prompt,
                 system_prompt=sys_prompt,
                 credential_data=config,
                 model=model,
                 format='json' if mode == 'json' else None
             )
             if not res['success']:
                 err_msg = res.get('error') or "Gemini execution failed"
                 if res.get('details'):
                     err_msg += f" - {res.get('details')}"
                 raise Exception(err_msg)
             
             raw = res['output']
             return {
                 "text": raw.get('text', ''),
                 "json": raw.get('json', {})
             }

        elif cred_prov in ['ollama', 'ollama_local', 'ai_offline', 'offline'] or provider in ['offline', 'ollama']:
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
    def get_or_create_default_credential(cls) -> Credential:
        """
        Retrieves or auto-provisions a default Credential for the active system AI provider.
        Prevents execution failure when environment-driven AI_PROVIDER is used without explicit credential selection.
        """
        try:
            provider = getattr(settings, "AI_PROVIDER", os.environ.get("AI_PROVIDER", "gemini")).lower().strip()
        except Exception:
            provider = os.environ.get("AI_PROVIDER", "gemini").lower().strip()

        if provider == "gemini":
            possible_types = ["gemini", "google"]
        else:
            possible_types = ["ollama", "ollama_local", "ai_offline"]

        cred = Credential.objects.filter(type__in=possible_types).order_by("-created_at").first()
        if cred:
            return cred

        system_user = None
        try:
            from django.contrib.auth.models import User
            system_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not system_user:
                system_user, _ = User.objects.get_or_create(
                    username="system_ai_user",
                    defaults={"email": "system@flowzen.local", "is_active": True}
                )
        except Exception:
            pass

        cred_name = f"Default System {provider.capitalize()} Provider"
        gemini_key = os.environ.get("GEMINI_API_KEY", "")

        cred_data = {
            "provider": provider,
            "api_key": gemini_key if provider == "gemini" else "",
            "model": os.environ.get("GEMINI_MODEL", "gemini-flash-latest") if provider == "gemini" else os.environ.get("OLLAMA_MODEL", "llama3:8b")
        }
        cred, _ = Credential.objects.get_or_create(
            name=cred_name,
            defaults={
                "type": provider if provider in ["gemini", "ollama"] else "ai_offline",
                "provider": provider,
                "encrypted_data": cred_data,
                "owner": system_user
            }
        )
        return cred

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
