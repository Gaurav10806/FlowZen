from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAIAdapter(ABC):
    """
    Abstract Base Class for AI Providers.
    Ensures all adapters implement a standard interface.
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                 temperature: float = 0.7, json_mode: bool = False) -> Dict[str, Any]:
        """
        Generate a response from the AI model.
        
        Args:
            prompt: User input prompt
            system_prompt: System context/instructions
            temperature: Creativity (0.0 - 2.0)
            json_mode: If True, enforce JSON output
            
        Returns:
             Dict with keys:
             - output: { text: str, json: dict|None }
             - usage: { tokens: int }
        """
        pass
