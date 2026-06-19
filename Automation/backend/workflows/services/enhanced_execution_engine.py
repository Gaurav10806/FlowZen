"""
Enhanced execution engine with proper state management, retry, and idempotency.
"""
import logging
import traceback
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.utils import timezone
from celery import shared_task

from ..models import WorkflowExecution, NodeExecution, Credential, DeadLetterItem
from ..services.retry_service import RetryService
from ..services.idempotency_service import IdempotencyService
from ..services.node_execution_queue import NodeExecutionQueue
from ..services.credential_encryption import get_encryption_service
from ..services.observability_service import ObservabilityService
from ..actions import get_action, ActionContext, ACTION_REGISTRY
from ..expression_evaluator import ExpressionEvaluator

logger = logging.getLogger(__name__)


class EnhancedExecutionEngine:
    """
    Enhanced execution engine with:
    - Proper READY state management
    - Retry with backoff
    - Idempotency
    - Credential decryption
    - Better error handling
    """
    
    def __init__(self, execution: WorkflowExecution):
        self.execution = execution
        self.workflow = execution.workflow
        self.graph = execution.workflow.graph or {}
        self.nodes = {n["id"]: n for n in self.graph.get("nodes", [])}
        self.edges = self.graph.get("edges", [])
        
        # CRITICAL: Edge compatibility normalization with validation
        for edge in self.edges:
            # Ensure both source/target and from/to are available
            source = edge.get("source") or edge.get("from")
            target = edge.get("target") or edge.get("to")
            
            if not source or not target:
                logger.error(f"Invalid edge: missing source/target - {edge}")
                continue  # Skip invalid edges
                
            edge["source"] = source
            edge["target"] = target
            # Keep from/to for backward compatibility
            edge["from"] = source
            edge["to"] = target
        
        # Track node outputs
        self.node_output_items: Dict[str, List[Dict]] = {}
        
        # Services
        self.retry_service = RetryService()
        self.idempotency_service = IdempotencyService()
        try:
            self.encryption_service = get_encryption_service()
        except Exception as e:
            logger.warning(f"Credential encryption service not available: {e}")
            self.encryption_service = None
    
    def _mask_items(self, items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Redact common secret fields in items to avoid leaking in DLQ/logs."""
        if not items:
            return []
        def _mask(v):
            try:
                if isinstance(v, dict):
                    redacted = {}
                    for k, val in v.items():
                        lk = str(k).lower()
                        if any(s in lk for s in ["token", "password", "secret", "api_key", "apikey", "key"]):
                            redacted[k] = "***"
                        else:
                            redacted[k] = _mask(val)
                    return redacted
                elif isinstance(v, list):
                    return [_mask(x) for x in v]
                else:
                    return v
            except Exception:
                return v
        out: List[Dict[str, Any]] = []
        for it in items:
            data = it.get("json", {}) if isinstance(it, dict) else {}
            out.append({"json": _mask(data)})
        return out
    
    def initialize_execution(self) -> None:
        """Initialize execution and mark trigger nodes as READY."""
        try:
            self.execution.status = "running"
            self.execution.started_at = timezone.now()
            self.execution.save(update_fields=["status", "started_at"])
            
            # CRITICAL LOGGING: Execution initialization
            logger.critical(f"🔥 INITIALIZING EXECUTION: {self.execution.id}")
            logger.critical(f"🔥 WORKFLOW: {self.workflow.name} ({self.workflow.id})")
            logger.critical(f"🔥 GRAPH NODES: {len(self.nodes)}")
            logger.critical(f"🔥 GRAPH EDGES: {len(self.edges)}")
            
            # PHASE-1: Emit execution_started event
            try:
                ObservabilityService.emit_execution_started(self.execution)
            except Exception as e:
                logger.warning(f"Failed to emit execution_started event: {e}")
            
            # Find trigger nodes - support both 'type' and 'action_type' fields
            trigger_types = {'webhook', 'schedule', 'manual', 'trigger'}
            trigger_nodes = []
            
            for node in self.nodes.values():
                node_type = node.get("type") or node.get("action_type", "")
                logger.critical(f"🔥 NODE: {node['id']} TYPE: {node_type}")
                if node_type.lower() in trigger_types:
                    trigger_nodes.append(node)
            
            if not trigger_nodes:
                # CRITICAL: No trigger nodes found - this is a validation error
                error_msg = f"No trigger nodes found in workflow. Available nodes: {list(self.nodes.keys())}"
                logger.error(error_msg)
                self.execution.mark_failed(
                    error_message=error_msg,
                    traceback=""
                )
                raise ValueError(error_msg)
            
            logger.critical(f"🔥 TRIGGER NODES FOUND: {len(trigger_nodes)} - {[n['id'] for n in trigger_nodes]}")
            
            # Mark trigger nodes as ready
            for node in trigger_nodes:
                try:
                    logger.critical(f"🔥 MARKING TRIGGER NODE READY: {node['id']}")
                    NodeExecutionQueue.mark_node_ready(
                        self.execution,
                        node["id"],
                        node.get("config", {})
                    )
                    logger.critical(f"🔥 TRIGGER NODE MARKED READY: {node['id']}")
                except Exception as e:
                    error_msg = f"Failed to mark trigger node {node['id']} as ready: {e}"
                    logger.error(error_msg, exc_info=True)
                    self.execution.mark_failed(
                        error_message=error_msg,
                        traceback=traceback.format_exc()
                    )
                    raise
            
            # CRITICAL LOGGING: Check edges from trigger nodes
            trigger_ids = {n['id'] for n in trigger_nodes}
            outgoing_edges = [e for e in self.edges if (e.get("from") or e.get("source")) in trigger_ids]
            logger.critical(f"🔥 OUTGOING EDGES FROM TRIGGERS: {len(outgoing_edges)}")
            
            for edge in outgoing_edges:
                source = edge.get("from") or edge.get("source")
                target = edge.get("to") or edge.get("target")
                logger.critical(f"🔥 EDGE: {source} → {target}")
            
            if not outgoing_edges:
                logger.warning("⚠️ WARNING: No outgoing edges from trigger nodes - child nodes will not become ready!")
                    
        except Exception as e:
            logger.error(f"Failed to initialize execution {self.execution.id}: {e}", exc_info=True)
            if self.execution.status != "failed":
                self.execution.mark_failed(
                    error_message=f"Execution initialization failed: {str(e)}",
                    traceback=traceback.format_exc()
                )
            raise

    def _save_node_result(self, result: Dict[str, Any]):
        """Save node execution result to execution history."""
        try:
            # Refresh execution to avoid overwrites
            self.execution.refresh_from_db()
            
            # Initialize node_results if needed
            if not isinstance(self.execution.node_results, list):
                self.execution.node_results = []
            
            # Add trace entry
            self.execution.node_results.append(result)
            
            # Update output data
            self.execution.final_output = result.get("output", {})
            
            # Update status text
            self.execution.save(update_fields=["node_results", "final_output"])
            
            logger.info(f"✅ Saved node result for {result.get('node_id')}")
            
        except Exception as e:
            logger.error(f"Failed to save node result: {e}")
    
    def execute_node(self, node_execution: NodeExecution) -> Dict[str, Any]:
        """
        Execute a single node with retry and idempotency.
        
        Args:
            node_execution: NodeExecution instance
            
        Returns:
            Result dictionary
        """
        node_id = node_execution.graph_node_id
        node_config = self.nodes.get(node_id, {})
        node_type = node_config.get("type")
        node_cfg = node_config.get("config", {})
        
        # Check idempotency
        idempotency_key = node_execution.idempotency_key
        if not idempotency_key:
            idempotency_key = IdempotencyService.generate_key(
                str(self.execution.id),
                node_id,
                attempt=node_execution.retry_count + 1,
                stable=True,
                tenant_id=str(self.execution.tenant_id) if getattr(self.execution, "tenant_id", None) else (str(self.execution.tenant.id) if getattr(self.execution, "tenant", None) else None)
            )
            node_execution.idempotency_key = idempotency_key
            node_execution.save(update_fields=["idempotency_key"])
        
        # Check cache
        cached_result, _ = self.idempotency_service.check_and_store(
            str(self.execution.id),
            node_id,
            attempt=node_execution.retry_count + 1,
            stable=True,
            tenant_id=str(self.execution.tenant_id) if getattr(self.execution, "tenant_id", None) else (str(self.execution.tenant.id) if getattr(self.execution, "tenant", None) else None)
        )
        
        if cached_result:
            logger.info(f"Using cached result for node {node_id}")
            node_execution.mark_completed(
                output_items=cached_result.get("items", []),
                logs="Result retrieved from idempotency cache"
            )
            # Adapt cached result to new contract
            node_result = {
                "success": True,
                "status": "success",
                "output": cached_result.get("items", []),
                "error": None,
                "node_id": node_id,
                "label": node_config.get("label", node_id),
                "execution_time_ms": 0,
                "timestamp": timezone.now().isoformat()
            }
            self._save_node_result(node_result)
            return node_result
        
        # Get retry policy
        retry_policy = node_execution.retry_policy or node_config.get("retry_policy", {})
        max_retries = retry_policy.get("retries", 3)
        retry_on = retry_policy.get("retry_on", [])
        
                # Mark as running
        node_execution.mark_started()
        
        # PHASE-1: Emit node_started event
        ObservabilityService.emit_node_started(node_execution)
        
        # Get handle-aware inputs
        handle_inputs = self._get_node_handle_inputs(node_id)
        
        # Get input items (flattened list for backward compatibility)
        input_items = self._get_node_input_items(node_id)
        
        # Get credential if needed
        credential = None
        credential_data = None
        credential_id = node_config.get("credential_id")
        if credential_id:
            try:
                credential = Credential.objects.get(
                    id=credential_id,
                    tenant=self.execution.tenant
                )
                # Get credential data (encrypted_data is JSONField, may already be decrypted)
                # If it's a string, try to decrypt it
                if isinstance(credential.encrypted_data, str) and self.encryption_service:
                    try:
                        credential_data = self.encryption_service.decrypt_credential_str(
                            credential.encrypted_data
                        )
                    except Exception as e:
                        logger.warning(f"Failed to decrypt credential: {e}")
                        # If decryption fails, assume it's already decrypted JSON
                        try:
                            import json
                            credential_data = json.loads(credential.encrypted_data)
                        except:
                            credential_data = credential.encrypted_data
                else:
                    # Already a dict (decrypted) or encryption service not available
                    credential_data = credential.encrypted_data
            except Credential.DoesNotExist:
                logger.warning(f"Credential {credential_id} not found")
            except Exception as e:
                logger.warning(f"Failed to load credential {credential_id}: {e}")
        
        # Create action context with FULL user and tenant objects
        # Extract user from input_payload (stored during execution creation)
        # SUPPORTS BOTH: _user_id (legacy/internal) and user_id (context/api)
        user_id = self.execution.input_payload.get('_user_id') or self.execution.input_payload.get('user_id')
        user = None
        if user_id:
            try:
                from django.contrib.auth.models import User
                # Convert to int if it's a string
                user_id = int(user_id) if isinstance(user_id, str) and str(user_id).isdigit() else user_id
                user = User.objects.get(id=user_id)
                logger.critical(f"🔥 USER FOUND: {user.id} ({user.email})")
            except (User.DoesNotExist, ValueError, TypeError) as e:
                logger.error(f"User lookup failed for ID {user_id}: {e}")
                user = None
        
        tenant = getattr(self.execution, 'tenant', None)
        
        # CRITICAL LOGGING: Verify user and tenant are available
        logger.critical(f"🔥 EXECUTION CONTEXT: USER={user.id if user else None}, TENANT={tenant.id if tenant else None}")
        logger.critical(f"🔥 EXECUTION INPUT_PAYLOAD USER_ID: {user_id}")
        logger.critical(f"🔥 EXECUTION TENANT: {self.execution.tenant}")
        
        context = ActionContext(
            execution_id=str(self.execution.id),
            node_outputs=self.node_output_items,
            items=input_items,
            inputs=handle_inputs,
            execution_context={
                "execution_id": str(self.execution.id),
                "workflow_id": str(self.workflow.id),
                "timeout_ms": node_cfg.get("timeout_ms"),
                # CRITICAL: Include actual user and tenant objects for Gmail OAuth
                "user": user,
                "tenant": tenant,
            },
            execution=self.execution,  # PHASE-1: Pass execution for NodeEffect
            node_execution=node_execution,  # PHASE-1: Pass node_execution for NodeEffect
        )
        
        # Execute with retry
        attempt = 1
        last_error = None
        
        # Optional OpenTelemetry tracing
        tracer = None
        span = None
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer("automation.workflows")
            span = tracer.start_span(f"node:{node_id}")
            span.set_attribute("workflow.id", str(self.workflow.id))
            span.set_attribute("execution.id", str(self.execution.id))
            span.set_attribute("node.id", node_id)
            span.set_attribute("node.type", node_type or "")
        except Exception:
            tracer = None
            span = None
        
        while attempt <= max_retries + 1:  # +1 for initial attempt
            try:
                # Get action handler with comprehensive error handling
                action_handler = get_action(node_type)
                if not action_handler:
                    # CRITICAL: Log available actions for debugging
                    available_actions = list(ACTION_REGISTRY.keys())
                    error_msg = f"Unknown node type '{node_type}'. Available types: {available_actions}"
                    logger.error(f"Node {node_id}: {error_msg}")
                    
                    # Mark node as failed with structured error
                    node_execution.mark_failed(
                        error_message=error_msg,
                        logs=f"Action type '{node_type}' not found in registry"
                    )
                    
                    error_result = {
                        "success": False,
                        "status": "failed",
                        "output": {},
                        "error": error_msg,
                        "node_id": node_id,
                        "label": node_config.get("label", node_id),
                        "execution_time_ms": 0,
                        "timestamp": timezone.now().isoformat()
                    }
                    self._save_node_result(error_result)
                    return error_result
                
                # Try to get Node model if available (optional)
                node_model = None
                try:
                    from ..models import Node
                    node_model = Node.objects.filter(
                        workflow=self.workflow,
                        node_id=node_id
                    ).first()
                except Exception as e:
                    logger.debug(f"Node model not found for {node_id}: {e}")
                    pass
                
                # Execute action with comprehensive error handling
                start_ts = timezone.now()
                try:
                    output_items = action_handler(
                        node=node_model or node_config.get("config", {}),  # Pass node model or JUST config sub-dict
                        items=input_items,
                        context=context
                    )
                except Exception as action_error:
                    # CRITICAL: Catch all action execution errors
                    error_msg = f"Action execution failed for node '{node_id}' (type: {node_type}): {str(action_error)}"
                    logger.error(error_msg, exc_info=True)
                    
                    # Mark node as failed with structured error
                    node_execution.mark_failed(
                        error_message=error_msg,
                        logs=f"Action execution error: {str(action_error)}"
                    )
                    
                    error_result = {
                        "success": False,
                        "status": "failed",
                        "output": {},
                        "error": error_msg,
                        "node_id": node_id,
                        "label": node_config.get("label", node_id),
                        "execution_time_ms": 0,
                        "timestamp": timezone.now().isoformat()
                    }
                    self._save_node_result(error_result)
                    return error_result
                
                elapsed_ms = int((timezone.now() - start_ts).total_seconds() * 1000)
                timeout_ms = 0
                try:
                    timeout_ms = int(node_cfg.get("timeout_ms") or 0)
                except Exception:
                    timeout_ms = 0
                
                if not isinstance(output_items, list):
                    output_items = [output_items] if output_items else []
                
                # Store output
                self.node_output_items[node_id] = output_items
                
                # STRICT VALIDATION: Trust the node's return value

                if isinstance(output_items, list) and len(output_items) > 0:
                     for item in output_items:
                         if isinstance(item, dict) and item.get("success") is False:
                             error_msg = item.get("error") or "Node execution reported failure"
                             logger.error(f"Node {node_id} returned success=False: {error_msg}")
                             node_execution.mark_failed(
                                 error_message=error_msg,
                                 logs=f"Node output indicated failure: {item}"
                             )
                             error_result = {
                                 "success": False,
                                 "status": "failed",
                                 "output": output_items,
                                 "error": error_msg,
                                 "node_id": node_id,
                                 "label": node_config.get("label", node_id),
                                 "execution_time_ms": elapsed_ms,
                                 "timestamp": timezone.now().isoformat()
                             }
                             self._save_node_result(error_result)
                             return error_result
                
                # Cache result for idempotency
                result = {
                    "success": True,
                    "status": "success",
                    "output": output_items,
                    "error": None,
                    "node_id": node_id,
                    "label": node_config.get("label", node_id),
                    "execution_time_ms": elapsed_ms,
                    "timestamp": timezone.now().isoformat()
                }
                
                # Save to execution history
                self._save_node_result(result)

                # Cache result for idempotency (store internal format)
                self.idempotency_service.store_result(idempotency_key, {
                    "status": "success",
                    "items": output_items
                })
                
                # Timeout enforcement
                if timeout_ms > 0 and elapsed_ms > timeout_ms:
                    error_str = f"Node {node_id} exceeded timeout {timeout_ms}ms (elapsed {elapsed_ms}ms)"
                    node_execution.retry_count = attempt - 1
                    node_execution.mark_failed(
                        error_message=error_str,
                        logs=error_str
                    )
                    try:
                        DeadLetterItem.objects.create(
                            workflow_execution=self.execution,
                            node_execution=node_execution,
                            tenant=self.execution.tenant,  # PHASE-1: Explicit tenant
                            node_id=node_id,
                            items=self._mask_items(input_items),
                            error_message=error_str,
                            error_type="TimeoutError",
                            retries=attempt - 1,
                        )
                    except Exception:
                        pass
                    raise TimeoutError(error_str)
                else:
                    # Mark as completed
                    node_execution.mark_completed(
                        output_items=output_items,
                        logs=f"Node executed successfully (attempt {attempt}) in {elapsed_ms}ms"
                    )
                    
                    # PHASE-1: Emit node_completed event
                    ObservabilityService.emit_node_completed(node_execution)
                
                # Update status to "success" for consistency (if status choice exists)
                if hasattr(node_execution, 'status') and 'success' in [choice[0] for choice in node_execution.STATUS_CHOICES]:
                    node_execution.status = "success"
                    node_execution.save(update_fields=["status"])
                
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                try:
                    if span:
                        span.record_exception(e)
                        span.set_attribute("node.error", error_str)
                except Exception:
                    pass
                
                # Check if should retry
                should_retry = self.retry_service.should_retry(
                    e, attempt, max_retries, retry_on
                )
                
                if not should_retry or attempt > max_retries:
                    # Max retries reached or error not retryable
                    node_execution.retry_count = attempt - 1
                    node_execution.mark_failed(
                        error_message=error_str,
                        logs=f"Node failed after {attempt} attempts: {error_str}"
                    )
                    
                    # PHASE-1: Emit node_failed event
                    ObservabilityService.emit_node_failed(node_execution, error_str)
                    
                    try:
                        DeadLetterItem.objects.create(
                            workflow_execution=self.execution,
                            node_execution=node_execution,
                            tenant=self.execution.tenant,  # PHASE-1: Explicit tenant
                            node_id=node_id,
                            items=self._mask_items(input_items),
                            error_message=error_str,
                            error_type=type(e).__name__,
                            retries=attempt - 1,
                        )
                    except Exception:
                        pass
                    # Route error branches
                    try:
                        from ..services.node_execution_queue import NodeExecutionQueue
                        NodeExecutionQueue.mark_children_on_failure(self.execution, node_id)
                    except Exception:
                        pass
                    raise
                
                # Retry with backoff
                attempt += 1
                node_execution.retry_count = attempt - 1
                node_execution.save(update_fields=["retry_count"])
                
                self.retry_service.sleep_with_backoff(attempt, retry_policy)
                logger.warning(f"Node {node_id} failed, retrying (attempt {attempt}/{max_retries})")
        
        # Should not reach here
        raise last_error or Exception("Execution failed")
    
    def __del__(self):
        try:
            # Finish tracing span if open
            span = getattr(self, "span", None)
            if span:
                span.end()
        except Exception:
            pass
    
    def _get_node_handle_inputs(self, node_id: str) -> Dict[str, List[Dict]]:
        """Get input items for a node grouped by targetHandle (n8n-style)."""
        incoming_edges = [e for e in self.edges if (e.get("to") or e.get("target")) == node_id]
        
        handle_inputs = {
            "main": [],
            "tools": [],
            "memory": [],
            "system": []
        }

        for edge in incoming_edges:
            source = edge.get("from") or edge.get("source")
            if not source:
                continue
            
            # Requirement 1: Default to "main" if targetHandle is missing
            handle = edge.get("targetHandle") or "main"
            
            if handle not in handle_inputs:
                handle_inputs[handle] = []
                
            items = self.node_output_items.get(source, [])
            
            # Evaluate edge conditions if present
            condition_expr = edge.get("condition_expr") or edge.get("condition")
            if condition_expr and items:
                try:
                    evaluator = ExpressionEvaluator(
                        items=items, 
                        node_outputs=self.node_output_items, 
                        execution_context={"execution_id": str(self.execution.id)}
                    )
                    kept = []
                    for idx in range(len(items)):
                        val = evaluator.evaluate(f"{{{{ {condition_expr} }}}}", item_index=idx)
                        truthy = False
                        if isinstance(val, bool):
                            truthy = val
                        else:
                            truthy = self._evaluate_simple_condition(condition_expr, items[idx].get("json", {}))
                            if truthy is None:
                                truthy = bool(val)
                        if truthy:
                            kept.append(items[idx])
                    items = kept
                except Exception as e:
                    logger.warning(f"Condition evaluation failed for edge {source}->{node_id}: {e}")
            
            # Requirement 2: Append instead of replacing
            handle_inputs[handle].extend(items)
            
        return handle_inputs

    def _get_node_input_items(self, node_id: str) -> List[Dict]:
        """Get input items for a node from parent nodes with edge conditions and aggregators."""
        # Find edges pointing to node
        incoming_edges = [e for e in self.edges if (e.get("to") or e.get("target")) == node_id]
        filtered_items: List[Dict] = []

        for edge in incoming_edges:
            source = edge.get("from") or edge.get("source")
            if not source:
                continue
            items = self.node_output_items.get(source, [])
            condition_expr = edge.get("condition_expr") or edge.get("condition")
            if condition_expr:
                try:
                    evaluator = ExpressionEvaluator(items=items, node_outputs=self.node_output_items, execution_context={"execution_id": str(self.execution.id)})
                    kept: List[Dict] = []
                    for idx, _ in enumerate(items):
                        val = evaluator.evaluate(f"{{{{ {condition_expr} }}}}", item_index=idx)
                        truthy = False
                        if isinstance(val, bool):
                            truthy = val
                        else:
                            # Fallback evaluator for simple comparisons like "$json.amount > 10"
                            truthy = self._evaluate_simple_condition(condition_expr, items[idx].get("json", {}))
                            if truthy is None:
                                # Non-boolean values: treat non-empty/non-zero as truthy
                                truthy = bool(val)
                        if truthy:
                            kept.append(items[idx])
                    items = kept
                except Exception:
                    # If condition evaluation fails, default to keeping items
                    pass
            filtered_items.extend(items)

        # If no parents produced items, use execution input
        if not filtered_items:
            filtered_items = self.execution.input_items or []

        # Aggregator: union (default), merge, reduce_sum and more
        node_cfg = self.nodes.get(node_id, {}).get("config", {})
        aggregator = node_cfg.get("aggregator") or "union"
        if aggregator == "union":
            return filtered_items
        elif aggregator == "merge":
            merged: Dict[str, Any] = {}
            for it in filtered_items:
                data = it.get("json", {})
                if isinstance(data, dict):
                    merged.update(data)
            return [{"json": merged}]
        elif aggregator == "reduce_sum":
            field = node_cfg.get("reduce_field")
            total = 0
            for it in filtered_items:
                val = it.get("json", {}).get(field, 0) if field else 0
                try:
                    total += float(val)
                except Exception:
                    continue
            return [{"json": {field or "sum": total}}]
        elif aggregator == "reduce_max":
            field = node_cfg.get("reduce_field")
            max_val: Optional[float] = None
            for it in filtered_items:
                val = it.get("json", {}).get(field) if field else None
                try:
                    num = float(val) if val is not None else None
                except Exception:
                    num = None
                if num is not None:
                    if max_val is None or num > max_val:
                        max_val = num
            return [{"json": {field or "max": (max_val if max_val is not None else 0)}}]
        elif aggregator == "reduce_min":
            field = node_cfg.get("reduce_field")
            min_val: Optional[float] = None
            for it in filtered_items:
                val = it.get("json", {}).get(field) if field else None
                try:
                    num = float(val) if val is not None else None
                except Exception:
                    num = None
                if num is not None:
                    if min_val is None or num < min_val:
                        min_val = num
            return [{"json": {field or "min": (min_val if min_val is not None else 0)}}]
        elif aggregator == "reduce_avg":
            field = node_cfg.get("reduce_field")
            total = 0.0
            count = 0
            for it in filtered_items:
                val = it.get("json", {}).get(field, 0) if field else 0
                try:
                    total += float(val)
                    count += 1
                except Exception:
                    continue
            avg = (total / count) if count > 0 else 0
            return [{"json": {field or "avg": avg}}]
        elif aggregator == "reduce_count":
            return [{"json": {"count": len(filtered_items)}}]
        elif aggregator == "reduce_concat":
            field = node_cfg.get("reduce_field")
            sep = node_cfg.get("reduce_separator") or ""
            parts: List[str] = []
            for it in filtered_items:
                val = it.get("json", {}).get(field) if field else None
                if val is None:
                    continue
                try:
                    parts.append(str(val))
                except Exception:
                    continue
            return [{"json": {field or "concat": sep.join(parts)}}]
        elif aggregator == "first":
            return filtered_items[:1]
        elif aggregator == "last":
            return filtered_items[-1:] if filtered_items else []
        elif aggregator == "flatten":
            field = node_cfg.get("flatten_field") or node_cfg.get("reduce_field")
            out: List[Dict[str, Any]] = []
            for it in filtered_items:
                arr = None
                if field:
                    arr = it.get("json", {}).get(field)
                else:
                    arr = it.get("json")
                if isinstance(arr, list):
                    for elem in arr:
                        out.append({"json": elem})
            return out
        else:
            return filtered_items
    
    def _evaluate_simple_condition(self, expr: str, item_json: Dict[str, Any]) -> Optional[bool]:
        """
        Evaluate simple comparison expressions like:
        "$json.amount > 10", "$json.user.age >= 18", "$json.status == \"ok\""
        Returns True/False or None if cannot evaluate.
        """
        try:
            import re
            m = re.match(r'^\s*\$json\.([a-zA-Z0-9_\.]+)\s*(==|!=|>=|<=|>|<)\s*(.+)\s*$', str(expr))
            if not m:
                return None
            path, op, rhs = m.groups()
            # Get LHS value from item_json
            lhs = item_json
            for key in path.split("."):
                if isinstance(lhs, dict):
                    lhs = lhs.get(key)
                else:
                    lhs = None
                if lhs is None:
                    break
            # Normalize RHS
            rhs = rhs.strip()
            if (rhs.startswith('"') and rhs.endswith('"')) or (rhs.startswith("'") and rhs.endswith("'")):
                rhs_val = rhs[1:-1]
            else:
                try:
                    rhs_val = float(rhs)
                except:
                    rhs_val = rhs
            # Normalize LHS to numeric if both look numeric
            lhs_val = lhs
            try:
                if isinstance(rhs_val, (int, float)) and lhs is not None:
                    lhs_val = float(lhs)
            except:
                lhs_val = lhs
            if op == "==":
                return lhs_val == rhs_val
            if op == "!=":
                return lhs_val != rhs_val
            if op == ">":
                return (lhs_val if lhs_val is not None else float("-inf")) > (rhs_val if isinstance(rhs_val, (int, float)) else float("-inf"))
            if op == "<":
                return (lhs_val if lhs_val is not None else float("inf")) < (rhs_val if isinstance(rhs_val, (int, float)) else float("inf"))
            if op == ">=":
                return (lhs_val if lhs_val is not None else float("-inf")) >= (rhs_val if isinstance(rhs_val, (int, float)) else float("-inf"))
            if op == "<=":
                return (lhs_val if lhs_val is not None else float("inf")) <= (rhs_val if isinstance(rhs_val, (int, float)) else float("inf"))
            return None
        except Exception:
            return None
    
    def process_ready_nodes(self, max_nodes: int = 10) -> List[str]:
        """
        Process ready nodes up to max_nodes.
        
        Returns:
            List of node IDs that were successfully processed
        """
        from django.db import transaction
        
        with transaction.atomic():
            ready_nodes = NodeExecutionQueue.get_ready_nodes(
                str(self.execution.id),
                limit=max_nodes
            )
        
        # CRITICAL LOGGING: Track ready nodes
        logger.critical(f"🔥 READY NODES FOUND: {len(ready_nodes)} - {[n.graph_node_id for n in ready_nodes]}")
        
        processed_node_ids = []
        for node_exec in ready_nodes:
            # CRITICAL LOGGING: Track node processing
            logger.critical(f"🔥 PROCESSING NODE: {node_exec.graph_node_id} (status: {node_exec.status})")
            
            # Acquire lock
            if not NodeExecutionQueue.acquire_lock(str(node_exec.id)):
                logger.warning(f"Could not acquire lock for node {node_exec.graph_node_id}")
                continue  # Skip if locked
            
            try:
                # Concurrency controls
                node_def = self.nodes.get(node_exec.graph_node_id, {})
                node_cfg = node_def.get("config", {})
                if not NodeExecutionQueue.can_schedule_node(self.execution, node_exec.graph_node_id, node_cfg):
                    logger.debug(f"Concurrency/rate limit prevents scheduling {node_exec.graph_node_id}")
                    continue
                
                # CRITICAL LOGGING: About to execute node
                logger.critical(f"🔥 EXECUTING NODE: {node_exec.graph_node_id}")
                
                # Execute node
                result = self.execute_node(node_exec)
                
                # CRITICAL LOGGING: Node execution result
                logger.critical(f"🔥 NODE EXECUTED: {node_exec.graph_node_id} - RESULT: {result.get('status', 'unknown')}")
                
                # Only count as processed if execution succeeded
                if result.get('success'):
                    processed_node_ids.append(node_exec.graph_node_id)
                
                # Check child nodes
                ready_children = NodeExecutionQueue.mark_parents_completed_and_check_children(
                    self.execution,
                    node_exec.graph_node_id
                )
                
                logger.critical(f"🔥 NODE COMPLETED: {node_exec.graph_node_id}, {len(ready_children)} children became ready: {ready_children}")
                
                # CRITICAL: If parent completed but no children became ready, investigate
                if result.get('success'):
                    # Find expected children from graph
                    expected_children = []
                    for edge in self.edges:
                        source = edge.get("from") or edge.get("source")
                        if source == node_exec.graph_node_id:
                            target = edge.get("to") or edge.get("target")
                            expected_children.append(target)
                    
                    if expected_children and not ready_children:
                        logger.error(f"❌ CRITICAL: Node {node_exec.graph_node_id} completed but expected children {expected_children} did not become ready")
                
            except Exception as e:
                logger.error(f"Failed to execute node {node_exec.graph_node_id}: {e}", exc_info=True)
                # CRITICAL: Don't count failed nodes as processed
            finally:
                NodeExecutionQueue.release_lock(str(node_exec.id))
        
        logger.critical(f"🔥 PROCESS_READY_NODES COMPLETE: PROCESSED={processed_node_ids}")
        return processed_node_ids
    
    def run(self) -> Dict[str, Any]:
        """
        Run execution until completion or failure.
        
        Returns:
            Execution result
        """
        try:
            # Initialize
            self.initialize_execution()
            
            # CRITICAL: Track actual node execution counts
            total_nodes_executed = 0
            email_nodes_executed = 0
            trigger_nodes_executed = 0
            
            # Identify email nodes in workflow
            email_node_ids = []
            trigger_node_ids = []
            for node_id, node in self.nodes.items():
                node_type = node.get("type") or node.get("action_type", "")
                if node_type.lower() in {"email_sender", "email_send", "email"}:
                    email_node_ids.append(node_id)
                elif node_type.lower() in {'webhook', 'schedule', 'manual', 'trigger'}:
                    trigger_node_ids.append(node_id)
            
            logger.critical(f"🔥 WORKFLOW ANALYSIS: EMAIL_NODES={email_node_ids}, TRIGGER_NODES={trigger_node_ids}")
            
            # Process nodes until no more ready nodes
            max_iterations = 1000  # Safety limit
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Cancellation/pause
                self.execution.refresh_from_db()
                if self.execution.status == "cancelled":
                    logger.info(f"Execution {self.execution.id} cancelled; draining stop")
                    return {"status": "cancelled"}
                if self.execution.status == "paused":
                    logger.info(f"Execution {self.execution.id} paused")
                    return {"status": "paused"}

                # Process ready nodes
                processed_nodes = self.process_ready_nodes(max_nodes=10)
                
                # Track node types executed
                for node_id in processed_nodes:
                    total_nodes_executed += 1
                    if node_id in email_node_ids:
                        email_nodes_executed += 1
                        logger.critical(f"🔥 EMAIL NODE EXECUTED: {node_id}")
                    elif node_id in trigger_node_ids:
                        trigger_nodes_executed += 1
                        logger.critical(f"🔥 TRIGGER NODE EXECUTED: {node_id}")
                
                logger.critical(f"🔥 ITERATION {iteration}: PROCESSED={len(processed_nodes)}, TOTAL={total_nodes_executed}, EMAIL={email_nodes_executed}")
                
                if len(processed_nodes) == 0:
                    # Check if execution is complete
                    remaining = NodeExecution.objects.filter(
                        workflow_execution=self.execution,
                        status__in=["ready", "running", "pending"]
                    ).count()
                    
                    logger.critical(f"🔥 NO NODES PROCESSED: REMAINING={remaining}, TOTAL_EXECUTED={total_nodes_executed}")
                    
                    if remaining == 0:
                        # CRITICAL: Validate execution before completion
                        break
                    else:
                        # Wait for nodes to become ready (they might be waiting for joins)
                        import time
                        time.sleep(0.1)
                        continue
                
                # Check for failures
                failed_nodes = NodeExecution.objects.filter(
                    workflow_execution=self.execution,
                    status="failed"
                ).count()
                
                if failed_nodes > 0:
                    self.execution.mark_failed(
                        error_message="One or more nodes failed"
                    )
                    return {"status": "failed", "error": "Node execution failed"}
            
            # CRITICAL VALIDATION BEFORE COMPLETION - PREVENT SILENT SUCCESS
            validation_errors = []
            
            # Define action node types (non-trigger types)
            from ..actions import ACTION_REGISTRY
            trigger_types = {'webhook', 'schedule', 'manual', 'trigger', 'manual_trigger', 'webhook_trigger', 'schedule_trigger'}
            action_node_types = {node_type for node_type in ACTION_REGISTRY.keys() if node_type not in trigger_types}
            
            # CRITICAL: Log every node execution attempt
            logger.critical(f"🔍 EXECUTION VALIDATION - WORKFLOW: {self.workflow.id}")
            logger.critical(f"🔍 TOTAL NODES IN GRAPH: {len(self.nodes)}")
            logger.critical(f"🔍 TOTAL NODES EXECUTED: {total_nodes_executed}")
            logger.critical(f"🔍 TRIGGER NODES EXECUTED: {trigger_nodes_executed}")
            logger.critical(f"🔍 EMAIL NODES EXECUTED: {email_nodes_executed}")
            
            # Log each node execution with type classification
            all_node_executions = NodeExecution.objects.filter(workflow_execution=self.execution)
            total_action_nodes_executed = 0
            
            for ne in all_node_executions:
                node_def = self.nodes.get(ne.graph_node_id, {})
                node_type = (node_def.get("type") or node_def.get("action_type", "unknown")).lower()
                is_action = node_type in action_node_types
                if ne.status in ["completed", "success"] and is_action:
                    total_action_nodes_executed += 1
            
            # 1. CRITICAL: Ensure at least one action node executed
            if total_action_nodes_executed == 0:
                # Check if workflow has any action nodes at all
                action_nodes_in_workflow = []
                for node_id, node in self.nodes.items():
                    node_type = (node.get("type") or node.get("action_type", "")).lower()
                    if node_type in action_node_types:
                        action_nodes_in_workflow.append(node_id)
                
                if action_nodes_in_workflow:
                    validation_errors.append(f"CRITICAL: No action nodes executed (only {trigger_nodes_executed} trigger nodes). Action nodes in workflow: {action_nodes_in_workflow}")
                    logger.critical(f"❌ VALIDATION FAILED: No action nodes executed")
            
            # 2. CRITICAL: If workflow contains EmailSenderNode, it MUST have executed
            if email_node_ids:
                completed_email_nodes = []
                for email_node_id in email_node_ids:
                    email_exec = NodeExecution.objects.filter(
                        workflow_execution=self.execution,
                        graph_node_id=email_node_id,
                        status__in=["completed", "success"]
                    ).first()
                    
                    if email_exec:
                        completed_email_nodes.append(email_node_id)
                    else:
                        validation_errors.append(f"EmailSenderNode {email_node_id} was never executed successfully")
                
                if len(completed_email_nodes) == 0:
                     validation_errors.append(f"CRITICAL: Workflow contains EmailSenderNode {email_node_ids} but none executed successfully")

            # 6. CRITICAL: Gmail OAuth validation for email nodes
            gmail_validation_errors = self._validate_gmail_oauth_requirements()
            if gmail_validation_errors:
                validation_errors.extend(gmail_validation_errors)
            
            # CRITICAL: If validation failed, FAIL the execution (NO SILENT SUCCESS)
            if validation_errors:
                error_msg = "EXECUTION VALIDATION FAILED: " + "; ".join(validation_errors)
                logger.critical(f"❌ EXECUTION VALIDATION FAILED: {error_msg}")
                self.execution.mark_failed(error_message=error_msg)
                return {"status": "failed", "error": error_msg}
            
            # Mark as completed (validation passed)
            final_items = []
            end_nodes = self._get_end_nodes()
            for node_id in end_nodes:
                if node_id in self.node_output_items:
                    final_items.extend(self.node_output_items[node_id])
            
            logger.critical(f"✅ EXECUTION VALIDATION PASSED: TOTAL={total_nodes_executed}, EMAIL={email_nodes_executed}")
            
            self.execution.mark_completed(
                result={
                    "item_count": len(final_items), 
                    "nodes_executed": total_nodes_executed,
                    "email_nodes_executed": email_nodes_executed
                },
                output_items=final_items
            )
            
            # PHASE-1: Emit execution_completed event
            ObservabilityService.emit_execution_completed(self.execution)
            
            # Store root context
            self.execution.root_context = {
                "node_outputs": self.node_output_items,
                "final_items": final_items,
                "nodes_executed": total_nodes_executed,
                "email_nodes_executed": email_nodes_executed,
            }
            self.execution.save(update_fields=["root_context"])
            return {
                "status": "completed", 
                "items": final_items, 
                "nodes_executed": total_nodes_executed,
                "email_nodes_executed": email_nodes_executed
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Execution failed: {e}", exc_info=True)
            try:
                 self.execution.mark_failed(error_message=error_str)
                 # PHASE-1: Emit execution_failed event
                 ObservabilityService.emit_execution_failed(self.execution, error_str)
            except Exception:
                 logger.error("Failed to mark execution as failed", exc_info=True)
            return {"status": "failed", "error": error_str}
        
        finally:
            # FORCE FINALIZATION
            try:
                self.execution.refresh_from_db()
                if self.execution.status == "running":
                    logger.error("Execution LEFT IN RUNNING STATE. Forcing FAILED status.")
                    self.execution.mark_failed(error_message="Execution crashed or stalled (Zombie Process)")
                
                # Ensure completed_at is set if finished (redundant but safe)
                if self.execution.status in ["completed", "failed", "success", "cancelled"] and not self.execution.completed_at:
                    self.execution.completed_at = timezone.now()
                    self.execution.save(update_fields=["completed_at"])
                    
                logger.critical(f"🏁 EXECUTION FINALIZED: Status={self.execution.status}")
            except Exception as e:
                logger.critical(f"FATAL: Failed to finalize execution state: {e}")
    
    def _get_end_nodes(self) -> List[str]:
        """Get nodes with no outgoing edges."""
        sources = {e.get("from") or e.get("source") for e in self.edges}
        return [nid for nid in self.nodes.keys() if nid not in sources]
    
    def _validate_gmail_oauth_requirements(self) -> List[str]:
        """
        Validate Gmail OAuth requirements for email nodes.
        
        Returns:
            List of validation error messages
        """
        from django.conf import settings
        
        validation_errors = []
        
        # Check if Gmail OAuth is enabled
        gmail_oauth_enabled = getattr(settings, 'GMAIL_OAUTH_ENABLED', False)
        
        # Find email nodes that use Gmail addresses
        gmail_email_nodes = []
        for node_id, node in self.nodes.items():
            node_type = (node.get("type") or node.get("action_type", "")).lower()
            if node_type in {"email_sender", "email_send", "email"}:
                # Check if from_email is Gmail
                from_email = node.get("config", {}).get("from") or node.get("config", {}).get("from_email", "")
                if from_email and "@gmail.com" in from_email.lower():
                    gmail_email_nodes.append({
                        "node_id": node_id,
                        "from_email": from_email
                    })
        
        if gmail_email_nodes:
            logger.critical(f"🔍 GMAIL EMAIL NODES FOUND: {len(gmail_email_nodes)}")
            
            # If Gmail nodes exist but OAuth is not enabled, FAIL
            if not gmail_oauth_enabled:
                validation_errors.append(
                    f"CRITICAL: Gmail email nodes found but Gmail OAuth is not configured. "
                    f"Nodes: {[n['node_id'] for n in gmail_email_nodes]}. "
                    f"Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET environment variables."
                )
                logger.critical(f"❌ GMAIL OAUTH NOT CONFIGURED FOR GMAIL NODES")
            
            # Check if user context is available
            user_id = self.execution.input_payload.get('_user_id') if self.execution.input_payload else None
            if not user_id:
                validation_errors.append(
                    f"CRITICAL: Gmail email nodes require user context but no user found in execution. "
                    f"Nodes: {[n['node_id'] for n in gmail_email_nodes]}"
                )
                logger.critical(f"❌ NO USER CONTEXT FOR GMAIL NODES")
            
            # Check if tenant context is available
            if not self.execution.tenant:
                validation_errors.append(
                    f"CRITICAL: Gmail email nodes require tenant context but no tenant found in execution. "
                    f"Nodes: {[n['node_id'] for n in gmail_email_nodes]}"
                )
                logger.critical(f"❌ NO TENANT CONTEXT FOR GMAIL NODES")
            
            # If OAuth is enabled, check for credentials
            if gmail_oauth_enabled and user_id and self.execution.tenant:
                try:
                    from django.contrib.auth.models import User
                    from ..models import Credential
                    
                    user = User.objects.get(id=user_id)
                    
                    # Check if Gmail OAuth credential exists
                    gmail_credential = Credential.objects.filter(
                        type__in=["gmail", "gmail_oauth", "google_oauth"],
                        owner=user
                    ).first()
                    
                    if not gmail_credential:
                        validation_errors.append(
                            f"CRITICAL: Gmail OAuth credential not found for user {user.email} in tenant {self.execution.tenant.name}. "
                            f"Please connect Gmail account before running workflow with Gmail nodes: {[n['node_id'] for n in gmail_email_nodes]}"
                        )
                        logger.critical(f"❌ NO GMAIL OAUTH CREDENTIAL FOUND")
                    else:
                        logger.critical(f"✅ GMAIL OAUTH CREDENTIAL FOUND: ID={gmail_credential.id}")
                        
                except Exception as e:
                    validation_errors.append(
                        f"CRITICAL: Error validating Gmail OAuth credential: {str(e)}"
                    )
                    logger.critical(f"❌ GMAIL OAUTH CREDENTIAL VALIDATION ERROR: {e}")
        
        return validation_errors


@shared_task
def execute_workflow_enhanced(execution_id: str) -> Dict[str, Any]:
    """
    Enhanced Celery task for workflow execution.
    
    Args:
        execution_id: WorkflowExecution ID
        
    Returns:
        Execution result
    """
    try:
        execution = WorkflowExecution.objects.select_related("workflow").get(id=execution_id)
        
        if execution.status not in ["queued", "pending"]:
            logger.warning(f"Execution {execution_id} not in queued state")
            return {"status": "skipped", "reason": "Invalid state"}
        
        engine = EnhancedExecutionEngine(execution)
        return engine.run()
        
    except WorkflowExecution.DoesNotExist:
        logger.error(f"Execution {execution_id} not found")
        return {"status": "error", "error": "Execution not found"}
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

