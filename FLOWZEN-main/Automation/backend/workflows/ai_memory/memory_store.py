
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MemoryStore:
    """
    Phase 11: AI Memory System.
    Stores and retrieves memory context for agents.
    For now, implemented as LocalFileMemory (JSON-based).
    Future: Vector DB (Chroma/Pinecone).
    """

    def __init__(self, brain_id: str, base_path: str = "./memory_data"):
        self.brain_id = brain_id
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        self.file_path = os.path.join(self.base_path, f"{brain_id}.json")
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    self.memories = json.load(f)
            except:
                self.memories = []
        else:
            self.memories = []

    def _save(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.memories, f, indent=2)

    def store(self, user_input: str, ai_output: str, metadata: Dict = None):
        """Stores an interaction."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "assistant": ai_output,
            "meta": metadata or {}
        }
        self.memories.append(entry)
        # Limit retention (simple FIFO)
        if len(self.memories) > 50: 
            self.memories.pop(0)
        self._save()

    def retrieve(self, query: str = None, limit: int = 5) -> List[Dict]:
        """
        Retrieves relevant context.
        Using simple 'recent' strategy for now.
        Future: Semantic search via embeddings.
        """
        # Return last N interactions
        return self.memories[-limit:]
    
    def format_for_prompt(self, memories: List[Dict]) -> str:
        """Formats memories for LLM insertion."""
        if not memories: return ""
        
        buffer = "\n\n=== RELEVANT MEMORY ===\n"
        for m in memories:
            buffer += f"User: {m['user']}\nAssistant: {m['assistant']}\n---\n"
        return buffer
