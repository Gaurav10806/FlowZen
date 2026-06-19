"""
Enhanced HTTP Node Plugin - Main Entry Point

This is the main entry point for the Enhanced HTTP Node plugin.
All node classes are imported and registered here.
"""

# Import the node class - this will automatically register it via @register_node decorator
from .src.enhanced_http_node import EnhancedHttpNode

# Plugin metadata
__version__ = "1.2.0"
__author__ = "John Developer"
__description__ = "Enhanced HTTP Request Node with advanced features"

# Export the node class for external access
__all__ = ['EnhancedHttpNode']

# Plugin initialization
def initialize_plugin():
    """
    Initialize the plugin.
    This function is called when the plugin is loaded.
    """
    print(f"Enhanced HTTP Node Plugin v{__version__} loaded successfully")
    return True

# Plugin cleanup
def cleanup_plugin():
    """
    Clean up plugin resources.
    This function is called when the plugin is unloaded.
    """
    print("Enhanced HTTP Node Plugin unloaded")
    return True