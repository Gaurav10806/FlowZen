import requests
import json
from typing import Dict, Any, Optional
from .base import BaseAIAdapter

class OpenAIAdapter(BaseAIAdapter):
    """
    OpenAI API Adapter.
    Uses direct HTTP requests to avoid compilation dependencies.
    """
    
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                 temperature: float = 0.7, json_mode: bool = False) -> Dict[str, Any]:
        
        base_url = (self.base_url or self.DEFAULT_BASE_URL).rstrip('/')
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            
            # Parse JSON if requested
            json_output = None
            if json_mode:
                try:
                    json_output = json.loads(content)
                except:
                    pass # Keep text if parsing fails
            
            return {
                "output": {
                    "text": content,
                    "json": json_output
                },
                "usage": {
                    "tokens": usage.get('total_tokens')
                }
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"OpenAI API Error: {e.response.status_code} - {e.response.text}"
            raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"AI Request Failed: {str(e)}")
