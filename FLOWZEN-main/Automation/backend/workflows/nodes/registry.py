"""
Node Registry System

This module provides the central registry for all workflow node types.
It enables dynamic node discovery and type mapping.
"""

from typing import Dict, Type, List, Optional, Any
import importlib
import pkgutil
import logging
from .base_node import BaseNode


logger = logging.getLogger(__name__)


class NodeRegistry:
    """
    Central registry for all workflow node types.
    
    Provides dynamic node discovery and type mapping.
    This is the core system that maps JSON node types to Python classes.
    """
    
    def __init__(self):
        self._nodes: Dict[str, Type[BaseNode]] = {}
        self._auto_discovered = False
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def register(self, node_class: Type[BaseNode]) -> None:
        """
        Register a node class manually.
        
        Args:
            node_class: Class that inherits from BaseNode
            
        Raises:
            ValueError: If class doesn't inherit from BaseNode or type already registered
        """
        if not issubclass(node_class, BaseNode):
            raise ValueError(f"{node_class} must inherit from BaseNode")
        
        node_type = node_class.get_node_type()
        
        if node_type in self._nodes:
            self.logger.warning(f"⚠️ Duplicate node type '{node_type}' detected. Skipping second registration.")
            return
        
        self._nodes[node_type] = node_class
        self.logger.info(f"Registered node: {node_type} -> {node_class.__name__}")
    
    def unregister(self, node_type: str) -> None:
        """
        Unregister a node type.
        
        Args:
            node_type: Node type to unregister
        """
        if node_type in self._nodes:
            del self._nodes[node_type]
            self.logger.info(f"Unregistered node: {node_type}")
    
    def get_node_class(self, node_type: str) -> Type[BaseNode]:
        """
        Get node class by type string.
        
        Args:
            node_type: Node type from workflow JSON
            
        Returns:
            Node class ready for instantiation
            
        Raises:
            KeyError: If node type not found
        """
        if not self._auto_discovered:
            self.auto_discover()
        
        # Normalize node type (hyphen to underscore)
        normalized_type = node_type.replace('-', '_')
        
        if normalized_type not in self._nodes:
            # Try original if normalization didn't help (safety)
            if node_type not in self._nodes:
                raise KeyError(f"Unknown node type: {node_type}. Available types: {list(self._nodes.keys())}")
            normalized_type = node_type
            
        return self._nodes[normalized_type]
    
    def has_node_type(self, node_type: str) -> bool:
        """
        Check if node type is registered.
        
        Args:
            node_type: Node type to check
            
        Returns:
            True if node type is registered
        """
        if not self._auto_discovered:
            self.auto_discover()
        
        # Normalize node type (hyphen to underscore)
        normalized_type = node_type.replace('-', '_')
        
        return normalized_type in self._nodes or node_type in self._nodes
    
    def list_node_types(self) -> List[str]:
        """
        Return all registered node types.
        
        Returns:
            List of node type strings
        """
        if not self._auto_discovered:
            self.auto_discover()
        return list(self._nodes.keys())
    
    def get_nodes_by_category(self, category: str) -> Dict[str, Type[BaseNode]]:
        """
        Get all nodes in a specific category.
        
        Args:
            category: Category name (e.g., 'triggers', 'actions', 'utilities')
            
        Returns:
            Dict mapping node types to classes for the category
        """
        if not self._auto_discovered:
            self.auto_discover()
        
        return {
            node_type: node_class 
            for node_type, node_class in self._nodes.items()
            if node_class.get_category() == category
        }
    
    def get_node_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Return parameter schemas for all nodes.
        
        Used by the UI to generate node parameter forms.
        
        Returns:
            Dict mapping node types to their complete schema information
        """
        if not self._auto_discovered:
            self.auto_discover()
        
        schemas = {}
        for node_type, node_class in self._nodes.items():
            try:
                schemas[node_type] = {
                    "type": node_type,
                    "name": node_class.get_display_name(),
                    "description": node_class.get_description(),
                    "category": node_class.get_category(),
                    "parameter_schema": node_class.get_schema(),
                    "input_schema": node_class().get_input_schema(),
                    "output_schema": node_class().get_output_schema(),
                    "supports_retry": node_class().supports_retry(),
                    "default_timeout": node_class().get_timeout()
                }
            except Exception as e:
                self.logger.error(f"Error getting schema for {node_type}: {e}")
                schemas[node_type] = {
                    "type": node_type,
                    "name": node_class.get_display_name(),
                    "description": f"Error loading schema: {e}",
                    "category": "unknown",
                    "parameter_schema": {"type": "object", "properties": {}},
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "supports_retry": True,
                    "default_timeout": 30
                }
        
        return schemas
    
    def auto_discover(self) -> None:
        """
        Automatically discover and register nodes from workflows.nodes package.
        
        This method scans all Python modules in the workflows.nodes package
        and automatically registers any BaseNode subclasses it finds.
        """
        if self._auto_discovered:
            return
        
        try:
            # Import the nodes package
            from workflows import nodes as nodes_package
            
            # Walk through all modules in workflows.nodes
            for importer, modname, ispkg in pkgutil.iter_modules(
                nodes_package.__path__, 
                nodes_package.__name__ + "."
            ):
                # Skip the base modules
                if modname.endswith('.base_node') or modname.endswith('.registry'):
                    continue
                
                try:
                    module = importlib.import_module(modname)
                    
                    # Find all BaseNode subclasses in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseNode) and 
                            attr not in (BaseNode,) and
                            not attr.__name__.startswith('Base') and
                            not getattr(attr, '__abstractmethods__', None)):
                            
                            try:
                                # Check if already registered (via decorator during import)
                                node_type = attr.get_node_type()
                                if node_type not in self._nodes:
                                    self.register(attr)
                            except ValueError as e:
                                # Node already registered, skip
                                if "already registered" in str(e):
                                    continue
                                raise
                                
                except ImportError as e:
                    self.logger.warning(f"Could not import {modname}: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing module {modname}: {e}")
                    
        except ImportError:
            self.logger.warning("workflows.nodes package not found for auto-discovery")
        except Exception as e:
            self.logger.error(f"Error during auto-discovery: {e}")
        
        self._auto_discovered = True
        self.logger.info(f"Auto-discovery complete. Registered {len(self._nodes)} node types.")
    
    def validate_workflow_nodes(self, workflow_definition: Dict[str, Any]) -> List[str]:
        """
        Validate that all nodes in a workflow definition are registered.
        
        Args:
            workflow_definition: Complete workflow JSON
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check trigger
        if 'trigger' in workflow_definition:
            trigger_type = workflow_definition['trigger'].get('type')
            if trigger_type and not self.has_node_type(trigger_type):
                errors.append(f"Unknown trigger type: {trigger_type}")
        
        # Check nodes
        if 'nodes' in workflow_definition:
            for node_id, node_def in workflow_definition['nodes'].items():
                node_type = node_def.get('type')
                if node_type and not self.has_node_type(node_type):
                    errors.append(f"Unknown node type: {node_type} (node: {node_id})")
        
        return errors
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics for monitoring.
        
        Returns:
            Dict with registry statistics
        """
        if not self._auto_discovered:
            self.auto_discover()
        
        categories = {}
        for node_class in self._nodes.values():
            category = node_class.get_category()
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_nodes": len(self._nodes),
            "categories": categories,
            "node_types": list(self._nodes.keys()),
            "auto_discovered": self._auto_discovered
        }


# Global registry instance
node_registry = NodeRegistry()

# STATIC REGISTRY - Single source of truth for all node types
# Exposing this explicitly as requested to avoid private internal access.
NODE_REGISTRY: Dict[str, Type[BaseNode]] = {}


def register_node(cls: Type[BaseNode]) -> Type[BaseNode]:
    """
    Decorator to register a node class.
    
    Usage:
        @register_node
        class MyCustomNode(BaseNode):
            pass
    
    Args:
        cls: Node class to register
        
    Returns:
        The same class (for decorator pattern)
    """
    node_registry.register(cls)
    
    # Also update the static registry
    node_type = cls.get_node_type()
    NODE_REGISTRY[node_type] = cls
    
    return cls


def get_node_class(node_type: str) -> Type[BaseNode]:
    """
    Convenience function to get a node class.
    
    Args:
        node_type: Node type string
        
    Returns:
        Node class
    """
    return node_registry.get_node_class(node_type)


def list_available_nodes() -> List[str]:
    """
    Convenience function to list all available node types.
    
    Returns:
        List of node type strings
    """
    return node_registry.list_node_types()


# Explicit imports removed to prevent circular dependency
# Triggers are registered via __init__.py and auto_discovery

# ALIAS REGISTRATION
# Register whatsapp-send as an alias for whatsapp_send to support existing workflow JSONs
from .whatsapp_nodes import WhatsAppSendNode
NODE_REGISTRY["whatsapp-send"] = WhatsAppSendNode
node_registry._nodes["whatsapp-send"] = WhatsAppSendNode
