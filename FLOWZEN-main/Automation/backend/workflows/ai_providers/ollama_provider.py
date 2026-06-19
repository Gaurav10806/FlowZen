
import requests
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class OllamaProvider:
    """
    Provider for interacting with local Ollama instance (Strict & Docker Safe).
    """

    def _request(self, method: str, original_base_url: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Internal helper to make requests with explicit prioritization:
        1. host.docker.internal (If localhost configured)
        2. 172.17.0.1 (Docker Bridge)
        3. Configured URL (Fallback/Remote)
        """
        clean_base = original_base_url.rstrip('/')
        # Clean suffix if present
        for suffix in ['/api/generate', '/api', '/v1']:
             if clean_base.endswith(suffix):
                 clean_base = clean_base[:-len(suffix)].rstrip('/')
        
        candidates = []
        docker_host = "http://host.docker.internal:11434"
        docker_bridge = "http://172.17.0.1:11434"
        
        # Docker Logic: If localhost is configured, it means the user intends "local machine".
        # Inside Docker, "localhost" is the container itself (wrong).
        # We must prioritize the host Gateway.
        if "localhost" in original_base_url or "127.0.0.1" in original_base_url:
            candidates.append(docker_host)
            candidates.append(docker_bridge)
            candidates.append(clean_base) # Keep original as last resort
        else:
            # Remote URL (e.g. 192.168.x.x) - Try it first
            candidates.append(clean_base)
            candidates.append(docker_host) # Fallback just in case
            
        last_error = None
        
        for base in candidates:
            url = f"{base}{endpoint}"
            try:
                # Short timeout for connection checks to fail fast
                current_timeout = kwargs.get('timeout', 10)
                # If we have multiple candidates, reduce connect timeout for the first ones to avoid hanging
                connect_timeout = 2 if len(candidates) > 1 and base != candidates[-1] else 5
                
                logger.debug(f"Ollama connecting: {url}")
                response = requests.request(method, url, **kwargs)
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Ollama connection failed for {url}: {e}")
                last_error = e
                continue
                
        if last_error:
            raise last_error
        raise requests.exceptions.ConnectionError("All Ollama connection attempts failed")

    def execute(self, prompt: str, system_prompt: str, credential_data: Dict[str, Any], model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Execute prompt against Ollama API (Strict Contract).
        """
        import time 
        start_time = time.time()
        
        try:
            # 1. Config Loading
            base_url = credential_data.get('base_url', 'http://localhost:11434')
            default_model = credential_data.get('default_model', 'llama3:8b')
            target_model = model if model else default_model
            
            # 2. LIVE MODEL VALIDATION (Strict Registry Check)
            # Before we even try to execute, we MUST know what is actually installed.
            # This prevents "gemma:4b" invention.
            installed_models = self.get_installed_models(base_url)
            
            # If we couldn't fetch models, we can't strictly validate, 
            # OR we should fail safe? 
            # If Ollama is down, get_installed_models returns [].
            if not installed_models:
                 return {
                     "success": False,
                     "error": "Ollama Unreachable or Empty Model List", 
                     "details": f"Could not fetch installed models from {base_url}. Ensure Ollama is running."
                 }
                 
            # STRICT CHECK: Is the target model actually installed?
            if target_model not in installed_models:
                # CRITICAL: Do NOT invent models. 
                return {
                    "success": False,
                    "error": f"Ollama model '{target_model}' not installed.",
                    "details": f"Available models: {', '.join(installed_models)}"
                }

            # Skip strict tag validation — llama3:latest and similar are valid

            temperature = float(credential_data.get('temperature', 0.7))
            max_tokens = int(credential_data.get('max_tokens', 2048))
            timeout = int(credential_data.get('timeout', 60))
            
            # 3. Prompt Construction (Merge System)
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            

            # 4. Payload Construction (Strict)
            payload = {
                "model": target_model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }

            # Add format if specified (e.g. "json")
            if kwargs.get('format'):
                 payload['format'] = kwargs['format']
            
            # 5. Request
            response = self._request('POST', base_url, "/api/generate", json=payload, timeout=timeout)
            response.raise_for_status()
            
            # 6. Response Parsing
            result = response.json()
            
            if result.get('done') is False:
                 logger.warning("Ollama returned done=False despite stream=False")
            
            response_text = result.get('response', '')
            execution_ms = (time.time() - start_time) * 1000
            
            # 7. Strict Output Format
            return {
                "success": True,
                "output": {
                    "text": response_text,
                    "json": None,
                    "model_used": target_model
                },
                "meta": {
                    "model_used": target_model
                },
                "error": None
            }
            
        except requests.exceptions.ReadTimeout:
            return {
                "success": False,
                "error": f"Ollama timed out after {timeout}s",
                "details": "Try increasing the timeout in credential settings."
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": "Ollama Unreachable",
                "details": f"Could not connect to {base_url} (or Docker fallbacks). Ensure Ollama is running and 'Ollama serve' is active."
            }
        except Exception as e:
            logger.error(f"Ollama Execution Error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "details": str(e)
            }

    def check_health(self, base_url: str) -> Dict[str, Any]:
        try:
            # We use get_installed_models logic implicitly
            models = self.get_installed_models(base_url)
            if models:
                 return {"success": True}
            else:
                 return {"success": False, "error": "No models found or unreachable"} 
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_models(self, base_url: str) -> list:
        # Legacy stub calling new method
        return self.get_installed_models(base_url)

    def get_installed_models(self, base_url: str) -> list:
        """Fetch live list of installed models from Ollama."""
        try:
            response = self._request('GET', base_url, "/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Strict: Only return full names
                return [m['name'] for m in data.get('models', [])]
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch installed models: {e}")
            return []
