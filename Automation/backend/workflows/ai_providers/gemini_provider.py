import os
import json
import logging
import requests
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiProvider:
    """
    Production-ready AI Provider for Google Gemini API.
    Exposes identical interface to OllamaProvider to ensure full compatibility.
    """

    MODEL_ALIASES = {
        "gemini-2.5-flash": "gemini-flash-latest",
        "gemini-2.5-pro": "gemini-pro-latest",
        "gemini-1.5-flash": "gemini-flash-latest",
        "gemini-1.5-pro": "gemini-pro-latest",
        "gemini-2.0-flash": "gemini-flash-latest",
        "gemini-2.5-flash-lite": "gemini-flash-lite-latest",
    }

    def __init__(self):
        self.default_model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
        self._session = requests.Session()

    def _normalize_model(self, raw_model: str) -> str:
        """Centralized Model Normalization Layer for Google Gemini API."""
        if not raw_model:
            raw_model = "gemini-flash-latest"
        clean = str(raw_model).replace("models/", "").strip()
        invalid_patterns = ["llama", "gemma", "mistral", "phi", "codellama"]
        if any(p in clean.lower() for p in invalid_patterns):
            normalized = "gemini-flash-latest"
        else:
            normalized = self.MODEL_ALIASES.get(clean, clean)
            
        if normalized in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
            normalized = "gemini-flash-latest"
        elif normalized in ["gemini-2.5-pro", "gemini-1.5-pro"]:
            normalized = "gemini-pro-latest"

        print(f"[MODEL TRACE] Raw='{raw_model}' -> Clean='{clean}' -> Normalized='{normalized}'")
        logger.info(f"Gemini Model Normalized: '{raw_model}' -> '{normalized}'")
        return normalized

    def _get_api_key(self, credential_data: Dict[str, Any]) -> Optional[str]:
        """Extract Gemini API Key from credential data or environment variable."""
        print(f"[KEY TRACE] GeminiProvider._get_api_key credential_data: {credential_data}")
        print(f"[KEY TRACE] gemini_api_key: {credential_data.get('gemini_api_key') if isinstance(credential_data, dict) else None}")
        print(f"[KEY TRACE] api_key: {credential_data.get('api_key') if isinstance(credential_data, dict) else None}")
        print(f"[KEY TRACE] os.environ['GEMINI_API_KEY']: {os.environ.get('GEMINI_API_KEY')}")

        key = (
            credential_data.get("gemini_api_key")
            or credential_data.get("api_key")
            or os.environ.get("GEMINI_API_KEY")
        )
        if key and isinstance(key, str):
            key = key.strip()

        selected_key_snippet = key[:10] if key else "None"
        print(f"[KEY TRACE] Selected key snippet (first 10 chars): {selected_key_snippet}")
        return key if key else None

    def execute(
        self,
        prompt: str,
        system_prompt: str,
        credential_data: Dict[str, Any],
        model: Optional[str] = None,
        format: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute prompt against Google Gemini API.
        """
        start_time = time.time()

        # 1. API Key Validation
        api_key = self._get_api_key(credential_data)
        if not api_key:
            return {
                "success": False,
                "error": "Gemini API Key Missing",
                "details": "GEMINI_API_KEY environment variable or credential key is required."
            }

        # 2. Model Selection & Centralized Normalization
        target_model = model or credential_data.get("gemini_model") or credential_data.get("default_model") or self.default_model
        print(f"[MODEL TRACE] [GeminiProvider.execute] input model='{model}', credential_data.gemini_model='{credential_data.get('gemini_model')}', target='{target_model}'")
        clean_model = self._normalize_model(target_model)

        # 3. Attempt Execution via Official SDK (or REST Fallback)
        try:
            raw_text = self._call_gemini_api(
                api_key=api_key,
                model=clean_model,
                prompt=prompt,
                system_prompt=system_prompt,
                response_format=format,
                **kwargs
            )

            # 4. Process Output & Extract JSON if requested
            parsed_json = {}
            if format == "json":
                try:
                    # Strip markdown code fencing ```json ... ``` if present
                    clean_str = raw_text.strip()
                    if clean_str.startswith("```json"):
                        clean_str = clean_str[7:]
                    elif clean_str.startswith("```"):
                        clean_str = clean_str[3:]
                    if clean_str.endswith("```"):
                        clean_str = clean_str[:-3]
                    clean_str = clean_str.strip()
                    
                    parsed_json = json.loads(clean_str)
                except Exception as json_err:
                    logger.warning(f"Gemini output parsing JSON failed: {json_err}. Raw text: {raw_text[:200]}")
                    parsed_json = {"raw_text": raw_text}

            logger.info(f"✅ Gemini execution succeeded using model {clean_model} in {int((time.time()-start_time)*1000)}ms")

            return {
                "success": True,
                "output": {
                    "text": raw_text,
                    "json": parsed_json
                }
            }

        except Exception as e:
            logger.error(f"❌ Gemini Execution Failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Gemini API Failure ({clean_model})",
                "details": str(e)
            }

    def _call_gemini_api(
        self,
        api_key: str,
        model: str,
        prompt: str,
        system_prompt: str,
        response_format: Optional[str] = None,
        **kwargs
    ) -> str:
        """Invokes Gemini using official SDK with REST fallback."""
        
        # Strategy A: Official google-genai / google.generativeai SDK
        sdk_errors = []
        try:
            import google.genai as genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            config_args = {}
            if system_prompt:
                config_args["system_instruction"] = system_prompt
            if response_format == "json":
                config_args["response_mime_type"] = "application/json"

            config = types.GenerateContentConfig(**config_args) if config_args else None
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            if hasattr(response, "text") and response.text:
                return response.text
        except Exception as e:
            sdk_errors.append(f"google-genai SDK: {e}")

        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)

            genai_kwargs = {}
            if system_prompt:
                genai_kwargs["system_instruction"] = system_prompt

            gm = genai_legacy.GenerativeModel(model_name=model, **genai_kwargs)
            gen_config = {}
            if response_format == "json":
                gen_config["response_mime_type"] = "application/json"

            response = gm.generate_content(
                prompt,
                generation_config=genai_legacy.types.GenerationConfig(**gen_config) if gen_config else None
            )
            if hasattr(response, "text") and response.text:
                return response.text
        except Exception as e:
            sdk_errors.append(f"google-generativeai SDK: {e}")

        # Strategy B: Direct REST API Fallback (Guarantees execution without SDK dependency issues)
        logger.info("Falling back to Gemini REST API endpoint...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        print(f"[FINAL GEMINI REST URL] https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key[:10]}***")
        
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }

        if system_prompt:
            payload["system_instruction"] = {
                "parts": [
                    {"text": system_prompt}
                ]
            }

        generation_config = {}
        if response_format == "json":
            generation_config["responseMimeType"] = "application/json"
        
        if generation_config:
            payload["generationConfig"] = generation_config

        headers = {"Content-Type": "application/json"}
        logger.warning(f"🔗 FINAL REST URL: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key[:12]}...")
        logger.warning(f"📦 FINAL JSON PAYLOAD: {payload}")
        logger.warning(f"HEADER: {headers}")

        resp = self._session.post(url, json=payload, headers=headers, timeout=60)
        
        logger.warning(f"📥 RESPONSE STATUS: {resp.status_code}")
        logger.warning(f"📥 FULL RESPONSE BODY: {resp.text}")

        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get("error", {}).get("message", resp.text)
            except Exception:
                pass
            raise RuntimeError(f"Gemini REST API Error ({resp.status_code}): {err_msg}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini REST API returned no response candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini REST API response contained no content parts.")

        return parts[0].get("text", "")

    def get_installed_models(self, base_url: Optional[str] = None) -> list:
        """Returns supported Gemini models for router discovery."""
        return [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash"
        ]
