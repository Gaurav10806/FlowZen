"""
Plugin Security and Sandboxing

This module provides security controls and sandboxing for plugin execution
to ensure plugins cannot compromise system security or access unauthorized resources.
"""

import os
import sys
import time
import threading
import resource
import logging
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Set, Callable
from contextlib import contextmanager
from dataclasses import dataclass
import importlib.util
import builtins

from .plugin_manifest import PluginManifest, PluginPermissions


logger = logging.getLogger(__name__)


class PluginSecurityError(Exception):
    """Raised when plugin violates security constraints."""
    pass


class PluginResourceError(Exception):
    """Raised when plugin exceeds resource limits."""
    pass


@dataclass
class PluginEnvironment:
    """Represents a sandboxed environment for plugin execution."""
    plugin_id: str
    temp_directory: str
    allowed_imports: Set[str]
    resource_limits: Dict[str, Any]
    network_allowed: bool
    file_access_allowed: bool
    database_access_allowed: bool
    custom_permissions: Set[str]


@dataclass
class ResourceUsage:
    """Tracks resource usage for a plugin."""
    cpu_time: float = 0.0
    memory_peak: int = 0
    network_requests: int = 0
    file_operations: int = 0
    execution_time: float = 0.0


class SecurityMonitor:
    """Monitors plugin execution for security violations."""
    
    def __init__(self):
        self.violations: List[Dict[str, Any]] = []
        self.resource_usage: Dict[str, ResourceUsage] = {}
    
    def record_violation(self, plugin_id: str, violation_type: str, details: str):
        """Record a security violation."""
        violation = {
            'plugin_id': plugin_id,
            'type': violation_type,
            'details': details,
            'timestamp': time.time()
        }
        self.violations.append(violation)
        logger.warning(f"Security violation: {plugin_id} - {violation_type}: {details}")
    
    def get_violations(self, plugin_id: str = None) -> List[Dict[str, Any]]:
        """Get security violations for a plugin or all plugins."""
        if plugin_id:
            return [v for v in self.violations if v['plugin_id'] == plugin_id]
        return self.violations.copy()


