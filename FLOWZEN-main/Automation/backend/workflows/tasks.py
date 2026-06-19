"""
Celery tasks for workflow execution.
"""
import uuid
import traceback
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import requests
from django.conf import settings
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Workflow, WorkflowExecution, NodeExecution, Node, WorkflowExecutionStep
from .actions import get_action, ActionContext
from .services.enhanced_execution_engine import EnhancedExecutionEngine
from .services.node_execution_queue import NodeExecutionQueue
from .nodes import NodeExecutionError
from .chat_response_handler import handle_chat_workflow_completion
from django.db import connections
from .utils.json_utils import sanitize_payload

logger = logging.getLogger(__name__)


@shared_task
def execution_timeout_check(execution_id: str):
    """
    Safety task to prevent executions from getting stuck in queued/running state.
    Called 5 minutes after execution creation to check if it's still stuck.
    """
    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
        
        # If execution is still queued or running after 5 minutes, mark as failed
        if execution.status in ['queued', 'running']:
            logger.warning(f"Execution {execution_id} stuck in {execution.status} state - marking as failed")
            execution.mark_failed(
                error_message=f"Execution timed out in {execution.status} state. This may indicate a Celery worker issue.",
                traceback=""
            )
            
    except WorkflowExecution.DoesNotExist:
        logger.warning(f"Execution {execution_id} not found during timeout check")
    except Exception as e:
        logger.error(f"Error during execution timeout check: {e}", exc_info=True)




def broadcast_log(execution_id: str, message: str, level: str = "info", data: Dict = None):
    """Broadcast log message via WebSocket."""
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"execution_{execution_id}",
            {
                "type": "log_message",
                "message": message,
                "level": level,
                "data": sanitize_payload(data or {}),
            }
        )


def build_adjacency_list(nodes: List[Dict], edges: List[Dict]) -> Dict[str, List[str]]:
    """Build adjacency list from graph nodes and edges."""
    adj_list = defaultdict(list)
    node_ids = {node.get("id") for node in nodes}
    
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in node_ids and target in node_ids:
            adj_list[source].append(target)
    
    return adj_list


def topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """
    Perform topological sort to determine execution order.
    Returns list of node IDs in execution order.
    """
    adj_list = build_adjacency_list(nodes, edges)
    node_ids = {node.get("id") for node in nodes}
    
    # Calculate in-degrees
    in_degree = {node_id: 0 for node_id in node_ids}
    for source, targets in adj_list.items():
        for target in targets:
            in_degree[target] = in_degree.get(target, 0) + 1
    
    # Kahn's algorithm
    queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
    result = []
    
    while queue:
        node_id = queue.popleft()
        result.append(node_id)
        
        for neighbor in adj_list.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # Add any remaining nodes (cycles or disconnected)
    for node_id in node_ids:
        if node_id not in result:
            result.append(node_id)
    
    return result


