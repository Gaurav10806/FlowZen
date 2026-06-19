"""
Idempotency service using Redis for storing idempotency keys and results.
"""
import json
import hashlib
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class IdempotencyService:
    """
    Service for managing idempotency keys to prevent duplicate side effects.
    
    Uses Redis cache to store idempotency keys with TTL.
    """
    
    IDEMPOTENCY_KEY_PREFIX = "idempotency:"
    DEFAULT_TTL = 86400  # 24 hours
    
    @staticmethod
    def generate_key(
        execution_id: str,
        node_id: str,
        attempt: int = 1,
        stable: bool = True,
        tenant_id: str | None = None,
    ) -> str:
        """
        Generate idempotency key.
        
        Args:
            execution_id: Workflow execution ID
            node_id: Node ID
            attempt: Attempt number (use 1 for stable key across retries)
            stable: If True, use attempt=1 for stable key across retries
            
        Returns:
            Idempotency key string
        """
        if stable:
            # Stable key: same across retries
            key_data = f"{execution_id}:{node_id}:stable"
        else:
            # Per-attempt key
            key_data = f"{execution_id}:{node_id}:{attempt}"
        
        # Hash for consistent length
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()
        ns = tenant_id or "global"
        return f"{IdempotencyService.IDEMPOTENCY_KEY_PREFIX}{ns}:{key_hash}"
    
    @staticmethod
    def get_cached_result(key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached result for idempotency key.
        
        Args:
            key: Idempotency key
            
        Returns:
            Cached result dict or None
        """
        try:
            cached = cache.get(key)
            if cached:
                if isinstance(cached, str):
                    return json.loads(cached)
                return cached
            return None
        except Exception as e:
            logger.error(f"Failed to get idempotency cache: {e}")
            return None
    
    @staticmethod
    def set_cached_result(
        key: str,
        result: Dict[str, Any],
        ttl: int = None,
    ) -> bool:
        """
        Cache result for idempotency key.
        
        Args:
            key: Idempotency key
            result: Result dictionary to cache
            ttl: Time to live in seconds (default: 24 hours)
            
        Returns:
            True if cached successfully
        """
        try:
            if ttl is None:
                ttl = IdempotencyService.DEFAULT_TTL
            
            cache.set(key, json.dumps(result), timeout=ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set idempotency cache: {e}")
            return False
    
    @staticmethod
    def check_and_store(
        execution_id: str,
        node_id: str,
        attempt: int = 1,
        stable: bool = True,
        tenant_id: str | None = None,
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """
        Check if idempotency key exists, return cached result if found.
        Otherwise, return None and the key to use.
        
        Args:
            execution_id: Workflow execution ID
            node_id: Node ID
            attempt: Attempt number
            stable: Use stable key across retries
            
        Returns:
            Tuple of (cached_result_or_none, key_to_use)
        """
        key = IdempotencyService.generate_key(execution_id, node_id, attempt, stable, tenant_id=tenant_id)
        cached = IdempotencyService.get_cached_result(key)
        
        if cached:
            logger.info(f"Idempotency cache hit for {key}")
            return cached, key
        
        logger.debug(f"Idempotency cache miss for {key}")
        return None, key
    
    @staticmethod
    def store_result(
        key: str,
        result: Dict[str, Any],
        ttl: int = None,
    ) -> bool:
        """
        Store result for idempotency key.
        
        Args:
            key: Idempotency key
            result: Result to store
            ttl: Time to live in seconds
            
        Returns:
            True if stored successfully
        """
        return IdempotencyService.set_cached_result(key, result, ttl)