class RestrictedImporter:
    """Custom import system that restricts plugin imports."""
    
    def __init__(self, allowed_imports: Set[str], plugin_id: str, monitor: SecurityMonitor):
        self.allowed_imports = allowed_imports
        self.plugin_id = plugin_id
        self.monitor = monitor
        self.original_import = builtins.__import__
    
    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Restricted import function."""
        # Check if import is allowed
        if not self._is_import_allowed(name):
            self.monitor.record_violation(
                self.plugin_id,
                'unauthorized_import',
                f"Attempted to import unauthorized module: {name}"
            )
            raise ImportError(f"Import of '{name}' not allowed for plugin {self.plugin_id}")
        
        # Use original import
        return self.original_import(name, globals, locals, fromlist, level)
    
    def _is_import_allowed(self, module_name: str) -> bool:
        """Check if a module import is allowed."""
        # Always allow standard safe modules
        safe_modules = {
            'json', 'datetime', 'time', 'math', 'random', 'uuid',
            'collections', 'itertools', 'functools', 'operator',
            'string', 'textwrap', 'unicodedata', 'stringprep',
            'struct', 'codecs', 'typing', 'enum', 'dataclasses'
        }
        
        if module_name in safe_modules:
            return True
        
        # Check against explicitly allowed imports
        if module_name in self.allowed_imports:
            return True
        
        # Check for wildcard permissions
        if '*' in self.allowed_imports:
            return True
        
        # Check for partial matches (e.g., 'requests.*' allows 'requests.auth')
        for allowed in self.allowed_imports:
            if allowed.endswith('.*') and module_name.startswith(allowed[:-2]):
                return True
        
        return False


class ResourceLimiter:
    """Enforces resource limits for plugin execution."""
    
    def __init__(self, limits: Dict[str, Any], plugin_id: str, monitor: SecurityMonitor):
        self.limits = limits
        self.plugin_id = plugin_id
        self.monitor = monitor
        self.start_time = None
        self.start_memory = None
    
    def start_monitoring(self):
        """Start resource monitoring."""
        self.start_time = time.time()
        
        # Set memory limit if specified
        max_memory_mb = self.limits.get('max_memory_mb')
        if max_memory_mb:
            try:
                # Set virtual memory limit (Linux/Unix only)
                memory_bytes = max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            except (OSError, AttributeError):
                # Not supported on this platform
                pass
        
        # Set CPU time limit if specified
        max_cpu_seconds = self.limits.get('max_cpu_time_seconds')
        if max_cpu_seconds:
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_seconds, max_cpu_seconds))
            except (OSError, AttributeError):
                # Not supported on this platform
                pass
    
    def check_limits(self):
        """Check if resource limits are exceeded."""
        if not self.start_time:
            return
        
        # Check execution time
        max_execution_time = self.limits.get('max_execution_time_seconds')
        if max_execution_time:
            elapsed = time.time() - self.start_time
            if elapsed > max_execution_time:
                self.monitor.record_violation(
                    self.plugin_id,
                    'execution_timeout',
                    f"Execution time exceeded: {elapsed:.2f}s > {max_execution_time}s"
                )
                raise PluginResourceError(f"Execution time limit exceeded: {elapsed:.2f}s")
        
        # Check memory usage (approximate)
        max_memory_mb = self.limits.get('max_memory_mb')
        if max_memory_mb:
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                if memory_mb > max_memory_mb:
                    self.monitor.record_violation(
                        self.plugin_id,
                        'memory_limit_exceeded',
                        f"Memory usage exceeded: {memory_mb:.2f}MB > {max_memory_mb}MB"
                    )
                    raise PluginResourceError(f"Memory limit exceeded: {memory_mb:.2f}MB")
            except ImportError:
                # psutil not available, skip memory check
                pass
    
    def stop_monitoring(self):
        """Stop resource monitoring and reset limits."""
        try:
            # Reset resource limits to unlimited
            resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
            resource.setrlimit(resource.RLIMIT_CPU, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        except (OSError, AttributeError):
            # Not supported on this platform
            pass


class NetworkMonitor:
    """Monitors and controls network access for plugins."""
    
    def __init__(self, plugin_id: str, allowed: bool, monitor: SecurityMonitor):
        self.plugin_id = plugin_id
        self.allowed = allowed
        self.monitor = monitor
        self.request_count = 0
        self.start_time = time.time()
    
    def check_network_access(self, url: str = None):
        """Check if network access is allowed."""
        if not self.allowed:
            self.monitor.record_violation(
                self.plugin_id,
                'unauthorized_network_access',
                f"Attempted network access to: {url or 'unknown'}"
            )
            raise PluginSecurityError("Network access not allowed for this plugin")
        
        self.request_count += 1
        
        # Check rate limits
        elapsed_minutes = (time.time() - self.start_time) / 60
        if elapsed_minutes > 0:
            rate = self.request_count / elapsed_minutes
            max_rate = 60  # 60 requests per minute default
            
            if rate > max_rate:
                self.monitor.record_violation(
                    self.plugin_id,
                    'network_rate_limit_exceeded',
                    f"Network request rate exceeded: {rate:.2f} > {max_rate} req/min"
                )
                raise PluginResourceError("Network request rate limit exceeded")


class FileSystemMonitor:
    """Monitors and controls file system access for plugins."""
    
    def __init__(self, plugin_id: str, allowed: bool, temp_dir: str, monitor: SecurityMonitor):
        self.plugin_id = plugin_id
        self.allowed = allowed
        self.temp_dir = temp_dir
        self.monitor = monitor
        self.operation_count = 0
    
    def check_file_access(self, path: str, operation: str):
        """Check if file access is allowed."""
        if not self.allowed:
            self.monitor.record_violation(
                self.plugin_id,
                'unauthorized_file_access',
                f"Attempted {operation} access to: {path}"
            )
            raise PluginSecurityError("File system access not allowed for this plugin")
        
        # Only allow access within temp directory
        abs_path = os.path.abspath(path)
        abs_temp = os.path.abspath(self.temp_dir)
        
        if not abs_path.startswith(abs_temp):
            self.monitor.record_violation(
                self.plugin_id,
                'unauthorized_file_path',
                f"Attempted access outside temp directory: {path}"
            )
            raise PluginSecurityError(f"File access outside temp directory not allowed: {path}")
        
        self.operation_count += 1


class PluginSandbox:
    """
    Main plugin sandboxing system that coordinates all security controls.
    """
    
    def __init__(self):
        self.monitor = SecurityMonitor()
        self.active_environments: Dict[str, PluginEnvironment] = {}
    
    def create_environment(self, installation) -> PluginEnvironment:
        """
        Create a sandboxed environment for plugin execution.
        
        Args:
            installation: Plugin installation with manifest and permissions
            
        Returns:
            PluginEnvironment for the plugin
        """
        plugin_id = installation.plugin_id
        manifest = installation.manifest
        permissions = manifest.permissions
        
        # Create temporary directory for plugin
        temp_dir = tempfile.mkdtemp(prefix=f"plugin_{plugin_id}_")
        
        # Set up environment
        environment = PluginEnvironment(
            plugin_id=plugin_id,
            temp_directory=temp_dir,
            allowed_imports=set(permissions.allowed_imports),
            resource_limits=permissions.resource_limits,
            network_allowed=permissions.network_access,
            file_access_allowed=permissions.file_system_access,
            database_access_allowed=permissions.database_access,
            custom_permissions=set(permissions.custom_permissions)
        )
        
        self.active_environments[plugin_id] = environment
        
        logger.info(f"Created sandbox environment for plugin: {plugin_id}")
        
        return environment
    
    @contextmanager
    def execute_in_sandbox(self, environment: PluginEnvironment):
        """
        Context manager for executing code in a sandboxed environment.
        
        Args:
            environment: Plugin environment to use
        """
        plugin_id = environment.plugin_id
        
        # Set up monitors
        resource_limiter = ResourceLimiter(
            environment.resource_limits, plugin_id, self.monitor
        )
        network_monitor = NetworkMonitor(
            plugin_id, environment.network_allowed, self.monitor
        )
        file_monitor = FileSystemMonitor(
            plugin_id, environment.file_access_allowed, 
            environment.temp_directory, self.monitor
        )
        
        # Set up restricted importer
        restricted_importer = RestrictedImporter(
            environment.allowed_imports, plugin_id, self.monitor
        )
        
        # Store original functions
        original_import = builtins.__import__
        
        try:
            # Install security hooks
            builtins.__import__ = restricted_importer
            
            # Start resource monitoring
            resource_limiter.start_monitoring()
            
            logger.info(f"Entering sandbox for plugin: {plugin_id}")
            
            yield {
                'resource_limiter': resource_limiter,
                'network_monitor': network_monitor,
                'file_monitor': file_monitor,
                'temp_directory': environment.temp_directory
            }
            
        except Exception as e:
            self.monitor.record_violation(
                plugin_id,
                'execution_error',
                f"Plugin execution failed: {str(e)}"
            )
            raise
        
        finally:
            # Restore original functions
            builtins.__import__ = original_import
            
            # Stop resource monitoring
            resource_limiter.stop_monitoring()
            
            logger.info(f"Exiting sandbox for plugin: {plugin_id}")
    
    def cleanup_environment(self, plugin_id: str):
        """
        Clean up a plugin's sandbox environment.
        
        Args:
            plugin_id: Plugin ID to clean up
        """
        if plugin_id in self.active_environments:
            environment = self.active_environments[plugin_id]
            
            # Clean up temporary directory
            if os.path.exists(environment.temp_directory):
                try:
                    shutil.rmtree(environment.temp_directory)
                    logger.info(f"Cleaned up temp directory for plugin: {plugin_id}")
                except OSError as e:
                    logger.error(f"Failed to clean up temp directory for {plugin_id}: {e}")
            
            del self.active_environments[plugin_id]
    
    def get_security_report(self, plugin_id: str = None) -> Dict[str, Any]:
        """
        Get security report for plugins.
        
        Args:
            plugin_id: Specific plugin ID or None for all plugins
            
        Returns:
            Security report with violations and statistics
        """
        violations = self.monitor.get_violations(plugin_id)
        
        # Group violations by type
        violation_types = {}
        for violation in violations:
            vtype = violation['type']
            violation_types[vtype] = violation_types.get(vtype, 0) + 1
        
        # Get active environments
        active_plugins = list(self.active_environments.keys())
        
        return {
            'total_violations': len(violations),
            'violation_types': violation_types,
            'active_environments': len(active_plugins),
            'active_plugins': active_plugins,
            'violations': violations[-10:] if not plugin_id else violations  # Last 10 or all for specific plugin
        }


class PluginPermissions:
    """
    Manages plugin permissions and access control.
    """
    
    def __init__(self):
        self.permission_cache: Dict[str, Dict[str, bool]] = {}
    
    def check_permission(self, plugin_id: str, permission: str, context: Dict[str, Any] = None) -> bool:
        """
        Check if a plugin has a specific permission.
        
        Args:
            plugin_id: Plugin ID
            permission: Permission to check
            context: Additional context for permission check
            
        Returns:
            True if permission is granted
        """
        # Get cached permissions
        if plugin_id in self.permission_cache:
            cached = self.permission_cache[plugin_id]
            if permission in cached:
                return cached[permission]
        
        # Default deny
        return False
    
    def grant_permission(self, plugin_id: str, permission: str):
        """Grant a permission to a plugin."""
        if plugin_id not in self.permission_cache:
            self.permission_cache[plugin_id] = {}
        
        self.permission_cache[plugin_id][permission] = True
        logger.info(f"Granted permission '{permission}' to plugin: {plugin_id}")
    
    def revoke_permission(self, plugin_id: str, permission: str):
        """Revoke a permission from a plugin."""
        if plugin_id in self.permission_cache:
            self.permission_cache[plugin_id][permission] = False
            logger.info(f"Revoked permission '{permission}' from plugin: {plugin_id}")
    
    def get_plugin_permissions(self, plugin_id: str) -> Dict[str, bool]:
        """Get all permissions for a plugin."""
        return self.permission_cache.get(plugin_id, {}).copy()
    
    def clear_plugin_permissions(self, plugin_id: str):
        """Clear all permissions for a plugin."""
        if plugin_id in self.permission_cache:
            del self.permission_cache[plugin_id]
            logger.info(f"Cleared all permissions for plugin: {plugin_id}")


# Security utility functions

def validate_plugin_code(code: str, allowed_imports: Set[str]) -> List[str]:
    """
    Validate plugin code for security issues.
    
    Args:
        code: Plugin source code
        allowed_imports: Set of allowed import modules
        
    Returns:
        List of security issues found
    """
    issues = []
    
    # Check for dangerous patterns
    dangerous_patterns = [
        (r'eval\s*\(', 'Use of eval() function'),
        (r'exec\s*\(', 'Use of exec() function'),
        (r'__import__\s*\(', 'Direct use of __import__()'),
        (r'subprocess\.', 'Use of subprocess module'),
        (r'os\.system', 'Use of os.system()'),
        (r'open\s*\(.*["\']w', 'File write operations'),
        (r'socket\.', 'Direct socket operations'),
    ]
    
    import re
    for pattern, description in dangerous_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            issues.append(description)
    
    # Check imports
    import_pattern = r'(?:from\s+(\w+)|import\s+(\w+))'
    imports = re.findall(import_pattern, code)
    
    for from_import, direct_import in imports:
        module = from_import or direct_import
        if module and module not in allowed_imports and '*' not in allowed_imports:
            issues.append(f"Unauthorized import: {module}")
    
    return issues