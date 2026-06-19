
import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PolicyViolationError(Exception):
    """Raised when an AI request violates a governance policy."""
    pass

class PolicyEngine:
    """
    Phase 14: AI Governance & Safety Layer.
    Enforces cost limits, content filtering, and usage policies.
    """

    @classmethod
    def check_policy(cls, credential_config: Dict, prompt: str, system_prompt: str, estimated_cost: float = 0.0):
        """
        Validates the request against the governance policy defined in the Brain (credential).
        Raises PolicyViolationError if blocked.
        """
        
        # 1. Load Policy Config (defaults to permissive)
        policy = credential_config.get('governance', {})
        
        # 2. Check Allowed Intents (Content Filtering)
        disallowed = policy.get('disallowed_patterns', [])
        if disallowed:
            combined_text = (prompt + " " + system_prompt).lower()
            for pattern in disallowed:
                if re.search(pattern, combined_text):
                    logger.warning(f"🛡️ Policy Blocked: Content matched disallowed pattern '{pattern}'")
                    raise PolicyViolationError(f"Request blocked by content policy: '{pattern}' detected.")

        # 3. Check Max Cost (Guardrail)
        max_cost = policy.get('max_cost_per_run')
        if max_cost is not None and estimated_cost > float(max_cost):
             logger.warning(f"💰 Policy Blocked: Estimated cost ${estimated_cost} > Limit ${max_cost}")
             raise PolicyViolationError(f"Estimated cost ${estimated_cost} exceeds run limit of ${max_cost}")

        # 4. Check PII (Basic Placeholder)
        if policy.get('filter_pii', False):
             # Simple regex for Credit Cards or SSN (Proof of concept)
             # In production, use Presidio or similar
             if re.search(r'\b\d{3}-\d{2}-\d{4}\b', prompt): # SSN-like
                  raise PolicyViolationError("Request blocked: Potential PII (SSN) detected.")

        # 5. Global Token Limit (if applicable)
        max_tokens = policy.get('max_tokens_per_execution')
        # We can't strictly check input tokens without tokenizer, but we can check char count approx
        if max_tokens:
             approx_tokens = len(prompt) / 4
             if approx_tokens > max_tokens:
                  raise PolicyViolationError(f"Input length ({int(approx_tokens)} toks) exceeds limit ({max_tokens}).")

        return True

    @classmethod
    def estimate_cost(cls, model: str, prompt_len: int) -> float:
        """
        Rough cost estimation used for pre-flight checks.
        """
        # Pricing Table (Approximate)
        pricing = {
             'gpt-4o': 5.00 / 1_000_000, # $5 per 1M input tokens
             'gpt-4o-mini': 0.15 / 1_000_000,
             'llama3': 0, # Offline is free
             'gemma': 0
        }
        
        # Default to highest if unknown online model to be safe
        rate = pricing.get(model, 0.0)
        if model.startswith('gpt') and model not in pricing:
             rate = 10.0 / 1_000_000
             
        # Tokens approx
        tokens = prompt_len / 4
        return tokens * rate
