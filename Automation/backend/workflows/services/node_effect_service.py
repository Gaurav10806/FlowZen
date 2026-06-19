"""
PHASE-1: NodeEffect service for preventing duplicate side effects.
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone

from ..models import NodeEffect, WorkflowExecution, NodeExecution, Tenant

logger = logging.getLogger(__name__)


class EffectAlreadyApplied(Exception):
    """Raised when an effect token already exists (duplicate prevention)."""
    pass


class NodeEffectService:
    """
    Service for managing node effects to prevent duplicate side effects.
    
    Effect tokens are computed as: sha256(execution_id + node_id + input_hash)
    This ensures that retries with the same input don't cause duplicate side effects.
    """
    
    @staticmethod
    def compute_effect_token(
        execution_id: str,
        node_id: str,
        input_data: Any,
        recipient: Optional[str] = None,
    ) -> str:
        """
        Compute effect token for a node execution.
        
        Args:
            execution_id: Workflow execution ID
            node_id: Node ID
            input_data: Input data (dict, list, or string) - will be JSON-serialized
            recipient: Optional recipient identifier (e.g., email address) for per-recipient effects
            
        Returns:
            SHA256 hash as hex string
        """
        # Normalize input data
        if isinstance(input_data, dict):
            # Sort keys for deterministic hashing
            normalized = json.dumps(input_data, sort_keys=True)
        elif isinstance(input_data, list):
            normalized = json.dumps(input_data, sort_keys=True)
        else:
            normalized = str(input_data)
        
        # Include recipient in hash if provided (for per-recipient effects)
        if recipient:
            token_data = f"{execution_id}:{node_id}:{normalized}:{recipient}"
        else:
            token_data = f"{execution_id}:{node_id}:{normalized}"
        
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    @staticmethod
    def check_effect_applied(
        tenant: Tenant,
        effect_token: str,
    ) -> bool:
        """
        Check if an effect token already exists (effect already applied).
        
        Args:
            tenant: Tenant instance
            effect_token: Effect token to check
            
        Returns:
            True if effect already applied, False otherwise
        """
        return NodeEffect.objects.filter(
            tenant=tenant,
            effect_token=effect_token
        ).exists()
    
    @staticmethod
    @transaction.atomic
    def record_effect(
        execution: WorkflowExecution,
        node_execution: NodeExecution,
        node_id: str,
        effect_token: str,
        effect_type: str,
        effect_data: Dict[str, Any],
    ) -> NodeEffect:
        """
        Record a node effect (idempotent - returns existing if token exists).
        
        Args:
            execution: Workflow execution
            node_execution: Node execution
            node_id: Node ID
            effect_token: Effect token
            effect_type: Type of effect (e.g., 'email_sent', 'http_request')
            effect_data: Effect details
            
        Returns:
            NodeEffect instance
            
        Raises:
            EffectAlreadyApplied: If effect token already exists (should not happen with atomic)
        """
        # Check if already exists (race condition protection)
        existing = NodeEffect.objects.filter(
            tenant=execution.tenant,
            effect_token=effect_token
        ).first()
        
        if existing:
            logger.info(f"Effect token {effect_token} already exists - effect already applied")
            return existing
        
        # Create new effect record
        effect = NodeEffect.objects.create(
            execution=execution,
            node_execution=node_execution,
            tenant=execution.tenant,
            node_id=node_id,
            effect_token=effect_token,
            effect_type=effect_type,
            effect_data=effect_data,
        )
        
        logger.info(f"Recorded effect {effect_type} for node {node_id} (token: {effect_token[:16]}...)")
        return effect
    
    @staticmethod
    def get_effect(
        tenant: Tenant,
        effect_token: str,
    ) -> Optional[NodeEffect]:
        """Get effect by token."""
        return NodeEffect.objects.filter(
            tenant=tenant,
            effect_token=effect_token
        ).first()
    
    @staticmethod
    def get_effects_for_execution(
        execution: WorkflowExecution,
        node_id: Optional[str] = None,
    ) -> List[NodeEffect]:
        """Get all effects for an execution (optionally filtered by node_id)."""
        qs = NodeEffect.objects.filter(execution=execution)
        if node_id:
            qs = qs.filter(node_id=node_id)
        return list(qs.order_by("created_at"))