def get_start_nodes(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """Get nodes with no incoming edges (start nodes)."""
    targets = {edge.get("target") for edge in edges}
    node_ids = {node.get("id") for node in nodes}
    return [node_id for node_id in node_ids if node_id not in targets]


@shared_task(bind=True, max_retries=3)
def execute_workflow_with_core_engine(self, execution_id: str):
    """
    Execute workflow using the new core execution engine.
    
    This is the MAIN execution task that uses the clean, simple execution engine.
    It provides safe, deterministic workflow execution with proper error handling.
    
    Args:
        execution_id: UUID of the WorkflowExecution to execute
    """
    try:
        logger.info(f"Starting core engine execution for {execution_id}")
        
        from .execution.django_executor import execute_django_workflow
        # Execute using Django-integrated executor
        result = execute_django_workflow(execution_id)
        
        if result.success:
            logger.info(f"Core engine execution completed for {execution_id}: {result.success}")
            try:
                from notifications.services import create_notification
                execution = WorkflowExecution.objects.select_related('workflow').get(id=execution_id)
                create_notification(
                    user=execution.workflow.owner,
                    type='success',
                    title='Workflow Succeeded',
                    message=f"Workflow '{execution.workflow.name}' executed successfully.",
                    link=f"/workflows/executions/{execution.id}/"
                )
            except Exception as e:
                logger.warning(f"Failed to send success notification: {e}")
        else:
             try:
                from notifications.services import create_notification
                execution = WorkflowExecution.objects.select_related('workflow').get(id=execution_id)
                create_notification(
                    user=execution.workflow.owner,
                    type='error',
                    title='Workflow Failed',
                    message=f"Workflow '{execution.workflow.name}' failed: {result.error_message}",
                    link=f"/workflows/executions/{execution.id}/"
                )
             except Exception as e:
                logger.warning(f"🚀 ANTIGRAVITY_VERIFY: Failed to send failure notification: {e}")
        
        return {
            'success': result.success,
            'execution_id': execution_id,
            'final_output': result.final_output,
            'execution_time_ms': result.total_execution_time_ms,
            'node_count': len(result.node_results),
            'error_message': result.error_message
        }
        
    except WorkflowExecution.DoesNotExist:
        logger.error(f"WorkflowExecution {execution_id} not found")
        raise
        
    except Exception as e:
        logger.error(f"Core engine execution failed for {execution_id}: {e}")
        
        # Don't retry on execution engine errors - they should be deterministic
        raise


@shared_task(bind=True, max_retries=3)
def execute_workflow_with_node_system(self, execution_id: str):
    """
    Execute workflow using the new node-based system.
    
    This is the LEGACY execution task - use execute_workflow_with_core_engine instead.
    
    Args:
        execution_id: UUID of the WorkflowExecution to execute
    """
    logger.warning(f"Using legacy node system executor for {execution_id}")
    
    try:
        # Delegate to new core engine
        return execute_workflow_with_core_engine(execution_id)
        
    except Exception as e:
        logger.error(f"Legacy node system execution failed: {e}")
        raise


# Legacy functions removed - use execute_workflow_with_core_engine() or run_workflow_execution() instead


@shared_task
def execute_node(execution_id: str, node_id: str, payload: Dict[str, Any], node_outputs: Dict[str, Any]):
    """
    Execute a single node (for parallel execution).
    This can be called as a child task for parallel node execution.
    """
    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
        workflow = execution.workflow
        node = Node.objects.get(workflow=workflow, node_id=node_id)
        
        # Create NodeExecution
        node_execution = NodeExecution.objects.create(
            workflow_execution=execution,
            node=node,
            input_data=payload.copy(),
        )
        
        node_execution.mark_started()
        broadcast_log(str(execution_id), f"Executing node: {node.label}", "info")
        
        # Execute action
        context = ActionContext(str(execution_id), node_outputs)
        action_fn = get_action(node.action_type)
        
        if not action_fn:
            raise ValueError(f"Unknown action type: {node.action_type}")
        
        output = action_fn(node, payload, context)
        
        if output.get("success", False):
            node_execution.mark_completed(output=output)
            broadcast_log(str(execution_id), f"Node completed: {node.label}", "success")
            return output
        else:
            node_execution.mark_failed(error_message=output.get("error", "Unknown error"))
            broadcast_log(str(execution_id), f"Node failed: {node.label}", "error")
            raise Exception(output.get("error", "Node execution failed"))
            
    except Exception as e:
        logger.error(f"Node execution failed: {e}", exc_info=True)
        raise


@shared_task
def run_workflow_execution_simple(execution_id: str):
    """
    Simple workflow execution task that executes nodes linearly.
    Supports HTTP, Delay, and Email nodes directly.
    """
    import time
    
    try:
        execution = WorkflowExecution.objects.select_related('workflow').get(id=execution_id)
        workflow = execution.workflow
        
        # Mark as running
        execution.status = "running"
        execution.started_at = timezone.now()
        execution.logs = "Starting execution"
        execution.node_results = {}
        execution.save(update_fields=['status', 'started_at', 'logs', 'node_results'])
        
        # Get graph
        graph = workflow.graph or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        if not nodes:
            execution.status = "completed"
            execution.finished_at = timezone.now()
            execution.logs = "No nodes to execute"
            execution.save(update_fields=['status', 'finished_at', 'logs'])
            return
        
        # Build node lookup
        nodes_by_id = {node.get("id"): node for node in nodes}
        
        # Simple execution order: follow edges or use array order
        execution_order = []
        if edges:
            # Build dependency map
            targets = {edge.get("to") or edge.get("target") for edge in edges}
            sources = {edge.get("from") or edge.get("source") for edge in edges}
            start_nodes = [nid for nid in nodes_by_id.keys() if nid not in targets]
            
            # Simple BFS traversal
            visited = set()
            queue = list(start_nodes) if start_nodes else list(nodes_by_id.keys())[:1]
            
            while queue:
                node_id = queue.pop(0)
                if node_id in visited:
                    continue
                visited.add(node_id)
                execution_order.append(node_id)
                
                # Add connected nodes
                for edge in edges:
                    source = edge.get("from") or edge.get("source")
                    target = edge.get("to") or edge.get("target")
                    if source == node_id and target not in visited:
                        queue.append(target)
            
            # Add any remaining nodes
            for node_id in nodes_by_id.keys():
                if node_id not in visited:
                    execution_order.append(node_id)
        else:
            # No edges, use array order
            execution_order = [node.get("id") for node in nodes]
        
        # Execute nodes in order
        logs = ["Starting execution"]
        node_results = {}
        
        for node_id in execution_order:
            node = nodes_by_id.get(node_id)
            if not node:
                continue
            
            node_type = node.get("type")
            node_config = node.get("config", {})
            
            log_msg = f"Executing node {node_id} ({node_type})"
            logs.append(log_msg)
            logger.info(log_msg)
            
            try:
                if node_type == "trigger":
                    node_results[node_id] = {"message": "trigger start"}
                    logs.append(f"  Trigger node {node_id} started")
                    
                elif node_type == "http" or node_type == "http_request":
                    # HTTP Request node
                    method = node_config.get("method", "GET").upper()
                    url = node_config.get("url", "")
                    headers = {}
                    
                    # Process headers array
                    headers_list = node_config.get("headers", [])
                    if isinstance(headers_list, list):
                        for h in headers_list:
                            if isinstance(h, dict) and h.get("key"):
                                headers[h["key"]] = h.get("value", "")
                    
                    body = node_config.get("body", "")
                    
                    if not url:
                        raise ValueError("URL is required for HTTP node")
                    
                    # Make request
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=body if method in ["POST", "PUT", "PATCH"] else None,
                        timeout=15
                    )
                    
                    body_preview = response.text[:500] if response.text else ""
                    result = {
                        "status_code": response.status_code,
                        "body_preview": body_preview,
                        "headers": dict(response.headers)
                    }
                    
                    node_results[node_id] = result
                    logs.append(f"  HTTP {method} {url} → {response.status_code}")
                    logs.append(f"  Response preview: {body_preview[:100]}...")
                    
                elif node_type == "delay":
                    # Delay node
                    amount = node_config.get("amount", 5)
                    unit = node_config.get("unit", "seconds")
                    
                    # Convert to seconds
                    if unit == "minutes":
                        seconds = amount * 60
                    elif unit == "hours":
                        seconds = amount * 3600
                    else:
                        seconds = amount
                    
                    logs.append(f"  Sleeping for {seconds} seconds ({amount} {unit})")
                    time.sleep(seconds)
                    
                    node_results[node_id] = {
                        "delay_seconds": seconds,
                        "amount": amount,
                        "unit": unit
                    }
                    logs.append(f"  Delay completed")
                    
                elif node_type == "email_send":
                    # Email node
                    from_email = node_config.get("from", "") or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
                    to_emails = node_config.get("to", "")
                    subject = node_config.get("subject", "")
                    body = node_config.get("body", "")
                    
                    if not to_emails:
                        raise ValueError("Recipient email is required")
                    
                    # Split comma-separated emails
                    to_list = [e.strip() for e in to_emails.split(",") if e.strip()]
                    
                    # Send email
                    send_mail(
                        subject=subject or "(No subject)",
                        message=body,
                        from_email=from_email,
                        recipient_list=to_list,
                        fail_silently=False
                    )
                    
                    node_results[node_id] = {
                        "from": from_email,
                        "to": to_list,
                        "subject": subject,
                        "sent": True
                    }
                    logs.append(f"  Email sent to: {', '.join(to_list)}")
                    
                else:
                    # Unknown node type
                    logs.append(f"  Unknown node type: {node_type}, skipping")
                    node_results[node_id] = {"skipped": True, "reason": "Unknown node type"}
                
            except Exception as e:
                # Node execution failed
                error_msg = str(e)
                error_traceback = traceback.format_exc()
                
                logs.append(f"  ERROR: {error_msg}")
                logs.append(f"  Traceback: {error_traceback}")
                
                node_results[node_id] = {
                    "error": error_msg,
                    "failed": True
                }
                
                # Mark execution as failed
                execution.status = "failed"
                execution.finished_at = timezone.now()
                execution.error_message = f"Node {node_id} failed: {error_msg}"
                execution.traceback = error_traceback
                execution.logs = "\n".join(logs)
                execution.node_results = sanitize_payload(node_results)
                execution.save(update_fields=['status', 'finished_at', 'error_message', 'traceback', 'logs', 'node_results'])
                return
        
        # All nodes completed successfully
        execution.status = "success"
        execution.finished_at = timezone.now()
        execution.logs = "\n".join(logs)
        execution.node_results = sanitize_payload(node_results)
        execution.save(update_fields=['status', 'finished_at', 'logs', 'node_results'])
        
        logger.info(f"Workflow execution {execution_id} completed successfully")
        
    except WorkflowExecution.DoesNotExist:
        logger.error(f"WorkflowExecution {execution_id} not found")
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        try:
            execution = WorkflowExecution.objects.get(id=execution_id)
            execution.status = "failed"
            execution.finished_at = timezone.now()
            execution.error_message = str(e)
            execution.traceback = traceback.format_exc()
            execution.logs = execution.logs + "\n" + f"Fatal error: {str(e)}"
            execution.save(update_fields=['status', 'finished_at', 'error_message', 'traceback', 'logs'])
        except:
            pass


