
import os
import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)

INVALID_MODELS = ["llama3", "gemma", "mistral", "phi", "llama", "llama2", "codellama"]

def select_model(
    *,
    prompt: str,
    system_prompt: str,
    credential: dict,
    response_mode: str
) -> Dict[str, str]:
    """
    Intelligently select the best Provider AND Model based on prompt analysis and Brain Profile.
    Returns Dict with keys: 'provider', 'model', 'reason', 'profile_used'
    """
    try:
        prompt_lower = str(prompt).lower() if prompt else ""
        system_lower = str(system_prompt).lower() if system_prompt else ""
        combined_text = prompt_lower + " " + system_lower
        
        # Brain Config
        profile = credential.get('profile', 'balanced') 
        openai_key = credential.get('openai_backup_key') or credential.get('api_key')
        
        # Offline Config
        available_offline = credential.get('available_models', [])
        default_offline = credential.get('default_model', 'llama3:8b')
        
        # Decide Provider First
        if cred_provider in ['ai_offline', 'offline', 'ollama']:
             provider = "offline"
             if not available_offline and openai_key:
                  provider = "online"
             selected_model = None
             reason = "heuristic"
        elif cred_provider in ['gemini', 'google'] or has_gemini_key or env_provider in ['gemini', 'google']:
             provider = "gemini"
             selected_model = credential.get('model') or credential.get('gemini_model') or getattr(settings, 'GEMINI_MODEL', 'gemini-flash-latest')
             reason = "gemini_provider"
             return {
                 "provider": provider,
                 "model": selected_model,
                 "reason": reason,
                 "profile": profile
             }
        else:
             provider = "offline"
             if not available_offline and openai_key:
                  provider = "online"
             selected_model = None
             reason = "heuristic"
        
        # --- OFFLINE SELECTION ---
        if provider == "offline":
             # (Reuse existing logic)
             def find_in_offline(partial):
                  return next((m for m in available_offline if partial in m and ':' in m), None)

             if profile == 'fast':
                  selected_model = find_in_offline('gemma') or find_in_offline('phi')
                  if selected_model: reason = "profile_fast"
             elif profile == 'accurate':
                  selected_model = find_in_offline('llama3')
                  if selected_model: reason = "profile_accurate"

             if not selected_model:
                  if response_mode == "json":
                       selected_model = find_in_offline('llama3') or find_in_offline('gemma')
                       reason = "json_mode"
                  elif any(k in combined_text for k in ['plan', 'analyze', 'debug']):
                       selected_model = find_in_offline('llama3')
                       reason = "intent_reasoning"
                  elif any(k in combined_text for k in ['write', 'email']):
                       selected_model = find_in_offline('gemma')
                       reason = "intent_creative"

             if not selected_model:
                  selected_model = default_offline
                  reason = "default_fallback"

             # Validation — ensure we have something usable
             if not selected_model:
                  found = next((m for m in available_offline if m), None)
                  selected_model = found if found else default_offline

        # --- ONLINE SELECTION ---
        else: # Online
             # Simple mapping for now
             if response_mode == 'json' or profile == 'accurate':
                  selected_model = "gpt-4o"
                  reason = "online_accurate"
             else:
                  selected_model = "gpt-4o-mini"
                  reason = "online_fast"

        logger.info(f"✅ Router: {provider} -> {selected_model} ({reason})")
        
        return {
            "provider": provider,
            "model": selected_model,
            "reason": reason,
            "profile": profile
        }

    except Exception as e:
        logger.error(f"Router Error: {e}")
        # Respect the credential provider even in error fallback
        fallback_prov = str(credential.get('provider') or credential.get('type') or '').lower().strip()
        if fallback_prov in ['gemini', 'google']:
            return {
                "provider": "gemini",
                "model": credential.get('model') or "gemini-flash-latest",
                "reason": "error_fallback_gemini",
                "profile": "unknown"
            }
        return {
            "provider": "offline",
            "model": "llama3:8b",
            "reason": "error_fallback",
            "profile": "unknown"
        }
