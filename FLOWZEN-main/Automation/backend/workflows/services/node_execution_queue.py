"""
Node execution queue service for managing READY state and concurrent execution.
"""
import logging
from typing import List, Dict, Set, Optional
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from ..models import NodeExecution, WorkflowExecution

logger = logging.getLogger(__name__)


class NodeExecutionQueue:
    """
    Manages node execution queue with READY state and Redis locks.
    
    Similar to n8n's execution queue system.
    """
    
    LOCK_PREFIX = "node_exec_lock:"
    LOCK_TTL = 300  # 5 minutes
    RATE_PREFIX = "node_rate:"
    CAP_TENANT_PREFIX = "cap:tenant:"
    CAP_WORKFLOW_PREFIX = "cap:workflow:"
    CAP_GLOBAL_KEY = "cap:global"
    
    @staticmethod
    def mark_node_ready(
        execution: WorkflowExecution,
        node_id: str,
        node_config: Dict,
    ) -> Optional[NodeExecution]:
        """
        Mark a node as READY to execute (all dependencies met).
        
        Args:
            execution: Workflow execution
            node_id: Node ID from graph
            node_config: Node configuration from graph
            
        Returns:
            NodeExecution instance if created/marked ready, None if already exists
        """
        with transaction.atomic():
            # Check if already exists
            existing = NodeExecution.objects.filter(
                workflow_execution=execution,
                graph_node_id=node_id
            ).first()
            
            if existing:
                if existing.status == "ready":
                    return existing  # Already ready
                elif existing.status in ["completed", "success"]:
                    return existing  # Already completed
                elif existing.status == "failed":
                    # Can retry if retry policy allows
                    return existing
            
            # Create or update NodeExecution
            if existing:
                existing.status = "ready"
                existing.save(update_fields=["status"])
                return existing
            else:
                # Try to get Node model if available (optional)
                node_model = None
                try:
                    from ..models import Node
                    node_model = Node.objects.filter(
                        workflow=execution.workflow,
                        node_id=node_id
                    ).first()
                except:
                    pass
                
                return NodeExecution.objects.create(
                    workflow_execution=execution,
                    node=node_model,  # Can be None
                    graph_node_id=node_id,
                    status="ready",
                    retry_policy=node_config.get("retry_policy", {}),
                    join_strategy=node_config.get("join_strategy", "all"),
                    join_required_count=node_config.get("join_required_count"),
                    tenant=getattr(execution, "tenant", None) or None,
                )
    
    @staticmethod
    def get_ready_nodes(execution_id: str, limit: int = 10) -> List[NodeExecution]:
        """
        Get nodes ready for execution.
        
        Args:
            execution_id: Execution ID
            limit: Maximum number of nodes to return
            
        Returns:
            List of NodeExecution instances in READY state
        """
        return list(
            NodeExecution.objects.filter(
                workflow_execution_id=execution_id,
                status="ready"
            ).select_for_update(skip_locked=True)[:limit]
        )
    
    @staticmethod
    def acquire_lock(node_execution_id: str) -> bool:
        """
        Acquire Redis lock for node execution (prevents double-processing).
        
        Args:
            node_execution_id: NodeExecution ID
            
        Returns:
            True if lock acquired, False if already locked
        """
        try:
            ne = NodeExecution.objects.select_related("workflow_execution").get(id=node_execution_id)
            tenant_id = getattr(ne.workflow_execution, "tenant_id", None) or (getattr(ne.workflow_execution, "tenant", None).id if getattr(ne.workflow_execution, "tenant", None) else "global")
        except Exception:
            tenant_id = "global"
        lock_key = f"{NodeExecutionQueue.LOCK_PREFIX}{tenant_id}:{node_execution_id}"
        
        # Try to acquire lock
        acquired = cache.add(lock_key, "locked", NodeExecutionQueue.LOCK_TTL)
        
        if acquired:
            logger.debug(f"Acquired lock for node execution {node_execution_id}")
        else:
            logger.debug(f"Lock already held for node execution {node_execution_id}")
        
        return acquired
    
    @staticmethod
    def release_lock(node_execution_id: str) -> None:
        """Release Redis lock."""
        try:
            ne = NodeExecution.objects.select_related("workflow_execution").get(id=node_execution_id)
            tenant_id = getattr(ne.workflow_execution, "tenant_id", None) or (getattr(ne.workflow_execution, "tenant", None).id if getattr(ne.workflow_execution, "tenant", None) else "global")
        except Exception:
            tenant_id = "global"
        lock_key = f"{NodeExecutionQueue.LOCK_PREFIX}{tenant_id}:{node_execution_id}"
        cache.delete(lock_key)
        logger.debug(f"Released lock for node execution {node_execution_id}")
    
    @staticmethod
    def check_join_condition(
        execution: WorkflowExecution,
        node_id: str,
        join_strategy: str,
        required_count: Optional[int] = None,
    ) -> bool:
        """
        Check if join condition is met (all/any/n parents completed).
        
        Args:
            execution: Workflow execution
            node_id: Node ID to check
            join_strategy: "all", "any", or "n"
            required_count: Required count for "n" strategy
            
        Returns:
            True if join condition is met
        """
        # Get all incoming edges
        graph = execution.workflow.graph or {}
        edges = graph.get("edges", [])
        
        parent_nodes = []
        for edge in edges:
            target = edge.get("to") or edge.get("target")
            if target == node_id:
                source = edge.get("from") or edge.get("source")
                parent_nodes.append(source)
        
        logger.critical(f"🔥 JOIN CHECK {node_id}: PARENTS={parent_nodes}, STRATEGY={join_strategy}")
        
        if not parent_nodes:
            logger.critical(f"🔥 JOIN CHECK {node_id}: NO PARENTS - CAN EXECUTE")
            return True  # No parents, can execute
        
        # Check parent completion status
        completed_parents = NodeExecution.objects.filter(
            workflow_execution=execution,
            graph_node_id__in=parent_nodes,
            status__in=["completed", "success"]
        ).distinct().count()
        
        logger.critical(f"🔥 JOIN CHECK {node_id}: COMPLETED_PARENTS={completed_parents}/{len(parent_nodes)}")
        
        # Check individual parent statuses
        for parent_id in parent_nodes:
            parent_exec = NodeExecution.objects.filter(
                workflow_execution=execution,
                graph_node_id=parent_id
            ).first()
            
            if parent_exec:
                logger.critical(f"🔥 PARENT {parent_id}: STATUS={parent_exec.status}")
            else:
                logger.critical(f"🔥 PARENT {parent_id}: NO EXECUTION RECORD")
        
        result = False
        if join_strategy == "all":
            result = completed_parents == len(parent_nodes)
        elif join_strategy == "any":
            result = completed_parents > 0
        elif join_strategy == "n":
            result = completed_parents >= (required_count or len(parent_nodes))
        else:
            result = completed_parents == len(parent_nodes)  # Default to all
        
        logger.critical(f"🔥 JOIN CHECK {node_id}: RESULT={result}")
        return result
    
    @staticmethod
    def mark_parents_completed_and_check_children(
        execution: WorkflowExecution,
        completed_node_id: str,
    ) -> List[str]:
        """
        When a node completes, check which child nodes become READY.
        
        Args:
            execution: Workflow execution
            completed_node_id: Node ID that just completed
            
        Returns:
            List of node IDs that became READY
        """
        graph = execution.workflow.graph or {}
        # Drain mode: do not enqueue any new children
        try:
            if (execution.resume_data or {}).get("drain"):
                logger.critical(f"🔥 DRAIN MODE: Not enqueueing children for {completed_node_id}")
                return []
        except Exception:
            pass
        edges = graph.get("edges", [])
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        
        logger.critical(f"🔥 CHECKING CHILDREN FOR COMPLETED NODE: {completed_node_id}")
        
        ready_nodes = []
        
        # Find all child nodes
        child_nodes = []
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            if source == completed_node_id:
                target = edge.get("to") or edge.get("target")
                child_nodes.append((target, edge))
        
        logger.critical(f"🔥 CHILD NODES FOUND: {len(child_nodes)} - {[child_id for child_id, _ in child_nodes]}")
        
        # CRITICAL: If no children found but edges exist, this is an error
        if not child_nodes:
            # Check if this node has any outgoing edges at all
            has_outgoing = any(
                (edge.get("from") or edge.get("source")) == completed_node_id 
                for edge in edges
            )
            if not has_outgoing:
                logger.warning(f"⚠️ Node {completed_node_id} has no outgoing edges - workflow may end here")
            else:
                logger.error(f"❌ CRITICAL: Node {completed_node_id} should have children but none found")
        
        # Check each child node
        for child_id, edge in child_nodes:
            logger.critical(f"🔥 CHECKING CHILD NODE: {child_id}")
            
            node_config = nodes.get(child_id, {})
            # Per-edge retry/backoff override if present
            final_config = dict(node_config)
            edge_retry = edge.get("retry_policy")
            if isinstance(edge_retry, dict):
                final_config["retry_policy"] = edge_retry
            join_strategy = node_config.get("join_strategy", "all")
            required_count = node_config.get("join_required_count")
            
            logger.critical(f"🔥 CHILD {child_id} JOIN STRATEGY: {join_strategy}, REQUIRED: {required_count}")
            
            # Check if join condition is met
            join_met = NodeExecutionQueue.check_join_condition(
                execution, child_id, join_strategy, required_count
            )
            
            logger.critical(f"🔥 CHILD {child_id} JOIN CONDITION MET: {join_met}")
            
            if join_met:
                # Mark as ready
                node_exec = NodeExecutionQueue.mark_node_ready(
                    execution, child_id, final_config
                )
                if node_exec:
                    ready_nodes.append(child_id)
                    logger.critical(f"🔥 CHILD {child_id} MARKED READY")
                else:
                    logger.error(f"❌ FAILED to mark child {child_id} as ready")
            else:
                logger.critical(f"🔥 CHILD {child_id} NOT READY - JOIN CONDITION NOT MET")
        
        # CRITICAL: If parent completed but no children became ready, investigate why
        if child_nodes and not ready_nodes:
            logger.error(f"❌ CRITICAL: Parent {completed_node_id} completed but NO children became ready")
            logger.error(f"❌ Expected children: {[child_id for child_id, _ in child_nodes]}")
            
            # Log detailed join condition failures
            for child_id, edge in child_nodes:
                node_config = nodes.get(child_id, {})
                join_strategy = node_config.get("join_strategy", "all")
                
                # Get parent completion details
                parent_nodes = []
                for e in edges:
                    target = e.get("to") or e.get("target")
                    if target == child_id:
                        source = e.get("from") or e.get("source")
                        parent_nodes.append(source)
                
                completed_parents = NodeExecution.objects.filter(
                    workflow_execution=execution,
                    graph_node_id__in=parent_nodes,
                    status__in=["completed", "success"]
                ).count()
                
                logger.error(f"❌ Child {child_id}: {completed_parents}/{len(parent_nodes)} parents completed (strategy: {join_strategy})")
        
        logger.critical(f"🔥 CHILDREN MARKED READY: {ready_nodes}")
        return ready_nodes

    @staticmethod
    def mark_children_on_failure(
        execution: WorkflowExecution,
        failed_node_id: str,
    ) -> List[str]:
        """
        When a node fails without retry, follow error edges (on_error=true)
        and mark children as READY.
        """
        graph = execution.workflow.graph or {}
        edges = graph.get("edges", [])
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        ready_nodes: List[str] = []
        child_edges = []
        for edge in edges:
            source = edge.get("from") or edge.get("source")
            if source == failed_node_id and edge.get("on_error"):
                child_edges.append(edge)
        for edge in child_edges:
            target = edge.get("to") or edge.get("target")
            node_config = nodes.get(target, {})
            final_config = dict(node_config)
            edge_retry = edge.get("retry_policy")
            if isinstance(edge_retry, dict):
                final_config["retry_policy"] = edge_retry
            node_exec = NodeExecutionQueue.mark_node_ready(
                execution, target, final_config
            )
            if node_exec:
                ready_nodes.append(target)
        return ready_nodes

    @staticmethod
    def can_schedule_node(
        execution: WorkflowExecution,
        node_id: str,
        node_config: Dict,
    ) -> bool:
        """
        Rate-limit node scheduling within a one-second window.
        """
        limit = int(node_config.get("rate_limit_per_sec", 0) or 0)
        if limit <= 0:
            return True
        ts = int(timezone.now().timestamp())
        tenant_id = getattr(execution, "tenant_id", None) or (getattr(execution, "tenant", None).id if getattr(execution, "tenant", None) else "global")
        key = f"{NodeExecutionQueue.RATE_PREFIX}{tenant_id}:{execution.id}:{node_id}:{ts}"
        # Initialize counter if new window
        added = cache.add(key, 1, timeout=1)
        if added:
            return True
        # Existing window: increment if under limit
        try:
            current = int(cache.get(key) or 0)
        except Exception:
            current = 0
        if current < limit:
            cache.set(key, current + 1, timeout=1)
            return True
        return False

    @staticmethod
    def acquire_execution_capacity(execution: WorkflowExecution) -> bool:
        """Acquire capacity tokens for tenant, workflow, and global scopes."""
        from django.conf import settings
        tenant_id = getattr(execution, "tenant_id", None) or (getattr(execution, "tenant", None).id if getattr(execution, "tenant", None) else "global")
        workflow_id = str(execution.workflow_id)
        # Initialize caps if missing
        cache.add(NodeExecutionQueue.CAP_GLOBAL_KEY, settings.GLOBAL_EXECUTION_CAPACITY, timeout=None)
        cache.add(f"{NodeExecutionQueue.CAP_TENANT_PREFIX}{tenant_id}", settings.DEFAULT_TENANT_EXECUTION_CAPACITY, timeout=None)
        cache.add(f"{NodeExecutionQueue.CAP_WORKFLOW_PREFIX}{tenant_id}:{workflow_id}", settings.DEFAULT_WORKFLOW_EXECUTION_CAPACITY, timeout=None)
        # Atomic-ish decrement via get/set loop
        try:
            global_cap = int(cache.get(NodeExecutionQueue.CAP_GLOBAL_KEY) or 0)
            tenant_cap = int(cache.get(f"{NodeExecutionQueue.CAP_TENANT_PREFIX}{tenant_id}") or 0)
            wf_cap = int(cache.get(f"{NodeExecutionQueue.CAP_WORKFLOW_PREFIX}{tenant_id}:{workflow_id}") or 0)
        except Exception:
            global_cap = tenant_cap = wf_cap = 0
        if global_cap <= 0 or tenant_cap <= 0 or wf_cap <= 0:
            return False
        cache.set(NodeExecutionQueue.CAP_GLOBAL_KEY, global_cap - 1, timeout=None)
        cache.set(f"{NodeExecutionQueue.CAP_TENANT_PREFIX}{tenant_id}", tenant_cap - 1, timeout=None)
        cache.set(f"{NodeExecutionQueue.CAP_WORKFLOW_PREFIX}{tenant_id}:{workflow_id}", wf_cap - 1, timeout=None)
        return True

    @staticmethod
    def release_execution_capacity(execution: WorkflowExecution) -> None:
        """Release capacity tokens after completion/cancel."""
        tenant_id = getattr(execution, "tenant_id", None) or (getattr(execution, "tenant", None).id if getattr(execution, "tenant", None) else "global")
        workflow_id = str(execution.workflow_id)
        try:
            global_cap = int(cache.get(NodeExecutionQueue.CAP_GLOBAL_KEY) or 0)
            tenant_cap = int(cache.get(f"{NodeExecutionQueue.CAP_TENANT_PREFIX}{tenant_id}") or 0)
            wf_cap = int(cache.get(f"{NodeExecutionQueue.CAP_WORKFLOW_PREFIX}{tenant_id}:{workflow_id}") or 0)
            cache.set(NodeExecutionQueue.CAP_GLOBAL_KEY, global_cap + 1, timeout=None)
            cache.set(f"{NodeExecutionQueue.CAP_TENANT_PREFIX}{tenant_id}", tenant_cap + 1, timeout=None)
            cache.set(f"{NodeExecutionQueue.CAP_WORKFLOW_PREFIX}{tenant_id}:{workflow_id}", wf_cap + 1, timeout=None)
        except Exception:
            pass