@shared_task
def run_workflow_execution(execution_id):
    """
    Main workflow execution task using EnhancedExecutionEngine with READY queue and idempotency.
    PHASE-1: Ensures capacity is ALWAYS released, even on exceptions.
    """
    execution = None
    capacity_acquired = False
    try:
        execution = WorkflowExecution.objects.select_related("workflow", "tenant").get(id=execution_id)
        
        # PHASE-1: Fail fast if tenant is missing
        if not execution.tenant:
            logger.error(f"WorkflowExecution {execution_id} has no tenant - cannot execute")
            execution.mark_failed(
                error_message="Execution missing tenant_id",
                traceback=""
            )
            return {"status": "failed", "error": "Missing tenant"}
        
        # Validate workflow graph before execution
        if not execution.workflow.graph:
            error_msg = "Workflow has no graph defined"
            logger.error(f"Execution {execution_id}: {error_msg}")
            execution.mark_failed(
                error_message=error_msg,
                traceback=""
            )
            return {"status": "failed", "error": error_msg}
        
        nodes = execution.workflow.graph.get("nodes", [])
        if not nodes:
            error_msg = "Workflow graph has no nodes"
            logger.error(f"Execution {execution_id}: {error_msg}")
            execution.mark_failed(
                error_message=error_msg,
                traceback=""
            )
            return {"status": "failed", "error": error_msg}
        
        # Check for trigger nodes
        trigger_types = {'webhook', 'schedule', 'manual', 'trigger'}
        has_trigger = any(
            (node.get('action_type') or node.get('type', '')).lower() in trigger_types 
            for node in nodes
        )
        
        if not has_trigger:
            error_msg = f"Workflow has no trigger nodes. Available nodes: {[n.get('id', 'unknown') for n in nodes]}"
            logger.error(f"Execution {execution_id}: {error_msg}")
            execution.mark_failed(
                error_message=error_msg,
                traceback=""
            )
            return {"status": "failed", "error": error_msg}
        
        # Set DB session tenant for RLS
        try:
            tenant_id = str(execution.tenant_id or execution.tenant.id)
            if tenant_id:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET app.tenant_id = %s", [tenant_id])
        except Exception as e:
            logger.warning(f"Failed to set tenant context: {e}")
        
        # Gate QUEUED → RUNNING on capacity
        if not NodeExecutionQueue.acquire_execution_capacity(execution):
            # Requeue after short delay
            run_workflow_execution.apply_async(args=[execution_id], countdown=2)
            return {"status": "requeued"}
        
        capacity_acquired = True
        
        # Run engine with comprehensive error handling
        try:
            engine = EnhancedExecutionEngine(execution)
            result = engine.run()
            
            # Release capacity on success
            NodeExecutionQueue.release_execution_capacity(execution)
            capacity_acquired = False
            
            # NOTIFICATION TRIGGER (SUCCESS)
            try:
                from notifications.services import create_notification
                create_notification(
                    user=execution.workflow.owner,
                    type='success',
                    title='Workflow Succeeded',
                    message=f"Workflow '{execution.workflow.name}' executed successfully.",
                    link=f"/workflows/executions/{execution.id}/"
                )
            except Exception as e:
                logger.warning(f"Failed to send success notification: {e}")
            
            return result
            
        except ValueError as e:
            # Validation errors (like no trigger nodes)
            logger.error(f"Workflow validation error: {e}")
            execution.mark_failed(
                error_message=f"Validation error: {str(e)}",
                traceback=traceback.format_exc()
            )
            return {"status": "failed", "error": str(e)}
            
        except Exception as e:
            # Unexpected execution errors
            logger.error(f"Workflow execution engine error: {e}", exc_info=True)
            execution.mark_failed(
                error_message=f"Execution engine error: {str(e)}",
                traceback=traceback.format_exc()
            )
            
            # NOTIFICATION TRIGGER (ERROR)
            try:
                from notifications.services import create_notification
                create_notification(
                    user=execution.workflow.owner,
                    type='error',
                    title='Workflow Failed',
                    message=f"Workflow '{execution.workflow.name}' encountered an error: {str(e)}",
                    link=f"/workflows/executions/{execution.id}/"
                )
            except Exception as n_e:
                logger.warning(f"Failed to send error notification: {n_e}")

            return {"status": "failed", "error": str(e)}
        
    except WorkflowExecution.DoesNotExist:
        error_msg = f"WorkflowExecution {execution_id} not found"
        logger.error(error_msg)
        return {"status": "failed", "error": error_msg}
        
    except Exception as e:
        logger.error(f"Workflow execution task failed: {e}", exc_info=True)
        try:
            if execution is None:
                execution = WorkflowExecution.objects.get(id=execution_id)
            execution.mark_failed(
                error_message=f"Task execution error: {str(e)}",
                traceback=traceback.format_exc()
            )
        except Exception as e2:
            logger.error(f"Failed to mark execution as failed: {e2}", exc_info=True)
        return {"status": "failed", "error": str(e)}
        
    finally:
        # PHASE-1: ALWAYS release capacity, even if exception occurred
        if capacity_acquired and execution:
            try:
                NodeExecutionQueue.release_execution_capacity(execution)
            except Exception as e:
                logger.error(f"Failed to release capacity: {e}", exc_info=True)
            try:
                NodeExecutionQueue.release_execution_capacity(execution)
            except Exception as e:
                logger.error(f"Failed to release capacity: {e}", exc_info=True)


