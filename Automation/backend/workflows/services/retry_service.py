"""
Retry service with configurable backoff strategies.
"""
import time
import random
from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BackoffStrategy(str, Enum):
    """Backoff strategy types."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    JITTER = "jitter"  # Exponential with jitter


class RetryService:
    """
    Service for calculating retry delays with various backoff strategies.
    """
    
    @staticmethod
    def calculate_delay(
        attempt: int,
        strategy: str = "exponential",
        initial_delay_ms: int = 1000,
        max_delay_ms: int = 30000,
        base: float = 2.0,
    ) -> float:
        """
        Calculate delay in seconds for a retry attempt.
        
        Args:
            attempt: Current attempt number (1-indexed)
            strategy: Backoff strategy (fixed, linear, exponential, jitter)
            initial_delay_ms: Initial delay in milliseconds
            max_delay_ms: Maximum delay in milliseconds
            base: Base for exponential backoff
            
        Returns:
            Delay in seconds
        """
        initial_delay_sec = initial_delay_ms / 1000.0
        max_delay_sec = max_delay_ms / 1000.0
        
        if strategy == BackoffStrategy.FIXED:
            delay = initial_delay_sec
        elif strategy == BackoffStrategy.LINEAR:
            delay = initial_delay_sec * attempt
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = initial_delay_sec * (base ** (attempt - 1))
        elif strategy == BackoffStrategy.JITTER:
            # Exponential with random jitter (full jitter)
            exponential_delay = initial_delay_sec * (base ** (attempt - 1))
            delay = random.uniform(0, exponential_delay)
        else:
            logger.warning(f"Unknown strategy {strategy}, using exponential")
            delay = initial_delay_sec * (base ** (attempt - 1))
        
        # Cap at max delay
        return min(delay, max_delay_sec)
    
    @staticmethod
    def should_retry(
        error: Exception,
        attempt: int,
        max_retries: int,
        retry_on: Optional[list] = None,
    ) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number
            max_retries: Maximum number of retries
            retry_on: List of error types/codes to retry on (e.g., ['5xx', 'timeout', 'ConnectionError'])
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt > max_retries:
            return False
        
        if not retry_on:
            # Default: retry on all errors
            return True
        
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        for retry_condition in retry_on:
            retry_condition_lower = retry_condition.lower()
            
            # Check HTTP status codes
            if retry_condition_lower.startswith('5'):
                if '500' in error_str or '502' in error_str or '503' in error_str or '504' in error_str:
                    return True
            
            # Check error types
            if retry_condition_lower in error_type.lower() or retry_condition_lower in error_str:
                return True
        
        return False
    
    @staticmethod
    def sleep_with_backoff(
        attempt: int,
        retry_policy: Dict[str, Any],
    ) -> None:
        """
        Sleep for calculated delay based on retry policy.
        
        Args:
            attempt: Current attempt number
            retry_policy: Dictionary with strategy, initial_delay_ms, max_delay_ms, base
        """
        strategy = retry_policy.get('backoff', 'exponential')
        initial_delay_ms = retry_policy.get('initial_delay_ms', 1000)
        max_delay_ms = retry_policy.get('max_delay_ms', 30000)
        base = retry_policy.get('base', 2.0)
        
        delay = RetryService.calculate_delay(
            attempt=attempt,
            strategy=strategy,
            initial_delay_ms=initial_delay_ms,
            max_delay_ms=max_delay_ms,
            base=base,
        )
        
        logger.info(f"Retry attempt {attempt}, sleeping {delay:.2f}s")
        time.sleep(delay)

