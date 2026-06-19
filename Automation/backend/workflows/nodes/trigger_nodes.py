from typing import Dict, Any, List, Type, Optional
import os
import json
import logging
from .base_node import TriggerNode, NodeExecutionError
from .registry import register_node

logger = logging.getLogger(__name__)

@register_node
class WebhookTriggerNode(TriggerNode):
    """
    Webhook Trigger Node - starts workflow when a POST/GET request is received.
    """
    NODE_TYPE = "webhook_trigger"
    DISPLAY_NAME = "Webhook Trigger"
    DESCRIPTION = "Starts workflow via an external HTTP request (Webhook)"
    CATEGORY = "TRIGGERS"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Webhook execution receives the HTTP request data.
        """
        method = input_data.get('method', 'POST')
        body = input_data.get('body', {})
        query = input_data.get('query', {})
        headers = input_data.get('headers', {})
        
        return {
            "success": True,
            "output": {
                "method": method,
                "body": body,
                "query": query,
                "headers": headers,
                "workflow_id": context.get('workflow_id')
            }
        }
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "title": "Webhook Path",
                    "description": "URL path for webhook endpoint (e.g., /my-hook)",
                    "placeholder": "/my-hook",
                    "required": True
                },
                "method": {
                    "type": "select",
                    "options": ["GET", "POST"],
                    "default": "POST",
                    "title": "HTTP Method",
                    "description": "HTTP method that triggers the webhook"
                },
                "authentication": {
                    "type": "boolean",
                    "title": "Authentication",
                    "description": "Require authentication to trigger this webhook",
                    "default": False
                },
                "secret_token": {
                    "type": "string",
                    "title": "Secret Token",
                    "description": "Secret token required to authenticate (if enabled)",
                    "format": "password",
                    "visible_if": {
                        "field": "authentication",
                        "equals": True
                    }
                }
            },
            "required": ["path"]
        }


@register_node
class ScheduleTriggerNode(TriggerNode):
    """
    Schedule Trigger Node - starts workflow based on a cron expression.
    """
    NODE_TYPE = "schedule_trigger"
    DISPLAY_NAME = "Schedule Trigger"
    DESCRIPTION = "Starts workflow automatically on a timed schedule"
    CATEGORY = "TRIGGERS"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scheduled execution.
        """
        return {
            "success": True,
            "output": {
                "executed_at": context.get('execution_time'),
                "trigger": "scheduled"
            }
        }
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cron_expression": {
                    "type": "string",
                    "title": "Cron Expression",
                    "description": "Cron expression for schedule (e.g., '0 9 * * 1-5' for weekdays at 9 AM)",
                    "placeholder": "* * * * *",
                    "default": "0 0 * * *"
                },
                "timezone": {
                    "type": "select",
                    "title": "Timezone",
                    "description": "Timezone for schedule execution",
                    "default": "UTC",
                    "options": [
                        "UTC",
                        "Asia/Kolkata", 
                        "America/New_York", 
                        "Europe/London"
                    ]
                },
                "run_info": {
                    "type": "string",
                    "title": "Info",
                    "default": "Runs workflow automatically on schedule",
                    "readOnly": True
                }
            },
            "required": ["cron_expression"]
        }


@register_node
class ManualTriggerNode(TriggerNode):
    """
    Manual Trigger Node - starts workflow when manually triggered by user.
    """
    NODE_TYPE = "manual_trigger"
    DISPLAY_NAME = "Manual Trigger"
    DESCRIPTION = "Starts workflow manually from the builder or dashboard"
    CATEGORY = "TRIGGERS"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manually triggered node usually receives initial data from context.
        """
        manual_data = context.get('manual_data', {})
        trigger_data = input_data.get('trigger_data', {})
        
        return {
            "success": True,
            "output": {
                "started": True,
                "manual": manual_data,
                "trigger_data": trigger_data,
                **trigger_data
            },
            "error": None
        }
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "info": {
                    "type": "string",
                    "title": "Info",
                    "default": "This trigger starts the workflow manually for testing and debugging.",
                    "readOnly": True
                }
            }
        }