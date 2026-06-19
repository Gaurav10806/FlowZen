"""
PHASE-1: Observability service for emitting execution events and logs.
"""
import logging
from typing import Dict, Any, Optional
from django.utils import timezone

from ..models import ExecutionEvent, ExecutionLog, WorkflowExecution, NodeExecution, Tenant

logger = logging.getLogger(__name__)


class ObservabilityService:
    """
    Service for emitting execution events and logs for observability.
    """
    
    @staticmethod
    def emit_execution_event(
        execution: WorkflowExecution,
        event_type: str,
        message: str,
        node_execution: Optional[NodeExecution] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionEvent:
        """
        Emit an execution timeline event.
        
        Args:
            execution: Workflow execution
            event_type: Event type (e.g., "execution_started", "node_completed")
            message: Event message
            node_execution: Optional node execution (for node-level events)
            metadata: Optional metadata
            
        Returns:
            ExecutionEvent instance
        """
        # PHASE-1: Ensure tenant is set
        if not execution.tenant:
            logger.error(f"Execution {execution.id} has no tenant - cannot emit event")
            return None
        
        try:
            event = ExecutionEvent.objects.create(
                execution=execution,
                node_execution=node_execution,
                tenant=execution.tenant,
                event_type=event_type,
                message=message,
                metadata=metadata or {},
            )
            logger.debug(f"Emitted event {event_type} for execution {execution.id}")
            return event
        except Exception as e:
            logger.error(f"Failed to emit event {event_type}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def emit_execution_log(
        execution: WorkflowExecution,
        level: str,
        message: str,
        node_execution: Optional[NodeExecution] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionLog:
        """
        Emit an execution log entry.
        
        Args:
            execution: Workflow execution
            level: Log level ("debug", "info", "warning", "error")
            message: Log message
            node_execution: Optional node execution (for node-level logs)
            metadata: Optional metadata
            
        Returns:
            ExecutionLog instance
        """
        # PHASE-1: Ensure tenant is set
        if not execution.tenant:
            logger.error(f"Execution {execution.id} has no tenant - cannot emit log")
            return None
        
        try:
            try:
                log = ExecutionLog.objects.create(
                    execution=execution,
                    node_execution=node_execution,
                    tenant=execution.tenant,
                    level=level,
                    message=message,
                    metadata=metadata or {},
                )
            except TypeError as te:
                if 'tenant' in str(te):
                    # Mismatch fallback: Create without tenant
                    log = ExecutionLog.objects.create(
                        execution=execution,
                        node_execution=node_execution,
                        level=level,
                        message=message,
                        metadata=metadata or {},
                    )
                else:
                    raise te
            return log
        except Exception as e:
            logger.warning(f"Failed to emit log {level}: {e}")
            return None
            logger.debug(f"Emitted log {level} for execution {execution.id}")
            return log
        except Exception as e:
            logger.error(f"Failed to emit log {level}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def emit_execution_started(execution: WorkflowExecution):
        """Emit execution_started event."""
        return ObservabilityService.emit_execution_event(
            execution=execution,
            event_type="execution_started",
            message=f"Execution {execution.id} started",
            metadata={
                "workflow_id": str(execution.workflow_id),
                "triggered_by": execution.triggered_by,
            }
        )
    
    @staticmethod
    def emit_execution_completed(execution: WorkflowExecution):
        """Emit execution_completed event."""
        return ObservabilityService.emit_execution_event(
            execution=execution,
            event_type="execution_completed",
            message=f"Execution {execution.id} completed",
            metadata={
                "workflow_id": str(execution.workflow_id),
            }
        )
    
    @staticmethod
    def emit_execution_failed(execution: WorkflowExecution, error_message: str):
        """Emit execution_failed event."""
        return ObservabilityService.emit_execution_event(
            execution=execution,
            event_type="execution_failed",
            message=f"Execution {execution.id} failed: {error_message}",
            metadata={
                "workflow_id": str(execution.workflow_id),
                "error_message": error_message,
            }
        )
    
    @staticmethod
    def emit_node_started(node_execution: NodeExecution):
        """Emit node_started event."""
        return ObservabilityService.emit_execution_event(
            execution=node_execution.workflow_execution,
            event_type="node_started",
            message=f"Node {node_execution.graph_node_id} started",
            node_execution=node_execution,
            metadata={
                "node_id": node_execution.graph_node_id,
            }
        )
    
    @staticmethod
    def emit_node_completed(node_execution: NodeExecution):
        """Emit node_completed event."""
        return ObservabilityService.emit_execution_event(
            execution=node_execution.workflow_execution,
            event_type="node_completed",
            message=f"Node {node_execution.graph_node_id} completed",
            node_execution=node_execution,
            metadata={
                "node_id": node_execution.graph_node_id,
            }
        )
    
    @staticmethod
    def emit_node_failed(node_execution: NodeExecution, error_message: str):
        """Emit node_failed event."""
        return ObservabilityService.emit_execution_event(
            execution=node_execution.workflow_execution,
            event_type="node_failed",
            message=f"Node {node_execution.graph_node_id} failed: {error_message}",
            node_execution=node_execution,
            metadata={
                "node_id": node_execution.graph_node_id,
                "error_message": error_message,
            }
        )
    
    @staticmethod
    def emit_node_retry(node_execution: NodeExecution, attempt: int):
        """Emit node_retry event."""
        return ObservabilityService.emit_execution_event(
            execution=node_execution.workflow_execution,
            event_type="node_retry",
            message=f"Node {node_execution.graph_node_id} retry attempt {attempt}",
            node_execution=node_execution,
            metadata={
                "node_id": node_execution.graph_node_id,
                "attempt": attempt,
            }
        )

