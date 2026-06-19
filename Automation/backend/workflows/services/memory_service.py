"""
Memory Service - Long-term and Short-term Memory for AI Agents

This module provides memory capabilities for AI agents including:
- Short-term memory (session/conversation context)
- Long-term memory (vector-based knowledge storage)
- User-isolated memory with security boundaries
"""

import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# Vector database imports (would be actual imports in production)
# import faiss
# import chromadb
# from sentence_transformers import SentenceTransformer

from ..models import Tenant
from ..security_validators import PayloadSecurityValidator


logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory storage."""
    SHORT_TERM = "short_term"      # Session-based, temporary
    LONG_TERM = "long_term"        # Persistent, vector-based
    EPISODIC = "episodic"          # Event-based memories
    SEMANTIC = "semantic"          # Factual knowledge
    PROCEDURAL = "procedural"      # How-to knowledge


@dataclass
class MemoryEntry:
    """Represents a single memory entry."""
    memory_id: str
    memory_type: MemoryType
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]]
    user_id: str
    tenant_id: str
    session_id: Optional[str]
    created_at: str
    accessed_at: str
    access_count: int
    importance_score: float
    tags: List[str]


@dataclass
class MemoryQuery:
    """Represents a memory query."""
    query_text: str
    memory_types: List[MemoryType]
    user_id: str
    tenant_id: str
    session_id: Optional[str]
    max_results: int
    similarity_threshold: float
    time_range: Optional[Dict[str, str]]


@dataclass
class MemorySearchResult:
    """Represents memory search results."""
    memories: List[MemoryEntry]
    total_found: int
    search_time_ms: int
    query_embedding: Optional[List[float]]


class MemoryService:
    """
    Memory Service for AI Agents
    
    Provides both short-term (session) and long-term (vector) memory capabilities
    with user isolation, security controls, and efficient retrieval.
    """
    
    def __init__(self):
        self.safety_validator = PayloadSecurityValidator()
        
        # Memory storage (in production, these would be actual databases)
        self.short_term_memory: Dict[str, List[MemoryEntry]] = {}  # session_id -> memories
        self.long_term_memory: List[MemoryEntry] = []  # Would be vector database
        
        # Vector database simulation (would be actual vector DB in production)
        self.vector_index = None  # Would be FAISS index or ChromaDB collection
        self.embedding_model = None  # Would be SentenceTransformer model
        
        # Memory configuration
        self.max_short_term_memories = 100
        self.max_long_term_memories_per_user = 10000
        self.embedding_dimension = 384  # Typical for sentence transformers
        
        # Initialize vector components (simulated)
        self._initialize_vector_components()
    
    def save_memory(self, content: str, memory_type: MemoryType, metadata: Dict[str, Any],
                   user_id: str, tenant_id: str, session_id: Optional[str] = None,
                   importance_score: float = 0.5, tags: List[str] = None) -> str:
        """
        Save a memory entry.
        
        Args:
            content: Memory content (text)
            memory_type: Type of memory
            metadata: Additional metadata
            user_id: User ID for isolation
            tenant_id: Tenant ID for isolation
            session_id: Session ID for short-term memory
            importance_score: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            
        Returns:
            Memory ID
        """
        # Validate and sanitize content
        validated_metadata = self.safety_validator.validate_json_payload(metadata)
        
        # Generate memory ID
        memory_id = str(uuid.uuid4())
        
        # Generate embedding for content
        embedding = self._generate_embedding(content)
        
        # Create memory entry
        memory_entry = MemoryEntry(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            metadata=validated_metadata,
            embedding=embedding,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            created_at=datetime.utcnow().isoformat(),
            accessed_at=datetime.utcnow().isoformat(),
            access_count=0,
            importance_score=importance_score,
            tags=tags or []
        )
        
        # Store based on memory type
        if memory_type == MemoryType.SHORT_TERM:
            self._save_short_term_memory(memory_entry)
        else:
            self._save_long_term_memory(memory_entry)
        
        logger.info(f"Saved memory: {memory_id} (type: {memory_type.value}, user: {user_id})")
        
        return memory_id
    
    def search_memory(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Search memory using semantic similarity.
        
        Args:
            query: Memory query parameters
            
        Returns:
            Search results with relevant memories
        """
        start_time = datetime.utcnow()
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query.query_text)
        
        # Search in different memory types
        all_memories = []
        
        # Search short-term memory
        if MemoryType.SHORT_TERM in query.memory_types:
            short_term_results = self._search_short_term_memory(query, query_embedding)
            all_memories.extend(short_term_results)
        
        # Search long-term memory
        long_term_types = [mt for mt in query.memory_types if mt != MemoryType.SHORT_TERM]
        if long_term_types:
            long_term_results = self._search_long_term_memory(query, query_embedding, long_term_types)
            all_memories.extend(long_term_results)
        
        # Sort by similarity and importance
        scored_memories = []
        for memory in all_memories:
            similarity = self._calculate_similarity(query_embedding, memory.embedding)
            if similarity >= query.similarity_threshold:
                # Combine similarity and importance for final score
                final_score = (similarity * 0.7) + (memory.importance_score * 0.3)
                scored_memories.append((memory, final_score))
        
        # Sort by score and limit results
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        top_memories = [memory for memory, score in scored_memories[:query.max_results]]
        
        # Update access statistics
        for memory in top_memories:
            memory.accessed_at = datetime.utcnow().isoformat()
            memory.access_count += 1
        
        # Calculate search time
        end_time = datetime.utcnow()
        search_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return MemorySearchResult(
            memories=top_memories,
            total_found=len(scored_memories),
            search_time_ms=search_time_ms,
            query_embedding=query_embedding
        )
    
    def load_context(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load relevant memory context for an agent.
        
        Args:
            input_data: Current input data
            context: Execution context
            
        Returns:
            Memory context for the agent
        """
        user_id = context.get('user_id', '')
        tenant_id = context.get('tenant_id', '')
        session_id = context.get('session_id', '')
        
        # Extract query from input data
        query_text = self._extract_query_from_input(input_data)
        
        if not query_text:
            return {}
        
        # Create memory query
        memory_query = MemoryQuery(
            query_text=query_text,
            memory_types=[MemoryType.SHORT_TERM, MemoryType.LONG_TERM, MemoryType.SEMANTIC],
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            max_results=10,
            similarity_threshold=0.7,
            time_range=None
        )
        
        # Search for relevant memories
        search_result = self.search_memory(memory_query)
        
        # Format context
        memory_context = {
            'relevant_memories': [
                {
                    'content': memory.content,
                    'metadata': memory.metadata,
                    'created_at': memory.created_at,
                    'importance': memory.importance_score,
                    'tags': memory.tags
                }
                for memory in search_result.memories
            ],
            'conversation_history': self._get_conversation_history(session_id, user_id),
            'user_preferences': self._get_user_preferences(user_id, tenant_id),
            'search_stats': {
                'total_found': search_result.total_found,
                'search_time_ms': search_result.search_time_ms
            }
        }
        
        return memory_context
    
    def save_context(self, result: Dict[str, Any], context: Dict[str, Any]) -> None:
        """
        Save agent execution results to memory.
        
        Args:
            result: Agent execution results
            context: Execution context
        """
        user_id = context.get('user_id', '')
        tenant_id = context.get('tenant_id', '')
        session_id = context.get('session_id', '')
        
        # Save conversation turn
        if 'final_answer' in result:
            self.save_memory(
                content=result['final_answer'],
                memory_type=MemoryType.SHORT_TERM,
                metadata={
                    'type': 'agent_response',
                    'execution_id': result.get('execution_id', ''),
                    'reasoning_mode': result.get('reasoning_mode', ''),
                    'tools_used': result.get('tools_used', [])
                },
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                importance_score=0.6,
                tags=['agent_response', 'conversation']
            )
        
        # Save important insights to long-term memory
        if result.get('confidence', 0) > 0.8 and 'agent_output' in result:
            self.save_memory(
                content=json.dumps(result['agent_output']),
                memory_type=MemoryType.SEMANTIC,
                metadata={
                    'type': 'high_confidence_result',
                    'execution_id': result.get('execution_id', ''),
                    'confidence': result.get('confidence', 0)
                },
                user_id=user_id,
                tenant_id=tenant_id,
                importance_score=result.get('confidence', 0.8),
                tags=['high_confidence', 'semantic_knowledge']
            )
    
    def get_memory_stats(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Get memory usage statistics.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            
        Returns:
            Memory statistics
        """
        # Count memories by type
        user_memories = [
            memory for memory in self.long_term_memory
            if memory.user_id == user_id and memory.tenant_id == tenant_id
        ]
        
        memory_counts = {}
        for memory_type in MemoryType:
            memory_counts[memory_type.value] = len([
                m for m in user_memories if m.memory_type == memory_type
            ])
        
        # Calculate storage usage
        total_content_size = sum(len(m.content) for m in user_memories)
        
        # Get session counts
        session_memories = {}
        for session_id, memories in self.short_term_memory.items():
            user_session_memories = [
                m for m in memories if m.user_id == user_id and m.tenant_id == tenant_id
            ]
            if user_session_memories:
                session_memories[session_id] = len(user_session_memories)
        
        return {
            'total_memories': len(user_memories),
            'memory_by_type': memory_counts,
            'total_content_size_bytes': total_content_size,
            'active_sessions': len(session_memories),
            'session_memory_counts': session_memories,
            'most_accessed_memories': sorted(
                user_memories, key=lambda m: m.access_count, reverse=True
            )[:5]
        }
    
    def cleanup_old_memories(self, user_id: str, tenant_id: str, 
                           max_age_days: int = 30) -> Dict[str, int]:
        """
        Clean up old memories based on age and importance.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            max_age_days: Maximum age for memories
            
        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        cutoff_str = cutoff_date.isoformat()
        
        # Clean up short-term memory
        short_term_cleaned = 0
        for session_id, memories in list(self.short_term_memory.items()):
            old_memories = [
                m for m in memories
                if m.user_id == user_id and m.tenant_id == tenant_id and m.created_at < cutoff_str
            ]
            
            for memory in old_memories:
                memories.remove(memory)
                short_term_cleaned += 1
            
            # Remove empty sessions
            if not memories:
                del self.short_term_memory[session_id]
        
        # Clean up long-term memory (keep important memories longer)
        long_term_cleaned = 0
        memories_to_remove = []
        
        for memory in self.long_term_memory:
            if (memory.user_id == user_id and memory.tenant_id == tenant_id and
                memory.created_at < cutoff_str and memory.importance_score < 0.7):
                memories_to_remove.append(memory)
                long_term_cleaned += 1
        
        for memory in memories_to_remove:
            self.long_term_memory.remove(memory)
        
        logger.info(f"Memory cleanup for user {user_id}: "
                   f"{short_term_cleaned} short-term, {long_term_cleaned} long-term")
        
        return {
            'short_term_cleaned': short_term_cleaned,
            'long_term_cleaned': long_term_cleaned,
            'total_cleaned': short_term_cleaned + long_term_cleaned
        }
    
    def _initialize_vector_components(self) -> None:
        """Initialize vector database components (simulated)."""
        # In production, this would initialize:
        # - FAISS index or ChromaDB collection
        # - SentenceTransformer model
        # - Vector database connection
        
        logger.info("Vector components initialized (simulated)")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (simulated)."""
        # In production, this would use SentenceTransformer
        # embedding = self.embedding_model.encode(text)
        
        # Simulated embedding (hash-based for consistency)
        text_hash = hashlib.md5(text.encode()).hexdigest()
        # Convert hash to float values
        embedding = [float(int(text_hash[i:i+2], 16)) / 255.0 for i in range(0, min(len(text_hash), 32), 2)]
        
        # Pad or truncate to embedding dimension
        while len(embedding) < self.embedding_dimension:
            embedding.extend(embedding[:self.embedding_dimension - len(embedding)])
        
        return embedding[:self.embedding_dimension]
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        if not embedding1 or not embedding2:
            return 0.0
        
        # Cosine similarity calculation
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _save_short_term_memory(self, memory_entry: MemoryEntry) -> None:
        """Save memory to short-term storage."""
        session_id = memory_entry.session_id or 'default'
        
        if session_id not in self.short_term_memory:
            self.short_term_memory[session_id] = []
        
        self.short_term_memory[session_id].append(memory_entry)
        
        # Limit short-term memory size
        if len(self.short_term_memory[session_id]) > self.max_short_term_memories:
            # Remove oldest memories
            self.short_term_memory[session_id] = self.short_term_memory[session_id][-self.max_short_term_memories:]
    
    def _save_long_term_memory(self, memory_entry: MemoryEntry) -> None:
        """Save memory to long-term storage."""
        self.long_term_memory.append(memory_entry)
        
        # In production, this would:
        # 1. Save to vector database
        # 2. Update FAISS index
        # 3. Save metadata to relational database
    
    def _search_short_term_memory(self, query: MemoryQuery, query_embedding: List[float]) -> List[MemoryEntry]:
        """Search short-term memory."""
        results = []
        
        session_id = query.session_id or 'default'
        if session_id in self.short_term_memory:
            for memory in self.short_term_memory[session_id]:
                if (memory.user_id == query.user_id and 
                    memory.tenant_id == query.tenant_id):
                    results.append(memory)
        
        return results
    
    def _search_long_term_memory(self, query: MemoryQuery, query_embedding: List[float], 
                                memory_types: List[MemoryType]) -> List[MemoryEntry]:
        """Search long-term memory."""
        results = []
        
        for memory in self.long_term_memory:
            if (memory.user_id == query.user_id and 
                memory.tenant_id == query.tenant_id and
                memory.memory_type in memory_types):
                results.append(memory)
        
        return results
    
    def _extract_query_from_input(self, input_data: Dict[str, Any]) -> str:
        """Extract query text from input data."""
        # Try different common fields
        for field in ['message', 'query', 'text', 'content', 'input']:
            if field in input_data and isinstance(input_data[field], str):
                return input_data[field]
        
        # Fallback to JSON string
        return json.dumps(input_data)
    
    def _get_conversation_history(self, session_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for session."""
        if not session_id or session_id not in self.short_term_memory:
            return []
        
        conversation = []
        for memory in self.short_term_memory[session_id]:
            if (memory.user_id == user_id and 
                memory.metadata.get('type') in ['user_message', 'agent_response']):
                conversation.append({
                    'content': memory.content,
                    'type': memory.metadata.get('type'),
                    'timestamp': memory.created_at
                })
        
        # Sort by timestamp
        conversation.sort(key=lambda x: x['timestamp'])
        
        return conversation[-20:]  # Last 20 messages
    
    def _get_user_preferences(self, user_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get user preferences from memory."""
        # Search for preference memories
        preference_memories = [
            memory for memory in self.long_term_memory
            if (memory.user_id == user_id and memory.tenant_id == tenant_id and
                'preference' in memory.tags)
        ]
        
        preferences = {}
        for memory in preference_memories:
            try:
                pref_data = json.loads(memory.content)
                preferences.update(pref_data)
            except json.JSONDecodeError:
                continue
        
        return preferences