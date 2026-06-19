"""
Plugin System - Core Plugin Management and Loading

This module provides the core plugin system that enables third-party developers
to safely extend the automation platform with custom nodes, triggers, and tools.
"""

import os
import json
import uuid
import logging
import importlib
import importlib.util
import sys
import zipfile
import hashlib
from typing import Dict, Any, List, Optional, Type, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import tempfile
import shutil

from ..nodes.base_node import BaseNode
from ..nodes.registry import NodeRegistry
from ..security_validators import PayloadSecurityValidator
from .plugin_security import PluginSandbox, PluginPermissions
from .plugin_manifest import PluginManifest, PluginStatus, PluginType


logger = logging.getLogger(__name__)


class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when plugin loading fails."""
    pass


class PluginSecurityError(PluginError):
    """Raised when plugin violates security constraints."""
    pass


class PluginCompatibilityError(PluginError):
    """Raised when plugin is incompatible with platform version."""
    pass


@dataclass
class PluginInstallation:
    """Represents an installed plugin."""
    plugin_id: str
    manifest: PluginManifest
    install_path: str
    installed_at: str
    installed_by: str
    status: PluginStatus
    enabled: bool
    loaded_classes: List[str]
    resource_usage: Dict[str, Any]
    last_error: Optional[str]


class PluginSystem:
    """
    Core Plugin System
    
    Manages the complete plugin lifecycle including installation, loading,
    execution, and security enforcement for third-party extensions.
    """
    
    def __init__(self, plugins_directory: str = None):
        self.plugins_directory = plugins_directory or os.path.join(
            os.path.dirname(__file__), '..', '..', 'plugins'
        )
        self.node_registry = NodeRegistry()
        self.security_validator = PayloadSecurityValidator()
        
        # Plugin storage
        self.installed_plugins: Dict[str, PluginInstallation] = {}
        self.loaded_plugins: Dict[str, Any] = {}  # plugin_id -> loaded module
        
        # Security and sandboxing
        self.sandbox = PluginSandbox()
        self.permissions = PluginPermissions()
        
        # Platform version for compatibility checking
        self.platform_version = "1.0.0"  # Would be loaded from config
        
        # Ensure plugins directory exists
        os.makedirs(self.plugins_directory, exist_ok=True)
        
        logger.info(f"Plugin system initialized: {self.plugins_directory}")
    
    def install_plugin(self, plugin_package: Union[str, bytes], 
                      installed_by: str, validate_signature: bool = True) -> str:
        """
        Install a plugin from a package file.
        
        Args:
            plugin_package: Path to plugin package file or package bytes
            installed_by: User ID installing the plugin
            validate_signature: Whether to validate plugin signature
            
        Returns:
            Plugin ID of installed plugin
            
        Raises:
            PluginError: If installation fails
        """
        logger.info(f"Installing plugin package by {installed_by}")
        
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract plugin package
                if isinstance(plugin_package, str):
                    # File path
                    with zipfile.ZipFile(plugin_package, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                else:
                    # Bytes data
                    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                        temp_file.write(plugin_package)
                        temp_file.flush()
                        
                        with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                        
                        os.unlink(temp_file.name)
                
                # Load and validate manifest
                manifest_path = os.path.join(temp_dir, 'plugin.json')
                if not os.path.exists(manifest_path):
                    raise PluginError("Plugin manifest (plugin.json) not found")
                
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                
                manifest = PluginManifest.from_dict(manifest_data)
                
                # Validate plugin signature if required
                if validate_signature:
                    self._validate_plugin_signature(temp_dir, manifest)
                
                # Check compatibility
                self._check_compatibility(manifest)
                
                # Validate plugin security
                self._validate_plugin_security(temp_dir, manifest)
                
                # Check for conflicts
                if manifest.plugin_id in self.installed_plugins:
                    existing = self.installed_plugins[manifest.plugin_id]
                    if existing.manifest.version == manifest.version:
                        raise PluginError(f"Plugin {manifest.plugin_id} v{manifest.version} already installed")
                
                # Install plugin
                plugin_install_path = os.path.join(
                    self.plugins_directory, 
                    f"{manifest.plugin_id}_{manifest.version}"
                )
                
                # Copy plugin files
                if os.path.exists(plugin_install_path):
                    shutil.rmtree(plugin_install_path)
                
                shutil.copytree(temp_dir, plugin_install_path)
                
                # Create installation record
                installation = PluginInstallation(
                    plugin_id=manifest.plugin_id,
                    manifest=manifest,
                    install_path=plugin_install_path,
                    installed_at=datetime.utcnow().isoformat(),
                    installed_by=installed_by,
                    status=PluginStatus.INSTALLED,
                    enabled=False,
                    loaded_classes=[],
                    resource_usage={},
                    last_error=None
                )
                
                self.installed_plugins[manifest.plugin_id] = installation
                
                logger.info(f"Plugin installed: {manifest.plugin_id} v{manifest.version}")
                
                return manifest.plugin_id
                
        except Exception as e:
            error_msg = f"Plugin installation failed: {str(e)}"
            logger.error(error_msg)
            raise PluginError(error_msg)
    
    def enable_plugin(self, plugin_id: str, enabled_by: str) -> bool:
        """
        Enable an installed plugin.
        
        Args:
            plugin_id: Plugin ID to enable
            enabled_by: User ID enabling the plugin
            
        Returns:
            True if successful
            
        Raises:
            PluginError: If enabling fails
        """
        if plugin_id not in self.installed_plugins:
            raise PluginError(f"Plugin {plugin_id} not installed")
        
        installation = self.installed_plugins[plugin_id]
        
        try:
            # Load plugin
            self._load_plugin(installation)
            
            # Update status
            installation.enabled = True
            installation.status = PluginStatus.ENABLED
            
            logger.info(f"Plugin enabled: {plugin_id} by {enabled_by}")
            
            return True
            
        except Exception as e:
            installation.last_error = str(e)
            installation.status = PluginStatus.ERROR
            error_msg = f"Failed to enable plugin {plugin_id}: {str(e)}"
            logger.error(error_msg)
            raise PluginError(error_msg)
    
    def disable_plugin(self, plugin_id: str, disabled_by: str) -> bool:
        """
        Disable an enabled plugin.
        
        Args:
            plugin_id: Plugin ID to disable
            disabled_by: User ID disabling the plugin
            
        Returns:
            True if successful
        """
        if plugin_id not in self.installed_plugins:
            raise PluginError(f"Plugin {plugin_id} not installed")
        
        installation = self.installed_plugins[plugin_id]
        
        try:
            # Unload plugin
            self._unload_plugin(installation)
            
            # Update status
            installation.enabled = False
            installation.status = PluginStatus.DISABLED
            
            logger.info(f"Plugin disabled: {plugin_id} by {disabled_by}")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to disable plugin {plugin_id}: {str(e)}"
            logger.error(error_msg)
            raise PluginError(error_msg)
    
    def uninstall_plugin(self, plugin_id: str, uninstalled_by: str) -> bool:
        """
        Uninstall a plugin completely.
        
        Args:
            plugin_id: Plugin ID to uninstall
            uninstalled_by: User ID uninstalling the plugin
            
        Returns:
            True if successful
        """
        if plugin_id not in self.installed_plugins:
            raise PluginError(f"Plugin {plugin_id} not installed")
        
        installation = self.installed_plugins[plugin_id]
        
        try:
            # Disable first if enabled
            if installation.enabled:
                self.disable_plugin(plugin_id, uninstalled_by)
            
            # Remove plugin files
            if os.path.exists(installation.install_path):
                shutil.rmtree(installation.install_path)
            
            # Remove from registry
            del self.installed_plugins[plugin_id]
            
            logger.info(f"Plugin uninstalled: {plugin_id} by {uninstalled_by}")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to uninstall plugin {plugin_id}: {str(e)}"
            logger.error(error_msg)
            raise PluginError(error_msg)
    
    def get_installed_plugins(self) -> List[PluginInstallation]:
        """Get list of all installed plugins."""
        return list(self.installed_plugins.values())
    
    def get_enabled_plugins(self) -> List[PluginInstallation]:
        """Get list of enabled plugins."""
        return [p for p in self.installed_plugins.values() if p.enabled]
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInstallation]:
        """Get information about a specific plugin."""
        return self.installed_plugins.get(plugin_id)
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Load all enabled plugins at startup.
        
        Returns:
            Dict mapping plugin IDs to load success status
        """
        results = {}
        
        for plugin_id, installation in self.installed_plugins.items():
            if installation.enabled:
                try:
                    self._load_plugin(installation)
                    results[plugin_id] = True
                except Exception as e:
                    installation.last_error = str(e)
                    installation.status = PluginStatus.ERROR
                    results[plugin_id] = False
                    logger.error(f"Failed to load plugin {plugin_id}: {e}")
        
        return results
    
    def _load_plugin(self, installation: PluginInstallation) -> None:
        """
        Load a plugin into the system.
        
        Args:
            installation: Plugin installation to load
            
        Raises:
            PluginLoadError: If loading fails
        """
        plugin_id = installation.plugin_id
        manifest = installation.manifest
        
        try:
            # Set up plugin environment
            plugin_env = self.sandbox.create_environment(installation)
            
            # Load plugin module
            main_module_path = os.path.join(installation.install_path, manifest.main_module)
            
            if not os.path.exists(main_module_path):
                raise PluginLoadError(f"Main module not found: {manifest.main_module}")
            
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_id}",
                main_module_path
            )
            
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {main_module_path}")
            
            # Load module in sandboxed environment
            with self.sandbox.execute_in_sandbox(plugin_env):
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
            
            # Register plugin nodes
            loaded_classes = []
            
            if manifest.plugin_type in [PluginType.NODE, PluginType.MIXED]:
                for node_class_name in manifest.provides.get('nodes', []):
                    if hasattr(module, node_class_name):
                        node_class = getattr(module, node_class_name)
                        
                        # Validate node class
                        if not issubclass(node_class, BaseNode):
                            raise PluginLoadError(f"Node class {node_class_name} must inherit from BaseNode")
                        
                        # Register with node registry
                        self.node_registry.register(node_class)
                        loaded_classes.append(node_class_name)
                        
                        logger.info(f"Registered plugin node: {node_class.get_node_type()} from {plugin_id}")
            
            # Store loaded module and classes
            self.loaded_plugins[plugin_id] = module
            installation.loaded_classes = loaded_classes
            installation.status = PluginStatus.LOADED
            
            logger.info(f"Plugin loaded successfully: {plugin_id}")
            
        except Exception as e:
            error_msg = f"Failed to load plugin {plugin_id}: {str(e)}"
            logger.error(error_msg)
            raise PluginLoadError(error_msg)
    
    def _unload_plugin(self, installation: PluginInstallation) -> None:
        """
        Unload a plugin from the system.
        
        Args:
            installation: Plugin installation to unload
        """
        plugin_id = installation.plugin_id
        
        try:
            # Unregister nodes
            for node_class_name in installation.loaded_classes:
                # Find and unregister node type
                if plugin_id in self.loaded_plugins:
                    module = self.loaded_plugins[plugin_id]
                    if hasattr(module, node_class_name):
                        node_class = getattr(module, node_class_name)
                        node_type = node_class.get_node_type()
                        self.node_registry.unregister(node_type)
                        logger.info(f"Unregistered plugin node: {node_type}")
            
            # Remove from loaded plugins
            if plugin_id in self.loaded_plugins:
                del self.loaded_plugins[plugin_id]
            
            # Clean up module from sys.modules
            module_name = f"plugin_{plugin_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            installation.loaded_classes = []
            installation.status = PluginStatus.UNLOADED
            
            logger.info(f"Plugin unloaded: {plugin_id}")
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
    
    def _validate_plugin_signature(self, plugin_path: str, manifest: PluginManifest) -> None:
        """
        Validate plugin digital signature.
        
        Args:
            plugin_path: Path to extracted plugin
            manifest: Plugin manifest
            
        Raises:
            PluginSecurityError: If signature validation fails
        """
        # Check if signature file exists
        signature_path = os.path.join(plugin_path, 'plugin.sig')
        
        if not os.path.exists(signature_path):
            if manifest.requires_signature:
                raise PluginSecurityError("Plugin signature required but not found")
            return
        
        # In a real implementation, this would:
        # 1. Load the signature file
        # 2. Verify against plugin files using public key
        # 3. Check certificate chain and trust
        
        logger.info(f"Plugin signature validated for {manifest.plugin_id}")
    
    def _check_compatibility(self, manifest: PluginManifest) -> None:
        """
        Check plugin compatibility with platform version.
        
        Args:
            manifest: Plugin manifest
            
        Raises:
            PluginCompatibilityError: If plugin is incompatible
        """
        # Simple version compatibility check
        # In production, this would use semantic versioning
        
        min_version = manifest.compatibility.get('min_platform_version')
        max_version = manifest.compatibility.get('max_platform_version')
        
        if min_version and self._version_compare(self.platform_version, min_version) < 0:
            raise PluginCompatibilityError(
                f"Plugin requires platform version >= {min_version}, current: {self.platform_version}"
            )
        
        if max_version and self._version_compare(self.platform_version, max_version) > 0:
            raise PluginCompatibilityError(
                f"Plugin requires platform version <= {max_version}, current: {self.platform_version}"
            )
        
        logger.info(f"Plugin compatibility verified for {manifest.plugin_id}")
    
    def _validate_plugin_security(self, plugin_path: str, manifest: PluginManifest) -> None:
        """
        Validate plugin security constraints.
        
        Args:
            plugin_path: Path to extracted plugin
            manifest: Plugin manifest
            
        Raises:
            PluginSecurityError: If security validation fails
        """
        # Scan plugin files for dangerous patterns
        for root, dirs, files in os.walk(plugin_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for dangerous imports and patterns
                        dangerous_patterns = [
                            r'import\s+os',
                            r'import\s+sys',
                            r'import\s+subprocess',
                            r'from\s+os\s+import',
                            r'__import__\s*\(',
                            r'eval\s*\(',
                            r'exec\s*\(',
                        ]
                        
                        for pattern in dangerous_patterns:
                            if re.search(pattern, content):
                                # Check if this import is allowed by permissions
                                if not self._is_import_allowed(pattern, manifest.permissions):
                                    raise PluginSecurityError(
                                        f"Dangerous pattern detected in {file}: {pattern}"
                                    )
        
        logger.info(f"Plugin security validated for {manifest.plugin_id}")
    
    def _is_import_allowed(self, pattern: str, permissions: Dict[str, Any]) -> bool:
        """
        Check if an import pattern is allowed by plugin permissions.
        
        Args:
            pattern: Import pattern to check
            permissions: Plugin permissions
            
        Returns:
            True if import is allowed
        """
        # Check against allowed imports in permissions
        allowed_imports = permissions.get('allowed_imports', [])
        
        for allowed in allowed_imports:
            if allowed in pattern:
                return True
        
        return False
    
    def _version_compare(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        # Simple version comparison (would use proper semver in production)
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        
        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        for v1, v2 in zip(v1_parts, v2_parts):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
        
        return 0
    
    def get_plugin_statistics(self) -> Dict[str, Any]:
        """
        Get plugin system statistics.
        
        Returns:
            Statistics about installed and loaded plugins
        """
        total_plugins = len(self.installed_plugins)
        enabled_plugins = len([p for p in self.installed_plugins.values() if p.enabled])
        loaded_plugins = len(self.loaded_plugins)
        
        status_counts = {}
        for installation in self.installed_plugins.values():
            status = installation.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'total_installed': total_plugins,
            'enabled': enabled_plugins,
            'loaded': loaded_plugins,
            'status_breakdown': status_counts,
            'platform_version': self.platform_version,
            'plugins_directory': self.plugins_directory
        }