"""
Trigger Registry

This module provides a registry for different trigger types and their management.
It acts as a central hub for trigger-related operations.
"""

import logging
from typing import Dict, Any, List, Optional, Type
from enum import Enum

from ..nodes.base_node import TriggerNode
from ..nodes import node_registry
from .webhook_handler import WebhookHandler, get_webhook_url, test_webhook_configuration
from .schedule_manager import ScheduleManager, get_workflow_schedule_status


logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Enumeration of supported trigger types."""
    WEBHOOK = "webhook_trigger"
    SCHEDULE = "schedule_trigger"
    MANUAL = "manual_trigger"
    # Future trigger types
    # EVENT = "event_trigger"
    # DATABASE = "database_trigger"
    # FILE = "file_trigger"


class TriggerRegistry:
    """
    Central registry for trigger types and their management.
    
    This class provides a unified interface for working with different
    trigger types, their configuration, and status.
    """
    
    def __init__(self):
        """Initialize the trigger registry."""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._webhook_handler_cache = {}
        self._schedule_manager = None
    
    def get_available_trigger_types(self) -> List[Dict[str, Any]]:
        """
        Get list of available trigger types with their metadata.
        
        Returns:
            List of trigger type dictionaries
        """
        trigger_types = []
        
        for trigger_type in TriggerType:
            try:
                # Get node class from registry
                node_class = node_registry.get_node_class(trigger_type.value)
                
                trigger_info = {
                    'type': trigger_type.value,
                    'name': node_class.get_display_name(),
                    'description': node_class.get_description(),
                    'category': node_class.get_category(),
                    'schema': node_class.get_schema(),
                    'supports_retry': node_class().supports_retry(),
                    'available': True
                }
                
                # Add type-specific metadata
                if trigger_type == TriggerType.WEBHOOK:
                    trigger_info.update({
                        'supports_authentication': True,
                        'supports_custom_response': True,
                        'real_time': True
                    })
                elif trigger_type == TriggerType.SCHEDULE:
                    trigger_info.update({
                        'supports_cron': True,
                        'supports_timezone': True,
                        'real_time': False
                    })
                elif trigger_type == TriggerType.MANUAL:
                    trigger_info.update({
                        'test_only': True,
                        'real_time': True
                    })
                
                trigger_types.append(trigger_info)
                
            except Exception as e:
                self.logger.warning(f"Failed to get info for trigger type {trigger_type.value}: {e}")
                trigger_types.append({
                    'type': trigger_type.value,
                    'name': trigger_type.value.replace('_', ' ').title(),
                    'available': False,
                    'error': str(e)
                })
        
        return trigger_types
    
    def get_trigger_node_class(self, trigger_type: str) -> Optional[Type[TriggerNode]]:
        """
        Get trigger node class for a trigger type.
        
        Args:
            trigger_type: Trigger type identifier
            
        Returns:
            TriggerNode class or None if not found
        """
        try:
            node_class = node_registry.get_node_class(trigger_type)
            if issubclass(node_class, TriggerNode):
                return node_class
            else:
                self.logger.warning(f"Node class {node_class} is not a TriggerNode")
                return None
        except Exception as e:
            self.logger.error(f"Failed to get trigger node class for {trigger_type}: {e}")
            return None
    
    def validate_trigger_configuration(self, workflow, trigger_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate trigger configuration for a workflow.
        
        Args:
            workflow: Workflow instance
            trigger_config: Trigger configuration dictionary
            
        Returns:
            Validation result dictionary
        """
        trigger_type = trigger_config.get('type')
        if not trigger_type:
            return {
                'valid': False,
                'errors': ['Trigger type is required']
            }
        
        # Get trigger node class
        node_class = self.get_trigger_node_class(trigger_type)
        if not node_class:
            return {
                'valid': False,
                'errors': [f'Unknown trigger type: {trigger_type}']
            }
        
        # Validate parameters against schema
        params = trigger_config.get('params', {})
        errors = []
        
        try:
            # Create node instance and validate
            node_instance = node_class()
            if not node_instance.validate_params(params):
                errors.append('Invalid trigger parameters')
        except Exception as e:
            errors.append(f'Parameter validation failed: {e}')
        
        # Type-specific validation
        if trigger_type == TriggerType.WEBHOOK.value:
            webhook_errors = self._validate_webhook_config(workflow, params)
            errors.extend(webhook_errors)
        elif trigger_type == TriggerType.SCHEDULE.value:
            schedule_errors = self._validate_schedule_config(workflow, params)
            errors.extend(schedule_errors)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'trigger_type': trigger_type
        }
    
    def _validate_webhook_config(self, workflow, params: Dict[str, Any]) -> List[str]:
        """Validate webhook-specific configuration."""
        errors = []
        
        # Check if webhook is enabled on workflow
        if not workflow.webhook_enabled:
            errors.append('Webhook trigger requires webhook_enabled=True on workflow')
        
        # Validate authentication configuration
        auth_method = params.get('authentication', 'none')
        if auth_method != 'none':
            if auth_method == 'hmac_sha256' and not workflow.webhook_secret:
                errors.append('HMAC authentication requires webhook_secret on workflow')
            elif auth_method == 'bearer_token' and not params.get('auth_config', {}).get('token'):
                errors.append('Bearer token authentication requires token in auth_config')
        
        return errors
    
    def _validate_schedule_config(self, workflow, params: Dict[str, Any]) -> List[str]:
        """Validate schedule-specific configuration."""
        errors = []
        
        # Check if scheduling is enabled on workflow
        if not workflow.schedule_enabled:
            errors.append('Schedule trigger requires schedule_enabled=True on workflow')
        
        # Validate cron expression
        cron_expression = params.get('cron_expression')
        if not cron_expression:
            errors.append('Schedule trigger requires cron_expression parameter')
        else:
            try:
                from croniter import croniter
                croniter(cron_expression)
            except Exception as e:
                errors.append(f'Invalid cron expression: {e}')
        
        return errors
    
    def get_trigger_status(self, workflow) -> Dict[str, Any]:
        """
        Get comprehensive trigger status for a workflow.
        
        Args:
            workflow: Workflow instance
            
        Returns:
            Dictionary with trigger status information
        """
        # Determine trigger type from workflow definition
        trigger_config = self._extract_trigger_config(workflow)
        if not trigger_config:
            return {
                'configured': False,
                'error': 'No trigger configuration found in workflow'
            }
        
        trigger_type = trigger_config.get('type')
        status = {
            'configured': True,
            'trigger_type': trigger_type,
            'configuration': trigger_config
        }
        
        # Get type-specific status
        if trigger_type == TriggerType.WEBHOOK.value:
            status.update(self._get_webhook_status(workflow))
        elif trigger_type == TriggerType.SCHEDULE.value:
            status.update(self._get_schedule_status(workflow))
        elif trigger_type == TriggerType.MANUAL.value:
            status.update(self._get_manual_status(workflow))
        else:
            status['error'] = f'Unknown trigger type: {trigger_type}'
        
        return status
    
    def _extract_trigger_config(self, workflow) -> Optional[Dict[str, Any]]:
        """Extract trigger configuration from workflow definition."""
        try:
            definition = workflow.definition or {}
            return definition.get('trigger')
        except Exception as e:
            self.logger.error(f"Failed to extract trigger config from workflow {workflow.id}: {e}")
            return None
    
    def _get_webhook_status(self, workflow) -> Dict[str, Any]:
        """Get webhook-specific status."""
        try:
            # Test webhook configuration
            test_result = test_webhook_configuration(workflow)
            
            status = {
                'webhook_enabled': workflow.webhook_enabled,
                'webhook_url': get_webhook_url(workflow),
                'has_secret': bool(workflow.webhook_secret),
                'configuration_valid': test_result['valid'],
                'issues': test_result['issues']
            }
            
            # Get recent webhook executions
            recent_executions = workflow.executions.filter(
                triggered_by='webhook'
            ).order_by('-created_at')[:5]
            
            status['recent_executions'] = [
                {
                    'id': str(exec.id),
                    'created_at': exec.created_at.isoformat(),
                    'status': exec.status
                }
                for exec in recent_executions
            ]
            
            return status
            
        except Exception as e:
            return {'error': f'Failed to get webhook status: {e}'}
    
    def _get_schedule_status(self, workflow) -> Dict[str, Any]:
        """Get schedule-specific status."""
        try:
            return get_workflow_schedule_status(workflow)
        except Exception as e:
            return {'error': f'Failed to get schedule status: {e}'}
    
    def _get_manual_status(self, workflow) -> Dict[str, Any]:
        """Get manual trigger status."""
        try:
            # Get recent manual executions
            recent_executions = workflow.executions.filter(
                triggered_by='manual'
            ).order_by('-created_at')[:5]
            
            return {
                'always_available': True,
                'recent_executions': [
                    {
                        'id': str(exec.id),
                        'created_at': exec.created_at.isoformat(),
                        'status': exec.status,
                        'created_by': exec.created_by.username if exec.created_by else None
                    }
                    for exec in recent_executions
                ]
            }
            
        except Exception as e:
            return {'error': f'Failed to get manual trigger status: {e}'}
    
    def activate_trigger(self, workflow, trigger_type: str) -> Dict[str, Any]:
        """
        Activate a trigger for a workflow.
        
        Args:
            workflow: Workflow instance
            trigger_type: Type of trigger to activate
            
        Returns:
            Activation result dictionary
        """
        try:
            if trigger_type == TriggerType.WEBHOOK.value:
                return self._activate_webhook_trigger(workflow)
            elif trigger_type == TriggerType.SCHEDULE.value:
                return self._activate_schedule_trigger(workflow)
            elif trigger_type == TriggerType.MANUAL.value:
                return self._activate_manual_trigger(workflow)
            else:
                return {
                    'success': False,
                    'error': f'Unknown trigger type: {trigger_type}'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to activate trigger {trigger_type} for workflow {workflow.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _activate_webhook_trigger(self, workflow) -> Dict[str, Any]:
        """Activate webhook trigger."""
        workflow.webhook_enabled = True
        workflow.save(update_fields=['webhook_enabled'])
        
        return {
            'success': True,
            'webhook_url': get_webhook_url(workflow),
            'message': 'Webhook trigger activated'
        }
    
    def _activate_schedule_trigger(self, workflow) -> Dict[str, Any]:
        """Activate schedule trigger."""
        workflow.schedule_enabled = True
        workflow.save(update_fields=['schedule_enabled'])
        
        # Sync with Celery Beat
        if not self._schedule_manager:
            self._schedule_manager = ScheduleManager()
        
        sync_result = self._schedule_manager.sync_workflow_schedule(workflow)
        
        return {
            'success': True,
            'sync_result': sync_result,
            'message': 'Schedule trigger activated'
        }
    
    def _activate_manual_trigger(self, workflow) -> Dict[str, Any]:
        """Activate manual trigger (always available)."""
        return {
            'success': True,
            'message': 'Manual trigger is always available'
        }
    
    def deactivate_trigger(self, workflow, trigger_type: str) -> Dict[str, Any]:
        """
        Deactivate a trigger for a workflow.
        
        Args:
            workflow: Workflow instance
            trigger_type: Type of trigger to deactivate
            
        Returns:
            Deactivation result dictionary
        """
        try:
            if trigger_type == TriggerType.WEBHOOK.value:
                return self._deactivate_webhook_trigger(workflow)
            elif trigger_type == TriggerType.SCHEDULE.value:
                return self._deactivate_schedule_trigger(workflow)
            elif trigger_type == TriggerType.MANUAL.value:
                return self._deactivate_manual_trigger(workflow)
            else:
                return {
                    'success': False,
                    'error': f'Unknown trigger type: {trigger_type}'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to deactivate trigger {trigger_type} for workflow {workflow.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _deactivate_webhook_trigger(self, workflow) -> Dict[str, Any]:
        """Deactivate webhook trigger."""
        workflow.webhook_enabled = False
        workflow.save(update_fields=['webhook_enabled'])
        
        return {
            'success': True,
            'message': 'Webhook trigger deactivated'
        }
    
    def _deactivate_schedule_trigger(self, workflow) -> Dict[str, Any]:
        """Deactivate schedule trigger."""
        workflow.schedule_enabled = False
        workflow.save(update_fields=['schedule_enabled'])
        
        # Remove from Celery Beat
        if not self._schedule_manager:
            self._schedule_manager = ScheduleManager()
        
        disabled = self._schedule_manager.disable_workflow_schedule(workflow)
        
        return {
            'success': True,
            'task_removed': disabled,
            'message': 'Schedule trigger deactivated'
        }
    
    def _deactivate_manual_trigger(self, workflow) -> Dict[str, Any]:
        """Deactivate manual trigger (cannot be disabled)."""
        return {
            'success': True,
            'message': 'Manual trigger cannot be disabled'
        }


# Global registry instance
trigger_registry = TriggerRegistry()


# Convenience functions
def get_available_trigger_types() -> List[Dict[str, Any]]:
    """Get available trigger types - convenience function."""
    return trigger_registry.get_available_trigger_types()


def get_trigger_status(workflow) -> Dict[str, Any]:
    """Get trigger status for workflow - convenience function."""
    return trigger_registry.get_trigger_status(workflow)


def validate_trigger_configuration(workflow, trigger_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate trigger configuration - convenience function."""
    return trigger_registry.validate_trigger_configuration(workflow, trigger_config)