@shared_task
def execute_workflow(execution_id: str):
    """
    LEGACY EXECUTOR - DEPRECATED
    This function has been disabled to ensure all workflows use the Enhanced Core Engine.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.critical(f"🛑 BLOCKED LEGACY EXECUTION ATTEMPT: {execution_id}")
    raise Exception("Legacy execution path is disabled. Please use Enhanced Execution Engine.")

    # Original code commented out below for reference
    # import time
    # import traceback
    # import ast

    def _headers_from_list(lst):
        h = {}
        if isinstance(lst, list):
            for item in lst:
                if isinstance(item, dict) and item.get("key"):
                    h[item["key"]] = item.get("value", "")
        return h

    def _safe_eval(expr, payload):
        try:
            tree = ast.parse(expr, mode="eval")
            allowed = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Load, ast.Constant, ast.And, ast.Or, ast.NotEq, ast.Eq, ast.Gt, ast.GtE, ast.Lt, ast.LtE)
            for node in ast.walk(tree):
                if not isinstance(node, allowed):
                    raise ValueError("Unsupported expression")
            return bool(eval(compile(tree, filename="<expr>", mode="eval"), {"__builtins__": {}}, {"payload": payload}))
        except Exception:
            return False

    try:
        execution = WorkflowExecution.objects.select_related("workflow").get(id=execution_id)
        workflow = execution.workflow

        execution.status = "running"
        execution.started_at = timezone.now()
        execution.logs = "Starting execution"
        execution.node_results = {}
        execution.save(update_fields=["status", "started_at", "logs", "node_results"])

        # CRITICAL LOG: Simple Executor Start
        logger.critical(f"🚀 SIMPLE EXECUTOR START: {execution_id}")

        graph = workflow.graph or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if not nodes:
            execution.status = "completed"
            execution.finished_at = timezone.now()
            execution.logs = "No nodes to execute"
            execution.save(update_fields=["status", "finished_at", "logs"])
            return

        nodes_by_id = {n.get("id"): n for n in nodes}

        has_trigger = any((n.get("type") == "trigger") for n in nodes)
        if not has_trigger:
            execution.status = "failed"
            execution.finished_at = timezone.now()
            execution.error_message = "No trigger node found"
            execution.save(update_fields=["status", "finished_at", "error_message"])
            return

        targets = {e.get("to") or e.get("target") for e in edges}
        start_nodes = [nid for nid, n in nodes_by_id.items() if n.get("type") == "trigger"]
        if not start_nodes:
            start_nodes = [nid for nid in nodes_by_id.keys() if nid not in targets]

        visited = set()
        queue = list(start_nodes) if start_nodes else list(nodes_by_id.keys())[:1]

        logs = ["Starting execution"]
        node_results = {}
        payload = {}

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node = nodes_by_id.get(node_id)
            if not node:
                continue

            node_type = node.get("type")
            cfg = node.get("config", {})

            step = None
            try:
                step = WorkflowExecutionStep.objects.create(
                    execution=execution,
                    node_id=node_id,
                    node_type=node_type,
                    status="running",
                    input={"payload": payload, "config": cfg},
                )
            except Exception:
                step = None

            try:
                if node_type == "trigger":
                    out = {"message": "trigger start"}
                    node_results[node_id] = out
                    if step:
                        step.status = "completed"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                    logs.append(f"Trigger {node_id} started")
                    logger.critical(f"🚀 SIMPLE EXECUTOR: Trigger {node_id} executed")
                    
                elif node_type in ("http", "http_request"):
                    method = str(cfg.get("method", "GET")).upper()
                    url = cfg.get("url", "")
                    headers = _headers_from_list(cfg.get("headers", []))
                    body = cfg.get("body", "")
                    if not url:
                        raise ValueError("URL is required")
                    resp = requests.request(method=method, url=url, headers=headers, data=body if method in ("POST", "PUT", "PATCH") else None, timeout=15)
                    body_preview = resp.text[:500] if resp.text else ""
                    out = {"status_code": resp.status_code, "headers": dict(resp.headers), "body_preview": body_preview}
                    node_results[node_id] = out
                    payload.update({f"{node_id}_status": resp.status_code, f"{node_id}_body": body_preview})
                    if step:
                        step.status = "completed"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                    logs.append(f"HTTP {method} {url} → {resp.status_code}")

                elif node_type == "delay":
                    amount = cfg.get("amount", 0)
                    unit = cfg.get("unit", "seconds")
                    if amount is None or int(amount) < 0:
                        raise ValueError("Delay amount must be >= 0")
                    amount = int(amount)
                    seconds = amount if unit == "seconds" else amount * 60 if unit == "minutes" else amount * 3600
                    time.sleep(seconds)
                    out = {"delay_seconds": seconds, "amount": amount, "unit": unit}
                    node_results[node_id] = out
                    if step:
                        step.status = "completed"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                    logs.append(f"Delay {seconds}s completed")

                elif node_type == "email_send":
                    from_email = cfg.get("from", "") or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
                    to_emails = cfg.get("to", "")
                    subject = cfg.get("subject", "")
                    body = cfg.get("body", "")
                    if not to_emails:
                        raise ValueError("Recipient is required")
                    to_list = [e.strip() for e in str(to_emails).split(",") if e.strip()]
                    
                    logger.critical(f"🚀 SIMPLE EXECUTOR: Sending Email to {to_list}")
                    logger.critical(f"🚀 SIMPLE EXECUTOR: Using default send_mail (Might be Console/SMTP)")
                    
                    send_mail(subject=subject or "(No subject)", message=body, from_email=from_email, recipient_list=to_list, fail_silently=False)
                    out = {"from": from_email, "to": to_list, "subject": subject, "sent": True}
                    node_results[node_id] = out
                    if step:
                        step.status = "completed"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                    logs.append(f"Email sent to {', '.join(to_list)}")
                    logger.critical(f"🚀 SIMPLE EXECUTOR: Email Sent Successfully")

                elif node_type == "condition":
                    expr = cfg.get("expression", "True")  # Use Python boolean
                    ok = _safe_eval(expr, payload)
                    out = {"expression": expr, "result": ok}
                    node_results[node_id] = out
                    step.status = "completed"
                    step.output = out
                    step.save(update_fields=["status", "output"])
                    logs.append(f"Condition → {ok}")
                    if not ok:
                        break

                elif node_type == "webhook":
                    method = str(cfg.get("method", "POST")).upper()
                    url = cfg.get("url", cfg.get("path", ""))
                    headers = _headers_from_list(cfg.get("headers", []))
                    body = cfg.get("body", "")
                    if not url:
                        out = {"skipped": True}
                        node_results[node_id] = out
                        step.status = "skipped"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                        logs.append("Webhook node skipped")
                    else:
                        resp = requests.request(method=method, url=url, headers=headers, data=body if method in ("POST", "PUT", "PATCH") else None, timeout=15)
                        body_preview = resp.text[:500] if resp.text else ""
                        out = {"status_code": resp.status_code, "body_preview": body_preview}
                        node_results[node_id] = out
                        step.status = "completed"
                        step.output = out
                        step.save(update_fields=["status", "output"])
                        logs.append(f"Webhook {method} {url} → {resp.status_code}")

                else:
                    out = {"skipped": True, "reason": "Unknown node type"}
                    node_results[node_id] = out
                    step.status = "skipped"
                    step.output = out
                    step.save(update_fields=["status", "output"])
                    logs.append(f"Unknown node type {node_type}")

                for e in edges:
                    s = e.get("from") or e.get("source")
                    t = e.get("to") or e.get("target")
                    if s == node_id and t not in visited:
                        queue.append(t)

            except Exception as e:
                err = str(e)
                tb = traceback.format_exc()
                if step:
                    step.status = "failed"
                    step.output = {"error": err}
                    step.save(update_fields=["status", "output"])
                # Record node error in aggregated results for test visibility
                node_results[node_id] = {"error": err}
                logs.append(f"ERROR: {err}")
                execution.status = "failed"
                execution.finished_at = timezone.now()
                execution.error_message = err
                execution.traceback = tb
                execution.logs = "\n".join(logs)
                execution.node_results = node_results
                execution.save(update_fields=["status", "finished_at", "error_message", "traceback", "logs", "node_results"])
                
                # Handle chat workflow completion for failures
                try:
                    if execution.triggered_by == 'chat':
                        handle_chat_workflow_completion(execution)
                except Exception as chat_err:
                    logger.error(f"Error handling chat workflow failure: {chat_err}", exc_info=True)
                
                return

        execution.status = "success"
        execution.finished_at = timezone.now()
        execution.logs = "\n".join(logs)
        execution.node_results = node_results
        execution.save(update_fields=["status", "finished_at", "logs", "node_results"])
        
        # Handle chat workflow completion
        try:
            if execution.triggered_by == 'chat':
                handle_chat_workflow_completion(execution)
        except Exception as e:
            logger.error(f"Error handling chat workflow completion: {e}", exc_info=True)

    except WorkflowExecution.DoesNotExist:
        logger.error(f"WorkflowExecution {execution_id} not found")
    except Exception as e:
        try:
            execution = WorkflowExecution.objects.get(id=execution_id)
            execution.status = "failed"
            execution.finished_at = timezone.now()
            execution.error_message = str(e)
            execution.traceback = traceback.format_exc()
            execution.save(update_fields=["status", "finished_at", "error_message", "traceback"])
        except Exception:
            pass
