from typing import Dict, Any, Optional
from .adapters.openai import OpenAIAdapter

class AIService:
    """
    Orchestrator for AI interactions.
    Handles credential loading and adapter selection.
    """
    
    @staticmethod
    def execute(credential_data: Dict[str, Any], prompt: str, 
                system_prompt: Optional[str] = None, 
                temperature: float = 0.7, 
                json_mode: bool = False,
                provider: str = 'openai',
                model: str = 'gpt-4o-mini') -> Dict[str, Any]:
        """
        Execute AI generation securely.
        
        Args:
            credential_data: Decrypted credential data dictionary
            prompt: User prompt
            ...
        
        Returns:
            Standard response Dict
        """
        
        # 1. Select Adapter
        adapter = None
        
        api_key = credential_data.get('api_key')
        base_url = credential_data.get('base_url')
        
        if not api_key:
            return {
                "success": False,
                "error": "Missing API Key in credentials",
                "output": {"text": "Credential Error", "json": None}
            }
            
        if provider == 'openai':
            adapter = OpenAIAdapter(api_key=api_key, base_url=base_url, model=model)
        else:
            return {
                "success": False,
                "error": f"Unsupported provider: {provider}",
                "output": {"text": "Configuration Error", "json": None}
            }
            
        # 2. Execute
        try:
            result = adapter.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                json_mode=json_mode
            )
            
            return {
                "success": True,
                "output": result['output'],
                "usage": result['usage'],
                "error": None
            }
            
        except Exception as e:
            # Graceful Failure
            return {
                "success": False,
                "error": str(e),
                "output": {
                    "text": f"AI Generation Failed: {str(e)}", 
                    "json": None
                }
            }
