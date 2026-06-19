"""
Workflow Node System

This package contains the complete node system for the n8n-like workflow automation platform.
All workflow nodes must inherit from BaseNode and be registered in the node registry.
"""

from .base_node import BaseNode, NodeExecutionError
from .registry import node_registry, register_node

# Import modules to ensure registration
from . import action_nodes
from . import trigger_nodes
from . import utility_nodes
from . import logic_nodes
from . import ai_agent_node
from . import google_calendar_node
from . import google_calendar_trigger
from . import whatsapp_nodes
from . import telegram_trigger
from . import telegram_send
from . import telegram_chatbot_nodes
from .triggers.gmail_trigger import GmailTriggerNode
from .triggers.youtube_trigger import YouTubeTriggerNode
# Data Nodes
from .google_sheets_node import GoogleSheetsNode
from .database_query_node import DatabaseQueryNode
from .file_storage_node import FileStorageNode
from .bigquery_node import BigQueryNode

# Logic Nodes (Professional)
from .if_else_node import IfElseNode
from .switch_node import SwitchNode
from .delay_node import DelayNode

__all__ = [
    'BaseNode',
    'NodeExecutionError', 
    'node_registry',
    'register_node'
]